from django.contrib import admin

from .models import Expense


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "amount",
        "expense_date",
        "created_by",
    )
    list_filter = (
        "category",
        "expense_date",
    )
    search_fields = (
        "title",
        "description",
    )
    ordering = ("-expense_date",)