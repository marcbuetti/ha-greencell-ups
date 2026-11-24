"""Render the integration brand images (custom_components/greencell_ups/brand/*.png).

Original artwork: green rounded tile with a battery and a lightning bolt.
No Green Cell or Home Assistant marks.  Run: python3 tools/make_icon.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "custom_components" / "greencell_ups" / "brand"
S = 2048  # draw large, downsample for clean anti-aliasing

TOP = (0x4C, 0xD1, 0x6A)
BOTTOM = (0x0E, 0x8A, 0x3E)


def icon() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    grad = Image.new("RGBA", (S, S))
    gd = ImageDraw.Draw(grad)
    for y in range(S):
        t = y / (S - 1)
        gd.line(
            [(0, y), (S, y)],
            fill=tuple(round(a + (b - a) * t) for a, b in zip(TOP, BOTTOM, strict=True)) + (255,),
        )
    mask = Image.new("L", (S, S), 0)
    pad = int(S * 0.02)
    ImageDraw.Draw(mask).rounded_rectangle(
        [pad, pad, S - pad, S - pad], radius=int(S * 0.22), fill=255
    )
    img.paste(grad, (0, 0), mask)

    d = ImageDraw.Draw(img)
    white = (255, 255, 255, 255)

    # battery body (outline) + terminal on top
    bx0, by0, bx1, by1 = int(S * 0.29), int(S * 0.24), int(S * 0.71), int(S * 0.86)
    stroke = int(S * 0.055)
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=int(S * 0.07), outline=white, width=stroke)
    tw = int(S * 0.16)
    d.rounded_rectangle(
        [S // 2 - tw // 2, int(S * 0.15), S // 2 + tw // 2, by0 + stroke],
        radius=int(S * 0.03),
        fill=white,
    )
    # lightning bolt inside the battery
    cx, cy = S / 2, (by0 + by1) / 2 + S * 0.01
    k = S * 0.00135
    bolt = [(25, -160), (-80, 20), (-8, 20), (-30, 160), (80, -25), (8, -25)]
    d.polygon([(cx + x * k, cy + y * k) for x, y in bolt], fill=white)
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    big = icon()
    for name, size in (("icon.png", 256), ("icon@2x.png", 512)):
        big.resize((size, size), Image.LANCZOS).save(OUT / name, optimize=True)
        print("wrote", OUT / name)


if __name__ == "__main__":
    main()
