"""Crop фрагмента изображения по bounding_box (День 40.4)."""
import io

from PIL import Image


def crop_image(
    image_path: str,
    bounding_box: dict,
    output_format: str = "PNG",
) -> bytes:
    """
    Вырезать фрагмент изображения.

    bounding_box: {"x", "y", "w", "h"}
    Возвращает bytes (PNG).
    """
    img = Image.open(image_path)
    x = bounding_box.get("x", 0)
    y = bounding_box.get("y", 0)
    w = bounding_box.get("w", img.width)
    h = bounding_box.get("h", img.height)

    # Защита от выхода за пределы
    x = max(0, min(x, img.width))
    y = max(0, min(y, img.height))
    w = max(1, min(w, img.width - x))
    h = max(1, min(h, img.height - y))

    cropped = img.crop((x, y, x + w, y + h))

    buf = io.BytesIO()
    cropped.save(buf, format=output_format)
    return buf.getvalue()