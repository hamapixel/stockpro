from django.contrib import admin

from .models import Sale, SaleItem


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ("total_line",)


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = (
        "sale_number",
        "client",
        "sale_date",
        "total",
        "amount_paid",
        "remaining_amount",
        "payment_status",
        "payment_method",
        "is_cancelled",
    )
    list_filter = (
        "payment_status",
        "payment_method",
        "is_cancelled",
        "sale_date",
    )
    search_fields = (
        "sale_number",
        "client__full_name",
        "client__phone",
    )
    readonly_fields = (
        "sale_number",
        "subtotal",
        "total",
        "remaining_amount",
        "created_at",
        "updated_at",
    )
    inlines = [SaleItemInline]
    ordering = ("-sale_date",)


@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = (
        "sale",
        "product",
        "quantity",
        "unit_price",
        "discount",
        "total_line",
    )
    search_fields = (
        "sale__sale_number",
        "product__name",
    )