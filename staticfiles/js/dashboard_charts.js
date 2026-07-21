document.addEventListener("DOMContentLoaded", function () {
    const chartDataElement = document.getElementById(
        "dashboardChartData"
    );

    if (
        !chartDataElement
        || typeof Chart === "undefined"
    ) {
        return;
    }

    function parseNumber(value) {
        if (
            value === null
            || value === undefined
            || value === ""
        ) {
            return 0;
        }

        const cleanedValue = String(value)
            .replace(/\u00a0/g, "")
            .replace(/\s/g, "")
            .replace(",", ".");

        const parsedValue = Number.parseFloat(
            cleanedValue
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

    const values = {
        today: parseNumber(
            chartDataElement.dataset.today
        ),
        yesterday: parseNumber(
            chartDataElement.dataset.yesterday
        ),
        week: parseNumber(
            chartDataElement.dataset.week
        ),
        month: parseNumber(
            chartDataElement.dataset.month
        ),
        paid: parseNumber(
            chartDataElement.dataset.paid
        ),
        credit: parseNumber(
            chartDataElement.dataset.credit
        ),
        expenses: parseNumber(
            chartDataElement.dataset.expenses
        ),
        filteredTotal: parseNumber(
            chartDataElement.dataset.filteredTotal
        ),
        periodTitle:
            chartDataElement.dataset.periodTitle
            || "Période",
    };

    Chart.defaults.font.family = (
        "Inter, system-ui, -apple-system, "
        + "BlinkMacSystemFont, 'Segoe UI', sans-serif"
    );

    Chart.defaults.color = "#667085";

    const salesCanvas = document.getElementById(
        "salesComparisonChart"
    );

    if (salesCanvas) {
        const salesContext = salesCanvas.getContext(
            "2d"
        );

        const blueGradient =
            salesContext.createLinearGradient(
                0,
                0,
                0,
                320
            );

        blueGradient.addColorStop(
            0,
            "rgba(37, 99, 235, 0.95)"
        );

        blueGradient.addColorStop(
            1,
            "rgba(37, 99, 235, 0.30)"
        );

        const greenGradient =
            salesContext.createLinearGradient(
                0,
                0,
                0,
                320
            );

        greenGradient.addColorStop(
            0,
            "rgba(22, 163, 74, 0.92)"
        );

        greenGradient.addColorStop(
            1,
            "rgba(22, 163, 74, 0.28)"
        );

        new Chart(
            salesContext,
            {
                type: "bar",
                data: {
                    labels: [
                        "Aujourd’hui",
                        "Hier",
                        "Semaine",
                        "Mois",
                    ],
                    datasets: [
                        {
                            label: "Ventes",
                            data: [
                                values.today,
                                values.yesterday,
                                values.week,
                                values.month,
                            ],
                            backgroundColor: [
                                blueGradient,
                                "rgba(245, 158, 11, 0.78)",
                                "rgba(124, 58, 237, 0.78)",
                                greenGradient,
                            ],
                            borderColor: [
                                "#2563eb",
                                "#f59e0b",
                                "#7c3aed",
                                "#16a34a",
                            ],
                            borderWidth: 1,
                            borderRadius: 12,
                            borderSkipped: false,
                            maxBarThickness: 62,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: {
                        duration: 900,
                        easing: "easeOutQuart",
                    },
                    interaction: {
                        intersect: false,
                        mode: "index",
                    },
                    plugins: {
                        legend: {
                            display: false,
                        },
                        tooltip: {
                            backgroundColor: "#0f172a",
                            titleColor: "#ffffff",
                            bodyColor: "#ffffff",
                            padding: 12,
                            cornerRadius: 10,
                            callbacks: {
                                label: function (context) {
                                    return formatFcfa(
                                        context.raw || 0
                                    );
                                },
                            },
                        },
                    },
                    scales: {
                        x: {
                            grid: {
                                display: false,
                            },
                            border: {
                                display: false,
                            },
                            ticks: {
                                color: "#667085",
                                font: {
                                    size: 11,
                                    weight: "600",
                                },
                            },
                        },
                        y: {
                            beginAtZero: true,
                            border: {
                                display: false,
                            },
                            grid: {
                                color: "rgba(148, 163, 184, 0.18)",
                                drawTicks: false,
                            },
                            ticks: {
                                color: "#98a2b3",
                                padding: 10,
                                callback: function (value) {
                                    return new Intl.NumberFormat(
                                        "fr-FR",
                                        {
                                            notation: "compact",
                                            maximumFractionDigits: 1,
                                        }
                                    ).format(value);
                                },
                            },
                        },
                    },
                },
            }
        );
    }

    const centerTextPlugin = {
        id: "dashboardCenterText",

        afterDraw: function (chart) {
            if (
                chart.config.type !== "doughnut"
                || !chart.chartArea
            ) {
                return;
            }

            const context = chart.ctx;
            const chartArea = chart.chartArea;

            const centerX = (
                chartArea.left
                + chartArea.right
            ) / 2;

            const centerY = (
                chartArea.top
                + chartArea.bottom
            ) / 2;

            context.save();

            context.textAlign = "center";
            context.textBaseline = "middle";

            context.fillStyle = "#667085";

            context.font = (
                "600 11px Inter, system-ui, sans-serif"
            );

            context.fillText(
                "VENTES DU JOUR",
                centerX,
                centerY - 13
            );

            context.fillStyle = "#172033";

            context.font = (
                "800 16px Inter, system-ui, sans-serif"
            );

            context.fillText(
                formatFcfa(
                    values.paid + values.credit
                ),
                centerX,
                centerY + 11
            );

            context.restore();
        },
    };

    const donutCanvas = document.getElementById(
        "paymentDistributionChart"
    );

    if (donutCanvas) {
        const donutContext = donutCanvas.getContext(
            "2d"
        );

        const totalDistribution = (
            values.paid
            + values.credit
        );

        const hasData = totalDistribution > 0;

        new Chart(
            donutContext,
            {
                type: "doughnut",

                data: {
                    labels: hasData
                        ? [
                            "Encaissé",
                            "Crédit",
                        ]
                        : [
                            "Aucune vente",
                        ],

                    datasets: [
                        {
                            data: hasData
                                ? [
                                    values.paid,
                                    values.credit,
                                ]
                                : [
                                    1,
                                ],

                            backgroundColor: hasData
                                ? [
                                    "#16a34a",
                                    "#f59e0b",
                                ]
                                : [
                                    "#e2e8f0",
                                ],

                            borderColor: "#ffffff",
                            borderWidth: 6,

                            hoverOffset: hasData
                                ? 8
                                : 0,

                            borderRadius: 8,
                        },
                    ],
                },

                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: "72%",

                    animation: {
                        duration: 950,
                        easing: "easeOutQuart",
                    },

                    plugins: {
                        legend: {
                            display: false,
                        },

                        tooltip: {
                            enabled: hasData,
                            backgroundColor: "#0f172a",
                            titleColor: "#ffffff",
                            bodyColor: "#ffffff",
                            padding: 12,
                            cornerRadius: 10,

                            callbacks: {
                                label: function (context) {
                                    const amount = (
                                        context.raw || 0
                                    );

                                    const percentage = (
                                        totalDistribution > 0
                                            ? (
                                                amount
                                                / totalDistribution
                                                * 100
                                            )
                                            : 0
                                    );

                                    return (
                                        context.label
                                        + " : "
                                        + formatFcfa(amount)
                                        + " ("
                                        + percentage.toFixed(1)
                                        + " %)"
                                    );
                                },
                            },
                        },
                    },
                },

                plugins: [
                    centerTextPlugin,
                ],
            }
        );
    }
});