import base64
from io import BytesIO


def generate_code128_data_uri(value):
    """
    Génère un code-barres Code 128 au format SVG.
    Retourne une chaîne vide si python-barcode
    n’est pas encore installé.
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
        return ""