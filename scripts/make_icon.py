"""Draw the OfflinePDF app icon (assets/icon.png + assets/icon.ico) with Pillow.

Run: python scripts/make_icon.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
S = 1024  # draw large, downscale for crisp edges


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))


def gradient(size, top, bottom):
    image = Image.new("RGBA", (size, size))
    draw = ImageDraw.Draw(image)
    for y in range(size):
        draw.line([(0, y), (size, y)], fill=lerp(top, bottom, y / size) + (255,))
    return image


def rounded_mask(size, radius, box=None):
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(box or (0, 0, size - 1, size - 1), radius=radius, fill=255)
    return mask


def build() -> Image.Image:
    canvas = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    margin = 64
    bg_box = (margin, margin, S - margin, S - margin)

    # soft shadow
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((margin, margin + 24, S - margin, S - margin + 24), radius=210, fill=(20, 20, 60, 110))
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(28)))

    # background tile: indigo -> violet
    tile = gradient(S, (99, 102, 241), (124, 58, 237))
    canvas.paste(tile, (0, 0), rounded_mask(S, 210, bg_box))

    draw = ImageDraw.Draw(canvas)
    # document
    doc = (300, 210, 700, 760)
    fold = 120
    body = [(doc[0], doc[1]), (doc[2] - fold, doc[1]), (doc[2], doc[1] + fold), (doc[2], doc[3]), (doc[0], doc[3])]
    doc_shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(doc_shadow).polygon([(x + 14, y + 20) for x, y in body], fill=(30, 20, 90, 120))
    canvas.alpha_composite(doc_shadow.filter(ImageFilter.GaussianBlur(18)))
    draw = ImageDraw.Draw(canvas)
    draw.polygon(body, fill=(255, 255, 255, 255))
    draw.polygon([(doc[2] - fold, doc[1]), (doc[2] - fold, doc[1] + fold), (doc[2], doc[1] + fold)], fill=(214, 211, 255, 255))
    # "PDF" bars
    draw.rounded_rectangle((360, 400, 640, 436), radius=18, fill=(99, 102, 241, 255))
    draw.rounded_rectangle((360, 470, 600, 500), radius=15, fill=(203, 205, 236, 255))
    draw.rounded_rectangle((360, 530, 620, 560), radius=15, fill=(203, 205, 236, 255))
    draw.rounded_rectangle((360, 590, 540, 620), radius=15, fill=(203, 205, 236, 255))

    # shield badge (offline / private)
    cx, cy, r = 720, 740, 150
    badge_shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(badge_shadow).ellipse((cx - r + 8, cy - r + 14, cx + r + 8, cy + r + 14), fill=(10, 40, 30, 120))
    canvas.alpha_composite(badge_shadow.filter(ImageFilter.GaussianBlur(14)))
    draw = ImageDraw.Draw(canvas)
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(16, 185, 129, 255), outline=(255, 255, 255, 255), width=18)
    shield = [
        (cx, cy - 92),
        (cx + 74, cy - 62),
        (cx + 66, cy + 24),
        (cx, cy + 92),
        (cx - 66, cy + 24),
        (cx - 74, cy - 62),
    ]
    draw.polygon(shield, fill=(255, 255, 255, 255))
    draw.line([(cx - 34, cy + 2), (cx - 8, cy + 30), (cx + 40, cy - 30)], fill=(16, 185, 129, 255), width=22, joint="curve")
    return canvas


def main() -> None:
    assets = ROOT / "assets"
    assets.mkdir(exist_ok=True)
    big = build()
    big.resize((512, 512), Image.LANCZOS).save(assets / "icon.png")
    big.resize((256, 256), Image.LANCZOS).save(
        assets / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    )
    print("wrote", assets / "icon.png", assets / "icon.ico")


if __name__ == "__main__":
    main()
