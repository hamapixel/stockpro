from django.urls import path

from . import views


urlpatterns = [
    path("", views.document_center, name="document_center"),

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
]