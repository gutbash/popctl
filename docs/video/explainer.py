"""popctl explainer, 0.2.

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
        self.wrong()
        self.trace()
        self.mechanism()
        self.fix()
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
        tag = T("a research release, second edition", 24, MUTED, SERIF)
        g = VGroup(name, sub, rule, tag).arrange(DOWN, buff=0.36)
        rule.set_width(5.2)
        self.play(FadeIn(name, shift=UP * 0.3), run_time=0.9)
        self.play(FadeIn(sub), Create(rule), run_time=0.7)
        self.play(FadeIn(tag), run_time=0.5)
        self.wait(1.4)
        self.wipe()

    # ------------------------------------------------------------------
    def problem(self):
        head = T("Crowds vanish in front of you", 46, INK, SERIF).to_edge(UP, buff=0.8)
        self.play(FadeIn(head), run_time=0.6)

        player = Dot(radius=0.10, color=INK).shift(LEFT * 4.4)
        plab = T("player", 20, INK2, SERIF).next_to(player, DOWN, buff=0.22)
        axis = Line(LEFT * 4.4, RIGHT * 5.4, color=GRID, stroke_width=2).shift(DOWN * 0.2)
        self.play(FadeIn(player), FadeIn(plab), Create(axis), run_time=0.7)

        marks = VGroup()
        for d, x in ((30, -2.4), (74, 0.6), (115, 3.4)):
            t = Line(UP * 0.12, DOWN * 0.12, color=GRID).move_to([x, -0.2, 0])
            lb = T(f"{d} m", 20, MUTED, SERIF).next_to(t, DOWN, buff=0.18)
            marks.add(VGroup(t, lb))
        self.play(FadeIn(marks), run_time=0.5)

        peds = VGroup()
        for x in (-3.6, -2.8, -1.6, -0.6, 0.2, 1.1, 1.9, 2.8, 3.8, 4.6):
            peds.add(Dot(radius=0.075, color=BLUE).move_to([x, 0.45, 0]))
        self.play(LaggedStart(*[FadeIn(p, scale=0.5) for p in peds], lag_ratio=0.08), run_time=1.0)

        gone = VGroup(*[p for p in peds if p.get_x() > 0.6])
        self.play(*[FadeOut(p, scale=0.3) for p in gone], run_time=0.6)
        msg = T("groups of them, while you watch, at a median 74 m", 26, ORANGE, SERIF).shift(DOWN * 2.3)
        self.play(FadeIn(msg), run_time=0.5)
        self.wait(1.8)
        self.wipe()

    # ------------------------------------------------------------------
    def wrong(self):
        head = T("0.1 patched the wrong cull", 44, INK, SERIF).to_edge(UP, buff=0.8)
        self.play(FadeIn(head), run_time=0.6)

        rows = [
            ("moved the 80 m / 15 m distances", "changed only what survives behind you"),
            ("users: nothing changed", "correct"),
            ("users: still vanish in groups", "correct"),
        ]
        group = VGroup()
        for name, res in rows:
            bar = rbox(11.0, 0.95, ORANGE, "#3b1d10")
            n = T(name, 24, INK, SANS).move_to(bar.get_left() + RIGHT * 3.2)
            r = T(res, 22, ORANGE, SERIF).move_to(bar.get_right() + LEFT * 2.7)
            group.add(VGroup(bar, n, r))
        group.arrange(DOWN, buff=0.34).shift(UP * 0.2)
        for row in group:
            self.play(FadeIn(row, shift=RIGHT * 0.2), run_time=0.45)

        note = T("that cull skips every ped the camera can see.\n25 deletions out of 9,485.",
                 26, INK2, SERIF).shift(DOWN * 2.6)
        self.play(FadeIn(note), run_time=0.7)
        self.wait(1.9)
        self.wipe()

    # ------------------------------------------------------------------
    def trace(self):
        head = T("So measure it", 44, INK, SERIF).to_edge(UP, buff=0.7)
        self.play(FadeIn(head), run_time=0.6)

        hook = rbox(6.2, 0.95)
        hook_t = T("hook RemovePed   0x73BCD0", 24, INK, MONO).move_to(hook)
        top = VGroup(hook, hook_t).shift(UP * 1.7)
        sub = T("the one function all 49 removal paths go through", 22, MUTED, SERIF).next_to(top, DOWN, buff=0.2)
        self.play(FadeIn(top), FadeIn(sub), run_time=0.7)

        line = T("caller  distance  on camera?  pool fill", 24, INK2, MONO).shift(DOWN * 0.3)
        self.play(FadeIn(line), run_time=0.5)

        bars = VGroup()
        data = [("pool nearly full", 4426, ORANGE), ("conversions", 1695, MUTED),
                ("everything else", 1987, MUTED), ("the cull 0.1 patched", 21, YELLOW)]
        for name, n, col in data:
            w = max(0.08, 7.0 * n / 4426)
            bar = Rectangle(width=w, height=0.42, fill_color=col, fill_opacity=0.9, stroke_width=0)
            lab = T(name, 20, INK2, SANS)
            num = T(f"{n:,}", 20, col, MONO)
            row = VGroup(lab, bar, num).arrange(RIGHT, buff=0.25, aligned_edge=LEFT)
            lab.set_width(3.0) if lab.get_width() > 3.0 else None
            bars.add(row)
        bars.arrange(DOWN, buff=0.22, aligned_edge=LEFT).shift(DOWN * 1.9 + LEFT * 0.5)
        for row in bars:
            self.play(FadeIn(row, shift=RIGHT * 0.15), run_time=0.4)
        cap = T("stock game, one 180 s route. 2,847 of the orange ones were on camera.", 20, MUTED, SERIF).to_edge(DOWN, buff=0.35)
        self.play(FadeIn(cap), run_time=0.5)
        self.wait(2.0)
        self.wipe()

    # ------------------------------------------------------------------
    def mechanism(self):
        head = T("What actually deletes them", 44, INK, SERIF).to_edge(UP, buff=0.7)
        self.play(FadeIn(head), run_time=0.6)

        near = rbox(4.6, 1.3, GRID, PANEL)
        near_t = VGroup(T("full peds", 26, INK, SERIF), T("120 slots, within ~30 m", 20, MUTED, SERIF)).arrange(DOWN, buff=0.1).move_to(near)
        ng = VGroup(near, near_t).shift(LEFT * 3.2 + UP * 1.4)

        far = rbox(4.6, 1.3, GRID, PANEL)
        far_t = VGroup(T("far peds", 26, INK, SERIF), T("150 slots, everything you see", 20, MUTED, SERIF)).arrange(DOWN, buff=0.1).move_to(far)
        fg = VGroup(far, far_t).shift(RIGHT * 3.2 + UP * 1.4)

        a1 = Arrow(ng.get_right(), fg.get_left(), buff=0.1, color=AQUA, stroke_width=3, max_tip_length_to_length_ratio=0.15)
        swap = T("swapped as you walk", 18, AQUA, SERIF).next_to(a1, UP, buff=0.08)
        self.play(FadeIn(ng), FadeIn(fg), run_time=0.6)
        self.play(GrowArrow(a1), FadeIn(swap), run_time=0.5)

        full = rbox(9.0, 1.5, ORANGE, "#3b1d10").shift(DOWN * 0.6)
        full_t = VGroup(T("far pool nearly full: delete the farthest, 20 per frame", 24, ORANGE, SERIF),
                        T("no visibility test. the pool is always full on a busy street.", 20, INK2, SERIF)).arrange(DOWN, buff=0.12).move_to(full)
        a2 = Arrow(fg.get_bottom(), full.get_top(), buff=0.08, color=ORANGE, stroke_width=3, max_tip_length_to_length_ratio=0.2)
        self.play(GrowArrow(a2), FadeIn(VGroup(full, full_t)), run_time=0.8)

        msg = T("the crowd ends wherever the 138th-farthest ped stands", 26, INK, SERIF).shift(DOWN * 2.6)
        self.play(FadeIn(msg), run_time=0.6)
        self.wait(2.2)
        self.wipe()

    # ------------------------------------------------------------------
    def fix(self):
        head = T("What 0.2 does", 44, INK, SERIF).to_edge(UP, buff=0.7)
        self.play(FadeIn(head), run_time=0.6)

        items = [
            ("replace that cull", "same budget, never a ped the camera can see", AQUA),
            ("far pool 150 -> 300", "plus the twelve engine pools sized to it", AQUA),
            ("every distance -> 130 m", "keep, hidden, never-seen, and the spawn band", AQUA),
            ("spawns per frame -> 8", "back to stock; capacity sets density, not rate", MUTED),
        ]
        g = VGroup()
        for a, b, col in items:
            bar = rbox(11.4, 0.98, col, "#0e2c22" if col == AQUA else PANEL)
            ta = T(a, 25, col, SANS).move_to(bar.get_left() + RIGHT * 2.7)
            tb = T(b, 21, INK2, SERIF).move_to(bar.get_right() + LEFT * 3.6)
            g.add(VGroup(bar, ta, tb))
        g.arrange(DOWN, buff=0.28).shift(UP * 0.1)
        for row in g:
            self.play(FadeIn(row, shift=RIGHT * 0.2), run_time=0.45)

        foot = T("two crashes found the dependent pools. the log prints every live size.", 22, MUTED, SERIF).shift(DOWN * 2.7)
        self.play(FadeIn(foot), run_time=0.6)
        self.wait(2.2)
        self.wipe()

    # ------------------------------------------------------------------
    def limits(self):
        head = T("What it does not do", 42, INK, SERIF).to_edge(UP, buff=0.8)
        self.play(FadeIn(head), run_time=0.6)

        items = [
            "more peds inside 30 m: that pool is not grown",
            "a full street behind you: the pool is finite, far hidden peds go first",
            "traffic: the vehicle pool overran a table and crashed",
            "textures past ~100 m: the streamer's range, not the population's",
            "450 far peds: physics broke on the test machine. 300 is the number",
        ]
        g = VGroup()
        for s in items:
            d = Dot(radius=0.055, color=ORANGE)
            t = T(s, 25, INK2, SERIF)
            g.add(VGroup(d, t).arrange(RIGHT, buff=0.35))
        g.arrange(DOWN, buff=0.42, aligned_edge=LEFT).shift(UP * 0.1)
        for row in g:
            self.play(FadeIn(row, shift=RIGHT * 0.15), run_time=0.4)
        self.wait(2.2)
        self.wipe()

    # ------------------------------------------------------------------
    def outro(self):
        name = T("popctl", 76, INK, SERIF)
        url = T("github.com/gutbash/popctl", 30, AQUA, MONO)
        rule = Line(LEFT * 2.6, RIGHT * 2.6, color=GRID, stroke_width=2)
        comp = T("TraceRemovals = 1 shows you every deletion", 24, INK2, SERIF)
        comp2 = T("companion release: revd, the engine audio slot ceiling", 22, MUTED, SERIF)
        lic = T("MIT   ·   one mod, one job", 22, MUTED, SERIF)
        g = VGroup(name, url, rule, comp, comp2, lic).arrange(DOWN, buff=0.3)
        rule.set_width(6.0)
        self.play(FadeIn(name, shift=UP * 0.2), run_time=0.7)
        self.play(FadeIn(url), Create(rule), run_time=0.6)
        self.play(FadeIn(comp), FadeIn(comp2), run_time=0.6)
        self.play(FadeIn(lic), run_time=0.5)
        self.wait(2.4)
