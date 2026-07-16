from django.contrib import admin

from .models import CompanySettings


@admin.register(CompanySettings)
class CompanySettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        (
            "Identité",
            {
                "fields": (
                    "company_name",
                    "legal_name",
                    "activity",
                    "slogan",
                    "logo",
                )
            },
        ),
        (
            "Coordonnées",
            {
                "fields": (
                    "address",
                    "phone",
                    "phone_secondary",
                    "email",
                    "website",
                    "rccm",
                    "nif",
                    "bank_details",
                )
            },
        ),
        (
            "Factures",
            {
                "fields": (
                    "invoice_header_mode",
                    "invoice_header",
                    "invoice_header_height_mm",
                    "show_logo_on_generated_header",
                    "invoice_footer_text",
                    "invoice_terms",
                    "currency_label",
                )
            },
        ),
        (
            "Suivi",
            {
                "fields": (
                    "updated_at",
                )
            },
        ),
    )

    readonly_fields = (
        "updated_at",
    )

    def has_add_permission(self, request):
        return not CompanySettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False