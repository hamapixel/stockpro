from django.urls import path

from . import views


urlpatterns = [
    path("", views.client_list, name="client_list"),
    path("ajouter/", views.client_create, name="client_create"),
    path("<int:pk>/", views.client_detail, name="client_detail"),
    path("<int:pk>/modifier/", views.client_update, name="client_update"),
    path("<int:pk>/supprimer/", views.client_delete, name="client_delete"),
]