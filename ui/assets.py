from PIL import Image, ImageDraw
import customtkinter as ctk

from core.utils import resource_path


def load_ui_assets():
    logo_path = resource_path("assets\\logo_z.png")
    map_path = resource_path("assets\\world_map.png")
    logo_image = _open_or_build_logo(logo_path)
    map_image = _open_or_build_world_map(map_path)
    telegram_ctk = _load_telegram_logo_ctk()
    return {
        "logo": ctk.CTkImage(light_image=logo_image, dark_image=logo_image, size=(180, 120)),
        "map": ctk.CTkImage(light_image=map_image, dark_image=map_image, size=(306, 150)),
        "telegram": telegram_ctk,
    }


# Display size for the sidebar Telegram card (source may be 512×512 or larger).
TELEGRAM_ICON_DISPLAY_SIZE = (48, 48)


def _load_telegram_logo_ctk():
    path = resource_path("assets\\tg_logo.png")
    try:
        raw = Image.open(path).convert("RGBA")
        w, h = TELEGRAM_ICON_DISPLAY_SIZE
        return ctk.CTkImage(light_image=raw, dark_image=raw, size=(w, h))
    except OSError:
        return None


def _open_or_build_logo(path: str):
    try:
        return _remove_black_background(Image.open(path))
    except OSError:
        return _build_fallback_logo()


def _open_or_build_world_map(path: str):
    try:
        image = Image.open(path).convert("RGBA")
        return _stamp_stockholm_marker(image)
    except OSError:
        return _build_fallback_world_map()


def _remove_black_background(image: Image.Image):
    image = image.convert("RGBA")
    pixels = image.load()
    width, height = image.size
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if r <= 12 and g <= 12 and b <= 12:
                pixels[x, y] = (r, g, b, 0)
    return image


def _stamp_stockholm_marker(image: Image.Image):
    image = image.copy().convert("RGBA")
    draw = ImageDraw.Draw(image)
    x = int(image.width * 0.645)
    y = int(image.height * 0.41)
    draw.ellipse((x - 10, y - 10, x + 10, y + 10), fill=(86, 207, 243, 120))
    draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill="#56CFF3", outline="#B9F4FF", width=2)
    return image


def _build_fallback_logo():
    image = Image.new("RGBA", (900, 600), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    cyan = (72, 226, 245, 255)
    shadow = (20, 62, 75, 55)
    outer = [(110, 120), (740, 120), (610, 220), (300, 220), (720, 470), (110, 470), (250, 360), (540, 360)]
    inner = [(225, 172), (625, 172), (510, 250), (365, 250), (615, 416), (215, 416), (320, 336), (473, 336)]
    draw.polygon([(x + 10, y + 12) for x, y in outer], fill=shadow)
    draw.polygon(outer, fill=cyan)
    draw.polygon(inner, fill=(238, 249, 252, 255))
    return image


def _build_fallback_world_map():
    image = Image.new("RGBA", (612, 300), "#F7F8FA")
    draw = ImageDraw.Draw(image)
    land = "#E4E7EC"
    continents = [
        [(36, 74), (92, 48), (164, 56), (180, 86), (134, 112), (80, 100)],
        [(140, 126), (188, 102), (212, 132), (210, 194), (162, 238), (134, 206)],
        [(230, 72), (310, 46), (420, 58), (480, 92), (446, 120), (372, 126), (282, 110)],
        [(372, 150), (416, 136), (470, 148), (514, 190), (474, 226), (404, 208)],
        [(516, 210), (548, 194), (574, 220), (544, 250)],
    ]
    for polygon in continents:
        draw.polygon(polygon, fill=land)
    return _stamp_stockholm_marker(image)
