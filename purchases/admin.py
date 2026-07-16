from django.contrib import admin

from .models import (
    Purchase,
    PurchaseItem,
    PurchasePayment,
    Supplier,
)


class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem

    extra = 0

    fields = [
        "product",
        "quantity",
        "unit_cost",
        "discount",
        "total_line",
    ]

    readonly_fields = [
        "total_line",
    ]

    autocomplete_fields = [
        "product",
    ]


class PurchasePaymentInline(admin.TabularInline):
    model = PurchasePayment

    extra = 0

    fields = [
        "amount",
        "payment_method",
        "payment_date",
        "created_by",
    ]

    readonly_fields = [
        "created_by",
    ]


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "phone",
        "email",
        "formatted_balance",
        "is_active",
        "created_at",
    ]

    list_filter = [
        "is_active",
        "created_at",
    ]

    search_fields = [
        "name",
        "phone",
        "email",
        "address",
    ]

    readonly_fields = [
        "balance",
        "created_at",
        "updated_at",
    ]

    ordering = [
        "name",
    ]

    fieldsets = (
        (
            "Informations du fournisseur",
            {
                "fields": (
                    "name",
                    "phone",
                    "email",
                    "address",
                    "is_active",
                )
            },
        ),
        (
            "Situation financière",
            {
                "fields": (
                    "balance",
                )
            },
        ),
        (
            "Informations système",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )

    @admin.display(
        description="Dette fournisseur",
        ordering="balance",
    )
    def formatted_balance(self, obj):
        value = obj.balance or 0

        formatted_value = (
            f"{value:,.0f}"
            .replace(",", " ")
        )

        return f"{formatted_value} F CFA"


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = [
        "purchase_number",
        "supplier",
        "purchase_date",
        "formatted_total",
        "formatted_amount_paid",
        "formatted_remaining_amount",
        "payment_status",
        "is_cancelled",
    ]

    list_filter = [
        "payment_status",
        "payment_method",
        "is_cancelled",
        "purchase_date",
    ]

    search_fields = [
        "purchase_number",
        "supplier_reference",
        "supplier__name",
        "supplier__phone",
        "notes",
    ]

    readonly_fields = [
        "purchase_number",
        "subtotal",
        "total",
        "amount_paid",
        "remaining_amount",
        "payment_status",
        "created_at",
        "updated_at",
    ]

    autocomplete_fields = [
        "supplier",
        "created_by",
    ]

    date_hierarchy = "purchase_date"

    ordering = [
        "-purchase_date",
    ]

    list_select_related = [
        "supplier",
        "created_by",
    ]

    inlines = [
        PurchaseItemInline,
        PurchasePaymentInline,
    ]

    fieldsets = (
        (
            "Informations de l'achat",
            {
                "fields": (
                    "purchase_number",
                    "supplier",
                    "supplier_reference",
                    "purchase_date",
                    "payment_method",
                    "discount",
                    "notes",
                    "created_by",
                )
            },
        ),
        (
            "Montants",
            {
                "fields": (
                    "subtotal",
                    "total",
                    "amount_paid",
                    "remaining_amount",
                    "payment_status",
                )
            },
        ),
        (
            "État de l'achat",
            {
                "fields": (
                    "is_cancelled",
                )
            },
        ),
        (
            "Informations système",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )

    @admin.display(
        description="Total",
        ordering="total",
    )
    def formatted_total(self, obj):
        return self.format_fcfa(
            obj.total
        )

    @admin.display(
        description="Payé",
        ordering="amount_paid",
    )
    def formatted_amount_paid(self, obj):
        return self.format_fcfa(
            obj.amount_paid
        )

    @admin.display(
        description="Reste",
        ordering="remaining_amount",
    )
    def formatted_remaining_amount(
        self,
        obj,
    ):
        return self.format_fcfa(
            obj.remaining_amount
        )

    @staticmethod
    def format_fcfa(value):
        value = value or 0

        formatted_value = (
            f"{value:,.0f}"
            .replace(",", " ")
        )

        return f"{formatted_value} F CFA"


@admin.register(PurchaseItem)
class PurchaseItemAdmin(admin.ModelAdmin):
    list_display = [
        "purchase",
        "product",
        "quantity",
        "formatted_unit_cost",
        "formatted_discount",
        "formatted_total_line",
    ]

    list_filter = [
        "purchase__purchase_date",
        "product__category",
    ]

    search_fields = [
        "purchase__purchase_number",
        "product__name",
        "product__reference",
        "product__barcode",
    ]

    autocomplete_fields = [
        "purchase",
        "product",
    ]

    list_select_related = [
        "purchase",
        "product",
    ]

    readonly_fields = [
        "total_line",
        "created_at",
    ]

    @admin.display(
        description="Prix unitaire",
        ordering="unit_cost",
    )
    def formatted_unit_cost(self, obj):
        return self.format_fcfa(
            obj.unit_cost
        )

    @admin.display(
        description="Remise",
        ordering="discount",
    )
    def formatted_discount(self, obj):
        return self.format_fcfa(
            obj.discount
        )

    @admin.display(
        description="Montant ligne",
        ordering="total_line",
    )
    def formatted_total_line(self, obj):
        return self.format_fcfa(
            obj.total_line
        )

    @staticmethod
    def format_fcfa(value):
        value = value or 0

        formatted_value = (
            f"{value:,.0f}"
            .replace(",", " ")
        )

        return f"{formatted_value} F CFA"


@admin.register(PurchasePayment)
class PurchasePaymentAdmin(admin.ModelAdmin):
    list_display = [
        "purchase",
        "supplier",
        "formatted_amount",
        "payment_method",
        "payment_date",
        "created_by",
    ]

    list_filter = [
        "payment_method",
        "payment_date",
    ]

    search_fields = [
        "purchase__purchase_number",
        "supplier__name",
        "supplier__phone",
        "notes",
    ]

    autocomplete_fields = [
        "purchase",
        "supplier",
        "created_by",
    ]

    list_select_related = [
        "purchase",
        "supplier",
        "created_by",
    ]

    readonly_fields = [
        "created_at",
    ]

    date_hierarchy = "payment_date"

    ordering = [
        "-payment_date",
    ]

    @admin.display(
        description="Montant",
        ordering="amount",
    )
    def formatted_amount(self, obj):
        value = obj.amount or 0

        formatted_value = (
            f"{value:,.0f}"
            .replace(",", " ")
        )

        return f"{formatted_value} F CFA"