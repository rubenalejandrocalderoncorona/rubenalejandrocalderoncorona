#!/usr/bin/env python3
"""Render dark_mode.svg / light_mode.svg: colored ASCII portrait + neofetch-style info panel.
Needs Pillow + numpy.  Usage: python3 generate.py"""
import html, json, os
import numpy as np
from PIL import Image, ImageOps, ImageFilter, ImageEnhance

COLS, RAMP, GAMMA = 60, " .:-=+*#%@", 0.9
FS, CELL_W, LINE_H = 13.3, 8.0, 15.0       # portrait font metrics (bigger glyphs survive GitHub scaling)
PX, TOP = 18, 52
PANEL_X, W = 520, 860                       # 860px fits GitHub's README column without downscaling
MONO = 'ui-monospace,SFMono-Regular,Menlo,Consolas,"DejaVu Sans Mono","Liberation Mono",monospace'
THEMES = {
    "dark":  dict(bg="#0d1117", border="#30363d", fg="#c9d1d9", key="#ffa657", val="#a5d6ff",
                  dim="#8b949e", accent="#7ee787", title="#8b949e"),
    "light": dict(bg="#f6f8fa", border="#d0d7de", fg="#24292f", key="#bc4c00", val="#0550ae",
                  dim="#57606a", accent="#1a7f37", title="#57606a"),
}
esc = lambda s: html.escape(str(s), quote=False)
hexc = lambda p: "#%02x%02x%02x" % tuple(int(v) for v in p)

def portrait_rows(path, light):
    im = Image.open(path).convert("RGB").crop((130, 30, 600, 640))   # head + shoulders, drops watermark
    w, h = im.size
    rows = round(COLS * (h / w) * (CELL_W / LINE_H))
    small = im.resize((COLS, rows), Image.LANCZOS)
    lum = small.convert("L")
    bg = np.asarray(lum) < 38                              # near-black studio backdrop
    g = ImageOps.autocontrast(lum, cutoff=1).filter(
        ImageFilter.UnsharpMask(radius=1.2, percent=160, threshold=2))
    arr = np.asarray(g, dtype=np.float32)
    fg = ~bg
    ranks = np.zeros_like(arr)                             # percentile-rank tones inside the subject only
    order = arr[fg].argsort().argsort() / max(fg.sum() - 1, 1)
    ranks[fg] = order
    a = (0.08 + 0.92 * ranks) ** GAMMA
    idx = np.clip((a * (len(RAMP) - 1)).round().astype(int), 0, len(RAMP) - 1)
    idx[bg] = 0                          # near-black background -> empty
    rgb = np.asarray(ImageEnhance.Color(small).enhance(1.4), dtype=np.float32)
    m = rgb.max(axis=2, keepdims=True)
    rgb = rgb * np.clip(215.0 / (m + 1), 1, 5)           # lift value so chars read on a dark panel
    rgb = np.clip(rgb * (0.62 if light else 1.0), 0, 255).astype(np.uint8)
    rgb = (rgb // 8) * 8 + 4                # quantise -> longer same-colour runs, smaller file
    out = []
    for r in range(rows):
        runs, cur, col = [], "", None
        for c in range(COLS):
            ch = RAMP[idx[r, c]]
            if ch == " ":
                cur += " "; continue
            k = hexc(rgb[r, c])
            if k != col and cur.strip():
                runs.append((col, cur)); cur = ""
            elif k != col:
                runs.append((None, cur)); cur = ""
            col = k; cur += esc(ch)
        if cur.strip(): runs.append((col, cur))
        out.append(runs)
    while out and not out[0]: out.pop(0)                  # trim empty rows above the hair
    return out

def render(theme_name, prof, stats):
    t, light = THEMES[theme_name], theme_name == "light"
    rows = portrait_rows("assets/portrait.png", light)
    H = max(int(len(rows) * LINE_H + TOP + 30), 500)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
         f'role="img" aria-label="Terminal-style profile card for {esc(prof["host"])}">',
         f'<style>text{{font-family:{MONO};white-space:pre}}.p{{font-size:{FS}px;font-weight:700}}'
         f'.i{{font-size:12.5px}}.k{{fill:{t["key"]}}}.v{{fill:{t["val"]}}}.d{{fill:{t["dim"]}}}'
         f'.a{{fill:{t["accent"]}}}.f{{fill:{t["fg"]}}}'
         f'@keyframes b{{50%{{opacity:0}}}}.cur{{animation:b 1.1s steps(1) infinite}}</style>',
         f'<rect width="{W}" height="{H}" rx="10" fill="{t["bg"]}" stroke="{t["border"]}"/>',
         '<circle cx="20" cy="18" r="6" fill="#ff5f56"/><circle cx="40" cy="18" r="6" fill="#ffbd2e"/>'
         '<circle cx="60" cy="18" r="6" fill="#27c93f"/>',
         f'<text x="{W//2}" y="22" text-anchor="middle" class="i" fill="{t["title"]}">{esc(prof["host"])}: ~</text>',
         f'<line x1="0" x2="{W}" y1="34" y2="34" stroke="{t["border"]}"/>']
    # portrait
    for r, runs in enumerate(rows):
        if not runs: continue
        spans = "".join(
            (f'<tspan fill="{k}">{s}</tspan>' if k else f'<tspan>{s}</tspan>') for k, s in runs)
        n = sum(len(t) for _, t in runs)
        o.append(f'<text class="p" x="{PX}" y="{TOP + r*LINE_H:g}" textLength="{n*CELL_W:g}" '
                 f'lengthAdjust="spacing" xml:space="preserve">{spans}</text>')
    # info panel
    n_lines = 1 + len(prof['info']) + 1 + 3 + 1 + len(prof['projects']) + 1 + 4 + 1
    panel_h = n_lines * 20 + 4 * 6
    y, step = TOP + 6 + max(0, (len(rows) * LINE_H - panel_h) // 2), 20
    def line(content): 
        nonlocal y
        o.append(f'<text class="i" x="{PANEL_X}" y="{y}" xml:space="preserve">{content}</text>'); y += step
    def kv(k, v, w=12):
        line(f'<tspan class="k">{esc(k)}</tspan><tspan class="d">{"." * max(2, w - len(k))}</tspan> <tspan class="v">{esc(v)}</tspan>')
    def head(title):
        nonlocal y
        y += 6
        line(f'<tspan class="f">{esc(title)}</tspan> <tspan class="d">{"-" * max(2, 40 - len(title))}</tspan>')
    line(f'<tspan class="a">{esc(prof["host"])}</tspan> <tspan class="d">{"-" * 22}</tspan>')
    for k, v in prof["info"]: kv(k, v)
    head("Stack")
    kv("Languages", ", ".join(prof["languages"]))
    kv("Tools", ", ".join(prof["tools"][:3]))
    kv("Also", ", ".join(prof["tools"][3:]))
    head("Featured")
    for n, d in prof["projects"]: kv(n, d, w=15)
    head("GitHub Stats")
    s = stats
    kv("Repos", f'{s.get("repos","?")} {{Stars: {s.get("stars","?")}}}')
    kv("Commits", s.get("commits", "?"))
    kv("PRs / Issues", f'{s.get("prs","?")} / {s.get("issues","?")}')
    kv("Followers", s.get("followers", "?"))
    y += 6
    o.append(f'<text class="i" x="{PANEL_X}" y="{y}"><tspan class="a">$</tspan> <tspan class="f">whoami</tspan>'
             f'<tspan class="a cur"> ▮</tspan></text>')
    o.append("</svg>")
    return "\n".join(o)

if __name__ == "__main__":
    prof = json.load(open("profile.json"))
    stats = json.load(open("stats.json")) if os.path.exists("stats.json") else {}
    for name in THEMES:
        open(f"{name}_mode.svg", "w").write(render(name, prof, stats))
        print(f"{name}_mode.svg", os.path.getsize(f"{name}_mode.svg"), "bytes")
