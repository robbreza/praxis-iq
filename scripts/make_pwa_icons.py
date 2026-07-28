"""Generate the IRconnect PWA app icons (reproducible — commit the script, not just the PNGs).

A simple lighthouse mark in white on the brand blue: on-brand (the flagship feature is Lighthouse; a
lighthouse is also the natural "guiding light for IR" metaphor) and legible as a home-screen icon at
small sizes. Full-bleed background with the mark inside the central safe zone, so the same art works
both as a standard icon and as an Android maskable icon (purpose "any maskable").

Run:  python scripts/make_pwa_icons.py
Outputs: assets/pwa/icon-192.png, icon-512.png, apple-touch-icon.png (+ maskable variants).
"""
from __future__ import annotations
import os
from PIL import Image, ImageDraw, ImageFont

BRAND = (30, 64, 175)        # #1E40AF
WHITE = (255, 255, 255)
BEAM = (147, 178, 232)       # light beam / window tint
SS = 4                       # supersample for anti-aliasing
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "pwa")


def _load_font(px: int):
    for p in (r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\arialbd.ttf",
              "DejaVuSans-Bold.ttf", "arialbd.ttf"):
        try:
            return ImageFont.truetype(p, px)
        except Exception:
            continue
    return ImageFont.load_default()


def _draw_lighthouse(S: int, wordmark: bool = False) -> Image.Image:
    W = S * SS
    img = Image.new("RGBA", (W, W), BRAND + (255,))
    d = ImageDraw.Draw(img)

    # When the wordmark is shown, shrink the mark and lift it so the text has room below; keep the
    # mark within the central safe zone either way (so the text-free maskable variant crops cleanly).
    sc = 0.80 if wordmark else 1.0
    vc = 0.44 if wordmark else 0.50

    def px(fx, fy):
        return ((0.5 + (fx - 0.5) * sc) * W, (vc + (fy - 0.5) * sc) * W)

    def hw_at(y, base_y, base_hw, top_y, top_hw):
        t = (base_y - y) / (base_y - top_y)
        return base_hw + (top_hw - base_hw) * t

    cx = 0.5
    base_y, top_y = 0.72, 0.36
    base_hw, top_hw = 0.125, 0.085

    # light beams (behind the tower) — two soft symmetrical rays from the lantern
    ly = 0.30
    for dx in (-1, 1):
        d.polygon([px(cx, ly), px(cx + dx * 0.42, 0.14), px(cx + dx * 0.42, 0.30)], fill=BEAM + (150,))

    # base platform
    d.rounded_rectangle([px(cx - 0.17, 0.72)[0], px(0, 0.72)[1],
                         px(cx + 0.17, 0.80)[0], px(0, 0.80)[1]], radius=0.02 * W, fill=WHITE)

    # tower (tapered)
    d.polygon([px(cx - base_hw, base_y), px(cx + base_hw, base_y),
               px(cx + top_hw, top_y), px(cx - top_hw, top_y)], fill=WHITE)

    # two brand-blue stripes across the tower
    for sy in (0.50, 0.615):
        h = 0.045
        hw_hi = hw_at(sy, base_y, base_hw, top_y, top_hw)
        hw_lo = hw_at(sy + h, base_y, base_hw, top_y, top_hw)
        d.polygon([px(cx - hw_hi, sy), px(cx + hw_hi, sy),
                   px(cx + hw_lo, sy + h), px(cx - hw_lo, sy + h)], fill=BRAND + (255,))

    # gallery (platform under the lantern)
    d.rounded_rectangle([px(cx - 0.115, 0.335)[0], px(0, 0.335)[1],
                         px(cx + 0.115, 0.365)[0], px(0, 0.365)[1]], radius=0.01 * W, fill=WHITE)

    # lantern room + a lit window
    d.rectangle([px(cx - 0.075, 0.265)[0], px(0, 0.265)[1],
                 px(cx + 0.075, 0.335)[0], px(0, 0.335)[1]], fill=WHITE)
    d.rectangle([px(cx - 0.045, 0.285)[0], px(0, 0.285)[1],
                 px(cx + 0.045, 0.325)[0], px(0, 0.325)[1]], fill=BEAM + (255,))

    # roof
    d.polygon([px(cx, 0.205), px(cx - 0.10, 0.265), px(cx + 0.10, 0.265)], fill=WHITE)
    d.ellipse([px(cx - 0.016, 0.188)[0], px(0, 0.188)[1],
               px(cx + 0.016, 0.214)[0], px(0, 0.214)[1]], fill=WHITE)

    if wordmark:
        # "IRconnect" wordmark, fit to a target width within the safe zone. "IR" carries the accent
        # tint so the brand reads even at a glance; the rest is white.
        target_w = 0.82 * W
        fpx = int(0.16 * W)
        font = _load_font(fpx)
        tw = d.textlength("IRconnect", font=font)
        if tw > 0:
            fpx = max(8, int(fpx * target_w / tw))
            font = _load_font(fpx)
        y = 0.845 * W
        # draw as two runs ("IR" tinted, "connect" white) kept centred as one word
        full_w = d.textlength("IRconnect", font=font)
        ir_w = d.textlength("IR", font=font)
        x0 = 0.5 * W - full_w / 2
        d.text((x0, y), "IR", font=font, fill=BEAM + (255,), anchor="lm")
        d.text((x0 + ir_w, y), "connect", font=font, fill=WHITE, anchor="lm")

    return img.resize((S, S), Image.LANCZOS)


def main():
    os.makedirs(OUT, exist_ok=True)
    for size in (192, 512):
        # Standard ("any") icons carry the IRconnect wordmark — the branding opportunity; the maskable
        # variants stay text-free because Android crops them to circles/squircles and edge text clips.
        _draw_lighthouse(size, wordmark=True).save(os.path.join(OUT, f"icon-{size}.png"))
        _draw_lighthouse(size, wordmark=False).save(os.path.join(OUT, f"icon-maskable-{size}.png"))
    # apple-touch-icon: 180x180, opaque (iOS ignores alpha and rounds corners itself)
    _draw_lighthouse(180, wordmark=True).convert("RGB").save(os.path.join(OUT, "apple-touch-icon.png"))
    print(f"wrote icons to {OUT}: " + ", ".join(sorted(os.listdir(OUT))))


if __name__ == "__main__":
    main()
