import csv
from datetime import datetime, timedelta
from decimal import Decimal

from django import forms
from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import F, Q, Sum
from django.db.utils import OperationalError, ProgrammingError
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from accounts.decorators import admin_required
from catalog.models import Category, Product
from customers.models import Client
from expenses.models import Expense
from payments.models import Payment
from sales.models import Sale, SaleItem


def decimal_sum(queryset, field_name):
    result = queryset.aggregate(
        total=Sum(field_name)
    )["total"]

    return result or Decimal("0.00")


def parse_date(date_value, fallback):
    if not date_value:
        return fallback

    try:
        return datetime.strptime(
            date_value,
            "%Y-%m-%d",
        ).date()
    except (TypeError, ValueError):
        return fallback


def get_period_dates(request):
    today = timezone.localdate()

    default_start = today.replace(day=1)
    default_end = today

    start_date = parse_date(
        request.GET.get("start_date", "").strip(),
        default_start,
    )

    end_date = parse_date(
        request.GET.get("end_date", "").strip(),
        default_end,
    )

    if start_date > end_date:
        start_date, end_date = end_date, start_date

    return start_date, end_date


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
    Retourne la période utilisée par les rapports
    achats et fournisseurs.
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
            yesterday = today - timedelta(
                days=1
            )
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
    """
    try:
        from configuration.models import CompanySettings

        company = CompanySettings.get_solo()

        tax_parts = []

        if company.rccm:
            tax_parts.append(
                f"RCCM : {company.rccm}"
            )

        if company.nif:
            tax_parts.append(
                f"NIF : {company.nif}"
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
            "tax_number": " • ".join(
                tax_parts
            ),
            "bank_details": company.bank_details,
            "invoice_footer_text": (
                company.invoice_footer_text
            ),
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
            "invoice_footer_text": (
                "Merci pour votre confiance."
            ),
            "invoice_terms": "",
            "currency_label": "F CFA",
        }


def calculate_stock_values(products):
    purchase_value = Decimal("0.00")
    sale_value = Decimal("0.00")

    for product in products:
        purchase_value += (
            product.stock_quantity
            * product.purchase_price
        )

        sale_value += (
            product.stock_quantity
            * product.sale_price
        )

    margin_value = sale_value - purchase_value

    return (
        purchase_value,
        sale_value,
        margin_value,
    )


@admin_required
def report_dashboard(request):
    today = timezone.localdate()
    month_start = today.replace(day=1)
    year_start = today.replace(
        month=1,
        day=1,
    )

    today_sales = Sale.objects.filter(
        sale_date__date=today,
        is_cancelled=False,
    )

    month_sales = Sale.objects.filter(
        sale_date__date__gte=month_start,
        sale_date__date__lte=today,
        is_cancelled=False,
    )

    year_sales = Sale.objects.filter(
        sale_date__date__gte=year_start,
        sale_date__date__lte=today,
        is_cancelled=False,
    )

    today_expenses = Expense.objects.filter(
        expense_date__date=today,
    )

    month_expenses = Expense.objects.filter(
        expense_date__date__gte=month_start,
        expense_date__date__lte=today,
    )

    today_payments = Payment.objects.filter(
        payment_date__date=today,
    )

    products = Product.objects.filter(
        is_active=True,
    ).select_related(
        "unit",
        "category",
    )

    (
        purchase_value,
        sale_value,
        margin_value,
    ) = calculate_stock_values(products)

    low_stock_count = products.filter(
        stock_quantity__lte=F("alert_quantity")
    ).count()

    context = {
        "today_total": decimal_sum(
            today_sales,
            "total",
        ),
        "today_paid": decimal_sum(
            today_payments,
            "amount",
        ),
        "today_expenses": decimal_sum(
            today_expenses,
            "amount",
        ),
        "today_credit": decimal_sum(
            today_sales,
            "remaining_amount",
        ),

        "month_total": decimal_sum(
            month_sales,
            "total",
        ),
        "month_paid": decimal_sum(
            month_sales,
            "amount_paid",
        ),
        "month_expenses": decimal_sum(
            month_expenses,
            "amount",
        ),
        "month_credit": decimal_sum(
            month_sales,
            "remaining_amount",
        ),

        "year_total": decimal_sum(
            year_sales,
            "total",
        ),
        "year_paid": decimal_sum(
            year_sales,
            "amount_paid",
        ),
        "year_credit": decimal_sum(
            year_sales,
            "remaining_amount",
        ),

        "product_count": products.count(),
        "low_stock_count": low_stock_count,
        "client_count": Client.objects.count(),
        "credit_client_count": Client.objects.filter(
            balance__gt=0,
        ).count(),

        "stock_purchase_value": purchase_value,
        "stock_sale_value": sale_value,
        "stock_margin_value": margin_value,
    }

    return render(
        request,
        "reports/report_dashboard.html",
        context,
    )


@admin_required
def sales_report(request):
    start_date, end_date = get_period_dates(request)

    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()

    sales = Sale.objects.select_related(
        "client",
        "created_by",
    ).filter(
        sale_date__date__gte=start_date,
        sale_date__date__lte=end_date,
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

    if request.GET.get("export") == "csv":
        response = HttpResponse(
            content_type="text/csv; charset=utf-8"
        )

        filename = (
            f"rapport_ventes_"
            f"{start_date.isoformat()}_"
            f"{end_date.isoformat()}.csv"
        )

        response["Content-Disposition"] = (
            f'attachment; filename="{filename}"'
        )

        response.write("\ufeff")

        writer = csv.writer(
            response,
            delimiter=";",
        )

        writer.writerow([
            "Date",
            "N° Vente",
            "Client",
            "Téléphone",
            "Total",
            "Payé",
            "Reste",
            "Statut",
            "Mode paiement",
            "Vendeur",
        ])

        for sale in sales:
            local_sale_date = timezone.localtime(
                sale.sale_date
            )

            writer.writerow([
                local_sale_date.strftime(
                    "%d/%m/%Y %H:%M"
                ),
                sale.sale_number,
                (
                    sale.client.full_name
                    if sale.client
                    else "Client comptoir"
                ),
                (
                    sale.client.phone
                    if sale.client
                    else ""
                ),
                sale.total,
                sale.amount_paid,
                sale.remaining_amount,
                sale.get_payment_status_display(),
                sale.get_payment_method_display(),
                (
                    sale.created_by.username
                    if sale.created_by
                    else ""
                ),
            ])

        return response

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

    sale_count = sales.count()

    top_products = (
        SaleItem.objects.filter(
            sale__in=sales,
        )
        .values("product__name")
        .annotate(
            total_qty=Sum("quantity"),
            total_amount=Sum("total_line"),
        )
        .order_by("-total_amount")[:10]
    )

    paginator = Paginator(sales, 20)
    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    context = {
        "page_obj": page_obj,
        "query": query,
        "status": status,
        "status_choices": Sale.PaymentStatus.choices,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "total_sales": total_sales,
        "total_paid": total_paid,
        "total_remaining": total_remaining,
        "sale_count": sale_count,
        "top_products": top_products,
    }

    return render(
        request,
        "reports/sales_report.html",
        context,
    )


@admin_required
def stock_report(request):
    query = request.GET.get("q", "").strip()

    category_id = request.GET.get(
        "category",
        "",
    ).strip()

    stock_status = request.GET.get(
        "stock",
        "",
    ).strip()

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
        products = products.filter(
            category_id=category_id,
        )

    if stock_status == "low":
        products = products.filter(
            stock_quantity__lte=F("alert_quantity"),
        )

    elif stock_status == "zero":
        products = products.filter(
            stock_quantity=0,
        )

    elif stock_status == "available":
        products = products.filter(
            stock_quantity__gt=0,
        )

    if request.GET.get("export") == "csv":
        response = HttpResponse(
            content_type="text/csv; charset=utf-8"
        )

        response["Content-Disposition"] = (
            'attachment; filename="rapport_stock.csv"'
        )

        response.write("\ufeff")

        writer = csv.writer(
            response,
            delimiter=";",
        )

        writer.writerow([
            "Produit",
            "Référence",
            "Code-barres",
            "Catégorie",
            "Stock",
            "Unité",
            "Stock minimum",
            "Prix achat",
            "Prix vente",
            "Valeur achat",
            "Valeur vente",
        ])

        for product in products:
            writer.writerow([
                product.name,
                product.reference or "-",
                product.barcode or "-",
                (
                    product.category.name
                    if product.category
                    else "-"
                ),
                product.stock_quantity,
                product.unit.short_name,
                product.alert_quantity,
                product.purchase_price,
                product.sale_price,
                (
                    product.stock_quantity
                    * product.purchase_price
                ),
                (
                    product.stock_quantity
                    * product.sale_price
                ),
            ])

        return response

    categories = Category.objects.filter(
        is_active=True,
    ).order_by("name")

    (
        purchase_value,
        sale_value,
        margin_value,
    ) = calculate_stock_values(products)

    product_count = products.count()

    low_stock_count = products.filter(
        stock_quantity__lte=F("alert_quantity")
    ).count()

    zero_stock_count = products.filter(
        stock_quantity=0,
    ).count()

    paginator = Paginator(products, 20)
    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    context = {
        "page_obj": page_obj,
        "categories": categories,
        "query": query,
        "category_id": category_id,
        "stock_status": stock_status,
        "product_count": product_count,
        "low_stock_count": low_stock_count,
        "zero_stock_count": zero_stock_count,
        "purchase_value": purchase_value,
        "sale_value": sale_value,
        "margin_value": margin_value,
    }

    return render(
        request,
        "reports/stock_report.html",
        context,
    )


@admin_required
def profit_report(request):
    start_date, end_date = get_period_dates(request)

    sales = Sale.objects.filter(
        sale_date__date__gte=start_date,
        sale_date__date__lte=end_date,
        is_cancelled=False,
    )

    items = SaleItem.objects.select_related(
        "product",
    ).filter(
        sale__in=sales,
    )

    expenses = Expense.objects.filter(
        expense_date__date__gte=start_date,
        expense_date__date__lte=end_date,
    )

    gross_revenue = Decimal("0.00")
    cost_of_goods = Decimal("0.00")

    product_stats = {}

    for item in items:
        revenue = item.total_line

        cost = (
            item.quantity
            * item.product.purchase_price
        )

        profit = revenue - cost

        gross_revenue += revenue
        cost_of_goods += cost

        product_id = item.product_id

        if product_id not in product_stats:
            product_stats[product_id] = {
                "name": item.product.name,
                "qty": Decimal("0.00"),
                "revenue": Decimal("0.00"),
                "cost": Decimal("0.00"),
                "profit": Decimal("0.00"),
            }

        product_stats[product_id]["qty"] += (
            item.quantity
        )

        product_stats[product_id]["revenue"] += (
            revenue
        )

        product_stats[product_id]["cost"] += cost

        product_stats[product_id]["profit"] += (
            profit
        )

    global_discount = decimal_sum(
        sales,
        "discount",
    )

    net_revenue = gross_revenue - global_discount

    if net_revenue < Decimal("0.00"):
        net_revenue = Decimal("0.00")

    gross_profit = net_revenue - cost_of_goods

    total_expenses = decimal_sum(
        expenses,
        "amount",
    )

    net_profit = gross_profit - total_expenses

    top_profit_products = sorted(
        product_stats.values(),
        key=lambda item: item["profit"],
        reverse=True,
    )[:10]

    context = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "sale_count": sales.count(),
        "gross_revenue": gross_revenue,
        "global_discount": global_discount,
        "net_revenue": net_revenue,
        "cost_of_goods": cost_of_goods,
        "gross_profit": gross_profit,
        "total_expenses": total_expenses,
        "net_profit": net_profit,
        "top_profit_products": top_profit_products,
    }

    return render(
        request,
        "reports/profit_report.html",
        context,
    )
