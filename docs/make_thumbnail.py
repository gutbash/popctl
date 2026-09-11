"""popctl gallery thumbnail, 1920x1080.

Designed to survive being shrunk to a ~300 px mod card: three text elements, one shape,
thick strokes. Nothing here is meant to be read at full size.

    python make_thumbnail.py     -> writes ./figures/thumbnail.png
"""
import os
import plotly.graph_objects as go
from figstyle import SERIF, SANS, SURFACE, INK, INK2, MUTED, BLUE, ORANGE, AQUA, label

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
os.makedirs(OUT, exist_ok=True)

W, H = 1920, 1080
fig = go.Figure()
fig.update_layout(
    paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
    width=W, height=H, margin=dict(l=0, r=0, t=0, b=0), showlegend=False,
    xaxis=dict(range=[0, 100], visible=False, fixedrange=True),
    yaxis=dict(range=[0, 100], visible=False, fixedrange=True),
)

ar = H / W

# ---- right: the keep radius, thick enough to read tiny
cx, cy = 71.0, 50.0
Y_PER_M = 40.0 / 120.0


def ring(r_m, color, fill, width):
    ry = r_m * Y_PER_M
    rx = ry * ar
    fig.add_shape(type="circle", x0=cx - rx, y0=cy - ry, x1=cx + rx, y1=cy + ry,
                  line=dict(color=color, width=width), fillcolor=fill, layer="below")


ring(120, AQUA, "rgba(25,158,112,0.13)", 9)
ring(80, BLUE, "rgba(57,135,229,0.22)", 9)
ring(15, ORANGE, "rgba(217,89,38,0.55)", 7)

# ---- left: wordmark and the one number that matters
label(fig, 7, 70, "popctl", 150, INK, SERIF, anchor="left")
fig.add_shape(type="line", x0=7.5, y0=58, x1=42, y1=58, line=dict(color=AQUA, width=6))
label(fig, 7.5, 50, "pedestrians and traffic", 50, INK2, SERIF, anchor="left")
label(fig, 7.5, 43, "stay loaded further out", 50, INK2, SERIF, anchor="left")

label(fig, 7.5, 27, "80 m", 86, ORANGE, SANS, anchor="left")
label(fig, 21.5, 26, "to", 46, MUTED, SERIF, anchor="left")
label(fig, 27.5, 27, "120 m", 86, AQUA, SANS, anchor="left")

fig.write_image(os.path.join(OUT, "thumbnail.png"), scale=1)
print("wrote", os.path.join(OUT, "thumbnail.png"))
