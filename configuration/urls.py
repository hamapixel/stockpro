from django.urls import path

from . import views


urlpatterns = [
    path(
        "",
        views.company_settings_update,
        name="company_settings",
    ),
    path(
        "apercu-entete/",
        views.invoice_header_preview,
        name="invoice_header_preview",
    ),
]