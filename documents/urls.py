from django.urls import path

from . import proforma_views
from . import views


urlpatterns = [
    path(
        "",
        views.document_center,
        name="document_center",
    ),

    path(
        "vente/<int:sale_pk>/facture/",
        views.sale_invoice,
        name="sale_invoice",
    ),

    path(
        "vente/<int:sale_pk>/recu/",
        views.sale_receipt,
        name="sale_receipt",
    ),

    path(
        "paiement/<int:payment_pk>/recu/",
        views.payment_receipt,
        name="payment_receipt",
    ),

    # =====================================================
    # PROFORMAS
    # =====================================================

    path(
        "proformas/",
        proforma_views.proforma_list,
        name="proforma_list",
    ),

    path(
        "proformas/nouvelle/",
        proforma_views.proforma_create,
        name="proforma_create",
    ),

    path(
        "proformas/api/produits/",
        (
            proforma_views
            .proforma_product_search_api
        ),
        name="proforma_product_search_api",
    ),

    path(
        "proformas/<int:pk>/modifier/",
        proforma_views.proforma_update,
        name="proforma_update",
    ),

    path(
        "proformas/<int:pk>/dupliquer/",
        proforma_views.proforma_duplicate,
        name="proforma_duplicate",
    ),

    path(
        "proformas/<int:pk>/annuler/",
        proforma_views.proforma_cancel,
        name="proforma_cancel",
    ),

    path(
        "proformas/<int:pk>/imprimer/",
        proforma_views.proforma_print,
        name="proforma_print",
    ),

    path(
        "proformas/<int:pk>/convertir/",
        proforma_views.proforma_convert,
        name="proforma_convert",
    ),

    path(
        "proformas/<int:pk>/",
        proforma_views.proforma_detail,
        name="proforma_detail",
    ),
]