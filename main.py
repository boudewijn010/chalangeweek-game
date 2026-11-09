import math
import random
import sys
from typing import Optional

import pygame

# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------
W, H = 1024, 640
FPS = 60

SEG_LEN = 200
ROAD_W = 2000
LANES = 3
CAM_H = 1000
FOV = 100
CAM_DEPTH = 1.0 / math.tan(math.radians(FOV / 2))
PLAYER_Z = CAM_H * CAM_DEPTH
DRAW_DIST = 220
RUMBLE_LEN = 4

MAX_SPEED = 12000.0
SLIP_MULT = 1.05
ACCEL = MAX_SPEED / 3
BRAKE = -MAX_SPEED
DECEL = -MAX_SPEED / 3
OFFROAD_DECEL = -MAX_SPEED / 2
OFFROAD_LIMIT = MAX_SPEED / 4
CENTRIFUGAL = 0.3

CAR_W = 0.3
TOTAL_LAPS = 3
RACES = 3
POINTS = [10, 7, 5, 3, 1]
M_PER_UNIT = 0.00648
KMH = 280.0 / MAX_SPEED
KMH_MAX = 280.0 * SLIP_MULT

THEMES = [
    dict(name="GOLDEN HOUR", sky_top=(28, 60, 150), sky_bot=(255, 175, 105),
         sun=(255, 230, 160), sun_pos=(0.70, 0.66), sun_r=62,
         mount=(135, 95, 150), hill=(48, 105, 78),
         grass=((26, 152, 62), (16, 128, 52)), road=((114, 114, 122), (104, 104, 112)),
         rumble=((212, 40, 40), (240, 240, 240)), lane=(228, 228, 228),
         night=False, stars=False, neon=False, skyline=False,
         trees="pine", clouds=(255, 218, 196)),
]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def lerp(a, b, t):
    return a + (b - a) * t


def ease_in(a, b, p):
    return a + (b - a) * p * p


def ease_in_out(a, b, p):
    return a + (b - a) * ((-math.cos(p * math.pi) / 2) + 0.5)


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def mix(a, b, t):
    t = clamp(t, 0.0, 1.0)
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))


def fmt_time(t):
    m = int(t // 60)
    return f"{m}:{t - m * 60:05.2f}"


def project(wx, wy, wz, camx, camy, camz):
    """World point -> (screen_x, screen_y, screen_road_width, scale, cam_z)."""
    cx, cy, cz = wx - camx, wy - camy, wz - camz
    scale = CAM_DEPTH / max(cz, 1e-3)
    return (W / 2 + scale * cx * W / 2,
            H / 2 - scale * cy * H / 2,
            scale * ROAD_W * W / 2,
            scale,
            cz)


def make_vignette(color, strength):
    small = pygame.Surface((80, 50), pygame.SRCALPHA)
    for y in range(50):
        for x in range(80):
            dx, dy = (x - 39.5) / 40, (y - 24.5) / 25
            d = math.hypot(dx, dy) / 1.25
            a = int(255 * strength * clamp((d - 0.5) / 0.55, 0, 1) ** 2)
            small.set_at((x, y), (*color, a))
    return pygame.transform.smoothscale(small, (W, H))


# --------------------------------------------------------------------------
# Sprites (all drawn with code)
# --------------------------------------------------------------------------
def draw_car(surf, cx, by, w, color, neon=False, braking=False):
    """Car seen from behind. (cx, by) = bottom center, w = width in px."""
    if w < 2 or w > W * 0.9:
        return
    cx, by, w = int(cx), int(by), int(w)
    h = int(w * 0.55)
    if w < 7:
        pygame.draw.rect(surf, color, (cx - w // 2, by - h, w, h))
        return
    dark = tuple(int(c * 0.55) for c in color)
    light = mix(color, (255, 255, 255), 0.35)
    if neon:  # underglow
        glow = mix(color, (255, 255, 255), 0.25)
        pygame.draw.ellipse(surf, mix(glow, (0, 0, 0), 0.35),
                            (cx - int(w * 0.72), by - int(h * 0.26), int(w * 1.44), int(h * 0.5)))
        pygame.draw.ellipse(surf, glow, (cx - int(w * 0.6), by - int(h * 0.2), int(w * 1.2), int(h * 0.36)))
    else:
        pygame.draw.ellipse(surf, (28, 28, 28),
                            (cx - int(w * 0.55), by - int(h * 0.14), int(w * 1.1), int(h * 0.28)))
    # body
    pygame.draw.rect(surf, color, (cx - w // 2, by - int(h * 0.62), w, int(h * 0.5)),
                     border_radius=max(2, w // 14))
    pygame.draw.rect(surf, light, (cx - w // 2 + 2, by - int(h * 0.62), w - 4, max(1, int(h * 0.07))),
                     border_radius=2)
    # cabin + window
    top = by - h
    pygame.draw.polygon(surf, dark, [(cx - w * 0.38, by - h * 0.6), (cx - w * 0.27, top),
                                     (cx + w * 0.27, top), (cx + w * 0.38, by - h * 0.6)])
    pygame.draw.polygon(surf, (30, 45, 70), [(cx - w * 0.31, by - h * 0.64), (cx - w * 0.23, top + h * 0.1),
                                             (cx + w * 0.23, top + h * 0.1), (cx + w * 0.31, by - h * 0.64)])
    # spoiler
    pygame.draw.rect(surf, dark, (cx - int(w * 0.31), by - int(h * 0.72), max(1, int(w * 0.05)), int(h * 0.12)))
    pygame.draw.rect(surf, dark, (cx + int(w * 0.26), by - int(h * 0.72), max(1, int(w * 0.05)), int(h * 0.12)))
    pygame.draw.rect(surf, color, (cx - int(w * 0.46), by - int(h * 0.76), int(w * 0.92), max(2, int(h * 0.08))),
                     border_radius=2)
    # wheels
    ww, wh = max(2, int(w * 0.15)), max(2, int(h * 0.4))
    pygame.draw.rect(surf, (18, 18, 18), (cx - w // 2 - ww // 3, by - wh, ww, wh), border_radius=2)
    pygame.draw.rect(surf, (18, 18, 18), (cx + w // 2 - ww + ww // 3, by - wh, ww, wh), border_radius=2)
    # tail lights + license plate
    lw, lh = max(2, int(w * 0.2)), max(2, int(h * 0.12))
    ly = by - int(h * 0.52)
    if braking:
        pygame.draw.rect(surf, (255, 110, 110), (cx - int(w * 0.46), ly - 2, lw + 4, lh + 4), border_radius=2)
        pygame.draw.rect(surf, (255, 110, 110), (cx + int(w * 0.46) - lw - 4, ly - 2, lw + 4, lh + 4), border_radius=2)
    pygame.draw.rect(surf, (255, 40, 40), (cx - int(w * 0.42), ly, lw, lh))
    pygame.draw.rect(surf, (255, 40, 40), (cx + int(w * 0.42) - lw, ly, lw, lh))
    pygame.draw.rect(surf, (235, 235, 235), (cx - int(w * 0.1), ly, max(2, int(w * 0.2)), lh))


def draw_tree(surf, x, by, w, var, kind, f, fogc):
    if w < 3 or w > 1500:
        return
    x, by, w = int(x), int(by), int(w)
    if kind == "palm":
        h = int(w * 2.0)
        tw = max(2, int(w * 0.12))
        lean = int((var - 0.5) * w * 0.5)
        top = (x + lean, by - h)
        pygame.draw.line(surf, mix((130, 92, 55), fogc, f), (x, by), top, tw)
        leaf = mix((34, 150 + int(var * 50), 60), fogc, f)
        L = w * 0.65
        for dx, dy in ((-1, -0.1), (-0.65, -0.55), (0, -0.7), (0.65, -0.55), (1, -0.1)):
            mid = (top[0] + dx * L * 0.55, top[1] + dy * L * 0.55 - L * 0.08)
            end = (top[0] + dx * L, top[1] + dy * L * 0.7 + L * 0.32)
            pygame.draw.line(surf, leaf, top, mid, max(2, w // 11))
            pygame.draw.line(surf, leaf, mid, end, max(1, w // 15))
        return
    h = int(w * 1.8)
    if kind == "neon":
        col = mix((0, 255, 230) if var < 0.5 else (255, 70, 225), fogc, f)
        dark = mix((12, 6, 34), fogc, f)
        t1 = [(x - w // 2, by - int(h * 0.25)), (x + w // 2, by - int(h * 0.25)), (x, by - int(h * 0.7))]
        t2 = [(x - int(w * 0.4), by - int(h * 0.5)), (x + int(w * 0.4), by - int(h * 0.5)), (x, by - h)]
        pygame.draw.rect(surf, dark, (x - max(1, w // 14), by - int(h * 0.3), max(2, w // 7), int(h * 0.3)))
        for tri in (t1, t2):
            pygame.draw.polygon(surf, dark, tri)
            pygame.draw.polygon(surf, col, tri, max(1, w // 16))
        return
    tw = max(1, int(w * 0.14))
    pygame.draw.rect(surf, mix((90, 60, 30), fogc, f), (x - tw // 2, by - int(h * 0.35), tw, int(h * 0.35)))
    g = int(110 + var * 60)
    pygame.draw.polygon(surf, mix((20, g - 30, 30), fogc, f), [(x - w // 2, by - int(h * 0.25)),
                                                               (x + w // 2, by - int(h * 0.25)),
                                                               (x, by - int(h * 0.7))])
    pygame.draw.polygon(surf, mix((30, g, 40), fogc, f), [(x - int(w * 0.4), by - int(h * 0.5)),
                                                          (x + int(w * 0.4), by - int(h * 0.5)),
                                                          (x, by - h)])


def draw_lamp(surf, x, by, w, night, f, fogc):
    if w < 3 or w > 800:
        return
    x, by, w = int(x), int(by), int(w)
    h = int(w * 2.6)
    pw = max(1, w // 9)
    pygame.draw.rect(surf, mix((150, 150, 165), fogc, f), (x - pw // 2, by - h, pw, h))
    if night:
        glow = mix((255, 236, 150), fogc, f * 0.5)
        pygame.draw.circle(surf, mix(glow, fogc, 0.65), (x, by - h), max(2, int(w * 0.6)))
        pygame.draw.circle(surf, mix(glow, fogc, 0.3), (x, by - h), max(2, int(w * 0.32)))
        pygame.draw.circle(surf, glow, (x, by - h), max(1, int(w * 0.16)))
    else:
        pygame.draw.rect(surf, mix((90, 90, 100), fogc, f), (x - w // 6, by - h - w // 12, w // 3, max(2, w // 7)))


# --------------------------------------------------------------------------
# Track
# --------------------------------------------------------------------------
class Seg:
    __slots__ = ("index", "y1", "y2", "curve", "col", "props", "s1", "s2", "clip")

    def __init__(self, index, y1, y2, curve):
        self.index, self.y1, self.y2, self.curve = index, y1, y2, curve
        self.col = (index // RUMBLE_LEN) % 2
        self.props = []
        self.s1 = self.s2 = None
        self.clip = H


class Track:
    def __init__(self, theme, mirror=False):
        self.segs = []
        self.last_y = 0.0
        self.theme = theme
        self.mirror = mirror
        self._build()
        if mirror:
            for s in self.segs:
                s.curve = -s.curve
        self.n = len(self.segs)
        self.length = self.n * SEG_LEN
        self._dress()

    def _seg(self, curve, y):
        self.segs.append(Seg(len(self.segs), self.last_y, y, curve))
        self.last_y = y

    def _road(self, enter, hold, leave, curve, y):
        start, end = self.last_y, self.last_y + y * SEG_LEN
        total = enter + hold + leave
        for n in range(enter):
            self._seg(ease_in(0, curve, n / enter), ease_in_out(start, end, n / total))
        for n in range(hold):
            self._seg(curve, ease_in_out(start, end, (enter + n) / total))
        for n in range(leave):
            self._seg(ease_in_out(curve, 0, n / leave), ease_in_out(start, end, (enter + hold + n) / total))

    def _sect(self, n, curve=0, hill=0):
        n = int(n * 1.5)
        q = n // 4
        self._road(q, n - 2 * q, q, curve, hill)

    def _build(self):
        s = self._sect
        s(100)
        s(90, 3, 10)
        s(80, 0, 30)
        s(90, -5, 0)
        s(90, 0, -35)
        s(100, 2, 0)
        s(60, -4); s(60, 4); s(60, -3); s(60, 5)
        s(120)
        s(100, -3, -10)
        s(70, 0, 20); s(70, 0, -20); s(70, 0, 30); s(70, 0, -30)
        s(140, 5, 0)
        s(80)
        s(90, -2, -self.last_y / SEG_LEN)
        self.segs[-1].y2 = 0.0

    def _dress(self):
        rng = random.Random(7)
        th = self.theme
        for seg in self.segs:
            i = seg.index
            if i % 4 == 0:
                for side in (-1, 1):
                    if rng.random() < (0.45 if th["trees"] == "palm" else 0.7):
                        seg.props.append((side * (2.3 + rng.random() * 2.5), "tree", rng.random()))
            if th["night"] and i % 10 == 0:
                for side in (-1, 1):
                    seg.props.append((side * 1.28, "lamp", 0.0))
            elif i % 20 == 0 and not th["night"]:
                seg.props.append((-1.22 if (i // 20) % 2 else 1.22, "lamp", 0.0))

    def find(self, z):
        return self.segs[int((z % self.length) // SEG_LEN)]

    def index_of(self, z):
        return int((z % self.length) // SEG_LEN)


# --------------------------------------------------------------------------
# Cars, input, particles
# --------------------------------------------------------------------------
class Car:
    def __init__(self, name, color, dist, offset, skill=0.0, player=False):
        self.name, self.color = name, color
        self.dist = dist
        self.offset = offset
        self.lane = offset
        self.skill = skill
        self.player = player
        self.speed = 0.0
        self.laps_done = -1
        self.finish_time: Optional[float] = None
        self.braking = False


class Inp:
    def __init__(self, up=False, down=False, left=False, right=False):
        self.up, self.down, self.left, self.right = up, down, left, right


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max", "col", "size", "grav", "kind")

    def __init__(self, x, y, vx, vy, life, col, size, grav, kind):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.life = self.max = life
        self.col, self.size, self.grav, self.kind = col, size, grav, kind


# --------------------------------------------------------------------------
# Game
# --------------------------------------------------------------------------
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Turbo Racer 3D - ULTRA")
        self.screen = pygame.display.set_mode((W, H))
        self.clock = pygame.time.Clock()
        self.f_big = pygame.font.Font(None, 120)
        self.f_title = pygame.font.Font(None, 84)
        self.f_num = pygame.font.Font(None, 62)
        self.f_med = pygame.font.Font(None, 36)
        self.f_small = pygame.font.Font(None, 26)
        self.points = {}
        self.race_no = 1
        self.paused = False
        self.t = 0.0
        self.player_screen = (W / 2, H - 100, 300)
        self.new_race()

    # ---- setup -----------------------------------------------------------
    def new_race(self):
        self.theme = THEMES[(self.race_no - 1) % len(THEMES)]
        th = self.theme
        self.cols = [dict(road=th["road"][i], grass=th["grass"][i], rumble=th["rumble"][i],
                          lane=th["lane"] if i == 0 else None) for i in range(2)]
        self.track = Track(th, mirror=(self.race_no % 2 == 0))
        self._make_background()
        self._make_overlays()
        self.reset()

    def _make_hills(self, color, comps, base):
        surf = pygame.Surface((W, H // 2), pygame.SRCALPHA)
        pts = [(0, H // 2)]
        for x in range(W + 1):
            y = base + sum(a * math.sin(2 * math.pi * k * x / W + ph) for k, a, ph in comps)
            pts.append((x, H // 2 - y))
        pts.append((W, H // 2))
        pygame.draw.polygon(surf, color, pts)
        return surf

    def _make_background(self):
        th = self.theme
        top, bot = th["sky_top"], th["sky_bot"]

        def skycol(y):
            return mix(top, bot, clamp(y / (H / 2), 0, 1) ** 1.2)

        sky = pygame.Surface((W, H))
        for y in range(H // 2 + 1):
            pygame.draw.line(sky, skycol(y), (0, y), (W, y))
        rng = random.Random(3)
        if th["stars"]:
            for _ in range(170):
                x, y = rng.randint(0, W), rng.randint(0, int(H * 0.36))
                b = rng.randint(140, 255)
                pygame.draw.circle(sky, (b, b, min(255, b + 20)), (x, y), rng.choice((1, 1, 1, 2)))
        sx, sy = th["sun_pos"]
        cx, cy, r = int(W * sx), int(H / 2 * sy), th["sun_r"]
        for k in range(10, 0, -1):
            pygame.draw.circle(sky, mix(skycol(cy), th["sun"], (1 - k / 10) * 0.35), (cx, cy), int(r * (1 + k * 0.2)))
        pygame.draw.circle(sky, th["sun"], (cx, cy), r)
        if th["neon"]:
            pygame.draw.circle(sky, mix(th["sun"], (255, 220, 90), 0.5), (cx, cy - r // 3), int(r * 0.7))
            pygame.draw.circle(sky, th["sun"], (cx, cy + r // 5), int(r * 0.9))
            for k in range(8):
                y0 = cy + int(r * (0.02 + 0.12 * k))
                hh = max(2, int(2 + k * 1.7))
                pygame.draw.rect(sky, skycol(y0 + hh // 2), (cx - r - 2, y0, 2 * r + 4, hh))
        if th["clouds"]:
            for _ in range(7):
                ccx, ccy = rng.randint(0, W), rng.randint(30, 180)
                for dx, dy, rr in ((0, 0, 28), (30, 6, 22), (-30, 8, 20), (12, -10, 22)):
                    pygame.draw.ellipse(sky, th["clouds"], (ccx + dx - rr * 1.6, ccy + dy - rr * 0.7, rr * 3.2, rr * 1.4))
        self.sky = sky

        far = self._make_hills(th["mount"], [(1, 30, 0.5), (3, 18, 1.3), (7, 8, 2.1)], 55)
        near = self._make_hills(th["hill"], [(2, 22, 2.0), (5, 12, 0.7), (11, 6, 1.1)], 28)
        self.layers = [(far, 0.3)]
        if th["skyline"]:
            sk = pygame.Surface((W, H // 2), pygame.SRCALPHA)
            x = 0
            while x < W:
                bw, bh = rng.randint(28, 70), rng.randint(40, 150)
                pygame.draw.rect(sk, (16, 7, 42), (x, H // 2 - bh, bw, bh))
                pygame.draw.line(sk, (255, 60, 200), (x, H // 2 - bh), (x + bw, H // 2 - bh), 2)
                for wy in range(H // 2 - bh + 8, H // 2 - 6, 12):
                    for wx in range(x + 5, x + bw - 6, 10):
                        if rng.random() < 0.33:
                            pygame.draw.rect(sk, rng.choice([(255, 230, 120), (0, 255, 230), (255, 80, 200)]), (wx, wy, 4, 6))
                x += bw + rng.randint(0, 6)
            self.layers.append((sk, 0.5))
        self.layers.append((near, 0.7))
        self.bg_off = 0.0

    def _make_overlays(self):
        th = self.theme
        self.vig = make_vignette((0, 0, 0), 0.85 if th["night"] else 0.5)
        self.cone = None
        if th["night"]:
            cone = pygame.Surface((W, H))
            cone.fill((0, 0, 0))
            y0, y1 = H // 2 + 30, H - 70
            for y in range(y0, y1):
                t = (y - y0) / (y1 - y0)
                hw = lerp(30, 300, t)
                b = 0.18 + 0.5 * t
                for sc, br in ((1.0, 0.35), (0.72, 0.65), (0.42, 1.0)):
                    c = (int(95 * b * br), int(90 * b * br), int(60 * b * br))
                    pygame.draw.line(cone, c, (W / 2 - hw * sc, y), (W / 2 + hw * sc, y))
            self.cone = cone

    def reset(self):
        specs = [("Dan", (225, 45, 45), 0.93), ("Sam", (245, 205, 30), 0.90),
                 ("Ray", (40, 185, 80), 0.87), ("Fay", (175, 80, 205), 0.84)]
        rows = [(0, -0.5), (0, 0.5), (1, -0.5), (1, 0.5)]
        self.ai = []
        for (name, col, skill), (row, off) in zip(specs, rows):
            c = Car(name, col, -SEG_LEN * (4 + 5 * row), off, skill + random.uniform(-0.015, 0.015))
            c.lane = random.choice([-0.6, -0.25, 0.25, 0.6]) if row else off
            self.ai.append(c)
        self.player = Car("YOU", (35, 100, 235), -SEG_LEN * (4 + 5 * 2), -0.5, player=True)
        self.cars = [self.player] + self.ai
        self.state = "ready"
        self.cd = 3.99
        self.last_cd = 4
        self.race_time = 0.0
        self.go_timer = 0.0
        self.lap_start = 0.0
        self.last_lap = None
        self.best_lap = None
        self.shake = 0.0
        self.final_order = []
        self.race_points = {}
        self.order = list(self.cars)
        self.prev_pos = len(self.cars)
        self.parts = []
        self.banners = []
        self.slip = False

    # ---- helpers ---------------------------------------------------------
    def signed(self, d):
        L = self.track.length
        return ((d + L / 2) % L) - L / 2

    def camera_pos(self):
        return (self.player.dist - PLAYER_Z) % self.track.length

    def standings(self):
        return sorted(self.cars, key=lambda c: (0, c.finish_time) if c.finish_time is not None else (1, -c.dist))

    def say(self, text, color=(255, 255, 255)):
        self.banners.append([text, color, 1.7])
        self.banners = self.banners[-3:]

    def spawn(self, x, y, vx, vy, life, col, size, grav=0.0, kind=0):
        if len(self.parts) < 450:
            self.parts.append(Particle(x, y, vx, vy, life, col, size, grav, kind))

    # ---- logic -----------------------------------------------------------
    def update(self, dt, inp):
        self.t += dt
        if self.paused or self.state in ("ready", "champion"):
            return
        self.update_particles(dt)
        for b in self.banners:
            b[2] -= dt
        self.banners = [b for b in self.banners if b[2] > 0]
        if self.state == "countdown":
            self.cd -= dt
            n = int(self.cd) + 1 if self.cd > 0 else 0
            if n != self.last_cd:
                self.last_cd = n
            if self.cd <= 0:
                self.state = "racing"
                self.race_time = 0.0
                self.go_timer = 1.0
            return
        self.race_time += dt
        self.go_timer = max(0.0, self.go_timer - dt)
        self.shake = max(0.0, self.shake - dt)
        self.update_player(dt, inp, self.state == "racing")
        for c in self.ai:
            self.update_ai(c, dt)
        self.collisions()
        self.check_laps()
        self.order = self.standings()
        pos = self.order.index(self.player) + 1
        # if self.state == "racing" and self.race_time > 2 and pos < self.prev_pos:
            # self.say(f"OVERTAKE!  P{pos}", (130, 255, 150))
        self.prev_pos = pos
        seg = self.track.find(self.player.dist)
        self.bg_off += seg.curve * (self.player.speed / MAX_SPEED) * dt * 60 * 0.6

    def update_player(self, dt, inp, can_drive):
        p = self.player
        seg = self.track.find(p.dist)
        sp = p.speed / MAX_SPEED
        dx = dt * 2 * sp
        if can_drive:
            if inp.left:
                p.offset -= dx
            if inp.right:
                p.offset += dx
        p.offset -= dx * sp * seg.curve * CENTRIFUGAL

        # slipstream
        self.slip = False
        if can_drive and p.speed > 3000:
            for a in self.ai:
                dz = a.dist - p.dist
                if 200 < dz < 1800 and abs(a.offset - p.offset) < 0.3:
                    self.slip = True
                    p.speed += ACCEL * 0.35 * dt
                    break
        top = MAX_SPEED * (SLIP_MULT if self.slip else 1.0)

        p.braking = bool(can_drive and inp.down and p.speed > 500)
        if can_drive and inp.up:
            p.speed += ACCEL * dt
        elif can_drive and inp.down:
            p.speed += BRAKE * dt
        else:
            p.speed += (DECEL if can_drive else DECEL * 2) * dt
        offroad = p.offset < -1 or p.offset > 1
        if offroad and p.speed > OFFROAD_LIMIT:
            p.speed += OFFROAD_DECEL * dt
        p.offset = clamp(p.offset, -2.0, 2.0)
        if p.speed > top:
            p.speed = max(top, p.speed - MAX_SPEED * 0.5 * dt)
        p.speed = clamp(p.speed, 0, MAX_SPEED * SLIP_MULT)
        p.dist += p.speed * dt

        # particles
        px, py, pw = self.player_screen
        if offroad and p.speed > 1500:
            dust = mix(self.cols[0]["d"], (255, 255, 255), 0.35)
            for sgn in (-1, 1):
                if random.random() < 0.7:
                    self.spawn(px + sgn * pw * 0.45, py - 4, random.uniform(-70, 70), random.uniform(-90, -20),
                               random.uniform(0.35, 0.7), dust, random.uniform(6, 14), 0, 1)

    def update_ai(self, car, dt):
        L = self.track.length
        seg = self.track.find(car.dist)
        if car.finish_time is not None:
            target = MAX_SPEED * 0.55
        else:
            target = MAX_SPEED * car.skill * (1 - 0.06 * max(0.0, abs(seg.curve) - 2))
            gap = self.signed(self.player.dist - car.dist)
            target *= 1 + 0.05 * clamp(gap / (L * 0.25), -1, 1)
            target = min(target, MAX_SPEED * 0.97)

        LOOK = 6000
        nearest, nd = None, LOOK
        for o in self.cars:
            if o is car:
                continue
            dz = self.signed(o.dist - car.dist)
            if 0 < dz < nd and abs(car.offset - o.offset) < 0.55:
                nearest, nd = o, dz
        if nearest is not None:
            d_off = car.offset - nearest.offset
            direction = 1 if d_off > 0 else -1
            if abs(d_off) < 0.05:
                direction = 1 if car.offset < 0 else -1
            if (car.offset > 0.75 and direction > 0) or (car.offset < -0.75 and direction < 0):
                direction = -direction
            car.offset += direction * dt * (0.5 + 1.0 * (1 - nd / LOOK))
            if nd < 1000 and abs(d_off) < 0.35:
                target = min(target, nearest.speed * 0.97)
        else:
            car.offset += clamp(car.lane - car.offset, -0.3 * dt, 0.3 * dt)

        car.offset = clamp(car.offset, -0.85, 0.85)
        car.speed += (target - car.speed) * min(1.0, dt * 1.2)
        car.speed = clamp(car.speed, 0, MAX_SPEED * 1.2)
        car.dist += car.speed * dt

    def collisions(self):
        p = self.player
        for a in self.ai:
            dz = a.dist - p.dist
            hit = False
            if 0 < dz < 500 and abs(a.offset - p.offset) < CAR_W:
                p.speed = min(p.speed, a.speed * 0.8)
                p.dist = a.dist - 520
                hit = True
            elif -500 < dz <= 0 and abs(a.offset - p.offset) < CAR_W:
                a.speed = min(a.speed, p.speed * 0.8)
                a.dist = p.dist - 520
                hit = True
            if hit:
                self.shake = 0.25
                px, py, pw = self.player_screen
                for _ in range(26):
                    ang = random.uniform(0, math.tau)
                    sp = random.uniform(120, 420)
                    self.spawn(px + random.uniform(-pw / 3, pw / 3), py - pw * 0.25, math.cos(ang) * sp,
                               math.sin(ang) * sp - 120, random.uniform(0.25, 0.6), (255, 220, 110), 2, 600, 2)

    def check_laps(self):
        L = self.track.length
        for c in self.cars:
            laps = int(math.floor(c.dist / L))
            if laps > c.laps_done:
                prev = c.laps_done
                c.laps_done = laps
                if c.player and prev >= 0:
                    t = self.race_time - self.lap_start
                    self.last_lap = t
                    if self.best_lap is None or t < self.best_lap:
                        self.best_lap = t
                        self.say("FASTEST LAP!  " + fmt_time(t), (190, 130, 255))
                    elif laps < TOTAL_LAPS:
                        self.say(f"LAP {laps + 1}/{TOTAL_LAPS}", (255, 255, 255))
                    if laps == TOTAL_LAPS - 1:
                        self.say("FINAL LAP!", (255, 90, 90))
                if c.player:
                    self.lap_start = self.race_time
                if laps >= TOTAL_LAPS and c.finish_time is None:
                    c.finish_time = self.race_time
                    if c.player:
                        self.player_finished()

    def player_finished(self):
        self.state = "finished"
        self.final_order = self.standings()
        for i, c in enumerate(self.final_order):
            pts = POINTS[i]
            self.points[c.name] = self.points.get(c.name, 0) + pts
            self.race_points[c.name] = pts
    def update_particles(self, dt):
        for p in self.parts:
            p.life -= dt
            p.vy += p.grav * dt
            p.x += p.vx * dt
            p.y += p.vy * dt
        self.parts = [p for p in self.parts if p.life > 0 and p.y < H + 40]

    # ---- drawing ---------------------------------------------------------
    def text(self, s, font, color, pos, anchor="topleft", shadow=True):
        img = font.render(s, True, color)
        r = img.get_rect(**{anchor: pos})
        if shadow:
            self.screen.blit(font.render(s, True, (0, 0, 0)), r.move(2, 2))
        self.screen.blit(img, r)

    def panel(self, rect, alpha=150):
        s = pygame.Surface(rect[2:], pygame.SRCALPHA)
        s.fill((10, 12, 20, alpha))
        self.screen.blit(s, rect[:2])

    def render_world(self):
        scr = self.screen
        th = self.theme
        fogc = th["sky_bot"]
        track, segs, N = self.track, self.track.segs, self.track.n
        L = track.length
        p = self.player

        scr.blit(self.sky, (0, 0))
        for layer, f in self.layers:
            off = int(self.bg_off * f) % W
            scr.blit(layer, (-off, 0))
            scr.blit(layer, (W - off, 0))
        scr.fill(mix(self.cols[0]["grass"], fogc, 0.9), (0, H // 2, W, H - H // 2))

        pos = self.camera_pos()
        base = track.find(pos)
        base_pct = (pos % SEG_LEN) / SEG_LEN
        pseg = track.find(p.dist)
        ppct = (p.dist % SEG_LEN) / SEG_LEN
        player_y = lerp(pseg.y1, pseg.y2, ppct)
        cam_y = CAM_H + player_y
        cam_x = p.offset * ROAD_W

        maxy = H
        x, dx = 0.0, -base.curve * base_pct
        poly = pygame.draw.polygon
        for n in range(DRAW_DIST):
            seg = segs[(base.index + n) % N]
            camz = pos - (L if seg.index < base.index else 0)
            s1 = seg.s1 = project(0, seg.y1, seg.index * SEG_LEN, cam_x - x, cam_y, camz)
            s2 = seg.s2 = project(0, seg.y2, (seg.index + 1) * SEG_LEN, cam_x - x - dx, cam_y, camz)
            x += dx
            dx += seg.curve
            seg.clip = maxy
            if s1[4] <= CAM_DEPTH or s2[1] >= s1[1] or s2[1] >= maxy:
                continue
            x1, y1, w1 = s1[0], s1[1], s1[2]
            x2, y2, w2 = s2[0], s2[1], s2[2]
            col = self.cols[seg.col]
            f = (n / DRAW_DIST) ** 1.4 * 0.9
            gy2, gy1 = int(y2), int(y1)
            scr.fill(mix(col["grass"], fogc, f), (0, gy2, W, gy1 - gy2))
            r1, r2 = w1 / max(6, 2 * LANES), w2 / max(6, 2 * LANES)
            rc = mix(col["rumble"], fogc, f)
            poly(scr, rc, [(x1 - w1 - r1, y1), (x1 - w1, y1), (x2 - w2, y2), (x2 - w2 - r2, y2)])
            poly(scr, rc, [(x1 + w1 + r1, y1), (x1 + w1, y1), (x2 + w2, y2), (x2 + w2 + r2, y2)])
            poly(scr, mix(col["road"], fogc, f), [(x1 - w1, y1), (x1 + w1, y1), (x2 + w2, y2), (x2 - w2, y2)])
            if seg.index < 2:
                for c in range(8):
                    cc = (235, 235, 235) if (c + seg.index) % 2 == 0 else (25, 25, 25)
                    a, b = c / 8, (c + 1) / 8
                    poly(scr, mix(cc, fogc, f), [(x1 - w1 + 2 * w1 * a, y1), (x1 - w1 + 2 * w1 * b, y1),
                                                 (x2 - w2 + 2 * w2 * b, y2), (x2 - w2 + 2 * w2 * a, y2)])
            elif col["lane"]:
                lc = mix(col["lane"], fogc, f)
                lw1, lw2 = w1 / max(32, 8 * LANES), w2 / max(32, 8 * LANES)
                lane_w1, lane_w2 = w1 * 2 / LANES, w2 * 2 / LANES
                lx1, lx2 = x1 - w1 + lane_w1, x2 - w2 + lane_w2
                for _ in range(1, LANES):
                    poly(scr, lc, [(lx1 - lw1 / 2, y1), (lx1 + lw1 / 2, y1),
                                   (lx2 + lw2 / 2, y2), (lx2 - lw2 / 2, y2)])
                    lx1 += lane_w1
                    lx2 += lane_w2
            maxy = y1

        if self.cone is not None:
            scr.blit(self.cone, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

        # sprites from far to near
        buckets = {}
        for c in self.ai:
            buckets.setdefault(track.index_of(c.dist), []).append(c)
        for n in range(DRAW_DIST - 1, -1, -1):
            seg = segs[(base.index + n) % N]
            s1, s2 = seg.s1, seg.s2
            cars_here = buckets.get(seg.index)
            if not seg.props and not cars_here and seg.index != 0:
                continue
            if s1 is None or s2 is None:
                continue
            scr.set_clip((0, 0, W, max(0, int(seg.clip))))
            if s1[4] > 200:
                f = (n / DRAW_DIST) ** 1.4 * 0.9
                for off, kind, var in seg.props:
                    sx = s1[0] + s1[3] * off * ROAD_W * W / 2
                    if kind == "tree":
                        draw_tree(scr, sx, s1[1], s1[3] * 1300 * W / 2, var, th["trees"], f, fogc)
                    else:
                        draw_lamp(scr, sx, s1[1], s1[3] * 600 * W / 2, th["night"], f, fogc)
                if seg.index == 0:
                    self.draw_gantry(s1)
            if cars_here:
                for c in cars_here:
                    pct = (c.dist % SEG_LEN) / SEG_LEN
                    camz = lerp(s1[4], s2[4], pct)
                    if camz <= CAM_DEPTH:
                        continue
                    scale = lerp(s1[3], s2[3], pct)
                    sx = lerp(s1[0], s2[0], pct) + scale * c.offset * ROAD_W * W / 2
                    sy = lerp(s1[1], s2[1], pct)
                    draw_car(scr, sx, sy, scale * CAR_W * ROAD_W * W / 2, c.color, neon=th["neon"])
        scr.set_clip(None)

        # player
        scale = CAM_DEPTH / PLAYER_Z
        py = H / 2 - scale * (player_y - cam_y) * H / 2 - 14
        shake = random.uniform(-4, 4) if self.shake > 0 else 0
        bounce = random.uniform(0, 2 + (4 if abs(p.offset) > 1 else 0)) * (p.speed / MAX_SPEED)
        pw = scale * CAR_W * ROAD_W * W / 2
        self.player_screen = (W / 2 + shake, py - bounce, pw)
        draw_car(scr, W / 2 + shake, py - bounce, pw, p.color, neon=th["neon"], braking=p.braking)

        self.draw_particles()

    def draw_gantry(self, s1):
        scr = self.screen
        sx, sy, sw, scale = s1[0], s1[1], s1[2], s1[3]
        hpx = scale * 3500 * H / 2
        if sw > 3000:
            return
        lx, rx = sx - sw * 1.25, sx + sw * 1.25
        pw = max(2, int(sw * 0.06))
        pygame.draw.rect(scr, (200, 200, 205), (lx - pw // 2, sy - hpx, pw, hpx))
        pygame.draw.rect(scr, (200, 200, 205), (rx - pw // 2, sy - hpx, pw, hpx))
        bar_h = max(3, hpx * 0.2)
        cells = 24
        cw = (rx - lx) / cells
        for i in range(cells):
            for j in range(2):
                c = (240, 240, 240) if (i + j) % 2 == 0 else (25, 25, 25)
                pygame.draw.rect(scr, c, (lx + i * cw, sy - hpx + j * bar_h / 2, cw + 1, bar_h / 2 + 1))

    def draw_particles(self):
        scr = self.screen
        for p in self.parts:
            k = p.life / p.max
            if p.kind == 1:
                pygame.draw.circle(scr, p.col, (int(p.x), int(p.y)), max(1, int(p.size * (0.4 + k))))
            else:
                pygame.draw.line(scr, p.col, (p.x, p.y), (p.x - p.vx * 0.035, p.y - p.vy * 0.035), 2)

        self.screen.blit(self.vig, (0, 0))

    def draw_hud(self):
        p = self.player
        pos_idx = self.order.index(p) + 1
        lap = clamp(p.laps_done + 1, 1, TOTAL_LAPS)

        self.panel((10, 10, 250, 138))
        self.text(f"LAP  {lap}/{TOTAL_LAPS}", self.f_med, (255, 255, 255), (22, 18))
        self.text(f"POSITION  {pos_idx}/{len(self.cars)}", self.f_med, (255, 220, 80), (22, 46))
        self.text(f"TIME  {fmt_time(self.race_time)}", self.f_small, (230, 230, 230), (22, 80))
        self.text("BEST  " + (fmt_time(self.best_lap) if self.best_lap else "--"), self.f_small, (150, 255, 160), (22, 104))
        self.text("LAST  " + (fmt_time(self.last_lap) if self.last_lap else "--"), self.f_small, (230, 230, 230), (22, 126))

        self.draw_gauge()
        self.draw_banners()

    def draw_gauge(self):
        p = self.player
        cx, cy, r = W - 100, H - 100, 74
        self.panel((cx - r - 16, cy - r - 16, 2 * r + 32, 2 * r + 32), 140)
        ratio = clamp(p.speed * KMH / KMH_MAX, 0, 1)
        a0, sweep, segs = 150, 240, 40
        for i in range(segs):
            a_1 = math.radians(a0 + sweep * i / segs)
            a_2 = math.radians(a0 + sweep * (i + 1) / segs - 1.4)
            on = (i + 0.5) / segs <= ratio
            col = mix((60, 220, 120), (255, 70, 50), i / segs) if on else (45, 50, 62)
            pts = [(cx + math.cos(a_1) * r, cy + math.sin(a_1) * r), (cx + math.cos(a_2) * r, cy + math.sin(a_2) * r),
                   (cx + math.cos(a_2) * (r - 14), cy + math.sin(a_2) * (r - 14)),
                   (cx + math.cos(a_1) * (r - 14), cy + math.sin(a_1) * (r - 14))]
            pygame.draw.polygon(self.screen, col, pts)
        a = math.radians(a0 + sweep * ratio)
        pygame.draw.line(self.screen, (255, 255, 255), (cx, cy), (cx + math.cos(a) * (r - 20), cy + math.sin(a) * (r - 20)), 3)
        pygame.draw.circle(self.screen, (255, 255, 255), (cx, cy), 6)
        self.text(str(int(p.speed * KMH)), self.f_num, (255, 255, 255), (cx, cy + 28), "center")
        self.text("km/h", self.f_small, (200, 205, 215), (cx, cy + 56), "center")

    def draw_banners(self):
        for i, (txt, col, t) in enumerate(self.banners):
            img = self.f_med.render(txt, True, col)
            sh = self.f_med.render(txt, True, (0, 0, 0))
            a = int(255 * clamp(t * 3, 0, 1))
            img.set_alpha(a)
            sh.set_alpha(a)
            r = img.get_rect(center=(W // 2, 110 + i * 34))
            self.screen.blit(sh, r.move(2, 2))
            self.screen.blit(img, r)

    def draw_overlays(self):
        cx = W // 2
        if self.state == "ready":
            self.panel((cx - 320, 90, 640, 380), 195)
            for off, col in (((-3, 0), (0, 235, 255)), ((3, 0), (255, 50, 210)), ((0, 0), (255, 240, 120))):
                img = self.f_title.render("TURBO RACER 3D", True, col)
                self.screen.blit(img, img.get_rect(midtop=(cx + off[0], 120 + off[1])))
            self.text("ULTRA EDITION", self.f_med, (255, 255, 255), (cx, 196), "midtop")
            self.text(f"1 race -  {TOTAL_LAPS} laps  -  4 opponents", self.f_med, (190, 215, 255), (cx, 236), "midtop")
            lines = ["Arrows / WASD: accelerate, brake and steer",]
            for i, l in enumerate(lines):
                self.text(l, self.f_small, (210, 220, 235), (cx, 292 + i * 28), "midtop")
            if pygame.time.get_ticks() // 500 % 2:
                self.text("Press ENTER to start", self.f_med, (120, 255, 150), (cx, 420), "midtop")
        elif self.state == "countdown":
            n = int(self.cd) + 1 if self.cd > 0 else 0
            frac = self.cd - int(self.cd) if self.cd > 0 else 0
            img = self.f_big.render(str(min(n, 3)), True, (255, 255, 255))
            sc = 1.0 + 0.5 * frac
            img = pygame.transform.rotozoom(img, 0, sc)
            sh = pygame.transform.rotozoom(self.f_big.render(str(min(n, 3)), True, (0, 0, 0)), 0, sc)
            r = img.get_rect(center=(cx, H // 3))
            self.screen.blit(sh, r.move(3, 3))
            self.screen.blit(img, r)
        elif self.state == "racing" and self.go_timer > 0:
            self.text("GO!", self.f_big, (90, 255, 120), (cx, H // 3), "center")
        elif self.state == "finished":
            self.draw_results()
        elif self.state == "champion":
            self.draw_champion()

    def draw_results(self):
        cx = W // 2
        x0, y0, w, h = cx - 290, 90, 580, 80 + 5 * 42 + 70
        self.panel((x0, y0, w, h), 205)
        self.text(f"RESULTS  RACE {self.race_no}/{RACES}", self.f_title, (255, 215, 60), (cx, y0 + 12), "midtop")
        hy = y0 + 78
        for label, x, anc in (("#", x0 + 20, "topleft"), ("NAME", x0 + 60, "topleft"), ("TIME", x0 + 340, "topright"),
                              ("POINTS", x0 + 440, "topright"), ("TOTAL", x0 + w - 20, "topright")):
            self.text(label, self.f_small, (160, 180, 210), (x, hy), anc, shadow=False)
        for i, c in enumerate(self.final_order):
            y = hy + 30 + i * 38
            if c.player:
                pygame.draw.rect(self.screen, (255, 255, 255), (x0 + 8, y - 4, w - 16, 34), 2, border_radius=5)
            self.text(str(i + 1), self.f_med, (255, 255, 255), (x0 + 20, y))
            pygame.draw.rect(self.screen, c.color, (x0 + 55, y + 4, 18, 18), border_radius=3)
            self.text(c.name, self.f_med, (255, 255, 255), (x0 + 82, y))
            t = fmt_time(c.finish_time) if c.finish_time is not None else "racing..."
            self.text(t, self.f_small, (230, 230, 230), (x0 + 340, y + 4), "topright")
            self.text(f"+{self.race_points.get(c.name, 0)}", self.f_med, (150, 255, 160), (x0 + 440, y), "topright")
            self.text(str(self.points.get(c.name, 0)), self.f_med, (255, 220, 80), (x0 + w - 20, y), "topright")
        if pygame.time.get_ticks() // 500 % 2:
            msg = "ENTER: next race" if self.race_no < RACES else "ENTER: championship"
            self.text(msg, self.f_med, (120, 255, 150), (cx, y0 + h - 42), "midtop")

    def draw_champion(self):
        cx = W // 2
        ranking = sorted(self.cars, key=lambda c: -self.points.get(c.name, 0))
        x0, y0, w, h = cx - 290, 70, 580, 480
        self.panel((x0, y0, w, h), 215)
        self.text("CHAMPIONSHIP", self.f_title, (255, 215, 60), (cx, y0 + 12), "midtop")
        # trophy
        gold = (255, 205, 60)
        tx, ty = cx, y0 + 112
        pygame.draw.polygon(self.screen, gold, [(tx - 34, ty - 30), (tx + 34, ty - 30), (tx + 22, ty + 16), (tx - 22, ty + 16)])
        pygame.draw.arc(self.screen, gold, (tx - 52, ty - 26, 36, 34), math.pi / 2, math.pi * 1.5, 5)
        pygame.draw.arc(self.screen, gold, (tx + 16, ty - 26, 36, 34), -math.pi / 2, math.pi / 2, 5)
        pygame.draw.rect(self.screen, gold, (tx - 6, ty + 16, 12, 18))
        pygame.draw.rect(self.screen, gold, (tx - 24, ty + 34, 48, 10), border_radius=3)
        winner = ranking[0]
        self.text(("YOU ARE THE CHAMPION!" if winner.player else f"{winner.name.upper()} WINS THE CHAMPIONSHIP"),
                  self.f_med, (255, 255, 255), (cx, y0 + 168), "midtop")
        for i, c in enumerate(ranking):
            y = y0 + 222 + i * 40
            if c.player:
                pygame.draw.rect(self.screen, (255, 255, 255), (x0 + 12, y - 4, w - 24, 36), 2, border_radius=5)
            self.text(str(i + 1), self.f_med, (255, 255, 255), (x0 + 28, y))
            pygame.draw.rect(self.screen, c.color, (x0 + 66, y + 4, 18, 18), border_radius=3)
            self.text(c.name, self.f_med, (255, 255, 255), (x0 + 94, y))
            self.text(f"{self.points.get(c.name, 0)} pts", self.f_med, (255, 220, 80), (x0 + w - 28, y), "topright")
        if pygame.time.get_ticks() // 500 % 2:
            self.text("ENTER: start over", self.f_med, (120, 255, 150), (cx, y0 + h - 40), "midtop")

    def draw(self):
        self.render_world()
        self.draw_hud()
        self.draw_overlays()

    # ---- main loop -------------------------------------------------------
    def start_race(self):
        self.new_race()
        self.state = "countdown"

    def handle_key(self, key):
        if key == pygame.K_RETURN:
            if self.state == "ready":
                self.start_race()
            elif self.state == "finished":
                if self.race_no >= RACES:
                    self.state = "champion"
                    self.parts = []
                else:
                    self.race_no += 1
                    self.start_race()
            elif self.state == "champion":
                self.points, self.race_no = {}, 1
                self.start_race()
        elif key == pygame.K_r and self.state in ("ready", "countdown", "racing"):
            self.start_race()

    def run(self):
        while True:
            dt = min(self.clock.tick(FPS) / 1000.0, 1 / 30)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    return
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        return
                    self.handle_key(e.key)
            k = pygame.key.get_pressed()
            inp = Inp(k[pygame.K_UP] or k[pygame.K_w], k[pygame.K_DOWN] or k[pygame.K_s],
                      k[pygame.K_LEFT] or k[pygame.K_a], k[pygame.K_RIGHT] or k[pygame.K_d])
            self.update(dt, inp)
            self.draw()
            pygame.display.flip()


if __name__ == "__main__":
    Game().run()
    pygame.quit()
    sys.exit()