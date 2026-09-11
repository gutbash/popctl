"""popctl Nexus header banner, 1300x372.

    python make_header.py     -> writes ./figures/header.png
"""
import os
import math
import plotly.graph_objects as go
from figstyle import (SERIF, SANS, MONO, SURFACE, GRID, INK, INK2, MUTED,
                      BLUE, ORANGE, AQUA, label)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
os.makedirs(OUT, exist_ok=True)

W, H = 1300, 372
fig = go.Figure()
fig.update_layout(
    paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
    width=W, height=H, margin=dict(l=0, r=0, t=0, b=0),
    showlegend=False,
    xaxis=dict(range=[0, 100], visible=False, fixedrange=True),
    yaxis=dict(range=[0, 100], visible=False, fixedrange=True),
)

# left: the name
label(fig, 6, 66, "popctl", 74, INK, SERIF, anchor="left")
label(fig, 6.6, 44, "population control for GTA IV", 27, INK2, SERIF, anchor="left")
fig.add_shape(type="line", x0=6.5, y0=34, x1=34, y1=34,
              line=dict(color=AQUA, width=2))
label(fig, 6.6, 24, "a research release", 18, MUTED, SERIF, anchor="left")

# right: keep radius rings, to scale, clipped by the banner edge
cx, cy = 70.0, 50.0
ar = H / W  # keep circles round in axis units


# biggest ring (120 m) is 35 y-units in radius, so the rings sit inside the banner
Y_PER_M = 35.0 / 120.0


def ring(r_m, color, fill, dash=None, width=2):
    ry = r_m * Y_PER_M
    rx = ry * ar
    fig.add_shape(type="circle", x0=cx - rx, y0=cy - ry, x1=cx + rx, y1=cy + ry,
                  line=dict(color=color, width=width, dash=dash),
                  fillcolor=fill, layer="below")


ring(120, AQUA, "rgba(25,158,112,0.08)")
ring(80, BLUE, "rgba(57,135,229,0.11)")
ring(15, ORANGE, "rgba(217,89,38,0.18)")

fig.add_trace(go.Scatter(x=[cx], y=[cy], mode="markers",
                         marker=dict(size=7, color=INK), hoverinfo="skip"))

for y, col, txt in ((68, AQUA, "120 m   popctl"),
                    (52, BLUE, "80 m   stock"),
                    (36, ORANGE, "15 m   stock near")):
    label(fig, 85.5, y, txt, 15, col, SANS, anchor="left")

fig.write_image(os.path.join(OUT, "header.png"), scale=1)
print("wrote", os.path.join(OUT, "header.png"))
