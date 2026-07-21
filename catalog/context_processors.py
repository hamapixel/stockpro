from django.db.models import Count, F, Q

from .models import Product


def stock_notifications(request):
    """
    Rend les alertes de stock disponibles
    dans tous les templates de l'application.
    """
    if not request.user.is_authenticated:
        return {
            "stock_alert_count": 0,
            "stock_out_count": 0,
            "stock_low_count": 0,
            "stock_out_preview": [],
            "stock_low_preview": [],
        }

    active_products = Product.objects.filter(
        is_active=True,
    )

    summary = active_products.aggregate(
        stock_out_count=Count(
            "id",
            filter=Q(
                stock_quantity__lte=0,
            ),
        ),
        stock_low_count=Count(
            "id",
            filter=Q(
                stock_quantity__gt=0,
                stock_quantity__lte=F(
                    "alert_quantity"
                ),
            ),
        ),
    )

    stock_out_count = (
        summary["stock_out_count"] or 0
    )

    stock_low_count = (
        summary["stock_low_count"] or 0
    )

    stock_out_preview = (
        active_products
        .filter(
            stock_quantity__lte=0,
        )
        .select_related(
            "unit",
            "category",
        )
        .order_by(
            "name",
        )[:5]
    )

    stock_low_preview = (
        active_products
        .filter(
            stock_quantity__gt=0,
            stock_quantity__lte=F(
                "alert_quantity"
            ),
        )
        .select_related(
            "unit",
            "category",
        )
        .order_by(
            "stock_quantity",
            "name",
        )[:5]
    )

    return {
        "stock_alert_count": (
            stock_out_count
            + stock_low_count
        ),
        "stock_out_count": stock_out_count,
        "stock_low_count": stock_low_count,
        "stock_out_preview": stock_out_preview,
        "stock_low_preview": stock_low_preview,
    }