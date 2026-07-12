from django.urls import path

from . import views


urlpatterns = [
    path("", views.report_dashboard, name="report_dashboard"),
    path("ventes/", views.sales_report, name="sales_report"),
    path("stock/", views.stock_report, name="stock_report"),
    path("benefices/", views.profit_report, name="profit_report"),
]