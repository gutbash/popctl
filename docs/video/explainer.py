"""popctl explainer.

    manim -qh explainer.py Explainer

Text only, no LaTeX. Type is CMU (Computer Modern), matching the figures.
"""
from manim import *

BG     = "#1a1a19"
PANEL  = "#232320"
INK    = "#f2f0ea"
INK2   = "#b8b4a8"
MUTED  = "#7d7a70"
GRID   = "#3a3a36"
BLUE   = "#3987e5"
ORANGE = "#d95926"
AQUA   = "#199e70"
YELLOW = "#c98500"

SERIF = "CMU Serif"
SANS  = "CMU Sans Serif"
MONO  = "CMU Typewriter Text"

config.background_color = BG


def T(s, size=28, color=INK, font=SERIF, weight=NORMAL):
    return Text(s, font=font, font_size=size, color=color, weight=weight)


def rbox(w, h, stroke=GRID, fill=PANEL, r=0.12, op=1.0):
    return RoundedRectangle(width=w, height=h, corner_radius=r,
                            stroke_color=stroke, stroke_width=2,
                            fill_color=fill, fill_opacity=op)


class Explainer(Scene):
    def construct(self):
        self.title()
        self.problem()
        self.false_lead()
        self.mechanism()
        self.fix()
        self.result()
        self.limits()
        self.outro()

    # ------------------------------------------------------------------
    def wipe(self, keep=None):
        keep = keep or []
        stuff = [m for m in self.mobjects if m not in keep]
        if stuff:
            self.play(*[FadeOut(m) for m in stuff], run_time=0.5)

    # ------------------------------------------------------------------
    def title(self):
        name = T("popctl", 96, INK, SERIF)
        sub = T("population control for GTA IV", 34, INK2, SERIF)
        rule = Line(LEFT * 3.2, RIGHT * 3.2, color=AQUA, stroke_width=2)
        tag = T("a research release", 24, MUTED, SERIF)
        g = VGroup(name, sub, rule, tag).arrange(DOWN, buff=0.36)
        rule.set_width(5.2)
        self.play(FadeIn(name, shift=UP * 0.3), run_time=0.9)
        self.play(FadeIn(sub), Create(rule), run_time=0.7)
        self.play(FadeIn(tag), run_time=0.5)
        self.wait(1.4)
        self.wipe()

    # ------------------------------------------------------------------
    def problem(self):
        head = T("Crowds vanish behind you", 46, INK, SERIF).to_edge(UP, buff=0.8)
        self.play(FadeIn(head), run_time=0.6)

        player = Dot(radius=0.10, color=INK).shift(LEFT * 4.4)
        plab = T("player", 20, INK2, SERIF).next_to(player, DOWN, buff=0.22)

        axis = Line(LEFT * 4.4, RIGHT * 5.4, color=GRID, stroke_width=2).shift(DOWN * 0.2)
        self.play(FadeIn(player), FadeIn(plab), Create(axis), run_time=0.7)

        # distance ticks
        marks = VGroup()
        for d, x in ((15, -3.0), (80, 1.4), (120, 3.9)):
            t = Line(UP * 0.12, DOWN * 0.12, color=GRID).move_to([x, -0.2, 0])
            lb = T(f"{d} m", 20, MUTED, SERIF).next_to(t, DOWN, buff=0.18)
            marks.add(VGroup(t, lb))
        self.play(FadeIn(marks), run_time=0.5)

        # peds
        peds = VGroup()
        for x in (-3.6, -2.4, -1.2, 0.1, 1.0, 2.2, 3.2, 4.4):
            peds.add(Dot(radius=0.075, color=BLUE).move_to([x, 0.45, 0]))
        self.play(LaggedStart(*[FadeIn(p, scale=0.5) for p in peds], lag_ratio=0.08), run_time=1.0)

        wall = DashedLine(UP * 1.5, DOWN * 1.1, color=ORANGE, stroke_width=3).move_to([1.4, 0.2, 0])
        wlab = T("80 m", 24, ORANGE, SERIF).next_to(wall, UP, buff=0.18)
        self.play(Create(wall), FadeIn(wlab), run_time=0.6)

        gone = VGroup(*[p for p in peds if p.get_x() > 1.4])
        self.play(*[FadeOut(p, scale=0.3) for p in gone], run_time=0.9)
        msg = T("deleted, every frame", 28, ORANGE, SERIF).shift(DOWN * 2.3)
        self.play(FadeIn(msg), run_time=0.5)
        self.wait(1.6)
        self.wipe()

    # ------------------------------------------------------------------
    def false_lead(self):
        head = T("The usual levers do nothing", 44, INK, SERIF).to_edge(UP, buff=0.8)
        self.play(FadeIn(head), run_time=0.6)

        rows = [
            ("density multiplier  2x", "no change past 60 m"),
            ("density multiplier  4x", "no change past 60 m"),
            ("popcycle.dat rewrite", "no change past 60 m"),
        ]
        group = VGroup()
        for name, res in rows:
            bar = rbox(10.4, 0.95, ORANGE, "#3b1d10")
            n = T(name, 26, INK, SANS).move_to(bar.get_left() + RIGHT * 2.9)
            r = T(res, 24, ORANGE, SERIF).move_to(bar.get_right() + LEFT * 2.3)
            group.add(VGroup(bar, n, r))
        group.arrange(DOWN, buff=0.34).shift(UP * 0.2)
        for row in group:
            self.play(FadeIn(row, shift=RIGHT * 0.2), run_time=0.45)

        note = T("density decides how many are created,\nnot where they are destroyed",
                 26, INK2, SERIF).shift(DOWN * 2.6)
        note.set_line_spacing = None
        self.play(FadeIn(note), run_time=0.7)
        self.wait(1.8)
        self.wipe()

    # ------------------------------------------------------------------
    def mechanism(self):
        head = T("What actually deletes them", 44, INK, SERIF).to_edge(UP, buff=0.7)
        self.play(FadeIn(head), run_time=0.6)

        loop = rbox(5.0, 0.95)
        loop_t = T("removal loop   0x73AF50", 24, INK, MONO).move_to(loop)
        top = VGroup(loop, loop_t).shift(UP * 1.9)

        flag = rbox(5.0, 0.95, YELLOW, "#332413")
        flag_t = T("per-ped flag", 24, YELLOW, SANS).move_to(flag)
        mid = VGroup(flag, flag_t).shift(UP * 0.45)

        a1 = Arrow(top.get_bottom(), mid.get_top(), buff=0.06,
                   color=MUTED, stroke_width=3, max_tip_length_to_length_ratio=0.2)

        left = rbox(5.4, 1.25, BLUE, "#16283f")
        left_t = VGroup(T("comiss xmm0, [6400.0]", 21, BLUE, MONO),
                        T("80 m", 20, INK2, SERIF)).arrange(DOWN, buff=0.14).move_to(left)
        lg = VGroup(left, left_t).shift(LEFT * 3.1 + DOWN * 1.5)

        right = rbox(5.4, 1.25, BLUE, "#16283f")
        right_t = VGroup(T("comiss xmm0, [225.0]", 21, BLUE, MONO),
                         T("15 m", 20, INK2, SERIF)).arrange(DOWN, buff=0.14).move_to(right)
        rg = VGroup(right, right_t).shift(RIGHT * 3.1 + DOWN * 1.5)

        a2 = Arrow(mid.get_bottom(), lg.get_top(), buff=0.06, color=BLUE,
                   stroke_width=3, max_tip_length_to_length_ratio=0.2)
        a3 = Arrow(mid.get_bottom(), rg.get_top(), buff=0.06, color=BLUE,
                   stroke_width=3, max_tip_length_to_length_ratio=0.2)

        self.play(FadeIn(top), run_time=0.5)
        self.play(GrowArrow(a1), FadeIn(mid), run_time=0.6)
        self.play(GrowArrow(a2), GrowArrow(a3), FadeIn(lg), FadeIn(rg), run_time=0.8)

        dele = rbox(3.0, 0.8, ORANGE, "#3b1d10").shift(DOWN * 3.1)
        dele_t = T("delete", 26, ORANGE, SERIF).move_to(dele)
        self.play(FadeIn(VGroup(dele, dele_t)), run_time=0.5)
        self.wait(1.8)
        self.wipe()

    # ------------------------------------------------------------------
    def fix(self):
        head = T("Why not just change the number?", 42, INK, SERIF).to_edge(UP, buff=0.7)
        self.play(FadeIn(head), run_time=0.6)

        pool = rbox(5.0, 3.4, GRID, PANEL).shift(LEFT * 3.3 + DOWN * 0.3)
        plab = T("constant pool", 24, INK2, SERIF).next_to(pool, UP, buff=0.2)
        e1 = VGroup(rbox(4.2, 0.7, BLUE, "#16283f"), T("225.0", 22, BLUE, MONO))
        e2 = VGroup(rbox(4.2, 0.7, ORANGE, "#3b1d10"), T("60.0", 22, ORANGE, MONO))
        e3 = VGroup(rbox(4.2, 0.7, BLUE, "#16283f"), T("6400.0", 22, BLUE, MONO))
        for e in (e1, e2, e3):
            e[1].move_to(e[0])
        col = VGroup(e1, e2, e3).arrange(DOWN, buff=0.3).move_to(pool)
        self.play(FadeIn(pool), FadeIn(plab), FadeIn(col), run_time=0.8)

        warn = T("119 other readers", 24, ORANGE, SERIF).next_to(e2, RIGHT, buff=0.5)
        self.play(FadeIn(warn), Indicate(e2, color=ORANGE, scale_factor=1.05), run_time=0.9)
        self.wait(1.0)
        self.play(FadeOut(warn), run_time=0.3)

        right = VGroup(
            T("popctl edits the instruction,", 30, AQUA, SERIF),
            T("not the pool.", 30, AQUA, SERIF),
            T("", 12),
            T("one reader changes.", 26, INK2, SERIF),
            T("nothing else does.", 26, INK2, SERIF),
        ).arrange(DOWN, buff=0.22, aligned_edge=LEFT).shift(RIGHT * 3.4 + DOWN * 0.3)
        self.play(FadeIn(right, shift=LEFT * 0.25), run_time=0.9)
        self.wait(1.9)
        self.wipe()

    # ------------------------------------------------------------------
    def result(self):
        head = T("What you get", 46, INK, SERIF).to_edge(UP, buff=0.9)
        self.play(FadeIn(head), run_time=0.6)

        centre = ORIGIN + DOWN * 0.4
        c80 = Circle(radius=1.55, color=BLUE, stroke_width=3,
                     fill_color=BLUE, fill_opacity=0.10).move_to(centre)
        c120 = Circle(radius=2.33, color=AQUA, stroke_width=3,
                      fill_color=AQUA, fill_opacity=0.08).move_to(centre)
        dot = Dot(radius=0.08, color=INK).move_to(centre)

        l80 = T("80 m  stock", 24, BLUE, SANS).next_to(c80, RIGHT, buff=0.25).shift(UP * 0.9)
        l120 = T("120 m  popctl", 24, AQUA, SANS).next_to(c120, RIGHT, buff=0.25).shift(UP * 1.5)

        self.play(Create(c80), FadeIn(dot), FadeIn(l80), run_time=0.8)
        self.play(Create(c120), FadeIn(l120), run_time=0.9)

        area = T("2.25 times the ground covered", 28, INK2, SERIF).shift(DOWN * 3.2)
        self.play(FadeIn(area), run_time=0.6)
        self.wait(1.8)
        self.wipe()

    # ------------------------------------------------------------------
    def limits(self):
        head = T("What was not measured", 42, INK, SERIF).to_edge(UP, buff=0.8)
        self.play(FadeIn(head), run_time=0.6)

        items = [
            "frame-time cost of a larger radius",
            "any build other than 1.2.0.59",
            "any machine but one",
        ]
        g = VGroup()
        for s in items:
            d = Dot(radius=0.055, color=ORANGE)
            t = T(s, 28, INK2, SERIF)
            g.add(VGroup(d, t).arrange(RIGHT, buff=0.35))
        g.arrange(DOWN, buff=0.5, aligned_edge=LEFT).shift(UP * 0.1)
        for row in g:
            self.play(FadeIn(row, shift=RIGHT * 0.15), run_time=0.4)

        foot = T("keeping more alive costs CPU. how much is an open question.",
                 24, MUTED, SERIF).shift(DOWN * 2.6)
        self.play(FadeIn(foot), run_time=0.6)
        self.wait(1.8)
        self.wipe()

    # ------------------------------------------------------------------
    def outro(self):
        name = T("popctl", 76, INK, SERIF)
        url = T("github.com/gutbash/popctl", 30, AQUA, MONO)
        rule = Line(LEFT * 2.6, RIGHT * 2.6, color=GRID, stroke_width=2)
        comp = T("companion release:  revd", 26, INK2, SERIF)
        comp2 = T("lifts the engine audio slot ceiling", 22, MUTED, SERIF)
        lic = T("MIT   ·   one mod, one job", 22, MUTED, SERIF)
        g = VGroup(name, url, rule, comp, comp2, lic).arrange(DOWN, buff=0.3)
        rule.set_width(6.0)
        self.play(FadeIn(name, shift=UP * 0.2), run_time=0.7)
        self.play(FadeIn(url), Create(rule), run_time=0.6)
        self.play(FadeIn(comp), FadeIn(comp2), run_time=0.6)
        self.play(FadeIn(lic), run_time=0.5)
        self.wait(2.4)
