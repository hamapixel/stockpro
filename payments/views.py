from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import seller_or_admin_required
from customers.models import Client
from sales.models import Sale

from .forms import PaymentForm
from .models import Payment


def decimal_sum(queryset, field_name):
    result = queryset.aggregate(
        total=Sum(field_name)
    )["total"]

    return result or Decimal("0.00")


@seller_or_admin_required
def credit_list(request):
    query = request.GET.get("q", "").strip()

    credits = Sale.objects.select_related(
        "client",
        "created_by",
    ).filter(
        is_cancelled=False,
        remaining_amount__gt=0,
    ).order_by("-sale_date")

    if query:
        credits = credits.filter(
            Q(sale_number__icontains=query)
            | Q(client__full_name__icontains=query)
            | Q(client__phone__icontains=query)
        )

    total_credit = decimal_sum(
        credits,
        "remaining_amount",
    )

    total_sales_credit = credits.count()

    credit_clients = Client.objects.filter(
        balance__gt=0,
    ).count()

    paginator = Paginator(credits, 15)
    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    context = {
        "page_obj": page_obj,
        "query": query,
        "total_credit": total_credit,
        "total_sales_credit": total_sales_credit,
        "credit_clients": credit_clients,
    }

    return render(
        request,
        "payments/credit_list.html",
        context,
    )


@seller_or_admin_required
def payment_list(request):
    query = request.GET.get("q", "").strip()
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

    payments = Payment.objects.select_related(
        "sale",
        "client",
        "created_by",
    ).order_by("-payment_date")

    if query:
        payments = payments.filter(
            Q(sale__sale_number__icontains=query)
            | Q(client__full_name__icontains=query)
            | Q(client__phone__icontains=query)
            | Q(notes__icontains=query)
        )

    if payment_method in Payment.PaymentMethod.values:
        payments = payments.filter(
            payment_method=payment_method,
        )

    if start_date:
        payments = payments.filter(
            payment_date__date__gte=start_date,
        )

    if end_date:
        payments = payments.filter(
            payment_date__date__lte=end_date,
        )

    total_paid = decimal_sum(
        payments,
        "amount",
    )

    payment_count = payments.count()

    paginator = Paginator(payments, 20)
    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    context = {
        "page_obj": page_obj,
        "query": query,
        "payment_method": payment_method,
        "start_date": start_date,
        "end_date": end_date,
        "payment_method_choices": Payment.PaymentMethod.choices,
        "total_paid": total_paid,
        "payment_count": payment_count,
    }

    return render(
        request,
        "payments/payment_list.html",
        context,
    )


@seller_or_admin_required
def payment_create(request, sale_pk):
    sale = get_object_or_404(
        Sale.objects.select_related(
            "client",
            "created_by",
        ),
        pk=sale_pk,
        is_cancelled=False,
    )

    if sale.remaining_amount <= Decimal("0.00"):
        messages.info(
            request,
            "Cette vente est déjà totalement payée.",
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
            with transaction.atomic():
                locked_sale = Sale.objects.select_for_update().get(
                    pk=sale.pk,
                    is_cancelled=False,
                )

                if locked_sale.remaining_amount <= Decimal("0.00"):
                    messages.info(
                        request,
                        "Cette vente vient d’être totalement payée.",
                    )

                    return redirect(
                        "sale_detail",
                        pk=locked_sale.pk,
                    )

                amount = form.cleaned_data["amount"]

                if amount > locked_sale.remaining_amount:
                    form.add_error(
                        "amount",
                        (
                            "Le montant ne peut pas dépasser le reste "
                            f"à payer : {locked_sale.remaining_amount} F CFA."
                        ),
                    )
                else:
                    payment = form.save(commit=False)
                    payment.sale = locked_sale
                    payment.client = locked_sale.client
                    payment.created_by = request.user
                    payment.save()

                    messages.success(
                        request,
                        "Paiement enregistré avec succès.",
                    )

                    return redirect(
                        "sale_detail",
                        pk=locked_sale.pk,
                    )
    else:
        form = PaymentForm(
            sale=sale,
            initial={
                "amount": sale.remaining_amount,
            },
        )

    context = {
        "form": form,
        "sale": sale,
    }

    return render(
        request,
        "payments/payment_form.html",
        context,
    )