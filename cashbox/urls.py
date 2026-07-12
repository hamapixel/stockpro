from django.urls import path

from . import views


urlpatterns = [
    path("", views.cashbox_today, name="cashbox_today"),
]