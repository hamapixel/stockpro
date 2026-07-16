from django.urls import path

from . import views


urlpatterns = [
    path(
        "",
        views.stock_list,
        name="stock_list",
    ),

    path(
        "api/produits/",
        views.product_search_api,
        name="product_search_api",
    ),

    path(
        "ajustement/",
        views.stock_adjustment_create,
        name="stock_adjustment_create",
    ),

    path(
        "entree/",
        views.stock_adjustment_create,
        {"default_type": "in"},
        name="stock_in_create",
    ),

    path(
        "sortie/",
        views.stock_adjustment_create,
        {"default_type": "out"},
        name="stock_out_create",
    ),

    path(
        "mouvements/",
        views.stock_movement_list,
        name="stock_movement_list",
    ),

    path(
        "mouvements/impression/",
        views.stock_movement_report_print,
        name="stock_movement_report_print",
    ),

    path(
        (
            "mouvements/lot/"
            "<str:batch_reference>/impression/"
        ),
        views.stock_movement_batch_print,
        name="stock_movement_batch_print",
    ),

    path(
        "mouvements/<int:movement_pk>/impression/",
        views.stock_movement_print,
        name="stock_movement_print",
    ),
]