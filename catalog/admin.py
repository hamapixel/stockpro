from django.contrib import admin

from .models import Category, Product, Unit


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("name", "short_name", "created_at")
    search_fields = ("name", "short_name")
    ordering = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "unit",
        "purchase_price",
        "sale_price",
        "stock_quantity",
        "alert_quantity",
        "is_active",
    )
    list_filter = ("is_active", "category", "unit")
    search_fields = ("name", "reference", "barcode")
    ordering = ("name",)