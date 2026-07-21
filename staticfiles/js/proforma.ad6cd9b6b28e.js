document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("proformaPosForm");

    if (!form) {
        return;
    }

    const productsUrl = form.dataset.productsUrl;

    const elements = {
        search: document.getElementById(
            "proformaProductSearch"
        ),

        clearSearch: document.getElementById(
            "clearProductSearch"
        ),

        category: document.getElementById(
            "proformaCategoryFilter"
        ),

        productGrid: document.getElementById(
            "proformaProductGrid"
        ),

        loader: document.getElementById(
            "proformaProductsLoader"
        ),

        empty: document.getElementById(
            "proformaProductsEmpty"
        ),

        productCount: document.getElementById(
            "productCountBadge"
        ),

        loadMoreWrap: document.getElementById(
            "proformaLoadMoreWrap"
        ),

        loadMore: document.getElementById(
            "proformaLoadMore"
        ),

        cartLines: document.getElementById(
            "proformaCartLines"
        ),

        cartEmpty: document.getElementById(
            "proformaCartEmpty"
        ),

        cartCount: document.getElementById(
            "proformaCartCount"
        ),

        productTemplate: document.getElementById(
            "proformaProductCardTemplate"
        ),

        cartTemplate: document.getElementById(
            "proformaCartLineTemplate"
        ),

        subtotal: document.getElementById(
            "proformaSubtotal"
        ),

        globalDiscountText: document.getElementById(
            "proformaGlobalDiscount"
        ),

        total: document.getElementById(
            "proformaTotal"
        ),

        globalDiscountInput: document.getElementById(
            "id_discount"
        ),
    };

    const requiredElements = [
        elements.search,
        elements.category,
        elements.productGrid,
        elements.loader,
        elements.empty,
        elements.productCount,
        elements.loadMoreWrap,
        elements.loadMore,
        elements.cartLines,
        elements.cartEmpty,
        elements.cartCount,
        elements.productTemplate,
        elements.cartTemplate,
        elements.subtotal,
        elements.globalDiscountText,
        elements.total,
    ];

    if (
        !productsUrl ||
        requiredElements.some((element) => !element)
    ) {
        console.error(
            "Proforma : certains éléments HTML sont introuvables."
        );

        return;
    }

    const state = {
        page: 1,
        hasNext: false,
        totalCount: 0,
        loading: false,
        categoriesLoaded: false,
        searchTimer: null,
        requestController: null,
        productCache: new Map(),
    };

    function parseNumber(value) {
        const normalized = String(value ?? "0")
            .trim()
            .replace(/\s/g, "")
            .replace(",", ".");

        const number = Number(normalized);

        return Number.isFinite(number)
            ? number
            : 0;
    }

    function formatMoney(value) {
        const formatted = new Intl.NumberFormat(
            "fr-FR",
            {
                minimumFractionDigits: 0,
                maximumFractionDigits: 2,
            }
        ).format(value);

        return `${formatted} F CFA`;
    }

    function buildProductMeta(product) {
        const parts = [];

        if (product.reference) {
            parts.push(
                `Réf : ${product.reference}`
            );
        }

        const unit = product.unit
            ? ` ${product.unit}`
            : "";

        parts.push(
            `Stock : ${product.stock}${unit}`
        );

        if (product.barcode) {
            parts.push(
                `Code-barres : ${product.barcode}`
            );
        }

        return parts.join(" • ");
    }

    function calculateLine(line) {
        const quantityInput = line.querySelector(
            ".js-quantity"
        );

        const priceInput = line.querySelector(
            ".js-unit-price"
        );

        const discountInput = line.querySelector(
            ".js-line-discount"
        );

        const totalElement = line.querySelector(
            ".js-line-total"
        );

        if (
            !quantityInput ||
            !priceInput ||
            !discountInput ||
            !totalElement
        ) {
            return 0;
        }

        const quantity = parseNumber(
            quantityInput.value
        );

        const unitPrice = parseNumber(
            priceInput.value
        );

        const discount = parseNumber(
            discountInput.value
        );

        const total = Math.max(
            0,
            quantity * unitPrice - discount
        );

        line.dataset.lineTotal = String(total);

        totalElement.textContent =
            formatMoney(total);

        return total;
    }

    function calculateTotals() {
        let subtotal = 0;

        elements.cartLines
            .querySelectorAll(
                ".proforma-cart-line"
            )
            .forEach((line) => {
                subtotal += calculateLine(line);
            });

        const globalDiscount = parseNumber(
            elements.globalDiscountInput?.value
        );

        const total = Math.max(
            0,
            subtotal - globalDiscount
        );

        elements.subtotal.textContent =
            formatMoney(subtotal);

        elements.globalDiscountText.textContent =
            formatMoney(globalDiscount);

        elements.total.textContent =
            formatMoney(total);
    }

    function updateCartState() {
        const lines =
            elements.cartLines.querySelectorAll(
                ".proforma-cart-line"
            );

        const count = lines.length;

        elements.cartEmpty.classList.toggle(
            "d-none",
            count > 0
        );

        elements.cartLines.classList.toggle(
            "d-none",
            count === 0
        );

        elements.cartCount.textContent =
            `${count} ${
                count > 1
                    ? "lignes"
                    : "ligne"
            }`;

        calculateTotals();
    }

    function hydrateCartLine(line) {
        const productId = String(
            line.dataset.productId || ""
        );

        const product =
            state.productCache.get(productId);

        if (!product) {
            return;
        }

        const nameElement = line.querySelector(
            ".js-product-name"
        );

        const metaElement = line.querySelector(
            ".js-product-meta"
        );

        const labelInput = line.querySelector(
            '[name="product_label"]'
        );

        if (nameElement) {
            nameElement.textContent =
                product.name;
        }

        if (metaElement) {
            metaElement.textContent =
                buildProductMeta(product);
        }

        if (labelInput) {
            labelInput.value =
                product.label;
        }
    }

    function bindCartLine(line) {
        line.querySelectorAll(
            ".js-quantity, " +
            ".js-unit-price, " +
            ".js-line-discount"
        ).forEach((input) => {
            input.addEventListener(
                "input",
                calculateTotals
            );
        });

        const removeButton =
            line.querySelector(
                ".js-remove-line"
            );

        if (removeButton) {
            removeButton.addEventListener(
                "click",
                () => {
                    line.remove();
                    updateCartState();
                }
            );
        }

        hydrateCartLine(line);
        calculateLine(line);
    }

    function findCartLine(productId) {
        const lines = Array.from(
            elements.cartLines.querySelectorAll(
                ".proforma-cart-line"
            )
        );

        return lines.find((line) => {
            return (
                String(line.dataset.productId) ===
                String(productId)
            );
        });
    }

    function addProductToCart(product) {
        const existingLine = findCartLine(
            product.id
        );

        if (existingLine) {
            const quantityInput =
                existingLine.querySelector(
                    ".js-quantity"
                );

            if (quantityInput) {
                const currentQuantity =
                    parseNumber(
                        quantityInput.value
                    );

                quantityInput.value = String(
                    currentQuantity + 1
                );
            }

            existingLine.classList.add(
                "proforma-cart-line-highlight"
            );

            window.setTimeout(() => {
                existingLine.classList.remove(
                    "proforma-cart-line-highlight"
                );
            }, 650);

            calculateTotals();

            existingLine.scrollIntoView({
                behavior: "smooth",
                block: "nearest",
            });

            return;
        }

        const fragment =
            elements.cartTemplate.content.cloneNode(
                true
            );

        const line = fragment.querySelector(
            ".proforma-cart-line"
        );

        if (!line) {
            return;
        }

        line.dataset.productId =
            String(product.id);

        const productInput = line.querySelector(
            '[name="product"]'
        );

        const productLabelInput =
            line.querySelector(
                '[name="product_label"]'
            );

        const productNameElement =
            line.querySelector(
                ".js-product-name"
            );

        const productMetaElement =
            line.querySelector(
                ".js-product-meta"
            );

        const unitPriceInput =
            line.querySelector(
                ".js-unit-price"
            );

        if (productInput) {
            productInput.value =
                product.id;
        }

        if (productLabelInput) {
            productLabelInput.value =
                product.label;
        }

        if (productNameElement) {
            productNameElement.textContent =
                product.name;
        }

        if (productMetaElement) {
            productMetaElement.textContent =
                buildProductMeta(product);
        }

        if (unitPriceInput) {
            unitPriceInput.value =
                product.sale_price;
        }

        elements.cartLines.appendChild(
            fragment
        );

        bindCartLine(line);
        updateCartState();

        line.scrollIntoView({
            behavior: "smooth",
            block: "nearest",
        });
    }

    function createProductCard(product) {
        const fragment =
            elements.productTemplate.content.cloneNode(
                true
            );

        const card = fragment.querySelector(
            ".proforma-product-card"
        );

        if (!card) {
            return fragment;
        }

        const image = card.querySelector(
            ".js-card-image"
        );

        const fallback = card.querySelector(
            ".proforma-product-image-fallback"
        );

        const stockBadge = card.querySelector(
            ".js-card-stock"
        );

        const nameElement = card.querySelector(
            ".js-card-name"
        );

        const referenceElement =
            card.querySelector(
                ".js-card-reference"
            );

        const categoryElement =
            card.querySelector(
                ".js-card-category"
            );

        const priceElement = card.querySelector(
            ".js-card-price"
        );

        if (nameElement) {
            nameElement.textContent =
                product.name;
        }

        if (referenceElement) {
            referenceElement.textContent =
                product.reference
                    ? `Réf : ${product.reference}`
                    : "Sans référence";
        }

        if (categoryElement) {
            categoryElement.textContent =
                product.category ||
                "Sans catégorie";
        }

        if (priceElement) {
            priceElement.textContent =
                formatMoney(
                    parseNumber(
                        product.sale_price
                    )
                );
        }

        const stock = parseNumber(
            product.stock
        );

        if (stockBadge) {
            const unit = product.unit
                ? ` ${product.unit}`
                : "";

            stockBadge.textContent =
                `${stock}${unit}`;

            stockBadge.classList.toggle(
                "is-empty",
                stock <= 0
            );
        }

        if (product.image_url && image) {
            image.loading = "lazy";
            image.decoding = "async";
            image.src = product.image_url;
            image.alt = product.name;

            image.classList.add(
                "is-visible"
            );

            if (fallback) {
                fallback.classList.add(
                    "d-none"
                );
            }

            image.addEventListener(
                "error",
                () => {
                    image.classList.remove(
                        "is-visible"
                    );

                    if (fallback) {
                        fallback.classList.remove(
                            "d-none"
                        );
                    }
                }
            );
        }

        card.addEventListener(
            "click",
            () => {
                addProductToCart(product);
            }
        );

        return fragment;
    }

    function appendProducts(productList) {
        productList.forEach((product) => {
            const productId = String(
                product.id
            );

            state.productCache.set(
                productId,
                product
            );

            const card =
                createProductCard(product);

            elements.productGrid.appendChild(
                card
            );
        });

        elements.cartLines
            .querySelectorAll(
                ".proforma-cart-line"
            )
            .forEach((line) => {
                hydrateCartLine(line);
            });
    }

    function buildCategories(categories) {
        if (
            state.categoriesLoaded ||
            !Array.isArray(categories)
        ) {
            return;
        }

        categories.forEach((category) => {
            const option =
                document.createElement(
                    "option"
                );

            option.value = category;
            option.textContent = category;

            elements.category.appendChild(
                option
            );
        });

        state.categoriesLoaded = true;
    }

    function updateProductState() {
        const loadedCount =
            elements.productGrid.children.length;

        elements.loader.classList.add(
            "d-none"
        );

        elements.empty.classList.toggle(
            "d-none",
            loadedCount > 0
        );

        elements.productGrid.classList.toggle(
            "d-none",
            loadedCount === 0
        );

        elements.loadMoreWrap.classList.toggle(
            "d-none",
            !state.hasNext ||
            loadedCount === 0
        );

        if (state.totalCount > 0) {
            elements.productCount.textContent =
                `${loadedCount} / ` +
                `${state.totalCount} produits`;
        } else {
            elements.productCount.textContent =
                "0 produit";
        }
    }

    function setLoadMoreLoading(isLoading) {
        elements.loadMore.disabled =
            isLoading;

        if (isLoading) {
            elements.loadMore.innerHTML =
                '<span class="' +
                'spinner-border ' +
                'spinner-border-sm ' +
                'me-2"></span>' +
                "Chargement...";
        } else {
            elements.loadMore.innerHTML =
                '<i class="' +
                'bi bi-arrow-down-circle">' +
                "</i> " +
                "Charger plus de produits";
        }
    }

    function showLoadError() {
        elements.loader.classList.add(
            "d-none"
        );

        elements.loadMoreWrap.classList.add(
            "d-none"
        );

        if (
            elements.productGrid.children.length ===
            0
        ) {
            elements.empty.classList.remove(
                "d-none"
            );

            const title =
                elements.empty.querySelector(
                    "strong"
                );

            const description =
                elements.empty.querySelector(
                    "span"
                );

            if (title) {
                title.textContent =
                    "Impossible de charger les produits";
            }

            if (description) {
                description.textContent =
                    "Vérifiez le serveur puis " +
                    "actualisez la page.";
            }
        }

        elements.productCount.textContent =
            "Erreur";
    }

    async function loadProducts({
        reset = false,
    } = {}) {
        if (
            state.loading &&
            !reset
        ) {
            return;
        }

        if (
            reset &&
            state.requestController
        ) {
            state.requestController.abort();
        }

        state.requestController =
            new AbortController();

        state.loading = true;

        if (reset) {
            state.page = 1;
            state.hasNext = false;
            state.totalCount = 0;

            elements.productGrid.innerHTML =
                "";

            elements.loader.classList.remove(
                "d-none"
            );

            elements.empty.classList.add(
                "d-none"
            );

            elements.loadMoreWrap.classList.add(
                "d-none"
            );
        } else {
            setLoadMoreLoading(true);
        }

        const params = new URLSearchParams({
            page: String(state.page),
        });

        const query =
            elements.search.value.trim();

        const category =
            elements.category.value;

        if (query) {
            params.set("q", query);
        }

        if (category) {
            params.set(
                "category",
                category
            );
        }

        try {
            const response = await fetch(
                `${productsUrl}?${params.toString()}`,
                {
                    headers: {
                        "X-Requested-With":
                            "XMLHttpRequest",
                    },

                    signal:
                        state.requestController.signal,
                }
            );

            if (!response.ok) {
                throw new Error(
                    `Erreur HTTP ${response.status}`
                );
            }

            const data =
                await response.json();

            state.totalCount = Number(
                data.total_count || 0
            );

            state.hasNext = Boolean(
                data.has_next
            );

            buildCategories(
                data.categories
            );

            appendProducts(
                data.results || []
            );

            updateProductState();
        } catch (error) {
            if (
                error.name !==
                "AbortError"
            ) {
                console.error(
                    "Erreur de chargement des produits :",
                    error
                );

                showLoadError();
            }
        } finally {
            state.loading = false;

            setLoadMoreLoading(false);
        }
    }

    function restartSearch() {
        window.clearTimeout(
            state.searchTimer
        );

        state.searchTimer =
            window.setTimeout(() => {
                loadProducts({
                    reset: true,
                });
            }, 300);
    }

    elements.cartLines
        .querySelectorAll(
            ".proforma-cart-line"
        )
        .forEach((line) => {
            bindCartLine(line);
        });

    elements.search.addEventListener(
        "input",
        restartSearch
    );

    elements.category.addEventListener(
        "change",
        () => {
            loadProducts({
                reset: true,
            });
        }
    );

    if (elements.clearSearch) {
        elements.clearSearch.addEventListener(
            "click",
            () => {
                elements.search.value = "";
                elements.category.value = "";

                loadProducts({
                    reset: true,
                });

                elements.search.focus();
            }
        );
    }

    elements.loadMore.addEventListener(
        "click",
        () => {
            if (
                !state.hasNext ||
                state.loading
            ) {
                return;
            }

            state.page += 1;

            loadProducts();
        }
    );

    if (elements.globalDiscountInput) {
        elements.globalDiscountInput
            .addEventListener(
                "input",
                calculateTotals
            );
    }

    form.addEventListener(
        "submit",
        (event) => {
            const lines = Array.from(
                elements.cartLines.querySelectorAll(
                    ".proforma-cart-line"
                )
            );

            if (lines.length === 0) {
                event.preventDefault();

                window.alert(
                    "Ajoutez au moins un produit " +
                    "à la proforma."
                );

                return;
            }

            const invalidLine = lines.find(
                (line) => {
                    const productId =
                        line.querySelector(
                            '[name="product"]'
                        )?.value;

                    const quantity =
                        parseNumber(
                            line.querySelector(
                                ".js-quantity"
                            )?.value
                        );

                    const unitPrice =
                        parseNumber(
                            line.querySelector(
                                ".js-unit-price"
                            )?.value
                        );

                    const discount =
                        parseNumber(
                            line.querySelector(
                                ".js-line-discount"
                            )?.value
                        );

                    const grossTotal =
                        quantity * unitPrice;

                    return (
                        !productId ||
                        quantity <= 0 ||
                        unitPrice < 0 ||
                        discount < 0 ||
                        discount > grossTotal
                    );
                }
            );

            if (invalidLine) {
                event.preventDefault();

                window.alert(
                    "Vérifiez le produit, " +
                    "la quantité, le prix " +
                    "et la remise."
                );

                invalidLine.scrollIntoView({
                    behavior: "smooth",
                    block: "center",
                });
            }
        }
    );

    updateCartState();

    loadProducts({
        reset: true,
    });
});