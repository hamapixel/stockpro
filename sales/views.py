from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import seller_or_admin_required
from catalog.models import Product
from customers.models import Client
from inventory.models import StockMovement
from payments.models import Payment

from .models import Sale, SaleItem


def to_decimal(value):
    try:
        return Decimal(str(value or "0").replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        return None


def product_label(product):
    reference = product.reference or "-"

    return (
        f"{product.name} — Réf: {reference} — "
        f"Stock: {product.stock_quantity} {product.unit.short_name} — "
        f"Prix: {int(product.sale_price)} F CFA"
    )


def update_client_balance(client):
    if not client:
        return

    balance = Sale.objects.filter(
        client=client,
        is_cancelled=False,
    ).aggregate(
        total=Sum("remaining_amount")
    )["total"] or Decimal("0.00")

    client.balance = balance
    client.save(update_fields=["balance", "updated_at"])


def get_pos_context(
    clients,
    posted_rows,
    payment_method,
    client_id="",
    discount=Decimal("0.00"),
    amount_paid=Decimal("0.00"),
    notes="",
):
    return {
        "clients": clients,
        "posted_rows": posted_rows,
        "payment_methods": Sale.PaymentMethod.choices,
        "selected_payment_method": payment_method,
        "selected_client_id": client_id,
        "discount": discount,
        "amount_paid": amount_paid,
        "notes": notes,
    }


@seller_or_admin_required
def product_search_api(request):
    query = request.GET.get("q", "").strip()

    products = Product.objects.filter(
        is_active=True,
    ).select_related(
        "unit",
        "category",
    ).order_by("name")

    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(reference__icontains=query)
            | Q(barcode__icontains=query)
        )
    else:
        products = products.none()

    results = []

    for product in products[:25]:
        results.append({
            "id": product.id,
            "name": product.name,
            "reference": product.reference or "",
            "stock": str(product.stock_quantity),
            "unit": product.unit.short_name,
            "sale_price": str(product.sale_price),
            "label": product_label(product),
        })

    return JsonResponse({
        "results": results,
    })


@seller_or_admin_required
def sale_pos(request):
    clients = Client.objects.all().order_by("full_name")

    posted_rows = [
        {
            "product_id": "",
            "product_label": "",
            "quantity": "",
            "unit_price": "",
            "line_discount": "",
        }
    ]

    if request.method == "POST":
        client_id = request.POST.get("client", "").strip()

        payment_method = request.POST.get(
            "payment_method",
            Sale.PaymentMethod.CASH,
        )

        global_discount = (
            to_decimal(request.POST.get("discount"))
            or Decimal("0.00")
        )

        amount_paid = (
            to_decimal(request.POST.get("amount_paid"))
            or Decimal("0.00")
        )

        notes = request.POST.get("notes", "").strip()

        product_ids = request.POST.getlist("product")
        product_labels = request.POST.getlist("product_label")
        quantities = request.POST.getlist("quantity")
        unit_prices = request.POST.getlist("unit_price")
        line_discounts = request.POST.getlist("line_discount")

        client = None

        if client_id:
            client = get_object_or_404(
                Client,
                pk=client_id,
            )

        if payment_method not in Sale.PaymentMethod.values:
            payment_method = Sale.PaymentMethod.CASH

        if global_discount < Decimal("0.00"):
            messages.error(
                request,
                "La remise globale ne peut pas être négative.",
            )

            return render(
                request,
                "sales/pos.html",
                get_pos_context(
                    clients,
                    posted_rows,
                    payment_method,
                    client_id,
                    global_discount,
                    amount_paid,
                    notes,
                ),
            )

        if amount_paid < Decimal("0.00"):
            messages.error(
                request,
                "Le montant payé ne peut pas être négatif.",
            )

            return render(
                request,
                "sales/pos.html",
                get_pos_context(
                    clients,
                    posted_rows,
                    payment_method,
                    client_id,
                    global_discount,
                    amount_paid,
                    notes,
                ),
            )

        rows = []
        posted_rows = []

        max_len = max(
            len(product_ids),
            len(product_labels),
            len(quantities),
            len(unit_prices),
            len(line_discounts),
        )

        for index in range(max_len):
            product_id = (
                product_ids[index].strip()
                if index < len(product_ids)
                else ""
            )

            product_label_value = (
                product_labels[index].strip()
                if index < len(product_labels)
                else ""
            )

            quantity_value = (
                quantities[index].strip()
                if index < len(quantities)
                else ""
            )

            unit_price_value = (
                unit_prices[index].strip()
                if index < len(unit_prices)
                else ""
            )

            line_discount_value = (
                line_discounts[index].strip()
                if index < len(line_discounts)
                else ""
            )

            posted_rows.append({
                "product_id": product_id,
                "product_label": product_label_value,
                "quantity": quantity_value,
                "unit_price": unit_price_value,
                "line_discount": line_discount_value,
            })

            if (
                not product_id
                and not quantity_value
                and not unit_price_value
            ):
                continue

            if not product_id:
                messages.error(
                    request,
                    f"Ligne {index + 1} : recherchez puis sélectionnez un produit.",
                )

                return render(
                    request,
                    "sales/pos.html",
                    get_pos_context(
                        clients,
                        posted_rows,
                        payment_method,
                        client_id,
                        global_discount,
                        amount_paid,
                        notes,
                    ),
                )

            quantity = to_decimal(quantity_value)
            unit_price = to_decimal(unit_price_value)

            line_discount = (
                to_decimal(line_discount_value)
                or Decimal("0.00")
            )

            if quantity is None or quantity <= Decimal("0.00"):
                messages.error(
                    request,
                    f"Ligne {index + 1} : quantité invalide.",
                )

                return render(
                    request,
                    "sales/pos.html",
                    get_pos_context(
                        clients,
                        posted_rows,
                        payment_method,
                        client_id,
                        global_discount,
                        amount_paid,
                        notes,
                    ),
                )

            if unit_price is None or unit_price < Decimal("0.00"):
                messages.error(
                    request,
                    f"Ligne {index + 1} : prix unitaire invalide.",
                )

                return render(
                    request,
                    "sales/pos.html",
                    get_pos_context(
                        clients,
                        posted_rows,
                        payment_method,
                        client_id,
                        global_discount,
                        amount_paid,
                        notes,
                    ),
                )

            if line_discount < Decimal("0.00"):
                messages.error(
                    request,
                    f"Ligne {index + 1} : remise invalide.",
                )

                return render(
                    request,
                    "sales/pos.html",
                    get_pos_context(
                        clients,
                        posted_rows,
                        payment_method,
                        client_id,
                        global_discount,
                        amount_paid,
                        notes,
                    ),
                )

            line_total = (
                quantity * unit_price
            ) - line_discount

            if line_total < Decimal("0.00"):
                messages.error(
                    request,
                    f"Ligne {index + 1} : la remise dépasse le montant de la ligne.",
                )

                return render(
                    request,
                    "sales/pos.html",
                    get_pos_context(
                        clients,
                        posted_rows,
                        payment_method,
                        client_id,
                        global_discount,
                        amount_paid,
                        notes,
                    ),
                )

            rows.append({
                "product_id": product_id,
                "quantity": quantity,
                "unit_price": unit_price,
                "line_discount": line_discount,
                "line_number": index + 1,
            })

        if not rows:
            messages.error(
                request,
                "Ajoutez au moins un produit dans la vente.",
            )

            return render(
                request,
                "sales/pos.html",
                get_pos_context(
                    clients,
                    posted_rows,
                    payment_method,
                    client_id,
                    global_discount,
                    amount_paid,
                    notes,
                ),
            )

        subtotal_preview = Decimal("0.00")

        for row in rows:
            subtotal_preview += (
                row["quantity"] * row["unit_price"]
            ) - row["line_discount"]

        if subtotal_preview <= Decimal("0.00"):
            messages.error(
                request,
                "Le total de la vente doit être supérieur à zéro.",
            )

            return render(
                request,
                "sales/pos.html",
                get_pos_context(
                    clients,
                    posted_rows,
                    payment_method,
                    client_id,
                    global_discount,
                    amount_paid,
                    notes,
                ),
            )

        if global_discount > subtotal_preview:
            messages.error(
                request,
                "La remise globale dépasse le sous-total.",
            )

            return render(
                request,
                "sales/pos.html",
                get_pos_context(
                    clients,
                    posted_rows,
                    payment_method,
                    client_id,
                    global_discount,
                    amount_paid,
                    notes,
                ),
            )

        total_preview = subtotal_preview - global_discount

        if amount_paid > total_preview:
            messages.error(
                request,
                "Le montant payé ne peut pas dépasser le total net.",
            )

            return render(
                request,
                "sales/pos.html",
                get_pos_context(
                    clients,
                    posted_rows,
                    payment_method,
                    client_id,
                    global_discount,
                    amount_paid,
                    notes,
                ),
            )

        if amount_paid < total_preview and not client:
            messages.error(
                request,
                "Sélectionnez un client pour une vente à crédit ou partiellement payée.",
            )

            return render(
                request,
                "sales/pos.html",
                get_pos_context(
                    clients,
                    posted_rows,
                    payment_method,
                    client_id,
                    global_discount,
                    amount_paid,
                    notes,
                ),
            )

        if (
            amount_paid > Decimal("0.00")
            and payment_method == Sale.PaymentMethod.CREDIT
        ):
            messages.error(
                request,
                "Choisissez le mode utilisé pour le montant encaissé.",
            )

            return render(
                request,
                "sales/pos.html",
                get_pos_context(
                    clients,
                    posted_rows,
                    payment_method,
                    client_id,
                    global_discount,
                    amount_paid,
                    notes,
                ),
            )

        product_ids_to_lock = list({
            row["product_id"]
            for row in rows
        })

        with transaction.atomic():
            locked_products = {
                str(product.id): product
                for product in (
                    Product.objects.select_for_update()
                    .select_related("unit")
                    .filter(
                        pk__in=product_ids_to_lock,
                        is_active=True,
                    )
                )
            }

            quantities_by_product = {}

            for row in rows:
                product = locked_products.get(
                    str(row["product_id"])
                )

                if not product:
                    messages.error(
                        request,
                        f"Ligne {row['line_number']} : produit introuvable ou inactif.",
                    )

                    transaction.set_rollback(True)

                    return render(
                        request,
                        "sales/pos.html",
                        get_pos_context(
                            clients,
                            posted_rows,
                            payment_method,
                            client_id,
                            global_discount,
                            amount_paid,
                            notes,
                        ),
                    )

                product_key = str(product.pk)

                quantities_by_product[product_key] = (
                    quantities_by_product.get(
                        product_key,
                        Decimal("0.00"),
                    )
                    + row["quantity"]
                )

            for product_id, total_quantity in quantities_by_product.items():
                product = locked_products[product_id]

                if total_quantity > product.stock_quantity:
                    messages.error(
                        request,
                        f"Stock insuffisant pour {product.name}. "
                        f"Disponible : {product.stock_quantity} "
                        f"{product.unit.short_name}.",
                    )

                    transaction.set_rollback(True)

                    return render(
                        request,
                        "sales/pos.html",
                        get_pos_context(
                            clients,
                            posted_rows,
                            payment_method,
                            client_id,
                            global_discount,
                            amount_paid,
                            notes,
                        ),
                    )

            sale = Sale.objects.create(
                client=client,
                discount=global_discount,
                amount_paid=Decimal("0.00"),
                payment_method=payment_method,
                notes=notes,
                created_by=request.user,
            )

            for row in rows:
                product = locked_products[
                    str(row["product_id"])
                ]

                SaleItem.objects.create(
                    sale=sale,
                    product=product,
                    quantity=row["quantity"],
                    unit_price=row["unit_price"],
                    discount=row["line_discount"],
                )

                old_quantity = product.stock_quantity
                new_quantity = old_quantity - row["quantity"]

                product.stock_quantity = new_quantity

                product.save(
                    update_fields=[
                        "stock_quantity",
                        "updated_at",
                    ]
                )

                StockMovement.objects.create(
                    product=product,
                    movement_type=StockMovement.MovementType.SALE,
                    quantity=row["quantity"],
                    old_quantity=old_quantity,
                    new_quantity=new_quantity,
                    reason=f"Vente {sale.sale_number}",
                )

            sale.calculate_totals(save=True)

            if amount_paid > Decimal("0.00"):
                payment_methods_allowed = {
                    value
                    for value, label in Payment.PaymentMethod.choices
                }

                payment_method_for_payment = payment_method

                if payment_method_for_payment not in payment_methods_allowed:
                    payment_method_for_payment = Payment.PaymentMethod.CASH

                Payment.objects.create(
                    sale=sale,
                    client=client,
                    amount=amount_paid,
                    payment_method=payment_method_for_payment,
                    created_by=request.user,
                    notes=f"Paiement initial vente {sale.sale_number}",
                )
            else:
                update_client_balance(client)

        messages.success(
            request,
            f"Vente {sale.sale_number} enregistrée avec succès.",
        )

        return redirect(
            "sale_detail",
            pk=sale.pk,
        )

    context = get_pos_context(
        clients=clients,
        posted_rows=posted_rows,
        payment_method=Sale.PaymentMethod.CASH,
    )

    return render(
        request,
        "sales/pos.html",
        context,
    )


@seller_or_admin_required
def sale_list(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()

    sales = Sale.objects.select_related(
        "client",
        "created_by",
    ).filter(
        is_cancelled=False,
    ).order_by("-sale_date")

    if query:
        sales = sales.filter(
            Q(sale_number__icontains=query)
            | Q(client__full_name__icontains=query)
            | Q(client__phone__icontains=query)
        )

    if status in Sale.PaymentStatus.values:
        sales = sales.filter(
            payment_status=status,
        )

    total_sales = sales.aggregate(
        total=Sum("total")
    )["total"] or Decimal("0.00")

    total_paid = sales.aggregate(
        total=Sum("amount_paid")
    )["total"] or Decimal("0.00")

    total_remaining = sales.aggregate(
        total=Sum("remaining_amount")
    )["total"] or Decimal("0.00")

    sale_count = sales.count()

    paginator = Paginator(sales, 15)
    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    context = {
        "page_obj": page_obj,
        "query": query,
        "status": status,
        "status_choices": Sale.PaymentStatus.choices,
        "sale_count": sale_count,
        "total_sales": total_sales,
        "total_paid": total_paid,
        "total_remaining": total_remaining,
    }

    return render(
        request,
        "sales/sale_list.html",
        context,
    )


@seller_or_admin_required
def sale_detail(request, pk):
    sale = get_object_or_404(
        Sale.objects.select_related(
            "client",
            "created_by",
        ),
        pk=pk,
    )

    items = sale.items.select_related(
        "product",
        "product__unit",
        "product__category",
    ).all()

    payments = sale.payments.select_related(
        "client",
        "created_by",
    ).order_by("-payment_date")

    context = {
        "sale": sale,
        "items": items,
        "payments": payments,
    }

    return render(
        request,
        "sales/sale_detail.html",
        context,
    )