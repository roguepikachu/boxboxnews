import io
from PIL import Image

from src.text_overlay import composite


def _make_test_image() -> bytes:
    img = Image.new("RGB", (1080, 1080), (50, 50, 100))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_composite_returns_png():
    result = composite(_make_test_image(), "HAMILTON TO FERRARI")
    img = Image.open(io.BytesIO(result))
    assert img.size == (1080, 1080)
    assert img.format == "PNG"


def test_composite_long_tagline():
    result = composite(_make_test_image(), "VERSTAPPEN SIGNS MEGA DEAL WITH MERCEDES")
    img = Image.open(io.BytesIO(result))
    assert img.size == (1080, 1080)
