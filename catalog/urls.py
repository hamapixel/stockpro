from django.urls import path

from . import views


urlpatterns = [
    path("categories/", views.category_list, name="category_list"),
    path("categories/ajouter/", views.category_create, name="category_create"),
    path("categories/<int:pk>/modifier/", views.category_update, name="category_update"),
    path("categories/<int:pk>/supprimer/", views.category_delete, name="category_delete"),

    path("unites/", views.unit_list, name="unit_list"),
    path("unites/ajouter/", views.unit_create, name="unit_create"),
    path("unites/<int:pk>/modifier/", views.unit_update, name="unit_update"),
    path("unites/<int:pk>/supprimer/", views.unit_delete, name="unit_delete"),

    path("produits/", views.product_list, name="product_list"),
    path("produits/ajouter/", views.product_create, name="product_create"),
    path("produits/<int:pk>/", views.product_detail, name="product_detail"),
    path("produits/<int:pk>/modifier/", views.product_update, name="product_update"),
    path("produits/<int:pk>/supprimer/", views.product_delete, name="product_delete"),
]