"""popctl figures.

Every number here comes from one of three places, and nothing is modelled or invented:
  - the disassembly of GTAIV.exe 1.2.0.59 (addresses, constants, the branch structure)
  - popctl.ini (the values shipped)
  - popctl.log from a real session (what actually got patched)

There is deliberately no benchmark chart. No ped-count-versus-distance dataset was ever
captured, so drawing one would be fiction. What the negative-result figure shows is which
levers were tried and what was observed, which is a finding, not a measurement series.

    python make_figures.py          -> writes ./figures/*.png
"""
import os
import math
import plotly.graph_objects as go
from figstyle import (SERIF, SANS, MONO, SURFACE, PANEL, GRID, INK, INK2, MUTED,
                      BLUE, ORANGE, AQUA, YELLOW, BLUE_F, ORANGE_F, AQUA_F, YELLOW_F,
                      base_layout, note, box, label, arrow)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
os.makedirs(OUT, exist_ok=True)
SCALE = 2


def save(fig, name):
    p = os.path.join(OUT, name + ".png")
    fig.write_image(p, scale=SCALE)
    print("wrote", p)


# ---------------------------------------------------------------- figure 1
def fig_mechanism():
    """What actually deletes a pedestrian, and where popctl intervenes."""
    fig = go.Figure()
    fig.update_layout(**base_layout(
        "Where a pedestrian is deleted",
        "CPopulation removal loop, GTAIV.exe 1.2.0.59. Addresses are RVAs.",
        height=880, width=1280))
    fig.update_xaxes(range=[0, 100], visible=False)
    fig.update_yaxes(range=[0, 100], visible=False)

    # the loop, top of the tree
    box(fig, 34, 87, 66, 98, GRID, PANEL)
    label(fig, 50, 94.5, "removal loop", 17, INK, SERIF)
    label(fig, 50, 89.8, "0x73AF50", 14, MUTED, MONO)

    box(fig, 34, 72, 66, 83, GRID, PANEL)
    label(fig, 50, 79.5, "squared distance to player", 15, INK2)
    label(fig, 50, 74.8, "one pedestrian at a time", 13, MUTED, SERIF)
    arrow(fig, 50, 87, 50, 83.6, MUTED)

    # the branch
    box(fig, 34, 57, 66, 68, YELLOW, YELLOW_F)
    label(fig, 50, 64.5, "per-ped flag", 15, YELLOW)
    label(fig, 50, 59.8, "vtable+0xD4 -> byte +0x142", 13, INK2, MONO)
    arrow(fig, 50, 72, 50, 68.6, MUTED)

    # two comparison sites, side by side
    box(fig, 5, 34, 45, 51, BLUE, BLUE_F)
    label(fig, 25, 46.5, "comiss xmm0, [6400.0]", 15, BLUE, MONO)
    label(fig, 25, 41, "0x73B04B", 13, MUTED, MONO)
    label(fig, 25, 36.5, "80 m, on screen", 14, INK2, SERIF)

    box(fig, 55, 34, 95, 51, BLUE, BLUE_F)
    label(fig, 75, 46.5, "comiss xmm0, [225.0]", 15, BLUE, MONO)
    label(fig, 75, 41, "0x73B054", 13, MUTED, MONO)
    label(fig, 75, 36.5, "15 m, everything else", 14, INK2, SERIF)

    arrow(fig, 42, 57, 32, 51.6, BLUE)
    arrow(fig, 58, 57, 68, 51.6, BLUE)

    # outcome
    box(fig, 37, 15, 63, 27, ORANGE, ORANGE_F)
    label(fig, 50, 23, "delete", 18, ORANGE, SERIF)
    label(fig, 50, 18.2, "beyond: gone", 13, INK2, SERIF)
    arrow(fig, 34, 34, 42, 27.6, ORANGE)
    arrow(fig, 66, 34, 58, 27.6, ORANGE)

    # popctl's intervention, underneath both sites
    box(fig, 14, 2, 86, 10, AQUA, AQUA_F, dash="dot")
    label(fig, 50, 6, "popctl repoints both displacements", 16, AQUA, SERIF)
    arrow(fig, 22, 10.6, 22, 33.4, AQUA)
    arrow(fig, 78, 10.6, 78, 33.4, AQUA)

    note(fig,
         "The comparison constants live in a shared pool and cannot be edited in place. popctl rewrites the "
         "four-byte displacement<br>of each <i>comiss</i> so it reads a float inside the plugin instead. "
         "Neither instruction is moved, and nothing on disk changes.",
         y=-0.03)
    save(fig, "fig1_mechanism")


# ---------------------------------------------------------------- figure 2
def fig_constant_pool():
    """Why the constants themselves cannot be edited."""
    fig = go.Figure()
    fig.update_layout(**base_layout(
        "Why not simply change the number?",
        "The two constants share the read-only pool with the rest of the executable.",
        height=620, width=1280))
    fig.update_xaxes(range=[0, 100], visible=False)
    fig.update_yaxes(range=[0, 100], visible=False)

    entries = [
        ("0xBE8C00", "225.0", "the 15 m test", 2, BLUE, BLUE_F),
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
          "changes one reader and nothing else. popctl<br>points the two <i>comiss</i> displacements at its own<br>"
          "floats, so the pool is untouched and every other<br>consumer of those constants is unaffected.",
          15, INK2, SERIF, anchor="left", valign="top")

    fig.add_shape(type="line", x0=59, y0=8, x1=59, y1=88, line=dict(color=GRID, width=1, dash="dot"))
    save(fig, "fig2_constant_pool")


# ---------------------------------------------------------------- figure 3
def fig_radius():
    """Stock keep radius against the shipped configuration, drawn to scale."""
    fig = go.Figure()
    fig.update_layout(**base_layout(
        "Keep radius, drawn to scale",
        "Stock against the values popctl ships. Metres from the player.",
        height=760, width=1280))
    lim = 135
    fig.update_xaxes(range=[-lim, lim], visible=False, scaleanchor="y", scaleratio=1)
    fig.update_yaxes(range=[-lim * 0.62, lim * 0.62], visible=False)

    def circle(r, color, fill, dash=None, width=2):
        fig.add_shape(type="circle", x0=-r, y0=-r, x1=r, y1=r,
                      line=dict(color=color, width=width, dash=dash),
                      fillcolor=fill, layer="below")

    circle(120, AQUA, "rgba(25,158,112,0.07)")
    circle(80, BLUE, "rgba(57,135,229,0.10)")
    circle(45, AQUA, "rgba(25,158,112,0.10)", dash="dot", width=2)
    circle(15, ORANGE, "rgba(217,89,38,0.16)")

    fig.add_trace(go.Scatter(x=[0], y=[0], mode="markers",
                             marker=dict(size=9, color=INK), hoverinfo="skip"))
    label(fig, 0, -7, "player", 13, INK2, SERIF)

    for r, col, txt in ((15, ORANGE, "15 m stock near"),
                        (45, AQUA, "45 m popctl near"),
                        (80, BLUE, "80 m stock far"),
                        (120, AQUA, "120 m popctl far")):
        a = math.radians(52)
        fig.add_shape(type="line", x0=0, y0=0,
                      x1=r * math.cos(a), y1=r * math.sin(a),
                      line=dict(color=col, width=1, dash="dot"))
        label(fig, r * math.cos(a) + 2, r * math.sin(a) + 3, txt, 14, col, SANS, anchor="left")

    label(fig, -128, -68, "area within the far radius grows with the square of it: "
                          "120 m covers 2.25 times the ground 80 m does",
          14, MUTED, SERIF, anchor="left")
    save(fig, "fig3_radius")


# ---------------------------------------------------------------- figure 4
def fig_levers():
    """What was tried before the removal loop was found."""
    fig = go.Figure()
    fig.update_layout(**base_layout(
        "Levers that do not move the keep radius",
        "Tried on 2026-09-06 before the removal loop was located. Observation, not a measurement series.",
        height=640, width=1280))
    fig.update_xaxes(range=[0, 100], visible=False)
    fig.update_yaxes(range=[0, 100], visible=False)

    rows = [
        ("density multiplier x2", "no change past 60 m", False),
        ("density multiplier x4", "no change past 60 m", False),
        ("popcycle.dat rewrite (v2)", "no change past 60 m", False),
        ("removal loop displacement", "crowds persist to the configured radius", True),
    ]
    y = 74
    for name, outcome, good in rows:
        col = AQUA if good else ORANGE
        fill = AQUA_F if good else ORANGE_F
        box(fig, 6, y, 94, y + 15, col, fill)
        label(fig, 10, y + 7.5, name, 16, INK, SANS, anchor="left")
        label(fig, 90, y + 7.5, outcome, 15, col, SERIF, anchor="right")
        y -= 19

    note(fig,
         "Spawn density and the removal radius are independent. Raising density without moving the radius makes the "
         "game spawn<br>more pedestrians and then delete them at the same distance, which is why the first three "
         "rows change nothing you can see.",
         y=0.02)
    save(fig, "fig4_levers")


# ---------------------------------------------------------------- figure 5
def fig_settings():
    """Everything popctl changes, with its stock value."""
    fig = go.Figure()
    fig.update_layout(**base_layout(
        "Every value popctl changes",
        "Stock read from the running process; shipped values from popctl.ini.",
        height=700, width=1280))
    fig.update_xaxes(range=[0, 100], visible=False)
    fig.update_yaxes(range=[0, 100], visible=False)

    rows = [
        ("FarKeepMetres",  "0x73B04B", "80",  "120", "ped keep radius, on screen"),
        ("NearKeepMetres", "0x73B054", "15",  "45",  "ped keep radius, otherwise"),
        ("SpawnsPerFrame", "0xC4594C", "8",   "16",  "spawn attempts per frame"),
        ("VehGenFar",      "0xC3FF70", "110", "160", "traffic generation band, far edge"),
        ("VehRemoveScale", "0xC3FF90", "65",  "100", "off-view removal distance scale"),
        ("VehRemoveNear",  "0xC3FF64", "56",  "80",  "near removal test"),
        ("VehMaxCars",     "0xC3FF98", "100", "110", "ambient car budget"),
        ("VehAttemptScale","0xC3FFA8", "3.5", "5.0", "spawn attempts multiplier"),
    ]
    hdr = 84
    for x, t in ((9, "setting"), (32, "address"), (52, "stock"), (66, "popctl"), (79, "what it controls")):
        label(fig, x, hdr, t, 14, MUTED, SERIF, anchor="left")
    fig.add_shape(type="line", x0=7, y0=hdr - 4, x1=95, y1=hdr - 4, line=dict(color=GRID, width=1))

    y = hdr - 12
    for name, rva, stock, new, what in rows:
        label(fig, 9,  y, name, 15, INK, MONO, anchor="left")
        label(fig, 32, y, rva, 14, MUTED, MONO, anchor="left")
        label(fig, 52, y, stock, 15, ORANGE, MONO, anchor="left")
        label(fig, 66, y, new, 15, AQUA, MONO, anchor="left")
        label(fig, 79, y, what, 14, INK2, SERIF, anchor="left")
        y -= 8.6

    note(fig,
         "A value is written only while the address still reads its stock value, so a different game build is a "
         "no-op that gets logged<br>rather than a crash. The vehicle pool holds 140 entries and the factory returns "
         "nothing past it, so VehMaxCars stays well clear.",
         y=0.02)
    save(fig, "fig5_settings")


if __name__ == "__main__":
    fig_mechanism()
    fig_constant_pool()
    fig_radius()
    fig_levers()
    fig_settings()
    print("done")
