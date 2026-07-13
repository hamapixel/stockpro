from django.urls import path

from . import views


urlpatterns = [
    path(
        "pos/",
        views.sale_pos,
        name="sale_pos",
    ),

    path(
        "",
        views.sale_list,
        name="sale_list",
    ),

    path(
        "api/produits/",
        views.product_search_api,
        name="sale_product_search_api",
    ),

    path(
        "<int:pk>/annuler/",
        views.sale_cancel,
        name="sale_cancel",
    ),

    path(
        "<int:pk>/",
        views.sale_detail,
        name="sale_detail",
    ),
]