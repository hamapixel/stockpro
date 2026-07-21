document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("purchaseForm");

    const container = document.getElementById(
        "purchaseItemsContainer"
    );

    const emptyTemplate = document.getElementById(
        "emptyPurchaseRowTemplate"
    );

    const totalFormsInput = document.getElementById(
        "id_items-TOTAL_FORMS"
    );

    const searchInput = document.getElementById(
        "purchaseProductSearch"
    );

    const clearSearchButton = document.getElementById(
        "clearPurchaseSearch"
    );

    const categoryFilter = document.getElementById(
        "purchaseCategoryFilter"
    );

    const productGrid = document.getElementById(
        "purchaseProductGrid"
    );

    const noSearchResult = document.getElementById(
        "purchaseNoSearchResult"
    );

    const visibleProductCount = document.getElementById(
        "visibleProductCount"
    );

    const cartCount = document.getElementById(
        "purchaseCartCount"
    );

    const cartEmpty = document.getElementById(
        "purchaseCartEmpty"
    );

    if (
        !form
        || !container
        || !emptyTemplate
        || !totalFormsInput
        || !productGrid
    ) {
        return;
    }

    const productCards = Array.from(
        productGrid.querySelectorAll(
            "[data-product-card]"
        )
    );

    const productMap = new Map();

    productCards.forEach(function (card) {
        productMap.set(
            String(card.dataset.productId),
            {
                id: String(
                    card.dataset.productId
                ),

                name:
                    card.dataset.productName
                    || "Produit",

                reference:
                    card.dataset.productReference
                    || "Sans référence",

                barcode:
                    card.dataset.productBarcode
                    || "",

                categoryId:
                    card.dataset.productCategoryId
                    || "",

                category:
                    card.dataset.productCategory
                    || "",

                unit:
                    card.dataset.productUnit
                    || "",

                cost: parseNumber(
                    card.dataset.productCost
                ),

                card: card,
            }
        );
    });

    function parseNumber(value) {
        if (
            value === null
            || value === undefined
            || value === ""
        ) {
            return 0;
        }

        const normalizedValue = String(value)
            .replace(/\u00a0/g, "")
            .replace(/\s/g, "")
            .replace(",", ".");

        const parsedValue = Number.parseFloat(
            normalizedValue
        );

        return Number.isFinite(parsedValue)
            ? parsedValue
            : 0;
    }

    function formatFcfa(value) {
        return new Intl.NumberFormat(
            "fr-FR",
            {
                maximumFractionDigits: 0,
            }
        ).format(value) + " F CFA";
    }

    function getDeleteInput(row) {
        return row.querySelector(
            'input[name$="-DELETE"]'
        );
    }

    function getProductInput(row) {
        return row.querySelector(
            ".purchase-product-input"
        );
    }

    function isRowDeleted(row) {
        const deleteInput = getDeleteInput(
            row
        );

        return Boolean(
            deleteInput
            && deleteInput.checked
        );
    }

    function getActiveRows() {
        return Array.from(
            container.querySelectorAll(
                "[data-purchase-row]"
            )
        ).filter(function (row) {
            const productInput =
                getProductInput(row);

            return (
                !row.hidden
                && !isRowDeleted(row)
                && productInput
                && productInput.value
            );
        });
    }

    function findRowByProductId(
        productId
    ) {
        return getActiveRows().find(
            function (row) {
                const productInput =
                    getProductInput(row);

                return (
                    productInput
                    && String(
                        productInput.value
                    ) === String(productId)
                );
            }
        );
    }

    function updateSelectedProduct(
        row
    ) {
        const productInput =
            getProductInput(row);

        if (
            !productInput
            || !productInput.value
        ) {
            return;
        }

        const product = productMap.get(
            String(productInput.value)
        );

        if (!product) {
            return;
        }

        const nameElement =
            row.querySelector(
                "[data-selected-product-name]"
            );

        const referenceElement =
            row.querySelector(
                "[data-selected-product-reference]"
            );

        if (nameElement) {
            nameElement.textContent =
                product.name;
        }

        if (referenceElement) {
            const parts = [];

            if (product.reference) {
                parts.push(
                    "Réf. "
                    + product.reference
                );
            }

            if (product.unit) {
                parts.push(
                    "Unité : "
                    + product.unit
                );
            }

            referenceElement.textContent = (
                parts.join(" • ")
                || "Produit sélectionné"
            );
        }
    }

    function updateProductCardStates() {
        const selectedIds = new Set(
            getActiveRows().map(
                function (row) {
                    const productInput =
                        getProductInput(row);

                    return String(
                        productInput.value
                    );
                }
            )
        );

        productCards.forEach(
            function (card) {
                card.classList.toggle(
                    "is-selected",
                    selectedIds.has(
                        String(
                            card.dataset
                                .productId
                        )
                    )
                );
            }
        );
    }

    function updateCartState() {
        const rows = getActiveRows();
        const count = rows.length;

        if (cartCount) {
            cartCount.textContent =
                String(count);
        }

        if (cartEmpty) {
            cartEmpty.classList.toggle(
                "d-none",
                count > 0
            );
        }

        updateProductCardStates();
    }

    function calculateLine(row) {
        const quantityInput =
            row.querySelector(
                ".purchase-quantity"
            );

        const costInput =
            row.querySelector(
                ".purchase-unit-cost"
            );

        const discountInput =
            row.querySelector(
                ".purchase-line-discount"
            );

        const totalElement =
            row.querySelector(
                "[data-line-total]"
            );

        if (
            !quantityInput
            || !costInput
            || !discountInput
            || !totalElement
        ) {
            return 0;
        }

        const quantity = parseNumber(
            quantityInput.value
        );

        const unitCost = parseNumber(
            costInput.value
        );

        const discount = parseNumber(
            discountInput.value
        );

        let total = (
            quantity * unitCost
        ) - discount;

        if (total < 0) {
            total = 0;
        }

        totalElement.textContent =
            formatFcfa(total);

        return total;
    }

    function calculatePurchaseTotals() {
        let subtotal = 0;

        getActiveRows().forEach(
            function (row) {
                subtotal += calculateLine(
                    row
                );
            }
        );

        const globalDiscountInput =
            document.getElementById(
                "id_discount"
            );

        const initialPaymentInput =
            document.getElementById(
                "id_initial_payment"
            );

        const globalDiscount =
            parseNumber(
                globalDiscountInput
                    ? globalDiscountInput.value
                    : 0
            );

        const initialPayment =
            parseNumber(
                initialPaymentInput
                    ? initialPaymentInput.value
                    : 0
            );

        let total =
            subtotal - globalDiscount;

        if (total < 0) {
            total = 0;
        }

        let remaining =
            total - initialPayment;

        if (remaining < 0) {
            remaining = 0;
        }

        const subtotalElement =
            document.getElementById(
                "purchaseSubtotal"
            );

        const discountElement =
            document.getElementById(
                "purchaseDiscount"
            );

        const totalElement =
            document.getElementById(
                "purchaseTotal"
            );

        const paidElement =
            document.getElementById(
                "purchasePaid"
            );

        const remainingElement =
            document.getElementById(
                "purchaseRemaining"
            );

        if (subtotalElement) {
            subtotalElement.textContent =
                formatFcfa(subtotal);
        }

        if (discountElement) {
            discountElement.textContent =
                formatFcfa(
                    globalDiscount
                );
        }

        if (totalElement) {
            totalElement.textContent =
                formatFcfa(total);
        }

        if (paidElement) {
            paidElement.textContent =
                formatFcfa(
                    initialPayment
                );
        }

        if (remainingElement) {
            remainingElement.textContent =
                formatFcfa(remaining);
        }

        updateCartState();
    }

    function attachRowEvents(row) {
        const inputs =
            row.querySelectorAll(
                ".purchase-quantity, "
                + ".purchase-unit-cost, "
                + ".purchase-line-discount"
            );

        inputs.forEach(
            function (input) {
                input.addEventListener(
                    "input",
                    calculatePurchaseTotals
                );
            }
        );

        const removeButton =
            row.querySelector(
                "[data-remove-row]"
            );

        if (removeButton) {
            removeButton.addEventListener(
                "click",
                function () {
                    const deleteInput =
                        getDeleteInput(row);

                    if (deleteInput) {
                        deleteInput.checked =
                            true;
                    }

                    row.hidden = true;

                    calculatePurchaseTotals();
                }
            );
        }

        updateSelectedProduct(row);
    }

    function createNewRow() {
        const formIndex =
            Number.parseInt(
                totalFormsInput.value,
                10
            );

        const rowHtml =
            emptyTemplate.innerHTML.replace(
                /__prefix__/g,
                String(formIndex)
            );

        const temporaryContainer =
            document.createElement("div");

        temporaryContainer.innerHTML =
            rowHtml.trim();

        const newRow =
            temporaryContainer
                .firstElementChild;

        if (!newRow) {
            return null;
        }

        container.insertBefore(
            newRow,
            cartEmpty
        );

        totalFormsInput.value =
            String(formIndex + 1);

        attachRowEvents(newRow);

        return newRow;
    }

    function getReusableEmptyRow() {
        return Array.from(
            container.querySelectorAll(
                "[data-purchase-row]"
            )
        ).find(function (row) {
            const productInput =
                getProductInput(row);

            return (
                productInput
                && !productInput.value
            );
        });
    }

    function resetRowForUse(row) {
        const deleteInput =
            getDeleteInput(row);

        if (deleteInput) {
            deleteInput.checked = false;
        }

        row.hidden = false;
    }

    function addProductToCart(
        productId
    ) {
        const product = productMap.get(
            String(productId)
        );

        if (!product) {
            return;
        }

        const existingRow =
            findRowByProductId(
                product.id
            );

        if (existingRow) {
            const quantityInput =
                existingRow.querySelector(
                    ".purchase-quantity"
                );

            if (quantityInput) {
                const currentQuantity =
                    parseNumber(
                        quantityInput.value
                    );

                quantityInput.value =
                    String(
                        currentQuantity > 0
                            ? currentQuantity + 1
                            : 1
                    );

                quantityInput.focus();
                quantityInput.select();
            }

            existingRow.scrollIntoView({
                behavior: "smooth",
                block: "center",
            });

            calculatePurchaseTotals();

            return;
        }

        let row = getReusableEmptyRow();

        if (!row) {
            row = createNewRow();
        }

        if (!row) {
            return;
        }

        resetRowForUse(row);

        const productInput =
            getProductInput(row);

        const quantityInput =
            row.querySelector(
                ".purchase-quantity"
            );

        const costInput =
            row.querySelector(
                ".purchase-unit-cost"
            );

        const discountInput =
            row.querySelector(
                ".purchase-line-discount"
            );

        if (productInput) {
            productInput.value =
                product.id;
        }

        if (quantityInput) {
            quantityInput.value = "1";
        }

        if (costInput) {
            costInput.value = String(
                product.cost || 0
            );
        }

        if (discountInput) {
            discountInput.value = "0";
        }

        updateSelectedProduct(row);
        calculatePurchaseTotals();

        row.scrollIntoView({
            behavior: "smooth",
            block: "nearest",
        });

        if (quantityInput) {
            quantityInput.focus();
            quantityInput.select();
        }
    }

    function normalizeSearchText(
        value
    ) {
        return String(value || "")
            .toLocaleLowerCase("fr")
            .normalize("NFD")
            .replace(
                /[\u0300-\u036f]/g,
                ""
            )
            .trim();
    }

    function filterProducts() {
        const searchValue =
            normalizeSearchText(
                searchInput
                    ? searchInput.value
                    : ""
            );

        const categoryValue = (
            categoryFilter
                ? categoryFilter.value
                : ""
        );

        let visibleCount = 0;

        productCards.forEach(
            function (card) {
                const cardSearchText =
                    normalizeSearchText(
                        card.dataset
                            .searchText
                    );

                const matchesSearch = (
                    !searchValue
                    || cardSearchText.includes(
                        searchValue
                    )
                );

                const matchesCategory = (
                    !categoryValue
                    || String(
                        card.dataset
                            .productCategoryId
                    ) === String(
                        categoryValue
                    )
                );

                const isVisible = (
                    matchesSearch
                    && matchesCategory
                );

                card.hidden = !isVisible;

                if (isVisible) {
                    visibleCount += 1;
                }
            }
        );

        if (visibleProductCount) {
            visibleProductCount.textContent = (
                visibleCount
                + (
                    visibleCount > 1
                        ? " produits"
                        : " produit"
                )
            );
        }

        if (noSearchResult) {
            noSearchResult.classList.toggle(
                "d-none",
                visibleCount > 0
            );
        }
    }

    productCards.forEach(
        function (card) {
            card.addEventListener(
                "click",
                function () {
                    addProductToCart(
                        card.dataset
                            .productId
                    );
                }
            );
        }
    );

    if (searchInput) {
        searchInput.addEventListener(
            "input",
            filterProducts
        );
    }

    if (clearSearchButton) {
        clearSearchButton.addEventListener(
            "click",
            function () {
                if (searchInput) {
                    searchInput.value = "";
                    searchInput.focus();
                }

                filterProducts();
            }
        );
    }

    if (categoryFilter) {
        categoryFilter.addEventListener(
            "change",
            filterProducts
        );
    }

    const globalDiscountInput =
        document.getElementById(
            "id_discount"
        );

    const initialPaymentInput =
        document.getElementById(
            "id_initial_payment"
        );

    if (globalDiscountInput) {
        globalDiscountInput
            .addEventListener(
                "input",
                calculatePurchaseTotals
            );
    }

    if (initialPaymentInput) {
        initialPaymentInput
            .addEventListener(
                "input",
                calculatePurchaseTotals
            );
    }

    Array.from(
        container.querySelectorAll(
            "[data-purchase-row]"
        )
    ).forEach(function (row) {
        const productInput =
            getProductInput(row);

        if (
            !productInput
            || !productInput.value
            || isRowDeleted(row)
        ) {
            row.hidden = true;
        } else {
            row.hidden = false;
        }

        attachRowEvents(row);
    });

    form.addEventListener(
        "submit",
        function (event) {
            if (
                getActiveRows().length === 0
            ) {
                event.preventDefault();

                window.alert(
                    "Ajoutez au moins un produit "
                    + "à l’approvisionnement."
                );

                if (searchInput) {
                    searchInput.focus();
                }

                return;
            }

            const submitButton =
                document.getElementById(
                    "submitPurchaseButton"
                );

            if (!submitButton) {
                return;
            }

            submitButton.disabled = true;

            submitButton.innerHTML = `
                <span
                    class="spinner-border spinner-border-sm"
                    aria-hidden="true"
                ></span>
                Enregistrement...
            `;
        }
    );

    filterProducts();
    calculatePurchaseTotals();

    if (searchInput) {
        searchInput.focus();
    }
});