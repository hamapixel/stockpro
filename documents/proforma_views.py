from decimal import Decimal, InvalidOperation
from uuid import uuid4

import traceback

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import DatabaseError, transaction
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from accounts.decorators import (
    seller_or_admin_required,
)
from catalog.models import Product
from inventory.models import StockMovement
from sales.models import Sale, SaleItem

from .barcodes import (
    generate_code128_data_uri,
)
from .forms import ProformaHeaderForm
from .models import (
    Proforma,
    ProformaItem,
    ZERO,
    default_valid_until,
)


class ProformaOperationError(Exception):
    """
    Erreur fonctionnelle annulant entièrement
    la transaction en cours.
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
        f"Réf : {reference} — "
        f"Stock : {product.stock_quantity} "
        f"{unit_name}"
    )


def empty_proforma_row(
    product_id="",
    product_label_value="",
    quantity="",
    unit_price="",
    line_discount="",
):
    return {
        "product_id": product_id,
        "product_label": (
            product_label_value
        ),
        "quantity": quantity,
        "unit_price": unit_price,
        "line_discount": line_discount,
    }


def issue_submission_token(request):
    token = uuid4().hex

    tokens = request.session.get(
        "proforma_form_tokens",
        [],
    )

    tokens.append(token)

    request.session[
        "proforma_form_tokens"
    ] = tokens[-10:]

    request.session.modified = True

    return token


def submission_token_is_valid(
    request,
    token,
):
    tokens = request.session.get(
        "proforma_form_tokens",
        [],
    )

    return bool(
        token
        and token in tokens
    )


def consume_submission_token(
    request,
    token,
):
    tokens = request.session.get(
        "proforma_form_tokens",
        [],
    )

    request.session[
        "proforma_form_tokens"
    ] = [
        current_token
        for current_token in tokens
        if current_token != token
    ]

    request.session.modified = True


def extract_posted_rows(request):
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

    rows = []

    for index in range(max_len):
        rows.append(
            empty_proforma_row(
                product_id=(
                    product_ids[index].strip()
                    if index
                    < len(product_ids)
                    else ""
                ),
                product_label_value=(
                    product_labels[index]
                    .strip()
                    if index
                    < len(product_labels)
                    else ""
                ),
                quantity=(
                    quantities[index].strip()
                    if index
                    < len(quantities)
                    else ""
                ),
                unit_price=(
                    unit_prices[index].strip()
                    if index
                    < len(unit_prices)
                    else ""
                ),
                line_discount=(
                    line_discounts[index]
                    .strip()
                    if index
                    < len(line_discounts)
                    else ""
                ),
            )
        )

    return rows


def build_existing_rows(proforma):
    rows = []

    items = (
        proforma.items
        .select_related(
            "product",
            "product__unit",
        )
        .order_by("pk")
    )

    for item in items:
        rows.append(
            empty_proforma_row(
                product_id=str(
                    item.product_id
                ),
                product_label_value=(
                    product_label(
                        item.product
                    )
                ),
                quantity=str(
                    item.quantity
                ),
                unit_price=str(
                    item.unit_price
                ),
                line_discount=str(
                    item.discount
                ),
            )
        )

    return rows or [
        empty_proforma_row()
    ]


def validate_rows(posted_rows):
    rows = []
    seen_product_ids = set()

    for line_number, posted_row in enumerate(
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

        line_discount_value = posted_row[
            "line_discount"
        ]

        if (
            not product_id
            and not product_label_value
            and not quantity_value
            and not unit_price_value
            and not line_discount_value
        ):
            continue

        if not product_id:
            raise ProformaOperationError(
                (
                    f"Ligne {line_number} : "
                    "recherchez et sélectionnez "
                    "un produit valide."
                )
            )

        normalized_product_id = str(
            product_id
        )

        if (
            normalized_product_id
            in seen_product_ids
        ):
            raise ProformaOperationError(
                (
                    f"Ligne {line_number} : "
                    "ce produit est déjà présent "
                    "dans la proforma."
                )
            )

        seen_product_ids.add(
            normalized_product_id
        )

        quantity = to_decimal(
            quantity_value
        )

        unit_price = to_decimal(
            unit_price_value
        )

        line_discount = (
            to_decimal(
                line_discount_value
            )
            if line_discount_value
            else ZERO
        )

        if (
            quantity is None
            or quantity <= ZERO
        ):
            raise ProformaOperationError(
                (
                    f"Ligne {line_number} : "
                    "la quantité doit être "
                    "supérieure à zéro."
                )
            )

        if (
            unit_price is None
            or unit_price < ZERO
        ):
            raise ProformaOperationError(
                (
                    f"Ligne {line_number} : "
                    "le prix proposé n’est "
                    "pas valide."
                )
            )

        if (
            line_discount is None
            or line_discount < ZERO
        ):
            raise ProformaOperationError(
                (
                    f"Ligne {line_number} : "
                    "la remise n’est pas valide."
                )
            )

        gross_total = (
            quantity * unit_price
        )

        if line_discount > gross_total:
            raise ProformaOperationError(
                (
                    f"Ligne {line_number} : "
                    "la remise dépasse le "
                    "montant brut de la ligne."
                )
            )

        rows.append(
            {
                "product_id": (
                    normalized_product_id
                ),
                "quantity": quantity,
                "unit_price": unit_price,
                "line_discount": (
                    line_discount
                ),
                "line_number": line_number,
            }
        )

    if not rows:
        raise ProformaOperationError(
            "Ajoutez au moins un produit."
        )

    return rows


def calculate_preview(
    rows,
    global_discount,
):
    subtotal = sum(
        (
            (
                row["quantity"]
                * row["unit_price"]
            )
            - row["line_discount"]
            for row in rows
        ),
        ZERO,
    )

    if global_discount > subtotal:
        raise ProformaOperationError(
            (
                "La remise globale dépasse "
                "le sous-total."
            )
        )

    return (
        subtotal,
        subtotal - global_discount,
    )


def fetch_products(rows, *, lock=False):
    """
    Récupère les produits sélectionnés.

    Lorsqu'un verrou PostgreSQL est demandé, aucune
    jointure externe vers unit ou category n'est utilisée.
    Cela évite l'erreur :
    FOR UPDATE ne peut être appliqué sur le côté
    possiblement NULL d'une jointure externe.
    """
    queryset = (
        Product.objects
        .filter(
            pk__in=[
                row["product_id"]
                for row in rows
            ],
            is_active=True,
        )
        .order_by("pk")
    )

    if lock:
        queryset = (
            queryset.select_for_update()
        )
    else:
        queryset = (
            queryset.select_related(
                "unit",
                "category",
            )
        )

    products = {
        str(product.pk): product
        for product in queryset
    }

    for row in rows:
        if (
            row["product_id"]
            not in products
        ):
            raise ProformaOperationError(
                (
                    f"Ligne "
                    f"{row['line_number']} : "
                    "produit introuvable ou "
                    "désactivé."
                )
            )

    return products


def create_items(
    proforma,
    rows,
    products,
):
    for row in rows:
        ProformaItem.objects.create(
            proforma=proforma,
            product=products[
                row["product_id"]
            ],
            quantity=row["quantity"],
            unit_price=row[
                "unit_price"
            ],
            discount=row[
                "line_discount"
            ],
        )


def add_validation_errors(
    form,
    exception,
):
    if hasattr(
        exception,
        "message_dict",
    ):
        for field_name, errors in (
            exception.message_dict.items()
        ):
            target_field = (
                field_name
                if field_name
                in form.fields
                else None
            )

            for error in errors:
                form.add_error(
                    target_field,
                    error,
                )

    else:
        for error in exception.messages:
            form.add_error(
                None,
                error,
            )


def render_proforma_form(
    request,
    *,
    form,
    submission_token,
    posted_rows=None,
    proforma=None,
):
    if not posted_rows:
        posted_rows = [
            empty_proforma_row()
        ]

    is_edit = proforma is not None

    return render(
        request,
        "documents/proforma_form.html",
        {
            "form": form,
            "submission_token": (
                submission_token
            ),
            "posted_rows": posted_rows,
            "proforma": proforma,
            "is_edit": is_edit,
            "page_title": (
                "Modifier la proforma"
                if is_edit
                else "Nouvelle proforma"
            ),
            "submit_label": (
                "Enregistrer les modifications"
                if is_edit
                else "Créer la proforma"
            ),
        },
    )


@seller_or_admin_required
def proforma_list(request):
    query = request.GET.get(
        "q",
        "",
    ).strip()

    status = request.GET.get(
        "status",
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

    proformas = (
        Proforma.objects
        .select_related(
            "client",
            "created_by",
            "converted_sale",
        )
        .annotate(
            item_count=Count("items")
        )
        .order_by(
            "-proforma_date",
            "-created_at",
        )
    )

    if query:
        proformas = proformas.filter(
            Q(
                proforma_number__icontains=(
                    query
                )
            )
            | Q(
                client__full_name__icontains=(
                    query
                )
            )
            | Q(
                client__phone__icontains=(
                    query
                )
            )
        )

    valid_statuses = {
        value
        for value, label
        in Proforma.Status.choices
    }

    if status in valid_statuses:
        proformas = proformas.filter(
            status=status
        )
    else:
        status = ""

    parsed_start = parse_date(
        start_date
    )

    parsed_end = parse_date(
        end_date
    )

    if parsed_start:
        proformas = proformas.filter(
            proforma_date__date__gte=(
                parsed_start
            )
        )
    else:
        start_date = ""

    if parsed_end:
        proformas = proformas.filter(
            proforma_date__date__lte=(
                parsed_end
            )
        )
    else:
        end_date = ""

    total_amount = (
        proformas.aggregate(
            total=Sum("total")
        )["total"]
        or ZERO
    )

    today = timezone.localdate()

    proforma_count = proformas.count()

    draft_count = proformas.filter(
        status=Proforma.Status.DRAFT
    ).count()

    expired_count = (
        proformas
        .filter(
            valid_until__lt=today
        )
        .exclude(
            status__in=[
                Proforma.Status.CONVERTED,
                Proforma.Status.CANCELLED,
            ]
        )
        .count()
    )

    paginator = Paginator(
        proformas,
        15,
    )

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    query_params = request.GET.copy()
    query_params.pop("page", None)

    return render(
        request,
        "documents/proforma_list.html",
        {
            "page_obj": page_obj,
            "query": query,
            "status": status,
            "start_date": start_date,
            "end_date": end_date,
            "status_choices": (
                Proforma.Status.choices
            ),
            "proforma_count": (
                proforma_count
            ),
            "draft_count": draft_count,
            "expired_count": (
                expired_count
            ),
            "total_amount": total_amount,
            "filter_query": (
                query_params.urlencode()
            ),
        },
    )


@seller_or_admin_required
def proforma_product_search_api(
    request,
):
    """
    API rapide du catalogue Proforma.

    - 60 produits par page ;
    - recherche côté serveur ;
    - filtre par catégorie ;
    - pagination avec chargement progressif ;
    - images chargées uniquement pour les produits affichés.
    """
    query = request.GET.get(
        "q",
        "",
    ).strip()

    category = request.GET.get(
        "category",
        "",
    ).strip()

    try:
        page = int(
            request.GET.get(
                "page",
                1,
            )
        )
    except (
        TypeError,
        ValueError,
    ):
        page = 1

    page = max(page, 1)
    page_size = 60

    products = (
        Product.objects
        .filter(is_active=True)
        .select_related(
            "unit",
            "category",
        )
        .only(
            "id",
            "name",
            "reference",
            "barcode",
            "stock_quantity",
            "sale_price",
            "image",
            "unit__short_name",
            "category__name",
        )
        .order_by(
            "name",
            "pk",
        )
    )

    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(
                reference__icontains=query
            )
            | Q(
                barcode__icontains=query
            )
        )

    if category:
        products = products.filter(
            category__name=category
        )

    total_count = products.count()

    start = (
        page - 1
    ) * page_size

    stop = (
        start
        + page_size
        + 1
    )

    page_products = list(
        products[start:stop]
    )

    has_next = (
        len(page_products)
        > page_size
    )

    page_products = page_products[
        :page_size
    ]

    results = []

    for product in page_products:
        unit_name = (
            product.unit.short_name
            if product.unit
            else ""
        )

        category_name = (
            product.category.name
            if product.category
            else ""
        )

        image_url = ""

        try:
            if product.image:
                image_url = (
                    product.image.url
                )
        except (
            AttributeError,
            ValueError,
        ):
            image_url = ""

        results.append(
            {
                "id": product.pk,
                "name": product.name,
                "reference": (
                    product.reference
                    or ""
                ),
                "barcode": (
                    product.barcode
                    or ""
                ),
                "stock": str(
                    product.stock_quantity
                    or ZERO
                ),
                "unit": unit_name,
                "category": category_name,
                "sale_price": str(
                    product.sale_price
                    or ZERO
                ),
                "image_url": image_url,
                "label": product_label(
                    product
                ),
            }
        )

    categories = list(
        Product.objects
        .filter(
            is_active=True,
            category__isnull=False,
        )
        .exclude(
            category__name="",
        )
        .values_list(
            "category__name",
            flat=True,
        )
        .distinct()
        .order_by(
            "category__name"
        )
    )

    return JsonResponse(
        {
            "results": results,
            "count": len(results),
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "has_next": has_next,
            "categories": categories,
        }
    )


@seller_or_admin_required
def proforma_create(request):
    if request.method != "POST":
        submission_token = (
            issue_submission_token(
                request
            )
        )

        return render_proforma_form(
            request,
            form=ProformaHeaderForm(),
            submission_token=(
                submission_token
            ),
        )

    submission_token = request.POST.get(
        "submission_token",
        "",
    ).strip()

    if not submission_token_is_valid(
        request,
        submission_token,
    ):
        messages.warning(
            request,
            (
                "Ce formulaire a déjà été "
                "envoyé ou a expiré."
            ),
        )

        return redirect(
            "proforma_list"
        )

    form = ProformaHeaderForm(
        request.POST
    )

    posted_rows = extract_posted_rows(
        request
    )

    def fail(message=None):
        if message:
            messages.error(
                request,
                message,
            )

        return render_proforma_form(
            request,
            form=form,
            submission_token=(
                submission_token
            ),
            posted_rows=posted_rows,
        )

    if not form.is_valid():
        messages.error(
            request,
            "Corrigez les erreurs.",
        )

        return fail()

    try:
        rows = validate_rows(
            posted_rows
        )

        global_discount = (
            form.cleaned_data[
                "discount"
            ]
            or ZERO
        )

        subtotal_preview, total_preview = (
            calculate_preview(
                rows,
                global_discount,
            )
        )

        with transaction.atomic():
            products = fetch_products(
                rows,
                lock=True,
            )

            proforma = form.save(
                commit=False
            )

            proforma.created_by = (
                request.user
            )

            proforma.save()

            create_items(
                proforma,
                rows,
                products,
            )

            proforma.calculate_totals(
                save=True
            )

            if (
                proforma.subtotal
                != subtotal_preview
                or proforma.total
                != total_preview
            ):
                raise ProformaOperationError(
                    (
                        "Incohérence détectée "
                        "dans les totaux."
                    )
                )

            consume_submission_token(
                request,
                submission_token,
            )

    except ProformaOperationError as error:
        return fail(str(error))

    except ValidationError as error:
        add_validation_errors(
            form,
            error,
        )

        return fail()

    except (
        DatabaseError,
        TypeError,
        ValueError,
    ) as error:
        traceback.print_exc()

        error_name = type(error).__name__

        print("=" * 80)
        print("ERREUR ENREGISTREMENT PROFORMA")
        print("TYPE :", error_name)
        print("DÉTAIL :", repr(error))
        print("=" * 80)

        return fail(
            (
                "Erreur technique pendant "
                "l'enregistrement : "
                f"{error_name} — {error}"
            )
        )

    except Exception as error:
        traceback.print_exc()

        error_name = type(error).__name__

        print("=" * 80)
        print("ERREUR INATTENDUE PROFORMA")
        print("TYPE :", error_name)
        print("DÉTAIL :", repr(error))
        print("=" * 80)

        return fail(
            (
                "Erreur inattendue pendant "
                "l'enregistrement : "
                f"{error_name} — {error}"
            )
        )

    messages.success(
        request,
        (
            f"Proforma "
            f"{proforma.proforma_number} "
            "créée. Le stock et la caisse "
            "n’ont pas été modifiés."
        ),
    )

    return redirect(
        "proforma_detail",
        pk=proforma.pk,
    )


@seller_or_admin_required
def proforma_detail(request, pk):
    proforma = get_object_or_404(
        Proforma.objects.select_related(
            "client",
            "created_by",
            "converted_sale",
        ),
        pk=pk,
    )

    items = (
        proforma.items
        .select_related(
            "product",
            "product__unit",
            "product__category",
        )
        .order_by("pk")
    )

    return render(
        request,
        "documents/proforma_detail.html",
        {
            "proforma": proforma,
            "items": items,
        },
    )


@seller_or_admin_required
def proforma_update(request, pk):
    proforma = get_object_or_404(
        Proforma.objects.select_related(
            "client",
            "converted_sale",
        ),
        pk=pk,
    )

    if not proforma.can_be_modified:
        messages.error(
            request,
            (
                "Cette proforma ne peut "
                "plus être modifiée."
            ),
        )

        return redirect(
            "proforma_detail",
            pk=pk,
        )

    if request.method != "POST":
        submission_token = (
            issue_submission_token(
                request
            )
        )

        return render_proforma_form(
            request,
            form=ProformaHeaderForm(
                instance=proforma
            ),
            submission_token=(
                submission_token
            ),
            posted_rows=(
                build_existing_rows(
                    proforma
                )
            ),
            proforma=proforma,
        )

    submission_token = request.POST.get(
        "submission_token",
        "",
    ).strip()

    if not submission_token_is_valid(
        request,
        submission_token,
    ):
        messages.warning(
            request,
            (
                "Ce formulaire a déjà été "
                "envoyé ou a expiré."
            ),
        )

        return redirect(
            "proforma_detail",
            pk=pk,
        )

    form = ProformaHeaderForm(
        request.POST,
        instance=proforma,
    )

    posted_rows = extract_posted_rows(
        request
    )

    def fail(message=None):
        if message:
            messages.error(
                request,
                message,
            )

        return render_proforma_form(
            request,
            form=form,
            submission_token=(
                submission_token
            ),
            posted_rows=posted_rows,
            proforma=proforma,
        )

    if not form.is_valid():
        messages.error(
            request,
            "Corrigez les erreurs.",
        )

        return fail()

    try:
        rows = validate_rows(
            posted_rows
        )

        global_discount = (
            form.cleaned_data[
                "discount"
            ]
            or ZERO
        )

        subtotal_preview, total_preview = (
            calculate_preview(
                rows,
                global_discount,
            )
        )

        with transaction.atomic():
            locked_proforma = (
                Proforma.objects
                .select_for_update()
                .get(pk=pk)
            )

            if (
                not locked_proforma
                .can_be_modified
            ):
                raise ProformaOperationError(
                    (
                        "La proforma a été "
                        "verrouillée entre-temps."
                    )
                )

            products = fetch_products(
                rows,
                lock=True,
            )

            cleaned = form.cleaned_data

            locked_proforma.client = (
                cleaned["client"]
            )

            locked_proforma.proforma_date = (
                cleaned["proforma_date"]
            )

            locked_proforma.valid_until = (
                cleaned["valid_until"]
            )

            locked_proforma.status = (
                cleaned["status"]
            )

            locked_proforma.discount = (
                global_discount
            )

            locked_proforma.notes = (
                cleaned["notes"]
            )

            locked_proforma.terms = (
                cleaned["terms"]
            )

            locked_proforma.save()

            locked_proforma.items.all().delete()

            create_items(
                locked_proforma,
                rows,
                products,
            )

            locked_proforma.calculate_totals(
                save=True
            )

            if (
                locked_proforma.subtotal
                != subtotal_preview
                or locked_proforma.total
                != total_preview
            ):
                raise ProformaOperationError(
                    (
                        "Incohérence détectée "
                        "dans les totaux."
                    )
                )

            consume_submission_token(
                request,
                submission_token,
            )

            proforma = locked_proforma

    except ProformaOperationError as error:
        return fail(str(error))

    except ValidationError as error:
        add_validation_errors(
            form,
            error,
        )

        return fail()

    except (
        DatabaseError,
        TypeError,
        ValueError,
    ) as error:
        traceback.print_exc()

        error_name = type(error).__name__

        print("=" * 80)
        print("ERREUR MODIFICATION PROFORMA")
        print("TYPE :", error_name)
        print("DÉTAIL :", repr(error))
        print("=" * 80)

        return fail(
            (
                "Erreur technique pendant "
                "la modification : "
                f"{error_name} — {error}"
            )
        )

    except Exception as error:
        traceback.print_exc()

        error_name = type(error).__name__

        print("=" * 80)
        print("ERREUR INATTENDUE MODIFICATION PROFORMA")
        print("TYPE :", error_name)
        print("DÉTAIL :", repr(error))
        print("=" * 80)

        return fail(
            (
                "Erreur inattendue pendant "
                "la modification : "
                f"{error_name} — {error}"
            )
        )

    messages.success(
        request,
        (
            f"Proforma "
            f"{proforma.proforma_number} "
            "modifiée."
        ),
    )

    return redirect(
        "proforma_detail",
        pk=proforma.pk,
    )


@require_POST
@seller_or_admin_required
def proforma_duplicate(request, pk):
    source = get_object_or_404(
        Proforma.objects.prefetch_related(
            "items"
        ),
        pk=pk,
    )

    try:
        with transaction.atomic():
            duplicated = Proforma.objects.create(
                client=source.client,
                proforma_date=timezone.now(),
                valid_until=(
                    default_valid_until()
                ),
                discount=(
                    source.discount or ZERO
                ),
                status=(
                    Proforma.Status.DRAFT
                ),
                notes=source.notes,
                terms=source.terms,
                created_by=request.user,
            )

            source_items = (
                source.items
                .select_related("product")
                .order_by("pk")
            )

            for item in source_items:
                ProformaItem.objects.create(
                    proforma=duplicated,
                    product=item.product,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    discount=item.discount,
                )

            duplicated.calculate_totals(
                save=True
            )

    except (
        DatabaseError,
        ValidationError,
    ):
        messages.error(
            request,
            (
                "La duplication de la "
                "proforma a échoué."
            ),
        )

        return redirect(
            "proforma_detail",
            pk=pk,
        )

    messages.success(
        request,
        (
            f"Nouvelle proforma "
            f"{duplicated.proforma_number} "
            "créée."
        ),
    )

    return redirect(
        "proforma_update",
        pk=duplicated.pk,
    )


@require_POST
@seller_or_admin_required
def proforma_cancel(request, pk):
    try:
        with transaction.atomic():
            proforma = (
                Proforma.objects
                .select_for_update()
                .get(pk=pk)
            )

            cancelled = proforma.cancel()

    except Proforma.DoesNotExist:
        messages.error(
            request,
            "Proforma introuvable.",
        )

        return redirect(
            "proforma_list"
        )

    except ValidationError as error:
        messages.error(
            request,
            "; ".join(
                error.messages
            ),
        )

        return redirect(
            "proforma_detail",
            pk=pk,
        )

    except DatabaseError:
        messages.error(
            request,
            "L’annulation a échoué.",
        )

        return redirect(
            "proforma_detail",
            pk=pk,
        )

    if cancelled:
        messages.success(
            request,
            "Proforma annulée.",
        )
    else:
        messages.info(
            request,
            "Proforma déjà annulée.",
        )

    return redirect(
        "proforma_detail",
        pk=pk,
    )


@seller_or_admin_required
def proforma_print(request, pk):
    proforma = get_object_or_404(
        Proforma.objects.select_related(
            "client",
            "created_by",
            "converted_sale",
        ),
        pk=pk,
    )

    items = (
        proforma.items
        .select_related(
            "product",
            "product__unit",
            "product__category",
        )
        .order_by("pk")
    )

    return render(
        request,
        "documents/proforma_print.html",
        {
            "proforma": proforma,
            "items": items,
            "proforma_barcode": (
                generate_code128_data_uri(
                    proforma.proforma_number
                )
            ),
        },
    )


@require_POST
@seller_or_admin_required
def proforma_convert(request, pk):
    """
    Conversion en vente à crédit :
    - création de la vente ;
    - création des lignes ;
    - diminution du stock ;
    - mouvements de stock regroupés avec
      le numéro de vente ;
    - aucun paiement automatique.
    """
    try:
        with transaction.atomic():
            proforma = (
                Proforma.objects
                .select_for_update()
                .get(pk=pk)
            )

            if proforma.converted_sale_id:
                messages.info(
                    request,
                    (
                        "Cette proforma est "
                        "déjà convertie."
                    ),
                )

                return redirect(
                    "proforma_detail",
                    pk=pk,
                )

            if not proforma.can_be_converted:
                raise ProformaOperationError(
                    (
                        "Cette proforma ne peut "
                        "pas être convertie. "
                        "Vérifiez le client, le "
                        "statut et la date de "
                        "validité."
                    )
                )

            items = list(
                proforma.items
                .select_for_update()
                .order_by(
                    "product_id",
                    "pk",
                )
            )

            if not items:
                raise ProformaOperationError(
                    (
                        "La proforma ne contient "
                        "aucun produit."
                    )
                )

            products = {
                product.pk: product
                for product in (
                    Product.objects
                    .select_for_update()
                    .filter(
                        pk__in=[
                            item.product_id
                            for item in items
                        ],
                        is_active=True,
                    )
                    .order_by("pk")
                )
            }

            stock_errors = []

            for item in items:
                product = products.get(
                    item.product_id
                )

                if product is None:
                    stock_errors.append(
                        (
                            f"{item.product.name} : "
                            "produit indisponible."
                        )
                    )
                    continue

                current_stock = (
                    product.stock_quantity
                    or ZERO
                )

                if item.quantity > current_stock:
                    unit_name = (
                        product.unit.short_name
                        if product.unit
                        else ""
                    )

                    stock_errors.append(
                        (
                            f"{product.name} : "
                            f"stock {current_stock} "
                            f"{unit_name}, demandé "
                            f"{item.quantity} "
                            f"{unit_name}."
                        )
                    )

            if stock_errors:
                raise ProformaOperationError(
                    (
                        "Stock insuffisant : "
                        + " | ".join(
                            stock_errors
                        )
                    )
                )

            sale_notes = (
                "Vente créée depuis la "
                f"proforma "
                f"{proforma.proforma_number}."
            )

            if proforma.notes:
                sale_notes += (
                    "\n"
                    + proforma.notes.strip()
                )

            sale = Sale.objects.create(
                client=proforma.client,
                sale_date=timezone.now(),
                subtotal=ZERO,
                discount=(
                    proforma.discount
                    or ZERO
                ),
                total=ZERO,
                amount_paid=ZERO,
                remaining_amount=ZERO,
                payment_status=(
                    Sale.PaymentStatus.CREDIT
                ),
                payment_method=(
                    Sale.PaymentMethod.CREDIT
                ),
                notes=sale_notes,
                created_by=request.user,
                is_cancelled=False,
            )

            for item in items:
                product = products[
                    item.product_id
                ]

                SaleItem.objects.create(
                    sale=sale,
                    product=product,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    discount=item.discount,
                )

                old_quantity = (
                    product.stock_quantity
                    or ZERO
                )

                new_quantity = (
                    old_quantity
                    - item.quantity
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
                    batch_reference=(
                        sale.sale_number
                    ),
                    quantity=item.quantity,
                    old_quantity=old_quantity,
                    new_quantity=new_quantity,
                    reason=(
                        "Conversion de la "
                        f"proforma "
                        f"{proforma.proforma_number} "
                        "en vente "
                        f"{sale.sale_number}"
                    ),
                )

            sale.calculate_totals(
                save=True
            )

            if (
                sale.subtotal
                != proforma.subtotal
                or sale.total
                != proforma.total
            ):
                raise ProformaOperationError(
                    (
                        "Incohérence entre les "
                        "totaux de la proforma "
                        "et de la vente."
                    )
                )

            Sale.update_client_balance(
                sale.client
            )

            proforma.converted_sale = sale
            proforma.status = (
                Proforma.Status.CONVERTED
            )

            proforma.save(
                update_fields=[
                    "converted_sale",
                    "status",
                    "updated_at",
                ]
            )

    except Proforma.DoesNotExist:
        messages.error(
            request,
            "Proforma introuvable.",
        )

        return redirect(
            "proforma_list"
        )

    except ProformaOperationError as error:
        messages.error(
            request,
            str(error),
        )

        return redirect(
            "proforma_detail",
            pk=pk,
        )

    except ValidationError as error:
        messages.error(
            request,
            "; ".join(
                error.messages
            ),
        )

        return redirect(
            "proforma_detail",
            pk=pk,
        )

    except DatabaseError:
        messages.error(
            request,
            (
                "La conversion a échoué. "
                "La vente et le stock n’ont "
                "pas été modifiés."
            ),
        )

        return redirect(
            "proforma_detail",
            pk=pk,
        )

    messages.success(
        request,
        (
            f"Proforma convertie en "
            f"vente {sale.sale_number}. "
            "Le stock a été mis à jour."
        ),
    )

    return redirect(
        "proforma_detail",
        pk=pk,
    )