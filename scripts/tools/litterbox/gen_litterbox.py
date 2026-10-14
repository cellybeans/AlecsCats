"""Generate Cat_Litterbox.blockymodel and its texture.

Usage: python scripts/tools/litterbox/gen_litterbox.py Common/Blocks/CatFurniture/Litterbox
The output is deterministic (fixed seed). Regenerate the item icon after a change.

Units: 32 per block, 1 texel per unit. Origin at the bottom centre of the cell.
"""
import json, math, sys, os
import numpy as np
from PIL import Image

OUT = sys.argv[1]
SEED = 7
rng = np.random.default_rng(SEED)

def hexs(*h):
    return [tuple(int(x[i:i + 2], 16) for i in (1, 3, 5)) for x in h]

RAMPS = {
    # Teal from Cat_Bed, cream from Cat_Bowl, brown from the bed base, sand warmed and muted.
    "teal": hexs("#1b4246", "#225157", "#2b6466", "#316d6c", "#387874", "#40827c", "#4a8d85", "#57988e"),
    "cream": hexs("#857b6d", "#a49b8c", "#b8b0a2", "#c4bdaf", "#ccc5b7", "#d4cdc0", "#dcd6ca", "#e4dfd3"),
    "wood": hexs("#4e2f1d", "#5e3a24", "#6a432a", "#714a2d", "#764e2f", "#7c5433", "#845b38"),
    "sand": hexs("#857150", "#9a845d", "#ac966a", "#b9a375", "#c4af80", "#ceba8b", "#d7c597", "#dfcfa4"),
}
MID = {"teal": 3.4, "cream": 4.0, "wood": 3.2, "sand": 3.6}


def qround(t, steps):
    return np.clip(np.round(t * 6) / 6, 0, steps - 1)


def colour(ramp, t):
    r = np.array(RAMPS[ramp], float)
    t = qround(t, len(r))
    lo = np.floor(t).astype(int)
    hi = np.minimum(lo + 1, len(r) - 1)
    f = (t - lo)[..., None]
    return r[lo] * (1 - f) + r[hi] * f


def smooth_noise(h, w, cell=4, amp=0.35):
    gh, gw = h // cell + 2, w // cell + 2
    g = rng.normal(0, 1, (gh, gw))
    img = Image.fromarray(((g - g.min()) / (np.ptp(g) or 1) * 255).astype(np.uint8))
    img = img.resize((gw * cell, gh * cell), Image.BICUBIC)
    a = np.asarray(img, float)[:h, :w] / 255.0
    return (a - 0.5) * 2 * amp


def clusters(t, n, delta, lmin=2, lmax=4, horiz=None):
    h, w = t.shape
    for _ in range(n):
        hz = bool(rng.integers(0, 2)) if horiz is None else horiz
        L = int(rng.integers(lmin, lmax + 1))
        y, x = int(rng.integers(0, h)), int(rng.integers(0, w))
        for k in range(L):
            yy, xx = (y, x + k) if hz else (y + k, x)
            if 0 <= yy < h and 0 <= xx < w:
                t[yy, xx] += delta
    return t


def paint(w, h, ramp, kind, face):
    """kind: material marks. face: side | top | bottom | inner."""
    t = np.full((h, w), MID[ramp])
    if face in ("side", "inner", "slots"):
        if h > 1:
            grad = np.linspace(0.55, -0.6, h)[:, None]
            t += grad
        t[0, :] += 0.5
        if h > 2:
            t[-1, :] -= 0.5
        if face == "inner":
            t -= 0.9
    elif face == "top":
        t += 0.6
    elif face == "bottom":
        t -= 1.8
    t += smooth_noise(h, w, 3, 0.55) + smooth_noise(h, w, 2, 0.25)
    if kind == "wood":
        t = clusters(t, max(1, w * h // 10), 0.8, 3, 7, True)
        t = clusters(t, max(1, w * h // 12), -0.8, 3, 6, True)
    elif kind == "paint":
        if face in ("side", "inner") and h >= 6:
            t[h // 2, :] -= 0.9  # plank seam
            t[h // 2 + 1, :] += 0.3
        t = clusters(t, max(1, w * h // 22), 0.5, 3, 6)
        t = clusters(t, max(1, w * h // 26), -0.5, 2, 5)
    elif kind == "rim":
        t = clusters(t, max(1, w * h // 18), 0.5, 2, 4)
        t = clusters(t, max(1, w * h // 22), -0.5, 2, 3)
        if face == "top" and h >= 3:
            t[0, :] += 0.5
    elif kind == "sand":
        t = clusters(t, w * h // 6, 0.6, 1, 3)
        t = clusters(t, w * h // 8, -0.6, 1, 3)
        if face == "top" and w >= 12 and h >= 12:
            # sunk below the rim: darker near the walls
            yy, xx = np.mgrid[0:h, 0:w]
            edge = np.minimum.reduce([yy, xx, h - 1 - yy, w - 1 - xx])
            t -= np.where(edge == 0, 0.9, np.where(edge == 1, 0.4, 0.0))
            # a few litter clumps: darker blob with a light top pixel
            for _ in range(4):
                cy, cx = int(rng.integers(3, h - 4)), int(rng.integers(3, w - 4))
                t[cy:cy + 2, cx:cx + 3] -= 1.6
                t[cy, cx + 1] += 0.7
    elif kind == "slots":
        if face == "slots":
            for x in range(1, w - 1, 2):
                t[1:h - 1, x] -= 2.2
    return colour(ramp, t)


# ---------------------------------------------------------------- model

def quat_y(deg):
    a = math.radians(deg) / 2
    return {"x": 0.0, "y": round(math.sin(a), 6), "z": 0.0, "w": round(math.cos(a), 6)}


def quat_x(deg):
    a = math.radians(deg) / 2
    return {"x": round(math.sin(a), 6), "y": 0.0, "z": 0.0, "w": round(math.cos(a), 6)}


def quat_xz(dx, dz):
    hx, hz = math.radians(dx) / 2, math.radians(dz) / 2
    # q = qz * qx
    return {"x": round(math.cos(hz) * math.sin(hx), 6), "y": round(math.sin(hz) * math.sin(hx), 6),
            "z": round(math.sin(hz) * math.cos(hx), 6), "w": round(math.cos(hz) * math.cos(hx), 6)}


IDENT = {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}

# name, pos, size, ramp, kind, shading, faces{face: (uvkey, facekind)}, orientation, parent
BOXES = []


def box(name, pos, size, ramp, kind, faces, shading="standard", orient=IDENT, parent=None):
    BOXES.append(dict(name=name, pos=pos, size=size, ramp=ramp, kind=kind, faces=faces,
                      shading=shading, orient=orient, parent=parent))


def fsize(face, s):
    sx, sy, sz = s
    return {"front": (sx, sy), "back": (sx, sy), "left": (sz, sy), "right": (sz, sy),
            "top": (sx, sz), "bottom": (sx, sz)}[face]


# Base: brown wooden plinth, flush under the walls.
box("Base", (0, 1, 0), (26, 2, 26), "wood", "wood",
    {f: ("base_side", "side") for f in ("front", "back", "left", "right")})
# Litter fill.
box("Litter", (0, 4.5, 0), (20, 5, 20), "sand", "sand", {"top": ("litter_top", "top")}, shading="flat")
# Walls (front of the model is +Z; the low entry is on the front).
box("Wall_Back", (0, 5.5, -11.5), (26, 7, 3), "teal", "paint",
    {"back": ("wall_out26", "side"), "front": ("wall_in26", "inner"),
     "left": ("wall_end", "side"), "right": ("wall_end", "side")})
for nm, x in (("Wall_L", 11.5), ("Wall_R", -11.5)):
    box(nm, (x, 5.5, 0), (3, 7, 20), "teal", "paint",
        {("right" if x > 0 else "left"): ("wall_out20", "side"),
         ("left" if x > 0 else "right"): ("wall_in20", "inner")})
for nm, x in (("Wall_Front_L", 9), ("Wall_Front_R", -9)):
    box(nm, (x, 5.5, 11.5), (8, 7, 3), "teal", "paint",
        {"front": ("wall_out8", "side"), "back": ("wall_in8", "inner"),
         "left": ("wall_end", "side"), "right": ("wall_end", "side")})
box("Wall_Front_Low", (0, 4, 11.5), (10, 4, 3), "teal", "paint", {"front": ("wall_out10", "side")})
# Cream rim cap with a small overhang.
box("Rim_Back", (0, 10, -11.5), (28, 2, 4), "cream", "rim",
    {"front": ("rim28", "side"), "back": ("rim28", "side"), "left": ("rim_end", "side"),
     "right": ("rim_end", "side"), "top": ("rim28_top", "top"), "bottom": ("rim28_bot", "bottom")})
for nm, x in (("Rim_L", 11.5), ("Rim_R", -11.5)):
    box(nm, (x, 10, 0), (4, 2, 19), "cream", "rim",
        {"left": ("rim19", "side"), "right": ("rim19", "side"),
         "top": ("rim19_top", "top"), "bottom": ("rim19_bot", "bottom")})
for nm, x in (("Rim_Front_L", 9.5), ("Rim_Front_R", -9.5)):
    box(nm, (x, 10, 11.5), (9, 2, 4), "cream", "rim",
        {"front": ("rim9", "side"), "back": ("rim9", "side"), "left": ("rim_end", "side"),
         "right": ("rim_end", "side"), "top": ("rim9_top", "top"), "bottom": ("rim9_bot", "bottom")})
box("Rim_Front_Low", (0, 7, 11.5), (10, 2, 4), "cream", "rim",
    {"front": ("rim10", "side"), "back": ("rim10", "side"),
     "top": ("rim10_top", "top"), "bottom": ("rim10_bot", "bottom")})
# A small dug mound of litter.
box("Litter_Mound", (4, 7.5, 2.5), (7, 2, 6), "sand", "sand",
    {"top": ("mound_top", "top"), "front": ("mound_fb", "side"), "back": ("mound_fb", "side"),
     "left": ("mound_lr", "side"), "right": ("mound_lr", "side")},
    shading="flat", orient=quat_y(20))
# Scoop standing outside the right (+X) wall, propped on the rim: tilted sideways toward the back and a
# touch toward the box. It stays inside the cell (x 13.75 to 15.75) and clears the rim edge at x 13.5.
SCOOP = dict(name="Scoop", pos=(14.75, 0, 5), orient=quat_xz(-18, 2))
box("Scoop_Head", (0, 3, 0), (2, 6, 6), "cream", "slots",
    {"right": ("scoop_face", "slots"), "left": ("scoop_back", "side"), "front": ("scoop_edge", "side"),
     "back": ("scoop_edge", "side"), "bottom": ("scoop_end", "bottom")},
    shading="flat", orient=IDENT, parent="Scoop")
box("Scoop_Handle", (0, 10.5, 0), (2, 9, 2), "teal", "paint",
    {"left": ("handle_side", "side"), "right": ("handle_side", "side"), "front": ("handle_side", "side"),
     "back": ("handle_side", "side"), "top": ("handle_end", "top")},
    shading="flat", orient=IDENT, parent="Scoop")

# ---------------------------------------------------------------- pack

rects = {}  # uvkey -> (w, h, ramp, kind, facekind)
for b in BOXES:
    for f, (key, fk) in b["faces"].items():
        w, h = fsize(f, b["size"])
        if key in rects:
            assert rects[key][:2] == (w, h), (key, rects[key][:2], (w, h))
        else:
            rects[key] = (w, h, b["ramp"], b["kind"], fk)


def pack(W, H):
    order = sorted(rects, key=lambda k: (-rects[k][1], -rects[k][0]))
    pos = {}
    x = y = shelf = 0
    for k in order:
        w, h = rects[k][:2]
        if x + w > W:
            x, y, shelf = 0, y + shelf, 0
        if y + h > H or w > W:
            return None
        pos[k] = (x, y)
        x += w
        shelf = max(shelf, h)
    return pos


for W, H in ((64, 64), (96, 64), (64, 96), (96, 96), (128, 64), (128, 96), (128, 128)):
    pos = pack(W, H)
    if pos:
        break
print("atlas", W, H, "rects", len(rects), "area", sum(r[0] * r[1] for r in rects.values()))

tex = np.zeros((H, W, 4), np.uint8)
for k, (x, y) in pos.items():
    w, h, ramp, kind, fk = rects[k]
    tex[y:y + h, x:x + w, :3] = np.round(paint(w, h, ramp, kind, fk)).astype(np.uint8)
    tex[y:y + h, x:x + w, 3] = 255
Image.fromarray(tex, "RGBA").save(os.path.join(OUT, "Cat_Litterbox_Texture.png"))

nid = [1]


def node(name, pos, orient, shape, children):
    nid[0] += 1
    return {"id": str(nid[0]), "name": name, "position": {"x": pos[0], "y": pos[1], "z": pos[2]},
            "orientation": orient, "shape": shape, "children": children}


def shape_none():
    return {"type": "none", "offset": {"x": 0, "y": 0, "z": 0}, "stretch": {"x": 1, "y": 1, "z": 1},
            "settings": {"isPiece": False}, "visible": True, "doubleSided": False,
            "shadingMode": "standard", "unwrapMode": "custom", "textureLayout": {}}


MIRROR = {}  # no mirroring: the painted faces are symmetric, and a mirrored face would need its offset at the far corner


def shape_box(b):
    tl = {}
    for f in ("front", "back", "left", "right", "top", "bottom"):
        if f in b["faces"]:
            x, y = pos[b["faces"][f][0]]
            tl[f] = {"offset": {"x": x, "y": y}, "mirror": {"x": MIRROR.get(f, False), "y": False}, "angle": 0}
    sx, sy, sz = b["size"]
    return {"type": "box", "offset": {"x": 0, "y": 0, "z": 0}, "stretch": {"x": 1, "y": 1, "z": 1},
            "settings": {"isPiece": False, "size": {"x": sx, "y": sy, "z": sz}}, "visible": True,
            "doubleSided": False, "shadingMode": b["shading"], "unwrapMode": "custom", "textureLayout": tl}


children = []
scoop_children = []
for b in BOXES:
    n = node(b["name"], b["pos"], b["orient"], shape_box(b), [])
    (scoop_children if b["parent"] == "Scoop" else children).append(n)
children.append(node(SCOOP["name"], SCOOP["pos"], SCOOP["orient"], shape_none(), scoop_children))
root = {"id": "1", "name": "Origin", "position": {"x": 0, "y": 0, "z": 0}, "orientation": IDENT,
        "shape": shape_none(), "children": children}
doc = {"nodes": [root], "format": "prop", "lod": "auto"}
with open(os.path.join(OUT, "Cat_Litterbox.blockymodel"), "w", newline="\n") as fh:
    json.dump(doc, fh, indent=2)
    fh.write("\n")
print("wrote", OUT)
