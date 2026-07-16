import logging
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import DatabaseError, transaction
from django.db.models import Count, Q, Sum
from django.http import Http404
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.utils.dateparse import parse_date
from django.views.decorators.http import (
    require_POST,
)

from accounts.decorators import admin_required

from .forms import (
    PurchaseForm,
    PurchaseItemFormSet,
    PurchasePaymentForm,
    SupplierForm,
)
from .models import (
    Purchase,
    PurchasePayment,
    Supplier,
)
from .services import (
    PurchaseOperationError,
    create_purchase_with_stock,
)


logger = logging.getLogger(__name__)

ZERO = Decimal("0.00")


def format_fcfa(value):
    value = value or ZERO

    return (
        f"{value:,.0f}"
        .replace(",", " ")
        + " F CFA"
    )


def add_validation_errors_to_form(
    form,
    exception,
):
    """
    Transfère une ValidationError Django
    vers le formulaire HTML.
    """
    if hasattr(
        exception,
        "message_dict",
    ):
        for field_name, error_messages in (
            exception.message_dict.items()
        ):
            target_field = (
                field_name
                if field_name in form.fields
                else None
            )

            for error_message in error_messages:
                form.add_error(
                    target_field,
                    error_message,
                )

        return

    error_messages = getattr(
        exception,
        "messages",
        None,
    )

    if error_messages:
        for error_message in error_messages:
            form.add_error(
                None,
                error_message,
            )

        return

    form.add_error(
        None,
        "L'opération n'est pas valide.",
    )


def get_valid_date(value):
    """
    Retourne une date valide ou None.
    """
    if not value:
        return None

    return parse_date(value)


# =========================================================
# FOURNISSEURS
# =========================================================


@admin_required
def supplier_list(request):
    """
    Liste et recherche des fournisseurs.
    """
    query = request.GET.get(
        "q",
        "",
    ).strip()

    status = request.GET.get(
        "status",
        "",
    ).strip()

    suppliers = (
        Supplier.objects
        .annotate(
            purchase_count=Count(
                "purchases",
                filter=Q(
                    purchases__is_cancelled=False
                ),
                distinct=True,
            ),
            purchase_total=Sum(
                "purchases__total",
                filter=Q(
                    purchases__is_cancelled=False
                ),
            ),
        )
        .order_by("name")
    )

    if query:
        suppliers = suppliers.filter(
            Q(name__icontains=query)
            | Q(phone__icontains=query)
            | Q(email__icontains=query)
            | Q(address__icontains=query)
        )

    if status == "active":
        suppliers = suppliers.filter(
            is_active=True
        )

    elif status == "inactive":
        suppliers = suppliers.filter(
            is_active=False
        )

    else:
        status = ""

    totals = suppliers.aggregate(
        total_balance=Sum("balance"),
    )

    supplier_count = suppliers.count()

    paginator = Paginator(
        suppliers,
        20,
    )

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    context = {
        "page_obj": page_obj,
        "query": query,
        "status": status,
        "supplier_count": supplier_count,
        "total_balance": (
            totals["total_balance"]
            or ZERO
        ),
    }

    return render(
        request,
        "purchases/supplier_list.html",
        context,
    )


@admin_required
def supplier_create(request):
    """
    Création d'un fournisseur.
    """
    if request.method == "POST":
        form = SupplierForm(
            request.POST
        )

        if form.is_valid():
            supplier = form.save()

            messages.success(
                request,
                (
                    f"Le fournisseur "
                    f"« {supplier.name} » "
                    "a été créé avec succès."
                ),
            )

            return redirect(
                "supplier_detail",
                pk=supplier.pk,
            )

        messages.error(
            request,
            "Corrigez les erreurs du formulaire.",
        )

    else:
        form = SupplierForm()

    context = {
        "form": form,
        "page_title": (
            "Nouveau fournisseur"
        ),
        "submit_label": (
            "Enregistrer le fournisseur"
        ),
    }

    return render(
        request,
        "purchases/supplier_form.html",
        context,
    )


@admin_required
def supplier_update(
    request,
    pk,
):
    """
    Modification d'un fournisseur.
    """
    supplier = get_object_or_404(
        Supplier,
        pk=pk,
    )

    if request.method == "POST":
        form = SupplierForm(
            request.POST,
            instance=supplier,
        )

        if form.is_valid():
            supplier = form.save()

            messages.success(
                request,
                (
                    f"Le fournisseur "
                    f"« {supplier.name} » "
                    "a été modifié avec succès."
                ),
            )

            return redirect(
                "supplier_detail",
                pk=supplier.pk,
            )

        messages.error(
            request,
            "Corrigez les erreurs du formulaire.",
        )

    else:
        form = SupplierForm(
            instance=supplier,
        )

    context = {
        "form": form,
        "supplier": supplier,
        "page_title": (
            "Modifier le fournisseur"
        ),
        "submit_label": (
            "Enregistrer les modifications"
        ),
    }

    return render(
        request,
        "purchases/supplier_form.html",
        context,
    )


@admin_required
def supplier_detail(
    request,
    pk,
):
    """
    Détail financier d'un fournisseur.
    """
    supplier = get_object_or_404(
        Supplier,
        pk=pk,
    )

    purchases = (
        supplier.purchases
        .select_related(
            "created_by",
        )
        .order_by(
            "-purchase_date"
        )
    )

    valid_purchases = purchases.filter(
        is_cancelled=False
    )

    purchase_totals = (
        valid_purchases.aggregate(
            total_purchase=Sum("total"),
            total_paid=Sum(
                "amount_paid"
            ),
            total_remaining=Sum(
                "remaining_amount"
            ),
        )
    )

    payments = (
        supplier.payments
        .select_related(
            "purchase",
            "created_by",
        )
        .order_by(
            "-payment_date"
        )
    )

    context = {
        "supplier": supplier,
        "recent_purchases": (
            purchases[:10]
        ),
        "recent_payments": (
            payments[:10]
        ),
        "purchase_count": (
            valid_purchases.count()
        ),
        "total_purchase": (
            purchase_totals[
                "total_purchase"
            ]
            or ZERO
        ),
        "total_paid": (
            purchase_totals[
                "total_paid"
            ]
            or ZERO
        ),
        "total_remaining": (
            purchase_totals[
                "total_remaining"
            ]
            or ZERO
        ),
    }

    return render(
        request,
        "purchases/supplier_detail.html",
        context,
    )


@require_POST
@admin_required
def supplier_toggle_status(
    request,
    pk,
):
    """
    Active ou désactive un fournisseur.

    Le fournisseur n'est pas supprimé afin de
    conserver son historique financier.
    """
    supplier = get_object_or_404(
        Supplier,
        pk=pk,
    )

    supplier.is_active = (
        not supplier.is_active
    )

    supplier.save(
        update_fields=[
            "is_active",
            "updated_at",
        ]
    )

    if supplier.is_active:
        messages.success(
            request,
            (
                f"Le fournisseur "
                f"« {supplier.name} » "
                "a été activé."
            ),
        )

    else:
        messages.warning(
            request,
            (
                f"Le fournisseur "
                f"« {supplier.name} » "
                "a été désactivé."
            ),
        )

    return redirect(
        "supplier_detail",
        pk=supplier.pk,
    )


# =========================================================
# ACHATS ET APPROVISIONNEMENTS
# =========================================================


@admin_required
def purchase_list(request):
    """
    Historique complet des achats.
    """
    query = request.GET.get(
        "q",
        "",
    ).strip()

    supplier_id = request.GET.get(
        "supplier",
        "",
    ).strip()

    payment_status = request.GET.get(
        "status",
        "",
    ).strip()

    start_date_value = request.GET.get(
        "start_date",
        "",
    ).strip()

    end_date_value = request.GET.get(
        "end_date",
        "",
    ).strip()

    purchases = (
        Purchase.objects
        .select_related(
            "supplier",
            "created_by",
        )
        .order_by(
            "-purchase_date"
        )
    )

    if query:
        purchases = purchases.filter(
            Q(
                purchase_number__icontains=query
            )
            | Q(
                supplier_reference__icontains=query
            )
            | Q(
                supplier__name__icontains=query
            )
            | Q(
                supplier__phone__icontains=query
            )
            | Q(
                notes__icontains=query
            )
        )

    if supplier_id.isdigit():
        purchases = purchases.filter(
            supplier_id=supplier_id
        )

    else:
        supplier_id = ""

    valid_statuses = {
        value
        for value, label
        in Purchase.PaymentStatus.choices
    }

    if payment_status in valid_statuses:
        purchases = purchases.filter(
            payment_status=payment_status
        )

    else:
        payment_status = ""

    start_date = get_valid_date(
        start_date_value
    )

    end_date = get_valid_date(
        end_date_value
    )

    if start_date:
        purchases = purchases.filter(
            purchase_date__date__gte=(
                start_date
            )
        )

    elif start_date_value:
        messages.warning(
            request,
            "La date de début est invalide.",
        )

        start_date_value = ""

    if end_date:
        purchases = purchases.filter(
            purchase_date__date__lte=(
                end_date
            )
        )

    elif end_date_value:
        messages.warning(
            request,
            "La date de fin est invalide.",
        )

        end_date_value = ""

    totals = purchases.aggregate(
        total_purchase=Sum("total"),
        total_paid=Sum("amount_paid"),
        total_remaining=Sum(
            "remaining_amount"
        ),
    )

    purchase_count = purchases.count()

    paginator = Paginator(
        purchases,
        20,
    )

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    suppliers = (
        Supplier.objects
        .order_by("name")
    )

    context = {
        "page_obj": page_obj,
        "query": query,
        "supplier_id": supplier_id,
        "payment_status": payment_status,
        "start_date": start_date_value,
        "end_date": end_date_value,
        "suppliers": suppliers,
        "status_choices": (
            Purchase.PaymentStatus.choices
        ),
        "purchase_count": purchase_count,
        "total_purchase": (
            totals["total_purchase"]
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
        "purchases/purchase_list.html",
        context,
    )


@admin_required
def purchase_create(request):
    """
    Création sécurisée d'un approvisionnement
    comportant plusieurs produits.
    """
    draft_purchase = Purchase()

    if request.method == "POST":
        form = PurchaseForm(
            request.POST,
            instance=draft_purchase,
        )

        item_formset = (
            PurchaseItemFormSet(
                request.POST,
                instance=draft_purchase,
                prefix="items",
            )
        )

        form_is_valid = form.is_valid()

        formset_is_valid = (
            item_formset.is_valid()
        )

        if (
            form_is_valid
            and formset_is_valid
        ):
            try:
                purchase = (
                    create_purchase_with_stock(
                        purchase_form=form,
                        item_formset=(
                            item_formset
                        ),
                        user=request.user,
                    )
                )

            except PurchaseOperationError as exception:
                add_validation_errors_to_form(
                    form,
                    exception,
                )

            except ValidationError as exception:
                add_validation_errors_to_form(
                    form,
                    exception,
                )

            except DatabaseError:
                logger.exception(
                    "Erreur PostgreSQL pendant "
                    "la création d'un achat."
                )

                form.add_error(
                    None,
                    (
                        "L'approvisionnement n'a "
                        "pas pu être enregistré. "
                        "Aucun stock ni montant "
                        "financier n'a été modifié."
                    ),
                )

            else:
                messages.success(
                    request,
                    (
                        "Approvisionnement "
                        f"{purchase.purchase_number} "
                        "enregistré avec succès. "
                        f"Total : "
                        f"{format_fcfa(purchase.total)}."
                    ),
                )

                return redirect(
                    "purchase_detail",
                    pk=purchase.pk,
                )

        else:
            messages.error(
                request,
                (
                    "Corrigez les erreurs de "
                    "l'approvisionnement."
                ),
            )

    else:
        form = PurchaseForm(
            instance=draft_purchase,
        )

        item_formset = (
            PurchaseItemFormSet(
                instance=draft_purchase,
                prefix="items",
            )
        )

    context = {
        "form": form,
        "item_formset": item_formset,
    }

    return render(
        request,
        "purchases/purchase_form.html",
        context,
    )


@admin_required
def purchase_detail(
    request,
    pk,
):
    """
    Affiche un achat, ses produits
    et ses paiements.
    """
    purchase = get_object_or_404(
        Purchase.objects
        .select_related(
            "supplier",
            "created_by",
        )
        .prefetch_related(
            "items__product",
            "items__product__category",
            "items__product__unit",
            "payments__created_by",
        ),
        pk=pk,
    )

    context = {
        "purchase": purchase,
        "purchase_items": (
            purchase.items.all()
        ),
        "payments": (
            purchase.payments.all()
        ),
    }

    return render(
        request,
        "purchases/purchase_detail.html",
        context,
    )


@require_POST
@admin_required
def purchase_cancel(
    request,
    pk,
):
    """
    Annule un achat et retire du stock
    les quantités ajoutées.

    L'annulation est refusée si le stock
    actuel est insuffisant.
    """
    purchase = get_object_or_404(
        Purchase.objects.select_related(
            "supplier",
        ),
        pk=pk,
    )

    reason = request.POST.get(
        "reason",
        "",
    ).strip()

    try:
        cancelled = (
            purchase.cancel_purchase(
                cancelled_by=request.user,
                reason=reason,
            )
        )

    except ValidationError as exception:
        error_messages = getattr(
            exception,
            "messages",
            [
                (
                    "Impossible d'annuler "
                    "cet achat."
                )
            ],
        )

        for error_message in error_messages:
            messages.error(
                request,
                error_message,
            )

    except DatabaseError:
        logger.exception(
            "Erreur PostgreSQL pendant "
            "l'annulation de l'achat %s.",
            purchase.pk,
        )

        messages.error(
            request,
            (
                "L'achat n'a pas pu être "
                "annulé. Aucun stock ni montant "
                "financier n'a été modifié."
            ),
        )

    else:
        if cancelled:
            messages.success(
                request,
                (
                    f"L'achat "
                    f"{purchase.purchase_number} "
                    "a été annulé. Les quantités "
                    "ont été retirées du stock."
                ),
            )

        else:
            messages.info(
                request,
                "Cet achat était déjà annulé.",
            )

    return redirect(
        "purchase_detail",
        pk=purchase.pk,
    )


# =========================================================
# PAIEMENTS FOURNISSEURS
# =========================================================


@admin_required
def purchase_payment_create(
    request,
    purchase_pk,
):
    """
    Ajoute un paiement à un achat fournisseur.
    """
    purchase = get_object_or_404(
        Purchase.objects.select_related(
            "supplier",
            "created_by",
        ),
        pk=purchase_pk,
    )

    if purchase.is_cancelled:
        messages.error(
            request,
            (
                "Cet achat est annulé. "
                "Aucun paiement ne peut "
                "être enregistré."
            ),
        )

        return redirect(
            "purchase_detail",
            pk=purchase.pk,
        )

    if (
        purchase.remaining_amount
        <= ZERO
    ):
        messages.info(
            request,
            (
                "Cet achat est déjà "
                "entièrement payé."
            ),
        )

        return redirect(
            "purchase_detail",
            pk=purchase.pk,
        )

    if request.method == "POST":
        form = PurchasePaymentForm(
            request.POST,
            purchase=purchase,
        )

        if form.is_valid():
            try:
                with transaction.atomic():
                    locked_purchase = (
                        Purchase.objects
                        .select_for_update()
                        .get(pk=purchase.pk)
                    )

                    if (
                        locked_purchase
                        .is_cancelled
                    ):
                        raise ValidationError(
                            (
                                "Cet achat vient "
                                "d'être annulé."
                            )
                        )

                    current_paid = (
                        PurchasePayment.objects
                        .filter(
                            purchase_id=(
                                locked_purchase.pk
                            )
                        )
                        .aggregate(
                            total=Sum("amount")
                        )["total"]
                        or ZERO
                    )

                    current_remaining = (
                        locked_purchase.total
                        - current_paid
                    )

                    if current_remaining < ZERO:
                        current_remaining = ZERO

                    payment_amount = (
                        form.cleaned_data[
                            "amount"
                        ]
                    )

                    if (
                        payment_amount
                        > current_remaining
                    ):
                        raise ValidationError(
                            {
                                "amount": (
                                    "Le paiement dépasse "
                                    "le reste actuel. "
                                    "Maximum autorisé : "
                                    f"{format_fcfa(current_remaining)}."
                                )
                            }
                        )

                    payment = form.save(
                        commit=False
                    )

                    payment.purchase = (
                        locked_purchase
                    )

                    payment.supplier = (
                        locked_purchase
                        .supplier
                    )

                    payment.created_by = (
                        request.user
                    )

                    payment.save()

            except ValidationError as exception:
                add_validation_errors_to_form(
                    form,
                    exception,
                )

            except DatabaseError:
                logger.exception(
                    "Erreur PostgreSQL pendant "
                    "le paiement de l'achat %s.",
                    purchase.pk,
                )

                form.add_error(
                    None,
                    (
                        "Le paiement n'a pas pu "
                        "être enregistré. Aucune "
                        "donnée financière n'a "
                        "été modifiée."
                    ),
                )

            else:
                messages.success(
                    request,
                    (
                        "Paiement fournisseur de "
                        f"{format_fcfa(payment.amount)} "
                        "enregistré avec succès."
                    ),
                )

                return redirect(
                    "purchase_detail",
                    pk=purchase.pk,
                )

        else:
            messages.error(
                request,
                "Corrigez les erreurs du formulaire.",
            )

    else:
        form = PurchasePaymentForm(
            purchase=purchase,
        )

    context = {
        "purchase": purchase,
        "supplier": purchase.supplier,
        "form": form,
    }

    return render(
        request,
        "purchases/purchase_payment_form.html",
        context,
    )


@admin_required
def purchase_payment_list(request):
    """
    Historique des paiements fournisseurs.
    """
    query = request.GET.get(
        "q",
        "",
    ).strip()

    supplier_id = request.GET.get(
        "supplier",
        "",
    ).strip()

    payment_method = request.GET.get(
        "payment_method",
        "",
    ).strip()

    start_date_value = request.GET.get(
        "start_date",
        "",
    ).strip()

    end_date_value = request.GET.get(
        "end_date",
        "",
    ).strip()

    payments = (
        PurchasePayment.objects
        .select_related(
            "purchase",
            "supplier",
            "created_by",
        )
        .order_by(
            "-payment_date"
        )
    )

    if query:
        payments = payments.filter(
            Q(
                purchase__purchase_number__icontains=query
            )
            | Q(
                supplier__name__icontains=query
            )
            | Q(
                supplier__phone__icontains=query
            )
            | Q(
                notes__icontains=query
            )
        )

    if supplier_id.isdigit():
        payments = payments.filter(
            supplier_id=supplier_id
        )

    else:
        supplier_id = ""

    valid_payment_methods = {
        value
        for value, label
        in PurchasePayment
        .PaymentMethod
        .choices
    }

    if (
        payment_method
        in valid_payment_methods
    ):
        payments = payments.filter(
            payment_method=payment_method
        )

    else:
        payment_method = ""

    start_date = get_valid_date(
        start_date_value
    )

    end_date = get_valid_date(
        end_date_value
    )

    if start_date:
        payments = payments.filter(
            payment_date__date__gte=(
                start_date
            )
        )

    elif start_date_value:
        messages.warning(
            request,
            "La date de début est invalide.",
        )

        start_date_value = ""

    if end_date:
        payments = payments.filter(
            payment_date__date__lte=(
                end_date
            )
        )

    elif end_date_value:
        messages.warning(
            request,
            "La date de fin est invalide.",
        )

        end_date_value = ""

    totals = payments.aggregate(
        total_amount=Sum("amount"),
    )

    payment_count = payments.count()

    paginator = Paginator(
        payments,
        20,
    )

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    suppliers = (
        Supplier.objects
        .order_by("name")
    )

    context = {
        "page_obj": page_obj,
        "query": query,
        "supplier_id": supplier_id,
        "payment_method": payment_method,
        "start_date": start_date_value,
        "end_date": end_date_value,
        "suppliers": suppliers,
        "payment_methods": (
            PurchasePayment
            .PaymentMethod
            .choices
        ),
        "payment_count": payment_count,
        "total_amount": (
            totals["total_amount"]
            or ZERO
        ),
    }

    return render(
        request,
        "purchases/purchase_payment_list.html",
        context,
    )