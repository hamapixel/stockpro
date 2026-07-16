from django.urls import path

from . import purchase_views
from . import views


urlpatterns = [
    # Centre des rapports
    path(
        "",
        views.report_dashboard,
        name="report_dashboard",
    ),

    # Rapport des ventes
    path(
        "ventes/",
        views.sales_report,
        name="sales_report",
    ),

    # Rapport du stock
    path(
        "stock/",
        views.stock_report,
        name="stock_report",
    ),

    # Rapport des bénéfices
    path(
        "benefices/",
        views.profit_report,
        name="profit_report",
    ),

    # Rapport des achats
    path(
        "achats/",
        purchase_views.purchase_report,
        name="purchase_report",
    ),
    path(
        "achats/impression/",
        purchase_views.purchase_report_print,
        name="purchase_report_print",
    ),

    # Rapport des fournisseurs
    path(
        "fournisseurs/",
        purchase_views.supplier_report,
        name="supplier_report",
    ),
    path(
        "fournisseurs/impression/",
        purchase_views.supplier_report_print,
        name="supplier_report_print",
    ),
]