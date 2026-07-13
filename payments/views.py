import logging
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import DatabaseError, transaction
from django.db.models import Q, Sum
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)

from accounts.decorators import (
    seller_or_admin_required,
)
from sales.models import Sale

from .forms import PaymentForm
from .models import Payment


logger = logging.getLogger(__name__)

ZERO = Decimal("0.00")


class PaymentOperationError(Exception):
    """
    Erreur fonctionnelle annulant complètement
    l'opération de paiement.
    """


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
    if hasattr(exception, "message_dict"):
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
        "Le paiement n'est pas valide.",
    )


@seller_or_admin_required
def payment_create(request, sale_pk):
    """
    Ajoute un paiement sécurisé à une vente.

    La vente est verrouillée avant la vérification finale
    afin d'empêcher deux paiements simultanés de dépasser
    le montant restant.
    """
    sale = get_object_or_404(
        Sale.objects.select_related(
            "client",
            "created_by",
        ),
        pk=sale_pk,
    )

    if sale.is_cancelled:
        messages.error(
            request,
            (
                "Cette vente est annulée. "
                "Aucun paiement ne peut être enregistré."
            ),
        )

        return redirect(
            "sale_detail",
            pk=sale.pk,
        )

    if sale.remaining_amount <= ZERO:
        messages.info(
            request,
            "Cette vente est déjà entièrement payée.",
        )

        return redirect(
            "sale_detail",
            pk=sale.pk,
        )

    if request.method == "POST":
        form = PaymentForm(
            request.POST,
            sale=sale,
        )

        if form.is_valid():
            try:
                with transaction.atomic():
                    locked_sale = (
                        Sale.objects
                        .select_for_update()
                        .get(pk=sale.pk)
                    )

                    if locked_sale.is_cancelled:
                        raise PaymentOperationError(
                            (
                                "Cette vente vient d'être annulée. "
                                "Le paiement n'a pas été enregistré."
                            )
                        )

                    total_already_paid = (
                        Payment.objects
                        .filter(
                            sale_id=locked_sale.pk
                        )
                        .aggregate(
                            total=Sum("amount")
                        )["total"]
                        or ZERO
                    )

                    current_remaining = (
                        locked_sale.total
                        - total_already_paid
                    )

                    if current_remaining < ZERO:
                        current_remaining = ZERO

                    if current_remaining <= ZERO:
                        raise PaymentOperationError(
                            (
                                "Cette vente est déjà "
                                "entièrement payée."
                            )
                        )

                    payment_amount = (
                        form.cleaned_data["amount"]
                    )

                    if (
                        payment_amount
                        > current_remaining
                    ):
                        raise PaymentOperationError(
                            (
                                "Le paiement dépasse le "
                                "reste actuel à payer. "
                                "Maximum autorisé : "
                                f"{format_fcfa(current_remaining)}."
                            )
                        )

                    payment = form.save(
                        commit=False
                    )

                    payment.sale = locked_sale
                    payment.client = (
                        locked_sale.client
                    )

                    payment.created_by = (
                        request.user
                    )

                    # Payment.save() effectue également
                    # la validation du modèle et recalcule
                    # les montants de la vente.
                    payment.save()

            except PaymentOperationError as exception:
                form.add_error(
                    "amount",
                    str(exception),
                )

            except ValidationError as exception:
                add_validation_errors_to_form(
                    form,
                    exception,
                )

            except DatabaseError as exception:
                logger.exception(
                    "Erreur PostgreSQL pendant "
                    "l'enregistrement du paiement "
                    "de la vente %s.",
                    sale.pk,
                )

                form.add_error(
                    None,
                    (
                        "Le paiement n'a pas pu être "
                        "enregistré. Aucune donnée "
                        "financière n'a été modifiée. "
                        "Consultez le terminal pour "
                        "le détail technique."
                    ),
                )

            else:
                messages.success(
                    request,
                    (
                        f"Paiement de "
                        f"{format_fcfa(payment.amount)} "
                        "enregistré avec succès."
                    ),
                )

                return redirect(
                    "sale_detail",
                    pk=sale.pk,
                )

        else:
            messages.error(
                request,
                "Corrigez les erreurs du formulaire.",
            )

    else:
        form = PaymentForm(
            sale=sale,
        )

    context = {
        "sale": sale,
        "form": form,
    }

    return render(
        request,
        "payments/payment_form.html",
        context,
    )


@seller_or_admin_required
def payment_list(request):
    """
    Historique complet des paiements.
    Les paiements des ventes annulées restent visibles.
    """
    query = request.GET.get(
        "q",
        "",
    ).strip()

    payment_method = request.GET.get(
        "payment_method",
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

    payments = (
        Payment.objects
        .select_related(
            "sale",
            "client",
            "created_by",
        )
        .order_by("-payment_date")
    )

    if query:
        payments = payments.filter(
            Q(
                sale__sale_number__icontains=query
            )
            | Q(
                client__full_name__icontains=query
            )
            | Q(
                client__phone__icontains=query
            )
            | Q(notes__icontains=query)
        )

    valid_payment_methods = {
        value
        for value, label
        in Payment.PaymentMethod.choices
    }

    if payment_method in valid_payment_methods:
        payments = payments.filter(
            payment_method=payment_method
        )
    else:
        payment_method = ""

    if start_date:
        payments = payments.filter(
            payment_date__date__gte=start_date
        )

    if end_date:
        payments = payments.filter(
            payment_date__date__lte=end_date
        )

    totals = payments.aggregate(
        total_amount=Sum("amount"),
    )

    paginator = Paginator(
        payments,
        20,
    )

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    context = {
        "page_obj": page_obj,
        "query": query,
        "payment_method": payment_method,
        "start_date": start_date,
        "end_date": end_date,
        "payment_methods": (
            Payment.PaymentMethod.choices
        ),
        "payment_count": payments.count(),
        "total_amount": (
            totals["total_amount"]
            or ZERO
        ),
    }

    return render(
        request,
        "payments/payment_list.html",
        context,
    )


@seller_or_admin_required
def credit_list(request):
    """
    Liste des ventes ayant encore un reste à payer.
    """
    query = request.GET.get(
        "q",
        "",
    ).strip()

    sales = (
        Sale.objects
        .select_related(
            "client",
            "created_by",
        )
        .filter(
            is_cancelled=False,
            remaining_amount__gt=ZERO,
        )
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

    totals = sales.aggregate(
        total_credit=Sum(
            "remaining_amount"
        ),
    )

    paginator = Paginator(
        sales,
        20,
    )

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    context = {
        "page_obj": page_obj,
        "query": query,
        "credit_count": sales.count(),
        "total_credit": (
            totals["total_credit"]
            or ZERO
        ),
    }

    return render(
        request,
        "payments/credit_list.html",
        context,
    )