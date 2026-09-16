"""popctl figures.

Every number here comes from one of three places, and nothing is modelled or invented:
  - the disassembly of GTAIV.exe 1.2.0.59 (addresses, constants, the branch structure)
  - popctl.ini (the values shipped)
  - ../data/trace_*.log, written by popctl's own removal trace during three hands-free runs
    of the same 180 s route (stock game, popctl 0.1, popctl 0.2)

    python make_figures.py          -> writes ./figures/*.png
"""
import os
import re
import glob
import math
import statistics as st
import collections
import plotly.graph_objects as go
from figstyle import (SERIF, SANS, MONO, SURFACE, PANEL, GRID, INK, INK2, MUTED,
                      BLUE, ORANGE, AQUA, YELLOW, BLUE_F, ORANGE_F, AQUA_F, YELLOW_F,
                      base_layout, note, box, label, arrow)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "figures")
DATA = os.path.join(HERE, "..", "data")
os.makedirs(OUT, exist_ok=True)
SCALE = 2


def save(fig, name):
    p = os.path.join(OUT, name + ".png")
    fig.write_image(p, scale=SCALE)
    print("wrote", p)


# ---------------------------------------------------------------- trace data
# Return addresses of the population code's calls into RemovePed (0x73BCD0).
PATHS = {
    0x7385FE: "far pool full",
    0x73B17B: "band cull",
    0x738839: "band cull",
    0x73B072: "hidden cull",
    0x738724: "hidden cull",
    0x73C760: "conversion",
    0x73C940: "conversion",
    0x73C8AB: "conversion",
    0x73BC82: "remove all",
    0x73BCBF: "remove all",
    0x5409A5: "script",
}
RX = re.compile(r"t=(\d+) f=(\d+) (\S+)\s+caller=([0-9A-F]+)(?: up=[0-9A-F]+/[0-9A-F]+ m=-?\d+)? pool=(\S+) type=\d+ model=-?\d+ flag=\d+ "
                r"dist=(-?[\d.]+) seen=(-?\d+) vis=(-?\d+) scale=(-?[\d.]+) used=(-?\d+)/(-?\d+) q=(-?\d+)/(-?\d+)")


def read_trace(path):
    rows, fill = [], []
    for line in open(path, encoding="utf-8", errors="replace"):
        if line.startswith("status"):
            m = re.search(r"q=(-?\d+)/(-?\d+)", line)
            if m and int(m.group(2)) > 0 and int(m.group(1)) > 0:
                fill.append((int(m.group(1)), int(m.group(2))))
            continue
        m = RX.search(line)
        if not m:
            continue
        name, caller = m.group(3), int(m.group(4), 16)
        path = "far pool full" if name.startswith("poolfull") else PATHS.get(caller, "other")
        rows.append(dict(path=path, pool=m.group(5)[0],
                         dist=float(m.group(6)), vis=int(m.group(8)),
                         qused=int(m.group(11)), qsize=int(m.group(12))))
    return rows, fill


RUNS = [("stock game", "trace_20260915_stock.log", ORANGE),
        ("popctl 0.1", "trace_20260915_popctl010.log", YELLOW),
        ("popctl 0.2", "trace_20260915_popctl020.log", AQUA)]


def load_runs():
    out = []
    for name, fn, col in RUNS:
        p = os.path.join(DATA, fn)
        if os.path.exists(p):
            rows, fill = read_trace(p)
            out.append((name, col, rows, fill))
    return out


# ---------------------------------------------------------------- figure 1
def fig_mechanism():
    """Every path that deletes an ambient pedestrian, and where popctl intervenes."""
    fig = go.Figure()
    fig.update_layout(**base_layout(
        "Where a pedestrian is deleted",
        "CPopulation on GTAIV.exe 1.2.0.59, from the disassembly and a hook on RemovePed. Addresses are RVAs.",
        height=900, width=1280))
    fig.update_xaxes(range=[0, 100], visible=False)
    fig.update_yaxes(range=[0, 100], visible=False)

    # the two pools
    box(fig, 4, 70, 46, 92, GRID, PANEL)
    label(fig, 25, 87.5, "full peds", 17, INK, SERIF)
    label(fig, 25, 82.5, "CPed pool, 120 x 3824 B", 13, MUTED, MONO)
    label(fig, 25, 76.5, "within ~30 m of the player", 13, INK2, SERIF)

    box(fig, 54, 70, 96, 92, GRID, PANEL)
    label(fig, 75, 87.5, "far peds", 17, INK, SERIF)
    label(fig, 75, 82.5, "second pool, 150 x 944 B", 13, MUTED, MONO)
    label(fig, 75, 76.5, "everything else you can see", 13, INK2, SERIF)

    # conversion between them
    arrow(fig, 46.5, 84, 53.5, 84, AQUA)
    arrow(fig, 53.5, 78, 46.5, 78, AQUA)
    label(fig, 50, 88.5, "swap", 12, AQUA, SERIF)
    label(fig, 50, 73.5, "~30 m", 12, AQUA, SERIF)

    # culls on the far pool
    box(fig, 54, 50, 96, 64, ORANGE, ORANGE_F)
    label(fig, 75, 60.5, "pool nearly full  0x738430", 15, ORANGE, MONO)
    label(fig, 75, 55.5, "under 12 free: delete the farthest, up to 20 per frame", 13, INK2, SERIF)
    label(fig, 75, 52, "no visibility test", 13, ORANGE, SERIF)
    arrow(fig, 75, 70, 75, 64.6, ORANGE)

    # shared band cull
    box(fig, 22, 30, 78, 44, BLUE, BLUE_F)
    label(fig, 50, 40.5, "band cull  0x737240, both pools", 15, BLUE, MONO)
    label(fig, 50, 35.5, "past 115 m: deleted even on camera   |   70-115 m: deleted if off camera and never flagged", 13, INK2, SERIF)
    label(fig, 50, 32, "after a 2.5-3.5 s grace timer", 13, MUTED, SERIF)
    arrow(fig, 25, 70, 32, 44.6, BLUE)
    arrow(fig, 75, 50, 68, 44.6, BLUE)

    # hidden culls
    box(fig, 4, 12, 46, 24, YELLOW, YELLOW_F)
    label(fig, 25, 20.5, "off-camera cull  0x73AF50", 15, YELLOW, MONO)
    label(fig, 25, 15.5, "past 80 m (flagged seen) or 15 m, immediate", 13, INK2, SERIF)
    box(fig, 54, 12, 96, 24, YELLOW, YELLOW_F)
    label(fig, 75, 20.5, "off-camera cull  0x738620", 15, YELLOW, MONO)
    label(fig, 75, 15.5, "past 15 m, immediate", 13, INK2, SERIF)
    arrow(fig, 12, 70, 12, 24.6, YELLOW)
    arrow(fig, 90, 50, 90, 24.6, YELLOW)

    # popctl
    box(fig, 4, 1, 96, 8, AQUA, AQUA_F, dash="dot")
    label(fig, 50, 4.5, "popctl 0.2: orange box replaced (never on camera), far pool 150 -> 300 with 12 sized pools, every distance -> 130, spawn band -> 130.  0.1 touched only the left yellow box.", 12, AQUA, SERIF)

    note(fig,
         "Measured over one 180 s route on the stock game: 4,426 of 8,129 deletions came from the orange box, 2,847 of them "
         "on camera at a median 74 m.<br>The yellow boxes, the only thing popctl 0.1 patched, accounted for 99.",
         y=-0.03)
    save(fig, "fig1_mechanism")


# ---------------------------------------------------------------- figure 2
def fig_constant_pool():
    """Why the off-camera constants cannot be edited in place."""
    fig = go.Figure()
    fig.update_layout(**base_layout(
        "Why not simply change the number?",
        "The off-camera constants share the read-only pool with the rest of the executable.",
        height=620, width=1280))
    fig.update_xaxes(range=[0, 100], visible=False)
    fig.update_yaxes(range=[0, 100], visible=False)

    entries = [
        ("0xBE8C00", "225.0", "the 15 m test, two sites", 2, BLUE, BLUE_F),
        ("0xBE8C64", "60.0", "119 other readers", 119, ORANGE, ORANGE_F),
        ("0xBE8CA4", "6400.0", "the 80 m test", 1, BLUE, BLUE_F),
    ]
    y = 66
    for rva, val, what, users, col, fill in entries:
        box(fig, 6, y, 52, y + 20, col, fill)
        label(fig, 9, y + 13.5, rva, 15, MUTED, MONO, anchor="left")
        label(fig, 9, y + 6.5, val, 20, col, MONO, anchor="left")
        label(fig, 49, y + 13.5, what, 15, INK, SANS, anchor="right")
        label(fig, 49, y + 6.5, f"{users} reader{'s' if users != 1 else ''}", 14, INK2, SERIF, anchor="right")
        y -= 26

    label(fig, 62, 78, "Editing the pool entry", 17, INK, SERIF, anchor="left")
    label(fig, 62, 70,
          "would change the value for every instruction<br>that reads it. The 60.0 two entries away has 119<br>"
          "readers across the executable, so a pool that<br>looks local is not.",
          15, INK2, SERIF, anchor="left", valign="top")

    label(fig, 62, 42, "Editing the instruction", 17, AQUA, SERIF, anchor="left")
    label(fig, 62, 34,
          "changes one reader and nothing else. popctl<br>points the three <i>comiss</i> displacements at its own<br>"
          "floats. The band distances and the pool size are<br>ordinary data and immediates, written directly.",
          15, INK2, SERIF, anchor="left", valign="top")

    fig.add_shape(type="line", x0=59, y0=8, x1=59, y1=88, line=dict(color=GRID, width=1, dash="dot"))
    save(fig, "fig2_constant_pool")


# ---------------------------------------------------------------- figure 3
def fig_radius():
    """Stock cull distances against the shipped configuration, drawn to scale."""
    fig = go.Figure()
    fig.update_layout(**base_layout(
        "Cull distances, drawn to scale",
        "Stock against the values popctl 0.2 ships. Metres from the player. All three popctl radii are 130 so pool pressure decides.",
        height=760, width=1280))
    lim = 150
    fig.update_xaxes(range=[-lim, lim], visible=False, scaleanchor="y", scaleratio=1)
    fig.update_yaxes(range=[-lim * 0.62, lim * 0.62], visible=False)

    def circle(r, color, fill, dash=None, width=2):
        fig.add_shape(type="circle", x0=-r, y0=-r, x1=r, y1=r,
                      line=dict(color=color, width=width, dash=dash),
                      fillcolor=fill, layer="below")

    circle(130, AQUA, "rgba(25,158,112,0.08)")
    circle(115, BLUE, "rgba(57,135,229,0.08)")
    circle(80, BLUE, "rgba(57,135,229,0.08)", dash="dot")
    circle(74, ORANGE, "rgba(217,89,38,0.10)", dash="dash")
    circle(15, ORANGE, "rgba(217,89,38,0.16)")

    fig.add_trace(go.Scatter(x=[0], y=[0], mode="markers",
                             marker=dict(size=9, color=INK), hoverinfo="skip"))
    label(fig, 0, -8, "player", 13, INK2, SERIF)

    for r, col, txt, deg in ((15, ORANGE, "15 m stock, off camera and never flagged", 30),
                             (74, ORANGE, "74 m stock, measured visible edge (pool full)", 42),
                             (80, BLUE, "80 m stock, off camera", 58),
                             (115, BLUE, "115 m stock, on camera", 70),
                             (130, AQUA, "130 m popctl, every radius and the spawn band", 82)):
        a = math.radians(deg)
        fig.add_shape(type="line", x0=0, y0=0, x1=r * math.cos(a), y1=r * math.sin(a),
                      line=dict(color=col, width=1, dash="dot"))
        label(fig, r * math.cos(a) + 2, r * math.sin(a) + 3, txt, 13, col, SANS, anchor="left")

    label(fig, -146, -80, "on-camera peds flagged as seen get 1.5x the on-camera distance. With the stock pool the visible "
                          "edge sat at a median 74 m regardless, because the pool was full.",
          13, MUTED, SERIF, anchor="left")
    save(fig, "fig3_radius")


# ---------------------------------------------------------------- figure 4
def fig_trace():
    """What the removal trace recorded on the same route under three configurations."""
    runs = load_runs()
    if not runs:
        print("no trace logs in data/, skipping fig4")
        return
    order = ["far pool full", "band cull", "hidden cull", "conversion", "remove all", "script", "other"]

    fig = go.Figure()
    fig.update_layout(**base_layout(
        "What deleted the pedestrians",
        "One 180 s route, three configurations. Every deletion logged by popctl's hook on RemovePed. "
        "Conversions replace a ped in place and are not despawns.",
        height=720, width=1280))
    fig.update_layout(barmode="group", showlegend=True,
                      legend=dict(orientation="h", x=0.0, y=1.02, xanchor="left", yanchor="bottom",
                                  font=dict(family=SANS, size=14, color=INK2), bgcolor="rgba(0,0,0,0)"),
                      margin=dict(l=70, r=60, t=150, b=150))
    for name, col, rows, fill in runs:
        counts = collections.Counter(r["path"] for r in rows)
        vis = collections.Counter(r["path"] for r in rows if r["vis"] == 1 and r["path"] != "conversion")
        fig.add_trace(go.Bar(name=name, x=order, y=[counts.get(k, 0) for k in order],
                             marker_color=col, opacity=0.92,
                             text=[f"{counts.get(k, 0):,}" + (f"<br><span style='font-size:11px'>{vis[k]:,} on camera</span>" if vis.get(k) else "") for k in order],
                             textposition="outside", textfont=dict(family=SANS, size=12, color=INK2),
                             cliponaxis=False))
    fig.update_yaxes(title_text="deletions in 180 s", gridcolor=GRID)
    fig.update_xaxes(title_text="")

    parts = []
    for name, col, rows, fill in runs:
        pf = [r["dist"] for r in rows if r["path"] == "far pool full" and r["vis"] == 1 and r["dist"] >= 0]
        q = [u for u, s in fill]
        parts.append(f"{name}: far pool median {st.median(q):.0f} of {fill[0][1]} slots"
                     + (f", on-camera pool-full deletions at a median {st.median(pf):.0f} m" if pf else ", no on-camera pool-full deletions"))
    note(fig, "<br>".join(parts), y=-0.20)
    save(fig, "fig4_trace")


# ---------------------------------------------------------------- figure 5
def fig_settings():
    """Everything popctl changes, with its stock value."""
    fig = go.Figure()
    fig.update_layout(**base_layout(
        "Every value popctl changes",
        "Stock read from the running process; shipped values from popctl.ini.",
        height=820, width=1280))
    fig.update_xaxes(range=[0, 100], visible=False)
    fig.update_yaxes(range=[0, 100], visible=False)

    rows = [
        ("FarPedPool",        "0x1C41E0", "150", "300", "far ped pool, plus 12 pools sized to it"),
        ("(pool cull)",       "0x738430", "any", "hidden", "batch cull replaced: never a ped on camera"),
        ("VisibleKeepMetres", "0xC45994", "115", "130", "on-camera cull distance (x1.5 if flagged seen)"),
        ("HiddenKeepMetres",  "0xC45990", "70",  "130", "off-camera timed cull distance"),
        ("HiddenKeepMetres",  "0x73B04B", "80",  "130", "off-camera immediate cull, flagged seen"),
        ("NearKeepMetres",    "0x73B054", "15",  "130", "off-camera immediate cull, never flagged"),
        ("NearKeepMetres",    "0x738700", "15",  "130", "the same test on the far pool"),
        ("PedSpawnFar",       "0xC45980", "105", "130", "spawner far edge, on foot"),
        ("SpawnsPerFrame",    "0xC4594C", "8",   "8",   "spawn attempts per frame (unchanged)"),
        ("VehGenFar",         "0xC3FF70", "110", "160", "traffic generation band, far edge"),
        ("VehRemoveScale",    "0xC3FF90", "65",  "100", "off-view removal distance scale"),
        ("VehRemoveNear",     "0xC3FF64", "56",  "80",  "near removal test"),
        ("VehMaxCars",        "0xC3FF98", "100", "110", "ambient car budget"),
        ("VehAttemptScale",   "0xC3FFA8", "3.5", "5.0", "spawn attempts multiplier"),
    ]
    hdr = 86
    for x, t in ((7, "setting"), (31, "address"), (48, "stock"), (60, "popctl"), (71, "what it controls")):
        label(fig, x, hdr, t, 14, MUTED, SERIF, anchor="left")
    fig.add_shape(type="line", x0=5, y0=hdr - 3.5, x1=97, y1=hdr - 3.5, line=dict(color=GRID, width=1))

    y = hdr - 10
    for name, rva, stock, new, what in rows:
        label(fig, 7,  y, name, 14, INK, MONO, anchor="left")
        label(fig, 31, y, rva, 13, MUTED, MONO, anchor="left")
        label(fig, 48, y, stock, 14, ORANGE, MONO, anchor="left")
        label(fig, 60, y, new, 14, AQUA if new != stock else MUTED, MONO, anchor="left")
        label(fig, 71, y, what, 13, INK2, SERIF, anchor="left")
        y -= 5.6

    note(fig,
         "A value is written only while the address still reads its stock value, so a different game build is a "
         "no-op that gets logged<br>rather than a crash. The far pool size is patched before the game constructs the "
         "pool and verified from the live pool header afterwards.",
         y=0.0)
    save(fig, "fig5_settings")


if __name__ == "__main__":
    fig_mechanism()
    fig_constant_pool()
    fig_radius()
    fig_trace()
    fig_settings()
    print("done")
