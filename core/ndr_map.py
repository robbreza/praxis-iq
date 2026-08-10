"""
core/ndr_map.py — a printable street-map of an NDR's route, to attach to the itinerary.

Given a trip's ordered stops (hotel + meetings in schedule order) it geocodes each stop
(core.routing, the same ORS key the itinerary already uses), pulls the real driving
polyline between consecutive stops, composites OpenStreetMap tiles into a base image
(PIL), and draws the route, numbered stop markers (schedule order), the hotel, a legend,
a scale bar and OSM attribution — returning PNG bytes.

Best-effort: a missing routing key or an ungeocodable stop degrades (skips the route
line / that marker) rather than raising. `build_route_map` returns None when nothing can
be placed, so callers can fall back to a plain message. Tiles and geometry are cached in
db (via routing), so a re-export makes zero new network calls.

Public API:
    build_route_map(hotel, meetings, focus=None, title=..., subtitle=...) -> bytes | None
"""

import io
import math

import requests

from core import routing

_TILE = 256
_MAX_Z = 16
_MIN_Z = 3
_UA = {"User-Agent": "PraxisPointIR-NDR-map/1.0 (IR roadshow itinerary)"}
_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"

# palette (matches the app's indigo/blue/emerald tokens)
_ROUTE = (79, 70, 229)          # indigo-600
_ROUTE_HALO = (255, 255, 255)
_PIN = (37, 99, 235)            # blue-600
_PIN_HOTEL = (5, 150, 105)      # emerald-600
_INK = (17, 24, 39)             # slate-900
_MUTED = (100, 116, 139)        # slate-500
_PANEL = (255, 255, 255)
_ANCHOR = (30, 41, 59)          # true-location dot


# ---- Web-Mercator (slippy-tile) projection -------------------------------------------

def _lonlat_to_world(lon, lat, z):
    """(lon, lat) -> global pixel coords at zoom z (top-left origin)."""
    n = _TILE * (2 ** z)
    x = (lon + 180.0) / 360.0 * n
    s = math.sin(math.radians(max(-85.05, min(85.05, lat))))
    y = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n
    return x, y


def _pick_zoom(pts, w, h, pad):
    """Largest zoom at which every point fits in a w×h canvas with `pad` margin."""
    for z in range(_MAX_Z, _MIN_Z - 1, -1):
        xs, ys = [], []
        for lon, lat in pts:
            x, y = _lonlat_to_world(lon, lat, z)
            xs.append(x)
            ys.append(y)
        if (max(xs) - min(xs)) <= w * (1 - 2 * pad) and (max(ys) - min(ys)) <= h * (1 - 2 * pad):
            return z
    return _MIN_Z


def _fetch_tile(z, x, y):
    from PIL import Image
    n = 2 ** z
    x %= n
    y %= n
    try:
        r = requests.get(_TILE_URL.format(z=z, x=x, y=y), headers=_UA, timeout=8)
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGB")
    except Exception:
        return None


def _compose_base(pts, w, h, pad):
    """Fetch + composite OSM tiles covering `pts`. Returns (base_img, project(lon,lat))."""
    from PIL import Image
    z = _pick_zoom(pts, w, h, pad)
    wx = [_lonlat_to_world(lon, lat, z) for lon, lat in pts]
    cx = (min(p[0] for p in wx) + max(p[0] for p in wx)) / 2
    cy = (min(p[1] for p in wx) + max(p[1] for p in wx)) / 2
    origin_x, origin_y = cx - w / 2, cy - h / 2

    base = Image.new("RGB", (w, h), (235, 233, 228))
    tx0, tx1 = int(math.floor(origin_x / _TILE)), int(math.floor((origin_x + w) / _TILE))
    ty0, ty1 = int(math.floor(origin_y / _TILE)), int(math.floor((origin_y + h) / _TILE))
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            tile = _fetch_tile(z, tx, ty)
            if tile is not None:
                base.paste(tile, (int(tx * _TILE - origin_x), int(ty * _TILE - origin_y)))

    def project(lon, lat):
        x, y = _lonlat_to_world(lon, lat, z)
        return x - origin_x, y - origin_y

    return base, project, z, cy


def _declutter(centers, min_d=34, iters=80):
    """Nudge overlapping marker centers apart (relaxation) so every number stays legible.
    Returns new centers, parallel to the input; a leader line ties each back to truth."""
    pts = [list(c) for c in centers]
    for _ in range(iters):
        moved = False
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                dx, dy = pts[j][0] - pts[i][0], pts[j][1] - pts[i][1]
                d = math.hypot(dx, dy) or 0.01
                if d < min_d:
                    push = (min_d - d) / 2.0
                    ux, uy = dx / d, dy / d
                    pts[i][0] -= ux * push
                    pts[i][1] -= uy * push
                    pts[j][0] += ux * push
                    pts[j][1] += uy * push
                    moved = True
        if not moved:
            break
    return [tuple(p) for p in pts]


# ---- fonts ---------------------------------------------------------------------------

def _font(size, bold=False):
    from PIL import ImageFont
    for name in (["arialbd.ttf", "Arialbd.ttf"] if bold else ["arial.ttf", "Arial.ttf"]):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size)
    except Exception:
        return ImageFont.load_default()


def _text_w(draw, s, font):
    try:
        b = draw.textbbox((0, 0), s, font=font)
        return b[2] - b[0]
    except Exception:
        return len(s) * (font.size // 2 if hasattr(font, "size") else 6)


def _rounded_panel(draw, box, radius, fill, outline=None):
    try:
        draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=1)
    except Exception:
        draw.rectangle(box, fill=fill, outline=outline)


# ---- public --------------------------------------------------------------------------

def build_route_map(hotel, meetings, focus=None, title="NDR route", subtitle="",
                    size=(1240, 900)):
    """PNG bytes of a street-map for the roadshow day, or None if nothing places.

    hotel     : {"name","address"} start/end of the day (may be None)
    meetings  : ordered [{"label"(str), "name", "time", "address"}] in schedule order
    focus     : (lat, lon) geocoding bias for the trip city
    """
    try:
        from PIL import Image, ImageDraw  # noqa: F401
    except Exception:
        return None

    # 1) geocode everything; keep what resolves, remember schedule order
    def _geo(addr):
        return routing.geocode(addr, focus=focus) if addr else None

    hotel_pt = _geo(hotel.get("address")) if hotel else None
    placed = []                                   # (label, lonlat, meeting)
    for m in meetings:
        pt = _geo(m.get("address"))
        if pt:
            placed.append((m.get("label", "?"), pt, m))

    if not placed and not hotel_pt:
        return None

    all_lonlat = [p for (_l, p, _m) in placed]
    if hotel_pt:
        all_lonlat.append(hotel_pt)

    w, h = size
    base, project, z, center_wy = _compose_base(all_lonlat, w, h, pad=0.14)
    draw = ImageDraw.Draw(base, "RGBA")

    # 2) route polyline: hotel -> stops... -> hotel, real road geometry where available
    seq = []
    if hotel:
        seq.append({"address": hotel.get("address")})
    seq.extend([{"address": m.get("address")} for (_l, _p, m) in placed])
    if hotel:
        seq.append({"address": hotel.get("address")})

    route_px = []
    for a, b in zip(seq, seq[1:]):
        poly = routing.route_polyline(a["address"], b["address"], focus=focus)
        if poly:
            route_px.extend([project(lon, lat) for lon, lat in poly])
        else:
            pa, pb = _geo(a["address"]), _geo(b["address"])
            if pa and pb:
                route_px.append(project(*pa))
                route_px.append(project(*pb))
    if len(route_px) >= 2:
        draw.line(route_px, fill=_ROUTE_HALO + (235,), width=9, joint="curve")
        draw.line(route_px, fill=_ROUTE + (255,), width=5, joint="curve")

    # 3) markers — anchors at true location, decluttered label positions with leaders
    anchors = [project(*p) for (_l, p, _m) in placed]
    labels = [l for (l, _p, _m) in placed]
    marker_c = _declutter(anchors, min_d=36)
    r = 15
    mf = _font(19, bold=True)
    for (ax, ay), (mx, my), lab in zip(anchors, marker_c, labels):
        if math.hypot(mx - ax, my - ay) > 2:
            draw.line([(ax, ay), (mx, my)], fill=(30, 41, 59, 200), width=2)
            draw.ellipse([ax - 3, ay - 3, ax + 3, ay + 3], fill=_ANCHOR + (255,))
        draw.ellipse([mx - r - 2, my - r - 2, mx + r + 2, my + r + 2], fill=(255, 255, 255, 255))
        draw.ellipse([mx - r, my - r, mx + r, my + r], fill=_PIN + (255,))
        tw = _text_w(draw, str(lab), mf)
        draw.text((mx - tw / 2, my - mf.size / 2 - 1), str(lab), font=mf, fill=(255, 255, 255))

    # hotel marker (rounded square, start & end of the day)
    if hotel_pt:
        hx, hy = project(*hotel_pt)
        s = 15
        _rounded_panel(draw, [hx - s, hy - s, hx + s, hy + s], 5, (255, 255, 255, 255))
        _rounded_panel(draw, [hx - s + 2, hy - s + 2, hx + s - 2, hy + s - 2], 4, _PIN_HOTEL + (255,))
        hf = _font(17, bold=True)
        tw = _text_w(draw, "H", hf)
        draw.text((hx - tw / 2, hy - hf.size / 2 - 1), "H", font=hf, fill=(255, 255, 255))

    # 4) legend panel — auto-placed in whichever corner covers the fewest markers
    pw, ph = _legend_size(draw, hotel, placed, title, subtitle)
    hotel_px = [project(*hotel_pt)] if hotel_pt else []
    occupied = list(anchors) + list(marker_c) + hotel_px + route_px[::20]
    x0, y0 = _best_corner(pw, ph, w, h, occupied)
    _legend(draw, x0, y0, hotel, placed, title, subtitle, pw, ph)

    # 5) scale bar (bottom-right) + attribution (bottom-left)
    _scale_bar(draw, w, h, z, center_wy)
    af = _font(12)
    attr = "© OpenStreetMap contributors"
    aw = _text_w(draw, attr, af)
    draw.rectangle([2, h - 18, aw + 10, h], fill=(255, 255, 255, 200))
    draw.text((5, h - 16), attr, font=af, fill=_MUTED)

    out = io.BytesIO()
    base.save(out, format="PNG")
    return out.getvalue()


def _legend_rows(hotel, placed):
    rows = []
    if hotel:
        rows.append(("H", hotel.get("name", "Hotel"), "start / end", _PIN_HOTEL))
    for (lab, _p, m) in placed:
        rows.append((str(lab), m.get("name", ""), (m.get("time") or "").strip(), _PIN))
    return rows


def _legend_size(draw, hotel, placed, title, subtitle):
    tf, sf, rowf = _font(21, bold=True), _font(13), _font(14)
    rows = _legend_rows(hotel, placed)
    pad, row_h = 14, 24
    title_h = 30 + (18 if subtitle else 0)
    max_name = max([_text_w(draw, n, rowf) for (_l, n, _t, _c) in rows] + [0])
    max_time = max([_text_w(draw, t, sf) for (_l, _n, t, _c) in rows] + [0])
    pw = max(_text_w(draw, title, tf), 26 + max_name + 14 + max_time) + pad * 2
    ph = title_h + len(rows) * row_h + pad
    return pw, ph


def _best_corner(pw, ph, w, h, points, margin=16):
    """Corner origin (x0, y0) for the legend that overlaps the fewest markers/route
    points. Order breaks ties toward the top-left (natural reading start)."""
    cands = [
        (margin, margin),                                   # TL
        (w - margin - pw, margin),                          # TR
        (margin, h - margin - ph - 22),                     # BL (above attribution)
        (w - margin - pw, h - margin - ph - 30),            # BR (above scale bar)
    ]
    best, best_score = cands[0], None
    for (x0, y0) in cands:
        score = sum(1 for (px, py) in points if x0 - 6 <= px <= x0 + pw + 6 and y0 - 6 <= py <= y0 + ph + 6)
        if best_score is None or score < best_score:
            best, best_score = (x0, y0), score
        if best_score == 0:
            break
    return best


def _legend(draw, x0o, y0o, hotel, placed, title, subtitle, pw, ph):
    tf = _font(21, bold=True)
    sf = _font(13)
    rowf = _font(14)
    rows = _legend_rows(hotel, placed)
    pad = 14
    row_h = 24
    _rounded_panel(draw, [x0o, y0o, x0o + pw, y0o + ph], 12, (255, 255, 255, 236),
                   outline=(226, 232, 240, 255))
    x0, y = x0o + pad, y0o + pad - 2
    draw.text((x0, y), title, font=tf, fill=_INK)
    y += 26
    if subtitle:
        draw.text((x0, y), subtitle, font=sf, fill=_MUTED)
        y += 18
    y += 6
    for (lab, name, t, col) in rows:
        cy = y + row_h / 2
        if lab == "H":
            _rounded_panel(draw, [x0, cy - 9, x0 + 18, cy + 9], 4, col + (255,))
        else:
            draw.ellipse([x0, cy - 9, x0 + 18, cy + 9], fill=col + (255,))
        lw = _text_w(draw, lab, _font(12, bold=True))
        draw.text((x0 + 9 - lw / 2, cy - 8), lab, font=_font(12, bold=True), fill=(255, 255, 255))
        draw.text((x0 + 26, cy - 8), name, font=rowf, fill=_INK)
        if t:
            draw.text((x0 + pw - pad * 2 - _text_w(draw, t, sf), cy - 7), t, font=sf, fill=_MUTED)
        y += row_h


def _scale_bar(draw, w, h, z, center_world_y):
    # meters per pixel at the map-center latitude
    lat = math.degrees(2 * math.atan(math.exp(math.pi - (center_world_y / (_TILE * 2 ** z)) * 2 * math.pi)) - math.pi / 2)
    mpp = 156543.03392 * math.cos(math.radians(lat)) / (2 ** z)
    # choose a “nice” distance ~ up to 120px
    for miles in (1, 2, 3, 5, 10, 20):
        px = miles * 1609.344 / mpp
        if px > 120:
            break
    bx1, by = w - 24, h - 26
    bx0 = bx1 - px
    draw.rectangle([bx0 - 6, by - 16, bx1 + 6, by + 8], fill=(255, 255, 255, 210))
    draw.line([(bx0, by), (bx1, by)], fill=_INK, width=3)
    draw.line([(bx0, by - 5), (bx0, by + 5)], fill=_INK, width=3)
    draw.line([(bx1, by - 5), (bx1, by + 5)], fill=_INK, width=3)
    lbl = f"{miles} mi"
    lf = _font(12, bold=True)
    draw.text((bx0 + (px - _text_w(draw, lbl, lf)) / 2, by - 15), lbl, font=lf, fill=_INK)
