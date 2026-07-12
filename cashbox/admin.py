from django.contrib import admin

from .models import CashMovement


@admin.register(CashMovement)
class CashMovementAdmin(admin.ModelAdmin):
    list_display = (
        "movement_type",
        "amount",
        "movement_date",
        "sale",
        "payment",
        "expense",
        "created_by",
    )
    list_filter = (
        "movement_type",
        "movement_date",
    )
    search_fields = (
        "notes",
        "sale__sale_number",
        "payment__sale__sale_number",
        "expense__title",
    )
    ordering = ("-movement_date",)