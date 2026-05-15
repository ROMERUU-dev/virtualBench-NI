from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = PROJECT_ROOT / "assets" / "branding"
PNG_PATH = ASSET_DIR / "vbarrido-icon.png"
ICO_PATH = ASSET_DIR / "vbarrido.ico"


def _rounded_gradient(size: int) -> Image.Image:
    base = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pixels = base.load()
    for y in range(size):
        for x in range(size):
            fx = x / max(size - 1, 1)
            fy = y / max(size - 1, 1)
            r = round(7 + 6 * fx + 2 * fy)
            g = round(17 + 10 * fx + 7 * fy)
            b = round(31 + 20 * fx + 12 * fy)
            pixels[x, y] = (r, g, b, 255)

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((24, 24, size - 24, size - 24), radius=220, fill=255)
    base.putalpha(mask)
    return base


def build_icon(size: int = 1024) -> Image.Image:
    icon = _rounded_gradient(size)
    draw = ImageDraw.Draw(icon)

    # Soft outer accent.
    border = Image.new("RGBA", icon.size, (0, 0, 0, 0))
    border_draw = ImageDraw.Draw(border)
    border_draw.rounded_rectangle(
        (36, 36, size - 36, size - 36),
        radius=208,
        outline=(38, 198, 218, 120),
        width=18,
    )
    icon = Image.alpha_composite(icon, border)
    draw = ImageDraw.Draw(icon)

    # Subtle instrument grid.
    grid_color = (142, 165, 190, 42)
    left, top, right, bottom = 170, 190, 850, 820
    for fraction in (0.25, 0.5, 0.75):
        x = round(left + (right - left) * fraction)
        y = round(top + (bottom - top) * fraction)
        draw.line((x, top, x, bottom), fill=grid_color, width=8)
        draw.line((left, y, right, y), fill=grid_color, width=8)

    axis_color = (194, 214, 235, 185)
    draw.line((left, bottom, right, bottom), fill=axis_color, width=18)
    draw.line((left, top, left, bottom), fill=axis_color, width=18)

    # Soft glow behind the response curve.
    response_points = [
        (192, 288),
        (318, 302),
        (438, 332),
        (546, 392),
        (640, 500),
        (720, 650),
        (818, 770),
    ]
    glow = Image.new("RGBA", icon.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.line(response_points, fill=(45, 212, 191, 120), width=58, joint="curve")
    glow = glow.filter(ImageFilter.GaussianBlur(radius=14))
    icon = Image.alpha_composite(icon, glow)
    draw = ImageDraw.Draw(icon)

    # Main gain curve.
    draw.line(response_points, fill=(45, 212, 191, 255), width=34, joint="curve")

    # Secondary phase cue, kept restrained so the icon stays readable when small.
    phase_points = [
        (208, 628),
        (344, 618),
        (474, 594),
        (594, 548),
        (700, 470),
        (812, 350),
    ]
    draw.line(phase_points, fill=(251, 146, 60, 235), width=22, joint="curve")

    # Measurement nodes.
    for x, y in (response_points[0], response_points[3], response_points[-1]):
        draw.ellipse((x - 26, y - 26, x + 26, y + 26), fill=(238, 252, 255, 255))
        draw.ellipse((x - 14, y - 14, x + 14, y + 14), fill=(45, 212, 191, 255))

    return icon


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    icon = build_icon()
    icon.save(PNG_PATH)
    icon.save(
        ICO_PATH,
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"Generated {PNG_PATH}")
    print(f"Generated {ICO_PATH}")


if __name__ == "__main__":
    main()
