from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import F, Sum
from django.shortcuts import render
from django.utils import timezone

from catalog.models import Product
from customers.models import Client
from expenses.models import Expense
from sales.models import Sale, SaleItem


def decimal_sum(queryset, field_name):
    result = queryset.aggregate(total=Sum(field_name))["total"]
    return result or Decimal("0.00")


@login_required
def dashboard_view(request):
    today = timezone.localdate()
    period = request.GET.get("period", "today")

    if period == "yesterday":
        start_date = today - timedelta(days=1)
        end_date = today - timedelta(days=1)
        period_title = "Hier"

    elif period == "week":
        start_date = today - timedelta(days=today.weekday())
        end_date = today
        period_title = "Cette semaine"

    elif period == "month":
        start_date = today.replace(day=1)
        end_date = today
        period_title = "Ce mois"

    elif period == "year":
        start_date = today.replace(month=1, day=1)
        end_date = today
        period_title = "Cette année"

    else:
        start_date = today
        end_date = today
        period = "today"
        period_title = "Aujourd’hui"

    filtered_sales = Sale.objects.filter(
        sale_date__date__gte=start_date,
        sale_date__date__lte=end_date,
        is_cancelled=False,
    )

    today_sales = Sale.objects.filter(
        sale_date__date=today,
        is_cancelled=False,
    )

    yesterday_sales = Sale.objects.filter(
        sale_date__date=today - timedelta(days=1),
        is_cancelled=False,
    )

    week_start = today - timedelta(days=today.weekday())
    week_sales = Sale.objects.filter(
        sale_date__date__gte=week_start,
        sale_date__date__lte=today,
        is_cancelled=False,
    )

    month_start = today.replace(day=1)
    month_sales = Sale.objects.filter(
        sale_date__date__gte=month_start,
        sale_date__date__lte=today,
        is_cancelled=False,
    )

    today_expenses = Expense.objects.filter(
        expense_date__date=today,
    )

    filtered_expenses = Expense.objects.filter(
        expense_date__date__gte=start_date,
        expense_date__date__lte=end_date,
    )

    best_products = (
        SaleItem.objects.filter(
            sale__is_cancelled=False,
        )
        .values("product__name")
        .annotate(
            total_qty=Sum("quantity"),
            total_amount=Sum("total_line"),
        )
        .order_by("-total_qty")[:5]
    )

    recent_sales = (
        Sale.objects.filter(
            is_cancelled=False,
        )
        .select_related("client")
        .order_by("-sale_date")[:8]
    )

    total_today = decimal_sum(today_sales, "total")
    paid_today = decimal_sum(today_sales, "amount_paid")
    credit_today = decimal_sum(today_sales, "remaining_amount")
    expenses_today = decimal_sum(today_expenses, "amount")

    low_stock_count = Product.objects.filter(
        is_active=True,
        stock_quantity__lte=F("alert_quantity"),
    ).count()

    context = {
        "period": period,
        "period_title": period_title,

        "total_today": total_today,
        "total_yesterday": decimal_sum(yesterday_sales, "total"),
        "total_week": decimal_sum(week_sales, "total"),
        "total_month": decimal_sum(month_sales, "total"),

        "filtered_total": decimal_sum(filtered_sales, "total"),
        "filtered_paid": decimal_sum(filtered_sales, "amount_paid"),
        "filtered_credit": decimal_sum(filtered_sales, "remaining_amount"),
        "filtered_expenses": decimal_sum(filtered_expenses, "amount"),
        "filtered_count": filtered_sales.count(),

        "paid_today": paid_today,
        "credit_today": credit_today,
        "expenses_today": expenses_today,
        "cash_balance_today": paid_today - expenses_today,

        "product_count": Product.objects.filter(is_active=True).count(),
        "low_stock_count": low_stock_count,

        "client_count": Client.objects.count(),
        "credit_client_count": Client.objects.filter(balance__gt=0).count(),

        "recent_sales": recent_sales,
        "best_products": best_products,
    }

    return render(request, "core/dashboard.html", context)