import csv
from datetime import timedelta
from decimal import Decimal

from django import forms
from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.db.utils import OperationalError, ProgrammingError
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from accounts.decorators import admin_required
from purchases.models import Purchase, PurchasePayment, Supplier



ZERO = Decimal("0.00")


class ReportPeriodForm(forms.Form):
    PERIOD_CHOICES = [
        ("today", "Aujourd’hui"),
        ("yesterday", "Hier"),
        ("week", "Cette semaine"),
        ("month", "Ce mois"),
        ("year", "Cette année"),
        ("custom", "Période personnalisée"),
    ]

    period = forms.ChoiceField(
        label="Période",
        choices=PERIOD_CHOICES,
        required=False,
        initial="month",
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )

    start_date = forms.DateField(
        label="Date de début",
        required=False,
        widget=forms.DateInput(
            attrs={
                "class": "form-control",
                "type": "date",
            }
        ),
    )

    end_date = forms.DateField(
        label="Date de fin",
        required=False,
        widget=forms.DateInput(
            attrs={
                "class": "form-control",
                "type": "date",
            }
        ),
    )

    def clean(self):
        cleaned_data = super().clean()

        period = cleaned_data.get("period") or "month"
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if period == "custom":
            if not start_date:
                self.add_error(
                    "start_date",
                    "Indiquez la date de début.",
                )

            if not end_date:
                self.add_error(
                    "end_date",
                    "Indiquez la date de fin.",
                )

        if (
            start_date
            and end_date
            and start_date > end_date
        ):
            self.add_error(
                "end_date",
                (
                    "La date de fin doit être égale "
                    "ou postérieure à la date de début."
                ),
            )

        return cleaned_data


def resolve_period(request):
    """
    Calcule la période des rapports achats/fournisseurs.

    Cette fonction est locale à purchase_views.py afin de ne
    plus dépendre d'une fonction absente de reports/views.py.
    """
    today = timezone.localdate()

    if request.GET:
        form = ReportPeriodForm(request.GET)
    else:
        form = ReportPeriodForm(
            initial={
                "period": "month",
            }
        )

    period = "month"
    start_date = today.replace(day=1)
    end_date = today
    period_label = "Ce mois"

    if form.is_valid():
        period = (
            form.cleaned_data.get("period")
            or "month"
        )

        if period == "today":
            start_date = today
            end_date = today
            period_label = "Aujourd’hui"

        elif period == "yesterday":
            yesterday = today - timedelta(days=1)
            start_date = yesterday
            end_date = yesterday
            period_label = "Hier"

        elif period == "week":
            start_date = today - timedelta(
                days=today.weekday()
            )
            end_date = today
            period_label = "Cette semaine"

        elif period == "year":
            start_date = today.replace(
                month=1,
                day=1,
            )
            end_date = today
            period_label = "Cette année"

        elif period == "custom":
            start_date = (
                form.cleaned_data.get("start_date")
                or today
            )
            end_date = (
                form.cleaned_data.get("end_date")
                or start_date
            )
            period_label = (
                f"Du {start_date.strftime('%d/%m/%Y')} "
                f"au {end_date.strftime('%d/%m/%Y')}"
            )

        else:
            period = "month"
            start_date = today.replace(day=1)
            end_date = today
            period_label = "Ce mois"

    return {
        "form": form,
        "period": period,
        "period_label": period_label,
        "start_date": start_date,
        "end_date": end_date,
    }


def get_company_data():
    """
    Retourne les informations de la société pour les
    rapports imprimables.

    Le module reste fonctionnel même lorsque l'application
    configuration n'est pas encore installée ou migrée.
    """
    try:
        from configuration.models import CompanySettings

        company = CompanySettings.get_solo()

        tax_parts = []

        if company.rccm:
            tax_parts.append(f"RCCM : {company.rccm}")

        if company.nif:
            tax_parts.append(f"NIF : {company.nif}")

        logo_url = (
            company.logo.url
            if company.logo
            else ""
        )

        invoice_header_url = (
            company.invoice_header.url
            if company.invoice_header
            else ""
        )

        return {
            "name": company.company_name,
            "company_name": company.company_name,
            "legal_name": company.legal_name,
            "activity": company.activity,
            "slogan": company.slogan,
            "address": company.address,
            "phone": company.phone,
            "phone_secondary": company.phone_secondary,
            "email": company.email,
            "website": company.website,
            "rccm": company.rccm,
            "nif": company.nif,
            "tax_number": " • ".join(tax_parts),
            "bank_details": company.bank_details,
            "logo_url": logo_url,
            "invoice_header_url": invoice_header_url,
            "invoice_footer_text": company.invoice_footer_text,
            "invoice_terms": company.invoice_terms,
            "currency_label": company.currency_label,
        }

    except (
        ImportError,
        LookupError,
        AttributeError,
        OperationalError,
        ProgrammingError,
    ):
        return {
            "name": getattr(
                settings,
                "COMPANY_NAME",
                "MSF SARL",
            ),
            "company_name": getattr(
                settings,
                "COMPANY_NAME",
                "MSF SARL",
            ),
            "legal_name": "",
            "activity": getattr(
                settings,
                "COMPANY_ACTIVITY",
                (
                    "Quincaillerie • Électricité • "
                    "Plomberie • Sanitaire"
                ),
            ),
            "slogan": "",
            "address": getattr(
                settings,
                "COMPANY_ADDRESS",
                "Bamako, Mali",
            ),
            "phone": getattr(
                settings,
                "COMPANY_PHONE",
                "",
            ),
            "phone_secondary": "",
            "email": getattr(
                settings,
                "COMPANY_EMAIL",
                "",
            ),
            "website": "",
            "rccm": "",
            "nif": "",
            "tax_number": getattr(
                settings,
                "COMPANY_TAX_NUMBER",
                "",
            ),
            "bank_details": "",
            "logo_url": "",
            "invoice_header_url": "",
            "invoice_footer_text": "Merci pour votre confiance.",
            "invoice_terms": "",
            "currency_label": "F CFA",
        }


def decimal_sum(queryset, field_name):
    result = queryset.aggregate(total=Sum(field_name))["total"]
    return result or ZERO


def build_purchase_report_data(request):
    period_data = resolve_period(request)
    start_date = period_data["start_date"]
    end_date = period_data["end_date"]

    query = request.GET.get("q", "").strip()
    supplier_id = request.GET.get("supplier", "").strip()
    status = request.GET.get("status", "").strip()

    purchases = (
        Purchase.objects
        .select_related("supplier", "created_by")
        .filter(
            purchase_date__date__gte=start_date,
            purchase_date__date__lte=end_date,
        )
        .order_by("-purchase_date", "-created_at")
    )

    if query:
        purchases = purchases.filter(
            Q(purchase_number__icontains=query)
            | Q(supplier_reference__icontains=query)
            | Q(supplier__name__icontains=query)
            | Q(supplier__phone__icontains=query)
            | Q(notes__icontains=query)
        )

    if supplier_id.isdigit():
        purchases = purchases.filter(supplier_id=supplier_id)
    else:
        supplier_id = ""

    valid_statuses = {
        value for value, label in Purchase.PaymentStatus.choices
    }

    if status == Purchase.PaymentStatus.CANCELLED:
        purchases = purchases.filter(is_cancelled=True)
    else:
        purchases = purchases.filter(is_cancelled=False)

        if status in valid_statuses:
            purchases = purchases.filter(payment_status=status)
        else:
            status = ""

    supplier_payments = (
        PurchasePayment.objects
        .select_related("purchase", "supplier", "created_by")
        .filter(
            payment_date__date__gte=start_date,
            payment_date__date__lte=end_date,
            purchase__is_cancelled=False,
        )
    )

    if supplier_id:
        supplier_payments = supplier_payments.filter(
            supplier_id=supplier_id
        )

    total_purchase = decimal_sum(purchases, "total")
    total_paid_on_purchases = decimal_sum(
        purchases,
        "amount_paid",
    )
    total_remaining = decimal_sum(
        purchases,
        "remaining_amount",
    )
    payments_made = decimal_sum(
        supplier_payments,
        "amount",
    )

    purchase_count = purchases.count()
    paid_count = purchases.filter(
        payment_status=Purchase.PaymentStatus.PAID,
        is_cancelled=False,
    ).count()
    partial_count = purchases.filter(
        payment_status=Purchase.PaymentStatus.PARTIAL,
        is_cancelled=False,
    ).count()
    credit_count = purchases.filter(
        payment_status=Purchase.PaymentStatus.CREDIT,
        is_cancelled=False,
    ).count()
    cancelled_count = purchases.filter(
        is_cancelled=True,
    ).count()

    top_suppliers = (
        purchases.filter(is_cancelled=False)
        .values(
            "supplier__id",
            "supplier__name",
            "supplier__phone",
        )
        .annotate(
            purchase_count=Count("id"),
            purchase_total=Sum("total"),
            paid_total=Sum("amount_paid"),
            remaining_total=Sum("remaining_amount"),
        )
        .order_by("-purchase_total")[:10]
    )

    return {
        "period_data": period_data,
        "query": query,
        "supplier_id": supplier_id,
        "status": status,
        "purchases": purchases,
        "supplier_payments": supplier_payments,
        "summary": {
            "purchase_count": purchase_count,
            "total_purchase": total_purchase,
            "total_paid_on_purchases": total_paid_on_purchases,
            "total_remaining": total_remaining,
            "payments_made": payments_made,
            "paid_count": paid_count,
            "partial_count": partial_count,
            "credit_count": credit_count,
            "cancelled_count": cancelled_count,
        },
        "top_suppliers": top_suppliers,
    }


@admin_required
def purchase_report(request):
    data = build_purchase_report_data(request)
    period_data = data["period_data"]
    purchases = data["purchases"]

    if request.GET.get("export") == "csv":
        response = HttpResponse(
            content_type="text/csv; charset=utf-8"
        )
        filename = (
            "rapport_achats_"
            f"{period_data['start_date'].isoformat()}_"
            f"{period_data['end_date'].isoformat()}.csv"
        )
        response["Content-Disposition"] = (
            f'attachment; filename="{filename}"'
        )
        response.write("\ufeff")

        writer = csv.writer(response, delimiter=";")
        writer.writerow(
            [
                "Date",
                "N° achat",
                "Fournisseur",
                "Téléphone",
                "Référence fournisseur",
                "Total",
                "Payé",
                "Reste",
                "Statut",
                "Mode de paiement",
                "Créé par",
            ]
        )

        for purchase in purchases:
            writer.writerow(
                [
                    purchase.purchase_date.strftime(
                        "%d/%m/%Y %H:%M"
                    ),
                    purchase.purchase_number,
                    purchase.supplier.name,
                    purchase.supplier.phone or "",
                    purchase.supplier_reference or "",
                    purchase.total,
                    purchase.amount_paid,
                    purchase.remaining_amount,
                    (
                        "Annulé"
                        if purchase.is_cancelled
                        else purchase.get_payment_status_display()
                    ),
                    purchase.get_payment_method_display(),
                    (
                        purchase.created_by.username
                        if purchase.created_by
                        else ""
                    ),
                ]
            )

        return response

    paginator = Paginator(purchases, 20)
    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    context = {
        "period_form": period_data["form"],
        "period": period_data["period"],
        "period_label": period_data["period_label"],
        "start_date": period_data["start_date"],
        "end_date": period_data["end_date"],
        "start_date_value": (
            period_data["start_date"].isoformat()
        ),
        "end_date_value": (
            period_data["end_date"].isoformat()
        ),
        "page_obj": page_obj,
        "suppliers": Supplier.objects.order_by("name"),
        "query": data["query"],
        "supplier_id": data["supplier_id"],
        "status": data["status"],
        "status_choices": Purchase.PaymentStatus.choices,
        "top_suppliers": data["top_suppliers"],
        **data["summary"],
    }

    return render(
        request,
        "reports/purchase_report.html",
        context,
    )


@admin_required
def purchase_report_print(request):
    data = build_purchase_report_data(request)
    period_data = data["period_data"]

    context = {
        "company": get_company_data(),
        "period_label": period_data["period_label"],
        "start_date": period_data["start_date"],
        "end_date": period_data["end_date"],
        "purchases": data["purchases"],
        "top_suppliers": data["top_suppliers"],
        **data["summary"],
    }

    return render(
        request,
        "reports/purchase_report_print.html",
        context,
    )


def build_supplier_report_data(request):
    period_data = resolve_period(request)
    start_date = period_data["start_date"]
    end_date = period_data["end_date"]

    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()

    suppliers = (
        Supplier.objects
        .annotate(
            period_purchase_count=Count(
                "purchases",
                filter=Q(
                    purchases__purchase_date__date__gte=start_date,
                    purchases__purchase_date__date__lte=end_date,
                    purchases__is_cancelled=False,
                ),
                distinct=True,
            ),
            period_purchase_total=Sum(
                "purchases__total",
                filter=Q(
                    purchases__purchase_date__date__gte=start_date,
                    purchases__purchase_date__date__lte=end_date,
                    purchases__is_cancelled=False,
                ),
            ),
            period_paid_total=Sum(
                "purchases__amount_paid",
                filter=Q(
                    purchases__purchase_date__date__gte=start_date,
                    purchases__purchase_date__date__lte=end_date,
                    purchases__is_cancelled=False,
                ),
            ),
            period_remaining_total=Sum(
                "purchases__remaining_amount",
                filter=Q(
                    purchases__purchase_date__date__gte=start_date,
                    purchases__purchase_date__date__lte=end_date,
                    purchases__is_cancelled=False,
                ),
            ),
        )
        .order_by("-balance", "name")
    )

    if query:
        suppliers = suppliers.filter(
            Q(name__icontains=query)
            | Q(phone__icontains=query)
            | Q(email__icontains=query)
            | Q(address__icontains=query)
        )

    if status == "active":
        suppliers = suppliers.filter(is_active=True)
    elif status == "inactive":
        suppliers = suppliers.filter(is_active=False)
    elif status == "debt":
        suppliers = suppliers.filter(balance__gt=ZERO)
    elif status == "clear":
        suppliers = suppliers.filter(balance__lte=ZERO)
    else:
        status = ""

    supplier_count = suppliers.count()
    active_count = suppliers.filter(
        is_active=True
    ).count()
    debt_supplier_count = suppliers.filter(
        balance__gt=ZERO
    ).count()
    total_current_debt = decimal_sum(
        suppliers,
        "balance",
    )

    supplier_ids = list(
        suppliers.values_list("pk", flat=True)
    )

    period_purchases = Purchase.objects.filter(
        supplier_id__in=supplier_ids,
        purchase_date__date__gte=start_date,
        purchase_date__date__lte=end_date,
        is_cancelled=False,
    )

    total_period_purchases = decimal_sum(
        period_purchases,
        "total",
    )
    total_period_paid = decimal_sum(
        period_purchases,
        "amount_paid",
    )
    total_period_remaining = decimal_sum(
        period_purchases,
        "remaining_amount",
    )

    return {
        "period_data": period_data,
        "suppliers": suppliers,
        "query": query,
        "status": status,
        "summary": {
            "supplier_count": supplier_count,
            "active_count": active_count,
            "debt_supplier_count": debt_supplier_count,
            "total_current_debt": total_current_debt,
            "total_period_purchases": total_period_purchases,
            "total_period_paid": total_period_paid,
            "total_period_remaining": total_period_remaining,
        },
    }


@admin_required
def supplier_report(request):
    data = build_supplier_report_data(request)
    period_data = data["period_data"]
    suppliers = data["suppliers"]

    if request.GET.get("export") == "csv":
        response = HttpResponse(
            content_type="text/csv; charset=utf-8"
        )
        filename = (
            "rapport_fournisseurs_"
            f"{period_data['start_date'].isoformat()}_"
            f"{period_data['end_date'].isoformat()}.csv"
        )
        response["Content-Disposition"] = (
            f'attachment; filename="{filename}"'
        )
        response.write("\ufeff")

        writer = csv.writer(response, delimiter=";")
        writer.writerow(
            [
                "Fournisseur",
                "Téléphone",
                "E-mail",
                "Statut",
                "Nombre achats période",
                "Total achats période",
                "Payé période",
                "Reste période",
                "Dette actuelle",
            ]
        )

        for supplier in suppliers:
            writer.writerow(
                [
                    supplier.name,
                    supplier.phone or "",
                    supplier.email or "",
                    (
                        "Actif"
                        if supplier.is_active
                        else "Inactif"
                    ),
                    supplier.period_purchase_count or 0,
                    supplier.period_purchase_total or ZERO,
                    supplier.period_paid_total or ZERO,
                    supplier.period_remaining_total or ZERO,
                    supplier.balance,
                ]
            )

        return response

    paginator = Paginator(suppliers, 20)
    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    context = {
        "period_form": period_data["form"],
        "period": period_data["period"],
        "period_label": period_data["period_label"],
        "start_date": period_data["start_date"],
        "end_date": period_data["end_date"],
        "start_date_value": (
            period_data["start_date"].isoformat()
        ),
        "end_date_value": (
            period_data["end_date"].isoformat()
        ),
        "page_obj": page_obj,
        "query": data["query"],
        "status": data["status"],
        **data["summary"],
    }

    return render(
        request,
        "reports/supplier_report.html",
        context,
    )


@admin_required
def supplier_report_print(request):
    data = build_supplier_report_data(request)
    period_data = data["period_data"]

    context = {
        "company": get_company_data(),
        "period_label": period_data["period_label"],
        "start_date": period_data["start_date"],
        "end_date": period_data["end_date"],
        "suppliers": data["suppliers"],
        **data["summary"],
    }

    return render(
        request,
        "reports/supplier_report_print.html",
        context,
    )