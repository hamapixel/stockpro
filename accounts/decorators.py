from functools import wraps

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import render


ADMIN_GROUP = "Administrateur"
SELLER_GROUP = "Vendeur"


def is_admin_user(user):
    if not user.is_authenticated:
        return False

    return (
        user.is_superuser
        or user.groups.filter(
            name=ADMIN_GROUP
        ).exists()
    )


def is_seller_user(user):
    if not user.is_authenticated:
        return False

    return user.groups.filter(
        name=SELLER_GROUP
    ).exists()


def has_role(user, allowed_roles):
    if not user.is_authenticated:
        return False

    if is_admin_user(user):
        return True

    return user.groups.filter(
        name__in=allowed_roles
    ).exists()


def role_required(*allowed_roles):
    def decorator(view_function):
        @wraps(view_function)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(
                    request.get_full_path(),
                    settings.LOGIN_URL,
                )

            if has_role(
                request.user,
                allowed_roles,
            ):
                return view_function(
                    request,
                    *args,
                    **kwargs,
                )

            return render(
                request,
                "errors/403.html",
                status=403,
            )

        return wrapper

    return decorator


def admin_required(view_function):
    return role_required(
        ADMIN_GROUP
    )(view_function)


def seller_or_admin_required(view_function):
    return role_required(
        ADMIN_GROUP,
        SELLER_GROUP,
    )(view_function)