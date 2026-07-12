from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Q, Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from catalog.models import Category, Product
from .models import StockMovement


def to_decimal(value):
    try:
        return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        return None


def product_label(product):
    reference = product.reference or "-"
    return f"{product.name} — Réf: {reference} — Stock: {product.stock_quantity} {product.unit.short_name}"


@login_required
def product_search_api(request):
    query = request.GET.get("q", "").strip()

    products = Product.objects.filter(is_active=True).select_related("unit").order_by("name")

    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(reference__icontains=query)
            | Q(barcode__icontains=query)
        )
    else:
        products = products.none()

    results = []

    for product in products[:20]:
        results.append({
            "id": product.id,
            "name": product.name,
            "reference": product.reference or "",
            "stock": str(product.stock_quantity),
            "unit": product.unit.short_name,
            "label": product_label(product),
        })

    return JsonResponse({"results": results})


@login_required
def stock_list(request):
    query = request.GET.get("q", "").strip()
    category_id = request.GET.get("category", "").strip()
    stock_status = request.GET.get("stock", "").strip()

    products = Product.objects.select_related(
        "category",
        "unit",
    ).filter(
        is_active=True,
    ).order_by("name")

    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(reference__icontains=query)
            | Q(barcode__icontains=query)
        )

    if category_id:
        products = products.filter(category_id=category_id)

    if stock_status == "low":
        products = products.filter(stock_quantity__lte=F("alert_quantity"))
    elif stock_status == "available":
        products = products.filter(stock_quantity__gt=0)
    elif stock_status == "zero":
        products = products.filter(stock_quantity=0)

    categories = Category.objects.filter(is_active=True).order_by("name")

    paginator = Paginator(products, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    active_products = Product.objects.filter(is_active=True)

    total_quantity = active_products.aggregate(
        total=Sum("stock_quantity")
    )["total"] or Decimal("0.00")

    low_stock_count = active_products.filter(
        stock_quantity__lte=F("alert_quantity")
    ).count()

    zero_stock_count = active_products.filter(stock_quantity=0).count()

    movements_today = StockMovement.objects.filter(
        created_at__date=timezone.localdate()
    ).count()

    context = {
        "page_obj": page_obj,
        "categories": categories,
        "query": query,
        "category_id": category_id,
        "stock_status": stock_status,
        "product_count": active_products.count(),
        "total_quantity": total_quantity,
        "low_stock_count": low_stock_count,
        "zero_stock_count": zero_stock_count,
        "movements_today": movements_today,
    }

    return render(request, "inventory/stock_list.html", context)


@login_required
def stock_adjustment_create(request, default_type="in"):
    initial_type = request.GET.get("type", default_type)

    if initial_type not in ["in", "out"]:
        initial_type = "in"

    initial_product_id = request.GET.get("product", "")
    initial_product_label = ""

    if initial_product_id:
        try:
            selected_product = Product.objects.select_related("unit").get(
                pk=initial_product_id,
                is_active=True,
            )
            initial_product_label = product_label(selected_product)
        except Product.DoesNotExist:
            initial_product_id = ""
            initial_product_label = ""

    posted_rows = [
        {
            "product_id": initial_product_id,
            "product_label": initial_product_label,
            "quantity": "",
            "reason": "",
        }
    ]

    if request.method == "POST":
        movement_type = request.POST.get("movement_type", "in")

        if movement_type not in ["in", "out"]:
            movement_type = "in"

        product_ids = request.POST.getlist("product")
        product_labels = request.POST.getlist("product_label")
        quantities = request.POST.getlist("quantity")
        reasons = request.POST.getlist("reason")

        rows = []
        posted_rows = []

        max_len = max(len(product_ids), len(quantities), len(reasons), len(product_labels))

        for index in range(max_len):
            product_id = product_ids[index].strip() if index < len(product_ids) else ""
            product_label_value = product_labels[index].strip() if index < len(product_labels) else ""
            quantity_value = quantities[index].strip() if index < len(quantities) else ""
            reason = reasons[index].strip() if index < len(reasons) else ""

            posted_rows.append({
                "product_id": product_id,
                "product_label": product_label_value,
                "quantity": quantity_value,
                "reason": reason,
            })

            if not product_id and not quantity_value:
                continue

            if not product_id:
                messages.error(request, f"Ligne {index + 1} : recherchez puis sélectionnez un produit.")
                return render(request, "inventory/stock_adjustment_form.html", {
                    "movement_type": movement_type,
                    "posted_rows": posted_rows,
                })

            quantity = to_decimal(quantity_value)

            if quantity is None or quantity <= Decimal("0"):
                messages.error(request, f"Ligne {index + 1} : quantité invalide.")
                return render(request, "inventory/stock_adjustment_form.html", {
                    "movement_type": movement_type,
                    "posted_rows": posted_rows,
                })

            rows.append({
                "product_id": product_id,
                "quantity": quantity,
                "reason": reason,
                "line_number": index + 1,
            })

        if not rows:
            messages.error(request, "Ajoutez au moins une ligne de produit.")
            return render(request, "inventory/stock_adjustment_form.html", {
                "movement_type": movement_type,
                "posted_rows": posted_rows,
            })

        with transaction.atomic():
            for row in rows:
                product = Product.objects.select_for_update().select_related("unit").get(
                    pk=row["product_id"],
                    is_active=True,
                )

                old_quantity = product.stock_quantity
                quantity = row["quantity"]

                if movement_type == "out" and quantity > old_quantity:
                    messages.error(
                        request,
                        f"Ligne {row['line_number']} : stock insuffisant pour {product.name}. "
                        f"Disponible : {old_quantity} {product.unit.short_name}."
                    )
                    return render(request, "inventory/stock_adjustment_form.html", {
                        "movement_type": movement_type,
                        "posted_rows": posted_rows,
                    })

                if movement_type == "in":
                    new_quantity = old_quantity + quantity
                    stock_type = StockMovement.MovementType.IN
                    default_reason = "Entrée de stock multi-ligne"
                else:
                    new_quantity = old_quantity - quantity
                    stock_type = StockMovement.MovementType.OUT
                    default_reason = "Sortie de stock multi-ligne"

                product.stock_quantity = new_quantity
                product.save(update_fields=["stock_quantity", "updated_at"])

                StockMovement.objects.create(
                    product=product,
                    movement_type=stock_type,
                    quantity=quantity,
                    old_quantity=old_quantity,
                    new_quantity=new_quantity,
                    reason=row["reason"] or default_reason,
                )

        if movement_type == "in":
            messages.success(request, "Entrée de stock multi-ligne enregistrée avec succès.")
        else:
            messages.success(request, "Sortie de stock multi-ligne enregistrée avec succès.")

        return redirect("stock_list")

    return render(request, "inventory/stock_adjustment_form.html", {
        "movement_type": initial_type,
        "posted_rows": posted_rows,
    })


@login_required
def stock_movement_list(request):
    query = request.GET.get("q", "").strip()
    movement_type = request.GET.get("type", "").strip()
    start_date = request.GET.get("start_date", "").strip()
    end_date = request.GET.get("end_date", "").strip()

    movements = StockMovement.objects.select_related(
        "product",
        "product__unit",
    ).order_by("-created_at")

    if query:
        movements = movements.filter(
            Q(product__name__icontains=query)
            | Q(product__reference__icontains=query)
            | Q(reason__icontains=query)
        )

    if movement_type:
        movements = movements.filter(movement_type=movement_type)

    if start_date:
        movements = movements.filter(created_at__date__gte=start_date)

    if end_date:
        movements = movements.filter(created_at__date__lte=end_date)

    paginator = Paginator(movements, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "page_obj": page_obj,
        "query": query,
        "movement_type": movement_type,
        "start_date": start_date,
        "end_date": end_date,
        "movement_choices": StockMovement.MovementType.choices,
    }

    return render(request, "inventory/stock_movement_list.html", context)   