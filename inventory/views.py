from decimal import Decimal, InvalidOperation
from uuid import uuid4

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import DatabaseError, transaction
from django.db.models import F, Q, Sum
from django.http import JsonResponse
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.utils import timezone

from accounts.decorators import admin_required
from catalog.models import Category, Product

from .models import StockMovement


VALID_MOVEMENT_TYPES = {"in", "out"}


def generate_batch_reference(movement_type):
    """
    Crée une référence commune à toutes les lignes
    d'une même entrée ou d'une même sortie.
    """
    prefix = (
        "ENT"
        if movement_type == "in"
        else "SOR"
    )

    date_part = timezone.localtime().strftime(
        "%Y%m%d-%H%M%S"
    )

    token = uuid4().hex[:6].upper()

    return f"{prefix}-{date_part}-{token}"


def get_movement_document_title(movement_type):
    """
    Retourne le titre du bon selon le type de mouvement.
    """
    if movement_type == StockMovement.MovementType.IN:
        return "Bon d’entrée de stock"

    if movement_type == StockMovement.MovementType.OUT:
        return "Bon de sortie de stock"

    if movement_type == StockMovement.MovementType.SALE:
        return "Mouvement de vente"

    return "Fiche de correction de stock"


def to_decimal(value):
    """
    Convertit une valeur en Decimal.
    Retourne None lorsque la valeur est invalide.
    """
    try:
        cleaned_value = str(value or "").strip().replace(",", ".")

        if not cleaned_value:
            return None

        return Decimal(cleaned_value)

    except (InvalidOperation, TypeError, ValueError):
        return None


def normalize_movement_type(value, default="in"):
    """
    Retourne uniquement un type de mouvement autorisé.
    """
    value = str(value or "").strip().lower()

    if value in VALID_MOVEMENT_TYPES:
        return value

    return default


def product_label(product):
    """
    Libellé complet utilisé par la recherche instantanée.
    """
    reference = product.reference or "-"
    unit_name = product.unit.short_name if product.unit else ""

    return (
        f"{product.name} — "
        f"Réf: {reference} — "
        f"Stock: {product.stock_quantity} {unit_name}"
    )


def empty_stock_row(
    product_id="",
    product_label_value="",
    quantity="",
    reason="",
):
    """
    Prépare une ligne compatible avec le template.
    """
    return {
        "product_id": product_id,
        "product_label": product_label_value,
        "quantity": quantity,
        "reason": reason,
    }


def render_stock_form(
    request,
    movement_type,
    posted_rows,
):
    """
    Réaffiche le formulaire sans perdre les lignes saisies.
    """
    if not posted_rows:
        posted_rows = [empty_stock_row()]

    return render(
        request,
        "inventory/stock_adjustment_form.html",
        {
            "movement_type": movement_type,
            "posted_rows": posted_rows,
        },
    )


@admin_required
def product_search_api(request):
    """
    Recherche instantanée des produits actifs.
    Réservée à l'administrateur.
    """
    query = request.GET.get("q", "").strip()

    products = (
        Product.objects
        .filter(is_active=True)
        .select_related("unit")
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
                "reference": product.reference or "",
                "stock": str(product.stock_quantity),
                "unit": unit_name,
                "label": product_label(product),
            }
        )

    return JsonResponse(
        {
            "results": results,
            "count": len(results),
        }
    )


@admin_required
def stock_list(request):
    """
    Liste et indicateurs du stock.
    """
    query = request.GET.get("q", "").strip()
    category_id = request.GET.get("category", "").strip()
    stock_status = request.GET.get("stock", "").strip()

    products = (
        Product.objects
        .select_related(
            "category",
            "unit",
        )
        .filter(is_active=True)
        .order_by("name")
    )

    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(reference__icontains=query)
            | Q(barcode__icontains=query)
        )

    if category_id:
        products = products.filter(
            category_id=category_id
        )

    if stock_status == "low":
        products = products.filter(
            stock_quantity__lte=F("alert_quantity")
        )

    elif stock_status == "available":
        products = products.filter(
            stock_quantity__gt=Decimal("0")
        )

    elif stock_status == "zero":
        products = products.filter(
            stock_quantity=Decimal("0")
        )

    categories = (
        Category.objects
        .filter(is_active=True)
        .order_by("name")
    )

    paginator = Paginator(products, 15)
    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    active_products = Product.objects.filter(
        is_active=True
    )

    total_quantity = (
        active_products.aggregate(
            total=Sum("stock_quantity")
        )["total"]
        or Decimal("0.00")
    )

    low_stock_count = active_products.filter(
        stock_quantity__lte=F("alert_quantity")
    ).count()

    zero_stock_count = active_products.filter(
        stock_quantity=Decimal("0")
    ).count()

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

    return render(
        request,
        "inventory/stock_list.html",
        context,
    )


@admin_required
def stock_adjustment_create(
    request,
    default_type="in",
):
    """
    Enregistre une entrée ou une sortie multi-ligne.

    Toutes les lignes sont contrôlées avant la première
    modification du stock.
    """
    initial_type = normalize_movement_type(
        request.GET.get("type"),
        normalize_movement_type(default_type),
    )

    initial_product_id = (
        request.GET.get("product", "").strip()
    )

    initial_product_label = ""

    if initial_product_id:
        try:
            selected_product = (
                Product.objects
                .select_related("unit")
                .get(
                    pk=initial_product_id,
                    is_active=True,
                )
            )

            initial_product_id = str(
                selected_product.pk
            )

            initial_product_label = product_label(
                selected_product
            )

        except (
            Product.DoesNotExist,
            ValidationError,
            TypeError,
            ValueError,
        ):
            initial_product_id = ""
            initial_product_label = ""

    posted_rows = [
        empty_stock_row(
            product_id=initial_product_id,
            product_label_value=initial_product_label,
        )
    ]

    if request.method != "POST":
        return render_stock_form(
            request,
            initial_type,
            posted_rows,
        )

    movement_type = normalize_movement_type(
        request.POST.get("movement_type"),
        "in",
    )

    product_ids = request.POST.getlist("product")
    product_labels = request.POST.getlist(
        "product_label"
    )
    quantities = request.POST.getlist("quantity")
    reasons = request.POST.getlist("reason")

    rows = []
    posted_rows = []
    seen_product_ids = set()

    max_len = max(
        len(product_ids),
        len(product_labels),
        len(quantities),
        len(reasons),
        0,
    )

    # =====================================================
    # 1. VALIDATION DES DONNÉES DU FORMULAIRE
    # =====================================================

    for index in range(max_len):
        line_number = index + 1

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

        reason = (
            reasons[index].strip()
            if index < len(reasons)
            else ""
        )

        posted_rows.append(
            empty_stock_row(
                product_id=product_id,
                product_label_value=product_label_value,
                quantity=quantity_value,
                reason=reason,
            )
        )

        # Une ligne totalement vide est ignorée.
        if (
            not product_id
            and not product_label_value
            and not quantity_value
            and not reason
        ):
            continue

        if not product_id:
            messages.error(
                request,
                (
                    f"Ligne {line_number} : "
                    "recherchez puis sélectionnez "
                    "un produit valide."
                ),
            )

            return render_stock_form(
                request,
                movement_type,
                posted_rows,
            )

        quantity = to_decimal(quantity_value)

        if quantity is None:
            messages.error(
                request,
                (
                    f"Ligne {line_number} : "
                    "la quantité n'est pas valide."
                ),
            )

            return render_stock_form(
                request,
                movement_type,
                posted_rows,
            )

        if quantity <= Decimal("0"):
            messages.error(
                request,
                (
                    f"Ligne {line_number} : "
                    "la quantité doit être "
                    "supérieure à zéro."
                ),
            )

            return render_stock_form(
                request,
                movement_type,
                posted_rows,
            )

        normalized_product_id = str(product_id)

        if normalized_product_id in seen_product_ids:
            messages.error(
                request,
                (
                    f"Ligne {line_number} : "
                    "ce produit est déjà présent "
                    "dans une autre ligne."
                ),
            )

            return render_stock_form(
                request,
                movement_type,
                posted_rows,
            )

        seen_product_ids.add(
            normalized_product_id
        )

        rows.append(
            {
                "product_id": normalized_product_id,
                "quantity": quantity,
                "reason": reason,
                "line_number": line_number,
            }
        )

    if not rows:
        messages.error(
            request,
            "Ajoutez au moins un produit avec une quantité.",
        )

        return render_stock_form(
            request,
            movement_type,
            posted_rows,
        )

    product_ids_to_lock = [
        row["product_id"]
        for row in rows
    ]

    batch_reference = generate_batch_reference(
        movement_type
    )

    validation_error = None

    try:
        # =================================================
        # 2. VERROUILLAGE ET VALIDATION DE TOUS LES PRODUITS
        # =================================================

        with transaction.atomic():
            locked_queryset = (
                Product.objects
                .select_for_update()
                .select_related("unit")
                .filter(
                    pk__in=product_ids_to_lock,
                    is_active=True,
                )
                .order_by("pk")
            )

            locked_products = {
                str(product.pk): product
                for product in locked_queryset
            }

            # Vérifier que chaque produit existe toujours.
            for row in rows:
                product = locked_products.get(
                    row["product_id"]
                )

                if product is None:
                    validation_error = (
                        f"Ligne {row['line_number']} : "
                        "le produit sélectionné est "
                        "introuvable ou désactivé."
                    )
                    break

            # Pour une sortie, vérifier tous les stocks
            # avant de modifier le premier produit.
            if (
                validation_error is None
                and movement_type == "out"
            ):
                for row in rows:
                    product = locked_products[
                        row["product_id"]
                    ]

                    current_stock = (
                        product.stock_quantity
                        or Decimal("0.00")
                    )

                    if row["quantity"] > current_stock:
                        unit_name = (
                            product.unit.short_name
                            if product.unit
                            else ""
                        )

                        validation_error = (
                            f"Ligne {row['line_number']} : "
                            f"stock insuffisant pour "
                            f"{product.name}. "
                            f"Disponible : "
                            f"{current_stock} "
                            f"{unit_name}."
                        )
                        break

            # =============================================
            # 3. ÉCRITURE UNIQUEMENT SI TOUT EST VALIDE
            # =============================================

            if validation_error is None:
                actor_name = (
                    request.user.get_full_name().strip()
                    or request.user.username
                )

                for row in rows:
                    product = locked_products[
                        row["product_id"]
                    ]

                    old_quantity = (
                        product.stock_quantity
                        or Decimal("0.00")
                    )

                    quantity = row["quantity"]

                    if movement_type == "in":
                        new_quantity = (
                            old_quantity + quantity
                        )

                        stock_type = (
                            StockMovement
                            .MovementType
                            .IN
                        )

                        default_reason = (
                            "Entrée de stock multi-ligne "
                            f"par {actor_name}"
                        )

                    else:
                        new_quantity = (
                            old_quantity - quantity
                        )

                        stock_type = (
                            StockMovement
                            .MovementType
                            .OUT
                        )

                        default_reason = (
                            "Sortie de stock multi-ligne "
                            f"par {actor_name}"
                        )

                    # Sécurité supplémentaire.
                    if new_quantity < Decimal("0"):
                        raise ValueError(
                            "Le stock ne peut pas "
                            "devenir négatif."
                        )

                    product.stock_quantity = new_quantity

                    product.save(
                        update_fields=[
                            "stock_quantity",
                            "updated_at",
                        ]
                    )

                    StockMovement.objects.create(
                        product=product,
                        movement_type=stock_type,
                        batch_reference=batch_reference,
                        quantity=quantity,
                        old_quantity=old_quantity,
                        new_quantity=new_quantity,
                        reason=(
                            row["reason"]
                            or default_reason
                        ),
                    )

    except (
        ValidationError,
        ValueError,
        TypeError,
    ):
        messages.error(
            request,
            (
                "Un produit sélectionné n'est pas valide. "
                "Rechargez la page puis recommencez."
            ),
        )

        return render_stock_form(
            request,
            movement_type,
            posted_rows,
        )

    except DatabaseError:
        messages.error(
            request,
            (
                "L'opération n'a pas pu être enregistrée. "
                "Aucune quantité de stock n'a été modifiée."
            ),
        )

        return render_stock_form(
            request,
            movement_type,
            posted_rows,
        )

    if validation_error:
        messages.error(
            request,
            validation_error,
        )

        return render_stock_form(
            request,
            movement_type,
            posted_rows,
        )

    if movement_type == "in":
        messages.success(
            request,
            (
                f"Entrée de stock enregistrée avec succès : "
                f"{len(rows)} produit(s)."
            ),
        )
    else:
        messages.success(
            request,
            (
                f"Sortie de stock enregistrée avec succès : "
                f"{len(rows)} produit(s)."
            ),
        )

    return redirect(
        "stock_movement_batch_print",
        batch_reference=batch_reference,
    )


def filter_stock_movements(request):
    """
    Applique les filtres communs à la liste
    et à l'impression générale.
    """
    query = request.GET.get("q", "").strip()

    movement_type = request.GET.get(
        "type",
        "",
    ).strip()

    start_date = request.GET.get(
        "start_date",
        "",
    ).strip()

    end_date = request.GET.get(
        "end_date",
        "",
    ).strip()

    movements = (
        StockMovement.objects
        .select_related(
            "product",
            "product__unit",
            "product__category",
        )
        .order_by(
            "-created_at",
            "-pk",
        )
    )

    if query:
        movements = movements.filter(
            Q(product__name__icontains=query)
            | Q(product__reference__icontains=query)
            | Q(product__barcode__icontains=query)
            | Q(batch_reference__icontains=query)
            | Q(reason__icontains=query)
        )

    allowed_movement_types = {
        value
        for value, label
        in StockMovement.MovementType.choices
    }

    if movement_type in allowed_movement_types:
        movements = movements.filter(
            movement_type=movement_type
        )
    else:
        movement_type = ""

    if start_date:
        movements = movements.filter(
            created_at__date__gte=start_date
        )

    if end_date:
        movements = movements.filter(
            created_at__date__lte=end_date
        )

    return movements, {
        "query": query,
        "movement_type": movement_type,
        "start_date": start_date,
        "end_date": end_date,
    }


@admin_required
def stock_movement_list(request):
    """
    Historique paginé des mouvements de stock.
    """
    movements, filters = filter_stock_movements(
        request
    )

    paginator = Paginator(
        movements,
        20,
    )

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    filter_params = request.GET.copy()
    filter_params.pop("page", None)

    context = {
        "page_obj": page_obj,
        "query": filters["query"],
        "movement_type": filters["movement_type"],
        "start_date": filters["start_date"],
        "end_date": filters["end_date"],
        "movement_choices": (
            StockMovement.MovementType.choices
        ),
        "filter_query": filter_params.urlencode(),
    }

    return render(
        request,
        "inventory/stock_movement_list.html",
        context,
    )


@admin_required
def stock_movement_report_print(request):
    """
    Imprime tous les mouvements correspondant
    aux filtres sélectionnés.
    """
    movements, filters = filter_stock_movements(
        request
    )

    context = {
        "movements": movements,
        "movement_count": movements.count(),
        "query": filters["query"],
        "movement_type": filters["movement_type"],
        "start_date": filters["start_date"],
        "end_date": filters["end_date"],
        "printed_at": timezone.localtime(),
    }

    return render(
        request,
        "inventory/stock_movement_report_print.html",
        context,
    )


@admin_required
def stock_movement_batch_print(
    request,
    batch_reference,
):
    """
    Imprime toutes les lignes appartenant au même bon
    d'entrée ou de sortie.
    """
    first_movement = get_object_or_404(
        StockMovement.objects.select_related(
            "product",
            "product__unit",
            "product__category",
        ),
        batch_reference=batch_reference,
    )

    movements = (
        StockMovement.objects
        .select_related(
            "product",
            "product__unit",
            "product__category",
        )
        .filter(
            batch_reference=batch_reference,
            movement_type=first_movement.movement_type,
        )
        .order_by(
            "created_at",
            "pk",
        )
    )

    context = {
        "movements": movements,
        "first_movement": first_movement,
        "batch_reference": batch_reference,
        "document_title": get_movement_document_title(
            first_movement.movement_type
        ),
        "line_count": movements.count(),
        "printed_at": timezone.localtime(),
    }

    return render(
        request,
        "inventory/stock_movement_print.html",
        context,
    )


@admin_required
def stock_movement_print(
    request,
    movement_pk,
):
    """
    Impression de secours pour un ancien mouvement
    qui ne possède pas encore de référence de bon.
    """
    movement = get_object_or_404(
        StockMovement.objects.select_related(
            "product",
            "product__unit",
            "product__category",
        ),
        pk=movement_pk,
    )

    if movement.batch_reference:
        return redirect(
            "stock_movement_batch_print",
            batch_reference=movement.batch_reference,
        )

    context = {
        "movements": [movement],
        "first_movement": movement,
        "batch_reference": f"MVT-{movement.pk}",
        "document_title": get_movement_document_title(
            movement.movement_type
        ),
        "line_count": 1,
        "printed_at": timezone.localtime(),
    }

    return render(
        request,
        "inventory/stock_movement_print.html",
        context,
    )