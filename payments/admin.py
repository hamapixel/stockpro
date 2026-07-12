from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "sale",
        "client",
        "amount",
        "payment_method",
        "payment_date",
        "created_by",
    )
    list_filter = (
        "payment_method",
        "payment_date",
    )
    search_fields = (
        "sale__sale_number",
        "client__full_name",
        "client__phone",
    )
    ordering = ("-payment_date",)