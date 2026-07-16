from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import include, path
from django.views.generic import RedirectView


urlpatterns = [
    path("", RedirectView.as_view(pattern_name="dashboard", permanent=False)),

    path("admin/", admin.site.urls),

    path(
        "login/",
        LoginView.as_view(
            template_name="auth/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("logout/", LogoutView.as_view(), name="logout"),

    path("dashboard/", include("core.urls")),
    path("catalogue/", include("catalog.urls")),
    path("stock/", include("inventory.urls")),
    path("clients/", include("customers.urls")),
    path("ventes/", include("sales.urls")),
    path("paiements/", include("payments.urls")),
    path("depenses/", include("expenses.urls")),
    path("caisse/", include("cashbox.urls")),
    path("documents/", include("documents.urls")),
    path("rapports/", include("reports.urls")),
    path("achats/",include("purchases.urls"),),
    path( "parametres/",include("configuration.urls"),),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)