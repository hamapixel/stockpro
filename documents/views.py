from decimal import Decimal

from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, render

from accounts.decorators import seller_or_admin_required
from payments.models import Payment
from sales.models import Sale


def decimal_sum(queryset, field_name):
    result = queryset.aggregate(
        total=Sum(field_name)
    )["total"]

    return result or Decimal("0.00")


@seller_or_admin_required
def document_center(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    start_date = request.GET.get(
        "start_date",
        "",
    ).strip()
    end_date = request.GET.get(
        "end_date",
        "",
    ).strip()

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

    if status:
        sales = sales.filter(
            payment_status=status,
        )

    if start_date:
        sales = sales.filter(
            sale_date__date__gte=start_date,
        )

    if end_date:
        sales = sales.filter(
            sale_date__date__lte=end_date,
        )

    total_sales = decimal_sum(
        sales,
        "total",
    )

    total_paid = decimal_sum(
        sales,
        "amount_paid",
    )

    total_remaining = decimal_sum(
        sales,
        "remaining_amount",
    )

    document_count = sales.count()

    paginator = Paginator(sales, 15)
    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    context = {
        "page_obj": page_obj,
        "query": query,
        "status": status,
        "start_date": start_date,
        "end_date": end_date,

        "status_choices": Sale.PaymentStatus.choices,

        "document_count": document_count,
        "total_sales": total_sales,
        "total_paid": total_paid,
        "total_remaining": total_remaining,
    }

    return render(
        request,
        "documents/document_center.html",
        context,
    )


@seller_or_admin_required
def sale_invoice(request, sale_pk):
    sale = get_object_or_404(
        Sale.objects.select_related(
            "client",
            "created_by",
        ),
        pk=sale_pk,
        is_cancelled=False,
    )

    items = sale.items.select_related(
        "product",
        "product__unit",
        "product__category",
    ).all()

    payments = sale.payments.select_related(
        "created_by",
    ).order_by("payment_date")

    context = {
        "sale": sale,
        "items": items,
        "payments": payments,
        "document_title": "Facture",
    }

    return render(
        request,
        "documents/sale_invoice.html",
        context,
    )


@seller_or_admin_required
def sale_receipt(request, sale_pk):
    sale = get_object_or_404(
        Sale.objects.select_related(
            "client",
            "created_by",
        ),
        pk=sale_pk,
        is_cancelled=False,
    )

    items = sale.items.select_related(
        "product",
        "product__unit",
        "product__category",
    ).all()

    payments = sale.payments.select_related(
        "created_by",
    ).order_by("-payment_date")

    latest_payment = payments.first()

    context = {
        "sale": sale,
        "items": items,
        "payments": payments,
        "latest_payment": latest_payment,
        "document_title": "Reçu de vente",
    }

    return render(
        request,
        "documents/sale_receipt.html",
        context,
    )


@seller_or_admin_required
def payment_receipt(request, payment_pk):
    payment = get_object_or_404(
        Payment.objects.select_related(
            "sale",
            "sale__client",
            "sale__created_by",
            "client",
            "created_by",
        ),
        pk=payment_pk,
    )

    sale = payment.sale

    context = {
        "payment": payment,
        "sale": sale,
        "document_title": "Reçu de paiement",
    }

    return render(
        request,
        "documents/payment_receipt.html",
        context,
    )