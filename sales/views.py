from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import DatabaseError, transaction
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.http import require_POST

from accounts.decorators import (
    admin_required,
    seller_or_admin_required,
)
from catalog.models import Product
from customers.models import Client
from inventory.models import StockMovement
from payments.models import Payment

from .models import Sale, SaleItem


ZERO = Decimal("0.00")


class SaleOperationError(Exception):
    """
    Erreur fonctionnelle provoquant l'annulation
    complète de la transaction.
    """


def to_decimal(value):
    try:
        cleaned_value = (
            str(value or "")
            .strip()
            .replace(",", ".")
        )

        if not cleaned_value:
            return None

        return Decimal(cleaned_value)

    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ):
        return None


def product_label(product):
    reference = product.reference or "-"

    unit_name = (
        product.unit.short_name
        if product.unit
        else ""
    )

    return (
        f"{product.name} — "
        f"Réf: {reference} — "
        f"Stock: {product.stock_quantity} "
        f"{unit_name} — "
        f"Prix: {product.sale_price} F CFA"
    )


def empty_pos_row():
    return {
        "product_id": "",
        "product_label": "",
        "quantity": "",
        "unit_price": "",
        "line_discount": "",
    }


def render_pos(
    request,
    *,
    clients,
    posted_rows=None,
    selected_payment_method=None,
    selected_client_id="",
    discount=ZERO,
    amount_paid=ZERO,
    notes="",
):
    if not posted_rows:
        posted_rows = [
            empty_pos_row()
        ]

    context = {
        "clients": clients,
        "posted_rows": posted_rows,
        "payment_methods": (
            Sale.PaymentMethod.choices
        ),
        "selected_payment_method": (
            selected_payment_method
            or Sale.PaymentMethod.CASH
        ),
        "selected_client_id": (
            selected_client_id
        ),
        "discount": discount,
        "amount_paid": amount_paid,
        "notes": notes,
    }

    return render(
        request,
        "sales/pos.html",
        context,
    )


@seller_or_admin_required
def product_search_api(request):
    query = request.GET.get(
        "q",
        "",
    ).strip()

    products = (
        Product.objects
        .filter(is_active=True)
        .select_related(
            "unit",
            "category",
        )
        .order_by("name")
    )

    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(reference__icontains=query)
            | Q(barcode__icontains=query)
        )
    else:
        products = products.none()

    results = []

    for product in products[:30]:
        unit_name = (
            product.unit.short_name
            if product.unit
            else ""
        )

        results.append(
            {
                "id": product.pk,
                "name": product.name,
                "reference": (
                    product.reference or ""
                ),
                "stock": str(
                    product.stock_quantity
                ),
                "unit": unit_name,
                "sale_price": str(
                    product.sale_price
                ),
                "label": product_label(
                    product
                ),
            }
        )

    return JsonResponse(
        {
            "results": results,
            "count": len(results),
        }
    )


@seller_or_admin_required
def sale_pos(request):
    clients = (
        Client.objects
        .all()
        .order_by("full_name")
    )

    if request.method != "POST":
        return render_pos(
            request,
            clients=clients,
        )

    client_id = request.POST.get(
        "client",
        "",
    ).strip()

    payment_method = request.POST.get(
        "payment_method",
        Sale.PaymentMethod.CASH,
    ).strip()

    discount_raw = request.POST.get(
        "discount",
        "",
    ).strip()

    amount_paid_raw = request.POST.get(
        "amount_paid",
        "",
    ).strip()

    notes = request.POST.get(
        "notes",
        "",
    ).strip()

    global_discount = (
        to_decimal(discount_raw)
        if discount_raw
        else ZERO
    )

    amount_paid = (
        to_decimal(amount_paid_raw)
        if amount_paid_raw
        else ZERO
    )

    product_ids = request.POST.getlist(
        "product"
    )

    product_labels = request.POST.getlist(
        "product_label"
    )

    quantities = request.POST.getlist(
        "quantity"
    )

    unit_prices = request.POST.getlist(
        "unit_price"
    )

    line_discounts = request.POST.getlist(
        "line_discount"
    )

    max_len = max(
        len(product_ids),
        len(product_labels),
        len(quantities),
        len(unit_prices),
        len(line_discounts),
        0,
    )

    posted_rows = []

    for index in range(max_len):
        posted_rows.append(
            {
                "product_id": (
                    product_ids[index].strip()
                    if index < len(product_ids)
                    else ""
                ),
                "product_label": (
                    product_labels[index].strip()
                    if index < len(product_labels)
                    else ""
                ),
                "quantity": (
                    quantities[index].strip()
                    if index < len(quantities)
                    else ""
                ),
                "unit_price": (
                    unit_prices[index].strip()
                    if index < len(unit_prices)
                    else ""
                ),
                "line_discount": (
                    line_discounts[index].strip()
                    if index < len(line_discounts)
                    else ""
                ),
            }
        )

    def fail(message):
        messages.error(
            request,
            message,
        )

        return render_pos(
            request,
            clients=clients,
            posted_rows=posted_rows,
            selected_payment_method=payment_method,
            selected_client_id=client_id,
            discount=(
                global_discount
                if global_discount is not None
                else discount_raw
            ),
            amount_paid=(
                amount_paid
                if amount_paid is not None
                else amount_paid_raw
            ),
            notes=notes,
        )

    if payment_method not in Sale.PaymentMethod.values:
        payment_method = (
            Sale.PaymentMethod.CASH
        )

    if global_discount is None:
        return fail(
            "La remise globale n'est pas valide."
        )

    if global_discount < ZERO:
        return fail(
            "La remise globale ne peut pas être négative."
        )

    if amount_paid is None:
        return fail(
            "Le montant payé n'est pas valide."
        )

    if amount_paid < ZERO:
        return fail(
            "Le montant payé ne peut pas être négatif."
        )

    client = None

    if client_id:
        client = (
            Client.objects
            .filter(pk=client_id)
            .first()
        )

        if client is None:
            return fail(
                "Le client sélectionné est introuvable."
            )

    rows = []
    seen_product_ids = set()

    for index, posted_row in enumerate(
        posted_rows,
        start=1,
    ):
        product_id = posted_row[
            "product_id"
        ]

        product_label_value = posted_row[
            "product_label"
        ]

        quantity_value = posted_row[
            "quantity"
        ]

        unit_price_value = posted_row[
            "unit_price"
        ]

        discount_value = posted_row[
            "line_discount"
        ]

        if (
            not product_id
            and not product_label_value
            and not quantity_value
            and not unit_price_value
            and not discount_value
        ):
            continue

        if not product_id:
            return fail(
                (
                    f"Ligne {index} : recherchez "
                    "puis sélectionnez un produit."
                )
            )

        if product_id in seen_product_ids:
            return fail(
                (
                    f"Ligne {index} : ce produit "
                    "est déjà présent dans la vente."
                )
            )

        seen_product_ids.add(
            product_id
        )

        quantity = to_decimal(
            quantity_value
        )

        unit_price = to_decimal(
            unit_price_value
        )

        line_discount = (
            to_decimal(discount_value)
            if discount_value
            else ZERO
        )

        if (
            quantity is None
            or quantity <= ZERO
        ):
            return fail(
                (
                    f"Ligne {index} : "
                    "la quantité n'est pas valide."
                )
            )

        if (
            unit_price is None
            or unit_price < ZERO
        ):
            return fail(
                (
                    f"Ligne {index} : "
                    "le prix unitaire n'est pas valide."
                )
            )

        if (
            line_discount is None
            or line_discount < ZERO
        ):
            return fail(
                (
                    f"Ligne {index} : "
                    "la remise n'est pas valide."
                )
            )

        gross_line_total = (
            quantity * unit_price
        )

        if line_discount > gross_line_total:
            return fail(
                (
                    f"Ligne {index} : la remise "
                    "dépasse le montant de la ligne."
                )
            )

        rows.append(
            {
                "product_id": product_id,
                "quantity": quantity,
                "unit_price": unit_price,
                "line_discount": line_discount,
                "line_number": index,
            }
        )

    if not rows:
        return fail(
            "Ajoutez au moins un produit dans la vente."
        )

    subtotal_preview = sum(
        (
            (
                row["quantity"]
                * row["unit_price"]
            )
            - row["line_discount"]
        )
        for row in rows
    )

    if global_discount > subtotal_preview:
        return fail(
            "La remise globale dépasse le sous-total."
        )

    total_preview = (
        subtotal_preview - global_discount
    )

    if amount_paid > total_preview:
        return fail(
            (
                "Le montant payé ne peut pas "
                "dépasser le total net."
            )
        )

    remaining_preview = (
        total_preview - amount_paid
    )

    if (
        remaining_preview > ZERO
        and client is None
    ):
        return fail(
            (
                "Sélectionnez un client pour "
                "une vente partielle ou à crédit."
            )
        )

    if (
        amount_paid > ZERO
        and payment_method
        == Sale.PaymentMethod.CREDIT
    ):
        return fail(
            (
                "Pour enregistrer un montant payé, "
                "choisissez le moyen réellement utilisé."
            )
        )

    product_ids_to_lock = sorted(
        {
            row["product_id"]
            for row in rows
        }
    )

    try:
        with transaction.atomic():
            locked_client = None

            if client is not None:
                locked_client = (
                    Client.objects
                    .select_for_update()
                    .get(pk=client.pk)
                )

            locked_products = {
                str(product.pk): product
                for product in (
                    Product.objects
                    .select_for_update()
                    .select_related("unit")
                    .filter(
                        pk__in=product_ids_to_lock,
                        is_active=True,
                    )
                    .order_by("pk")
                )
            }

            for row in rows:
                product = locked_products.get(
                    str(row["product_id"])
                )

                if product is None:
                    raise SaleOperationError(
                        (
                            f"Ligne {row['line_number']} : "
                            "le produit est introuvable "
                            "ou désactivé."
                        )
                    )

                available_stock = (
                    product.stock_quantity
                    or ZERO
                )

                if (
                    row["quantity"]
                    > available_stock
                ):
                    unit_name = (
                        product.unit.short_name
                        if product.unit
                        else ""
                    )

                    raise SaleOperationError(
                        (
                            "Stock insuffisant pour "
                            f"{product.name}. "
                            "Disponible : "
                            f"{available_stock} "
                            f"{unit_name}."
                        )
                    )

            sale = Sale.objects.create(
                client=locked_client,
                discount=global_discount,
                amount_paid=ZERO,
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
                    discount=row[
                        "line_discount"
                    ],
                )

                old_quantity = (
                    product.stock_quantity
                    or ZERO
                )

                new_quantity = (
                    old_quantity
                    - row["quantity"]
                )

                if new_quantity < ZERO:
                    raise SaleOperationError(
                        (
                            "Le stock de "
                            f"{product.name} "
                            "ne peut pas devenir négatif."
                        )
                    )

                product.stock_quantity = (
                    new_quantity
                )

                product.save(
                    update_fields=[
                        "stock_quantity",
                        "updated_at",
                    ]
                )

                StockMovement.objects.create(
                    product=product,
                    movement_type=(
                        StockMovement
                        .MovementType
                        .SALE
                    ),
                    quantity=row["quantity"],
                    old_quantity=old_quantity,
                    new_quantity=new_quantity,
                    reason=(
                        f"Vente {sale.sale_number}"
                    ),
                )

            sale.calculate_totals(
                save=True
            )

            if amount_paid > ZERO:
                if (
                    payment_method
                    not in Payment.PaymentMethod.values
                ):
                    raise SaleOperationError(
                        (
                            "Le mode de paiement "
                            "n'est pas valide."
                        )
                    )

                Payment.objects.create(
                    sale=sale,
                    client=locked_client,
                    amount=amount_paid,
                    payment_method=payment_method,
                    created_by=request.user,
                    notes=(
                        "Paiement initial de la vente "
                        f"{sale.sale_number}"
                    ),
                )

            else:
                Sale.update_client_balance(
                    locked_client
                )

    except SaleOperationError as exc:
        return fail(str(exc))

    except ValidationError as exc:
        message = (
            "; ".join(exc.messages)
            if exc.messages
            else (
                "Les informations de la vente "
                "ne sont pas valides."
            )
        )

        return fail(message)

    except DatabaseError:
        return fail(
            (
                "La vente n'a pas pu être enregistrée. "
                "Aucun stock n'a été modifié."
            )
        )

    messages.success(
        request,
        (
            f"Vente {sale.sale_number} "
            "enregistrée avec succès."
        ),
    )

    return redirect(
        "sale_detail",
        pk=sale.pk,
    )


@seller_or_admin_required
def sale_list(request):
    query = request.GET.get(
        "q",
        "",
    ).strip()

    status = request.GET.get(
        "status",
        "",
    ).strip()

    sales = (
        Sale.objects
        .select_related("client")
        .filter(is_cancelled=False)
        .order_by("-sale_date")
    )

    if query:
        sales = sales.filter(
            Q(sale_number__icontains=query)
            | Q(
                client__full_name__icontains=query
            )
            | Q(
                client__phone__icontains=query
            )
        )

    allowed_statuses = {
        Sale.PaymentStatus.PAID,
        Sale.PaymentStatus.PARTIAL,
        Sale.PaymentStatus.CREDIT,
    }

    if status in allowed_statuses:
        sales = sales.filter(
            payment_status=status
        )
    else:
        status = ""

    totals = sales.aggregate(
        total_sales=Sum("total"),
        total_paid=Sum("amount_paid"),
        total_remaining=Sum(
            "remaining_amount"
        ),
    )

    paginator = Paginator(
        sales,
        15,
    )

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    status_choices = [
        choice
        for choice
        in Sale.PaymentStatus.choices
        if choice[0]
        != Sale.PaymentStatus.CANCELLED
    ]

    context = {
        "page_obj": page_obj,
        "query": query,
        "status": status,
        "status_choices": status_choices,
        "total_sales": (
            totals["total_sales"]
            or ZERO
        ),
        "total_paid": (
            totals["total_paid"]
            or ZERO
        ),
        "total_remaining": (
            totals["total_remaining"]
            or ZERO
        ),
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

    items = (
        sale.items
        .select_related(
            "product",
            "product__unit",
        )
        .all()
    )

    payments = (
        sale.payments
        .select_related(
            "client",
            "created_by",
        )
        .order_by("-payment_date")
    )

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


@require_POST
@admin_required
def sale_cancel(request, pk):
    sale = get_object_or_404(
        Sale,
        pk=pk,
    )

    try:
        cancelled = sale.cancel_sale(
            cancelled_by=request.user,
            reason=(
                request.POST
                .get("reason", "")
                .strip()
            ),
        )

    except (
        ValidationError,
        DatabaseError,
    ):
        messages.error(
            request,
            (
                "La vente n'a pas pu être annulée. "
                "Aucun stock n'a été modifié."
            ),
        )

        return redirect(
            "sale_detail",
            pk=sale.pk,
        )

    if not cancelled:
        messages.warning(
            request,
            "Cette vente est déjà annulée.",
        )

        return redirect(
            "sale_detail",
            pk=sale.pk,
        )

    messages.success(
        request,
        (
            f"La vente {sale.sale_number} "
            "a été annulée et le stock restauré."
        ),
    )

    return redirect("sale_list")