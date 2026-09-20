from PIL import Image
from rembg import remove


def remove_background(image: Image.Image) -> Image.Image:
    """Return an RGBA image with the background removed (for parallax foreground layers)."""
    return remove(image)
