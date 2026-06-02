import io
from PIL import Image, ImageDraw, ImageFont

FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/nix/var/nix/profiles/default/share/fonts/truetype/DejaVuSans-Bold.ttf",
]


def _get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def make_banner(
    text: str,
    bg: tuple = (180, 0, 0),
    fg: tuple = (255, 255, 255),
    width: int = 900,
    height: int = 150,
    font_size: int = 64,
) -> io.BytesIO:
    img  = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)
    font = _get_font(font_size)

    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x  = (width  - tw) / 2 - bbox[0]
    y  = (height - th) / 2 - bbox[1]
    draw.text((x, y), text, fill=fg, font=font)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
