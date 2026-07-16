import base64
from io import BytesIO


def generate_code128_data_uri(value):
    """
    Génère un code-barres Code 128 au format SVG encodé
    directement dans la page HTML.

    La fonction retourne une chaîne vide lorsque la
    bibliothèque python-barcode n'est pas installée.
    """
    cleaned_value = str(value or "").strip()

    if not cleaned_value:
        return ""

    try:
        from barcode.codex import Code128
        from barcode.writer import SVGWriter

        output = BytesIO()

        barcode = Code128(
            cleaned_value,
            writer=SVGWriter(),
        )

        barcode.write(
            output,
            options={
                "write_text": False,
                "module_width": 0.30,
                "module_height": 12.0,
                "quiet_zone": 1.5,
                "background": "white",
                "foreground": "black",
            },
        )

        encoded = base64.b64encode(
            output.getvalue()
        ).decode("ascii")

        return (
            "data:image/svg+xml;base64,"
            f"{encoded}"
        )

    except Exception:
        # Le document reste utilisable même si la
        # bibliothèque n'est pas encore installée.
        return ""