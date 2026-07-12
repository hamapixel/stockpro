from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import admin_required

from .forms import CategoryForm, ProductForm, UnitForm
from .models import Category, Product, Unit


# =========================================================
# CATÉGORIES
# =========================================================

@admin_required
def category_list(request):
    query = request.GET.get("q", "").strip()

    categories = Category.objects.all().order_by("name")

    if query:
        categories = categories.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
        )

    category_count = categories.count()

    paginator = Paginator(categories, 10)
    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    context = {
        "page_obj": page_obj,
        "query": query,
        "category_count": category_count,
    }

    return render(
        request,
        "catalog/category_list.html",
        context,
    )


@admin_required
def category_create(request):
    if request.method == "POST":
        form = CategoryForm(request.POST)

        if form.is_valid():
            category = form.save()

            messages.success(
                request,
                f"La catégorie « {category.name} » a été ajoutée avec succès.",
            )

            return redirect("category_list")
    else:
        form = CategoryForm()

    context = {
        "form": form,
        "title": "Ajouter une catégorie",
        "button_label": "Enregistrer",
    }

    return render(
        request,
        "catalog/category_form.html",
        context,
    )


@admin_required
def category_update(request, pk):
    category = get_object_or_404(
        Category,
        pk=pk,
    )

    if request.method == "POST":
        form = CategoryForm(
            request.POST,
            instance=category,
        )

        if form.is_valid():
            updated_category = form.save()

            messages.success(
                request,
                f"La catégorie « {updated_category.name} » a été modifiée avec succès.",
            )

            return redirect("category_list")
    else:
        form = CategoryForm(instance=category)

    context = {
        "form": form,
        "category": category,
        "title": "Modifier la catégorie",
        "button_label": "Modifier",
    }

    return render(
        request,
        "catalog/category_form.html",
        context,
    )


@admin_required
def category_delete(request, pk):
    category = get_object_or_404(
        Category,
        pk=pk,
    )

    if request.method == "POST":
        category_name = category.name

        try:
            category.delete()

            messages.success(
                request,
                f"La catégorie « {category_name} » a été supprimée avec succès.",
            )

        except ProtectedError:
            messages.error(
                request,
                "Cette catégorie ne peut pas être supprimée, "
                "car elle est utilisée par un ou plusieurs produits.",
            )

        return redirect("category_list")

    context = {
        "category": category,
    }

    return render(
        request,
        "catalog/category_confirm_delete.html",
        context,
    )


# =========================================================
# UNITÉS
# =========================================================

@admin_required
def unit_list(request):
    query = request.GET.get("q", "").strip()

    units = Unit.objects.all().order_by("name")

    if query:
        units = units.filter(
            Q(name__icontains=query)
            | Q(short_name__icontains=query)
        )

    unit_count = units.count()

    paginator = Paginator(units, 10)
    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    context = {
        "page_obj": page_obj,
        "query": query,
        "unit_count": unit_count,
    }

    return render(
        request,
        "catalog/unit_list.html",
        context,
    )


@admin_required
def unit_create(request):
    if request.method == "POST":
        form = UnitForm(request.POST)

        if form.is_valid():
            unit = form.save()

            messages.success(
                request,
                f"L’unité « {unit.name} » a été ajoutée avec succès.",
            )

            return redirect("unit_list")
    else:
        form = UnitForm()

    context = {
        "form": form,
        "title": "Ajouter une unité",
        "button_label": "Enregistrer",
    }

    return render(
        request,
        "catalog/unit_form.html",
        context,
    )


@admin_required
def unit_update(request, pk):
    unit = get_object_or_404(
        Unit,
        pk=pk,
    )

    if request.method == "POST":
        form = UnitForm(
            request.POST,
            instance=unit,
        )

        if form.is_valid():
            updated_unit = form.save()

            messages.success(
                request,
                f"L’unité « {updated_unit.name} » a été modifiée avec succès.",
            )

            return redirect("unit_list")
    else:
        form = UnitForm(instance=unit)

    context = {
        "form": form,
        "unit": unit,
        "title": "Modifier l’unité",
        "button_label": "Modifier",
    }

    return render(
        request,
        "catalog/unit_form.html",
        context,
    )


@admin_required
def unit_delete(request, pk):
    unit = get_object_or_404(
        Unit,
        pk=pk,
    )

    if request.method == "POST":
        unit_name = unit.name

        try:
            unit.delete()

            messages.success(
                request,
                f"L’unité « {unit_name} » a été supprimée avec succès.",
            )

        except ProtectedError:
            messages.error(
                request,
                "Cette unité ne peut pas être supprimée, "
                "car elle est utilisée par un ou plusieurs produits.",
            )

        return redirect("unit_list")

    context = {
        "unit": unit,
    }

    return render(
        request,
        "catalog/unit_confirm_delete.html",
        context,
    )


# =========================================================
# PRODUITS
# =========================================================

@admin_required
def product_list(request):
    query = request.GET.get("q", "").strip()
    category_id = request.GET.get("category", "").strip()
    stock_status = request.GET.get("stock", "").strip()

    products = Product.objects.select_related(
        "category",
        "unit",
    ).all().order_by("name")

    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(reference__icontains=query)
            | Q(barcode__icontains=query)
            | Q(description__icontains=query)
        )

    if category_id:
        products = products.filter(
            category_id=category_id,
        )

    if stock_status == "low":
        products = products.filter(
            stock_quantity__lte=F("alert_quantity"),
            stock_quantity__gt=0,
        )

    elif stock_status == "available":
        products = products.filter(
            stock_quantity__gt=0,
        )

    elif stock_status == "zero":
        products = products.filter(
            stock_quantity=0,
        )

    elif stock_status == "active":
        products = products.filter(
            is_active=True,
        )

    elif stock_status == "inactive":
        products = products.filter(
            is_active=False,
        )

    categories = Category.objects.filter(
        is_active=True,
    ).order_by("name")

    product_count = products.count()

    paginator = Paginator(products, 12)
    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    context = {
        "page_obj": page_obj,
        "categories": categories,
        "query": query,
        "category_id": category_id,
        "stock_status": stock_status,
        "product_count": product_count,
    }

    return render(
        request,
        "catalog/product_list.html",
        context,
    )


@admin_required
def product_detail(request, pk):
    product = get_object_or_404(
        Product.objects.select_related(
            "category",
            "unit",
        ),
        pk=pk,
    )

    context = {
        "product": product,
    }

    return render(
        request,
        "catalog/product_detail.html",
        context,
    )


@admin_required
def product_create(request):
    if request.method == "POST":
        form = ProductForm(
            request.POST,
            request.FILES,
        )

        if form.is_valid():
            product = form.save()

            messages.success(
                request,
                f"Le produit « {product.name} » a été ajouté avec succès.",
            )

            return redirect(
                "product_detail",
                pk=product.pk,
            )
    else:
        form = ProductForm()

    context = {
        "form": form,
        "title": "Ajouter un produit",
        "button_label": "Enregistrer",
    }

    return render(
        request,
        "catalog/product_form.html",
        context,
    )


@admin_required
def product_update(request, pk):
    product = get_object_or_404(
        Product,
        pk=pk,
    )

    if request.method == "POST":
        form = ProductForm(
            request.POST,
            request.FILES,
            instance=product,
        )

        if form.is_valid():
            updated_product = form.save()

            messages.success(
                request,
                f"Le produit « {updated_product.name} » a été modifié avec succès.",
            )

            return redirect(
                "product_detail",
                pk=updated_product.pk,
            )
    else:
        form = ProductForm(instance=product)

    context = {
        "form": form,
        "product": product,
        "title": "Modifier le produit",
        "button_label": "Modifier",
    }

    return render(
        request,
        "catalog/product_form.html",
        context,
    )


@admin_required
def product_delete(request, pk):
    product = get_object_or_404(
        Product,
        pk=pk,
    )

    if request.method == "POST":
        product_name = product.name

        try:
            product.delete()

            messages.success(
                request,
                f"Le produit « {product_name} » a été supprimé avec succès.",
            )

        except ProtectedError:
            messages.error(
                request,
                "Ce produit ne peut pas être supprimé, "
                "car il est déjà associé à une vente ou à une opération de stock. "
                "Désactivez plutôt le produit.",
            )

        return redirect("product_list")

    context = {
        "product": product,
    }

    return render(
        request,
        "catalog/product_confirm_delete.html",
        context,
    )