from django.contrib import admin

from .models import StockMovement


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "movement_type",
        "quantity",
        "old_quantity",
        "new_quantity",
        "created_at",
    )
    list_filter = ("movement_type", "created_at")
    search_fields = ("product__name", "reason")
    ordering = ("-created_at",)