from django.urls import path

from . import views


urlpatterns = [
    # =====================================================
    # FOURNISSEURS
    # =====================================================
    path(
        "fournisseurs/",
        views.supplier_list,
        name="supplier_list",
    ),
    path(
        "fournisseurs/ajouter/",
        views.supplier_create,
        name="supplier_create",
    ),
    path(
        "fournisseurs/<int:pk>/",
        views.supplier_detail,
        name="supplier_detail",
    ),
    path(
        "fournisseurs/<int:pk>/modifier/",
        views.supplier_update,
        name="supplier_update",
    ),
    path(
        "fournisseurs/<int:pk>/statut/",
        views.supplier_toggle_status,
        name="supplier_toggle_status",
    ),

    # =====================================================
    # ACHATS ET APPROVISIONNEMENTS
    # =====================================================
    path(
        "",
        views.purchase_list,
        name="purchase_list",
    ),
    path(
        "nouvel-approvisionnement/",
        views.purchase_create,
        name="purchase_create",
    ),
    path(
        "<int:pk>/",
        views.purchase_detail,
        name="purchase_detail",
    ),
    path(
        "<int:pk>/annuler/",
        views.purchase_cancel,
        name="purchase_cancel",
    ),

    # =====================================================
    # PAIEMENTS FOURNISSEURS
    # =====================================================
    path(
        "paiements/",
        views.purchase_payment_list,
        name="purchase_payment_list",
    ),
    path(
        "<int:purchase_pk>/paiement/ajouter/",
        views.purchase_payment_create,
        name="purchase_payment_create",
    ),
]