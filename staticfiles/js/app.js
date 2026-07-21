document.addEventListener("DOMContentLoaded", function () {
    /*
    =========================================================
    MENU LATÉRAL : CONSERVATION DE LA POSITION
    =========================================================
    */

    const scrollMenus = document.querySelectorAll(
        "[data-preserve-scroll]"
    );

    scrollMenus.forEach(function (menu, index) {
        const storageKey =
            menu.dataset.scrollKey ||
            `stock-single-sidebar-${index}`;

        const savedPosition =
            sessionStorage.getItem(storageKey);

        if (savedPosition !== null) {
            menu.scrollTop =
                Number.parseInt(savedPosition, 10) || 0;
        }

        function saveScrollPosition() {
            sessionStorage.setItem(
                storageKey,
                String(menu.scrollTop)
            );
        }

        menu.addEventListener(
            "scroll",
            saveScrollPosition,
            { passive: true }
        );

        menu.querySelectorAll(".nav-link").forEach(function (link) {
            link.addEventListener(
                "click",
                saveScrollPosition
            );
        });

        window.addEventListener(
            "beforeunload",
            saveScrollPosition
        );

        if (savedPosition === null) {
            const activeLink =
                menu.querySelector(".nav-link.active");

            if (activeLink) {
                requestAnimationFrame(function () {
                    activeLink.scrollIntoView({
                        behavior: "auto",
                        block: "nearest",
                    });
                });
            }
        }
    });

    /*
    =========================================================
    FERMETURE AUTOMATIQUE DU MENU MOBILE
    =========================================================
    */

    const mobileMenuElement =
        document.getElementById("mobileMenu");

    if (mobileMenuElement) {
        mobileMenuElement
            .querySelectorAll("a.nav-link")
            .forEach(function (link) {
                link.addEventListener("click", function () {
                    const bootstrapOffcanvas =
                        bootstrap.Offcanvas.getInstance(
                            mobileMenuElement
                        );

                    if (bootstrapOffcanvas) {
                        bootstrapOffcanvas.hide();
                    }
                });
            });
    }

    /*
    =========================================================
    TABLEAUX : AJOUT AUTOMATIQUE DU CONTENEUR RESPONSIVE
    =========================================================
    */

    document.querySelectorAll("table").forEach(function (table) {
        const parent = table.parentElement;

        if (
            parent &&
            !parent.classList.contains("table-responsive") &&
            !table.closest(".document") &&
            !table.closest(".receipt")
        ) {
            const wrapper = document.createElement("div");
            wrapper.className = "table-responsive";

            parent.insertBefore(wrapper, table);
            wrapper.appendChild(table);
        }
    });

    /*
    =========================================================
    BOUTONS DE FORMULAIRE : ÉVITER LES DOUBLES CLICS
    =========================================================
    */

    document
        .querySelectorAll("form")
        .forEach(function (form) {
            form.addEventListener("submit", function () {
                const submitButton = form.querySelector(
                    'button[type="submit"]'
                );

                if (!submitButton) {
                    return;
                }

                submitButton.disabled = true;
                submitButton.classList.add("is-loading");

                const originalContent =
                    submitButton.innerHTML;

                submitButton.dataset.originalContent =
                    originalContent;

                submitButton.innerHTML = `
                    <span
                        class="spinner-border spinner-border-sm"
                        aria-hidden="true"
                    ></span>
                    Traitement...
                `;

                window.setTimeout(function () {
                    submitButton.disabled = false;
                    submitButton.classList.remove("is-loading");

                    submitButton.innerHTML =
                        submitButton.dataset.originalContent ||
                        originalContent;
                }, 7000);
            });
        });

    /*
    =========================================================
    ALERTES AUTOMATIQUES
    =========================================================
    */

    document
        .querySelectorAll(".alert-dismissible")
        .forEach(function (alertElement) {
            window.setTimeout(function () {
                if (!document.body.contains(alertElement)) {
                    return;
                }

                const alertInstance =
                    bootstrap.Alert.getOrCreateInstance(
                        alertElement
                    );

                alertInstance.close();
            }, 6000);
        });

    /*
    =========================================================
    EMPÊCHER LES DÉBORDEMENTS DES GRANDS TEXTES
    =========================================================
    */

    document
        .querySelectorAll(
            ".stat-card h4, .mini-card strong, .summary-box strong"
        )
        .forEach(function (element) {
            element.setAttribute(
                "title",
                element.textContent.trim()
            );
        });
});