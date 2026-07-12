from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.decorators import admin_required

from .forms import ExpenseForm
from .models import Expense


def decimal_sum(queryset, field_name):
    result = queryset.aggregate(total=Sum(field_name))["total"]
    return result or Decimal("0.00")


@admin_required
def expense_list(request):
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    start_date = request.GET.get("start_date", "").strip()
    end_date = request.GET.get("end_date", "").strip()

    expenses = Expense.objects.select_related(
        "created_by",
    ).order_by("-expense_date")

    if query:
        expenses = expenses.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
        )

    if category:
        expenses = expenses.filter(category=category)

    if start_date:
        expenses = expenses.filter(
            expense_date__date__gte=start_date,
        )

    if end_date:
        expenses = expenses.filter(
            expense_date__date__lte=end_date,
        )

    today = timezone.localdate()
    month_start = today.replace(day=1)

    total_expenses = decimal_sum(
        expenses,
        "amount",
    )

    today_expenses = decimal_sum(
        Expense.objects.filter(
            expense_date__date=today,
        ),
        "amount",
    )

    month_expenses = decimal_sum(
        Expense.objects.filter(
            expense_date__date__gte=month_start,
            expense_date__date__lte=today,
        ),
        "amount",
    )

    expense_count = expenses.count()

    paginator = Paginator(expenses, 20)
    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    context = {
        "page_obj": page_obj,
        "query": query,
        "category": category,
        "start_date": start_date,
        "end_date": end_date,
        "category_choices": Expense.ExpenseCategory.choices,
        "total_expenses": total_expenses,
        "today_expenses": today_expenses,
        "month_expenses": month_expenses,
        "expense_count": expense_count,
    }

    return render(
        request,
        "expenses/expense_list.html",
        context,
    )


@admin_required
def expense_create(request):
    if request.method == "POST":
        form = ExpenseForm(request.POST)

        if form.is_valid():
            expense = form.save(commit=False)
            expense.created_by = request.user
            expense.save()

            messages.success(
                request,
                "Dépense enregistrée avec succès.",
            )

            return redirect("expense_list")
    else:
        form = ExpenseForm(
            initial={
                "expense_date": timezone.localtime().strftime(
                    "%Y-%m-%dT%H:%M"
                ),
            }
        )

    context = {
        "form": form,
        "title": "Ajouter une dépense",
        "button_label": "Enregistrer",
    }

    return render(
        request,
        "expenses/expense_form.html",
        context,
    )


@admin_required
def expense_update(request, pk):
    expense = get_object_or_404(
        Expense,
        pk=pk,
    )

    if request.method == "POST":
        form = ExpenseForm(
            request.POST,
            instance=expense,
        )

        if form.is_valid():
            updated_expense = form.save(commit=False)

            if not updated_expense.created_by:
                updated_expense.created_by = request.user

            updated_expense.save()

            messages.success(
                request,
                "Dépense modifiée avec succès.",
            )

            return redirect("expense_list")
    else:
        form = ExpenseForm(
            instance=expense,
            initial={
                "expense_date": timezone.localtime(
                    expense.expense_date
                ).strftime("%Y-%m-%dT%H:%M"),
            },
        )

    context = {
        "form": form,
        "title": "Modifier la dépense",
        "button_label": "Modifier",
        "expense": expense,
    }

    return render(
        request,
        "expenses/expense_form.html",
        context,
    )


@admin_required
def expense_delete(request, pk):
    expense = get_object_or_404(
        Expense,
        pk=pk,
    )

    if request.method == "POST":
        expense.delete()

        messages.success(
            request,
            "Dépense supprimée avec succès.",
        )

        return redirect("expense_list")

    return render(
        request,
        "expenses/expense_confirm_delete.html",
        {
            "expense": expense,
        },
    )