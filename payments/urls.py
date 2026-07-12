from django.urls import path

from . import views


urlpatterns = [
    path("credits/", views.credit_list, name="credit_list"),
    path("", views.payment_list, name="payment_list"),
    path("vente/<int:sale_pk>/ajouter/", views.payment_create, name="payment_create"),
]