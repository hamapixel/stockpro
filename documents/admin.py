from django.contrib import admin

from .models import (
    Proforma,
    ProformaItem,
)


class ProformaItemInline(
    admin.TabularInline
):
    model = ProformaItem
    extra = 0

    fields = (
        "product",
        "quantity",
        "unit_price",
        "discount",
        "total_line",
    )

    readonly_fields = (
        "total_line",
    )


@admin.register(Proforma)
class ProformaAdmin(admin.ModelAdmin):
    list_display = (
        "proforma_number",
        "client",
        "proforma_date",
        "valid_until",
        "total",
        "status",
        "expired_display",
        "created_by",
    )

    list_filter = (
        "status",
        "proforma_date",
        "valid_until",
        "created_at",
    )

    search_fields = (
        "proforma_number",
        "client__full_name",
        "client__phone",
        "notes",
        "terms",
    )

    ordering = (
        "-proforma_date",
        "-created_at",
    )

    date_hierarchy = "proforma_date"

    readonly_fields = (
        "proforma_number",
        "subtotal",
        "total",
        "converted_sale",
        "created_at",
        "updated_at",
    )

    list_select_related = (
        "client",
        "created_by",
        "converted_sale",
    )

    inlines = [
        ProformaItemInline,
    ]

    def save_related(
        self,
        request,
        form,
        formsets,
        change,
    ):
        super().save_related(
            request,
            form,
            formsets,
            change,
        )

        form.instance.calculate_totals(
            save=True
        )

    @admin.display(
        boolean=True,
        description="Expirée",
    )
    def expired_display(
        self,
        obj,
    ):
        return obj.is_expired


@admin.register(ProformaItem)
class ProformaItemAdmin(
    admin.ModelAdmin
):
    list_display = (
        "proforma",
        "product",
        "quantity",
        "unit_price",
        "discount",
        "total_line",
    )

    search_fields = (
        "proforma__proforma_number",
        "product__name",
        "product__reference",
        "proforma__client__full_name",
    )

    list_select_related = (
        "proforma",
        "product",
    )

    readonly_fields = (
        "total_line",
        "created_at",
        "updated_at",
    )