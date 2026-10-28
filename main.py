#!/usr/bin/env python3
"""
TURBO RACER 3D  -  pseudo-3D racegame met pygame
------------------------------------------------
Eén circuit, 4 tegenstanders, live scorebord en puntentelling.

Starten:   pip install pygame   &&   python turbo_racer_3d.py

Besturing:
    Pijltjes / WASD  : gas, remmen, sturen
    ENTER            : start / nieuwe race
    R                : race opnieuw
    P                : pauze
    ESC              : afsluiten
"""
import math
import random
import sys

import pygame

# --------------------------------------------------------------------------
# Instellingen
# --------------------------------------------------------------------------
W, H = 1024, 640
FPS = 60

SEG_LEN = 200            # lengte van één wegsegment
ROAD_W = 2000            # halve wegbreedte
LANES = 3
CAM_H = 1000             # camerahoogte
FOV = 100
CAM_DEPTH = 1.0 / math.tan(math.radians(FOV / 2))
PLAYER_Z = CAM_H * CAM_DEPTH
DRAW_DIST = 220          # aantal segmenten dat getekend wordt
RUMBLE_LEN = 4

MAX_SPEED = 12000.0
ACCEL = MAX_SPEED / 3
BRAKE = -MAX_SPEED
DECEL = -MAX_SPEED / 3
OFFROAD_DECEL = -MAX_SPEED / 2
OFFROAD_LIMIT = MAX_SPEED / 4
CENTRIFUGAL = 0.3

CAR_W = 0.3              # autobreedte in halve wegbreedtes
TOTAL_LAPS = 3
POINTS = [10, 7, 5, 3, 1]
M_PER_UNIT = 0.00648     # spelunits -> meters
KMH = 280.0 / MAX_SPEED  # spelsnelheid -> km/u

SKY_TOP = (25, 95, 205)
SKY_BOT = (170, 215, 255)

ROAD_COL = [
    dict(road=(112, 112, 118), grass=(16, 190, 40), rumble=(205, 35, 35), lane=(215, 215, 215)),
    dict(road=(104, 104, 110), grass=(0, 150, 30), rumble=(235, 235, 235), lane=None),
]


# --------------------------------------------------------------------------
# Hulpfuncties
# --------------------------------------------------------------------------
def lerp(a, b, t):
    return a + (b - a) * t


def ease_in(a, b, p):
    return a + (b - a) * p * p


def ease_in_out(a, b, p):
    return a + (b - a) * ((-math.cos(p * math.pi) / 2) + 0.5)


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def fmt_time(t):
    m = int(t // 60)
    return f"{m}:{t - m * 60:05.2f}"


def project(wx, wy, wz, camx, camy, camz):
    """Wereldpunt -> (scherm_x, scherm_y, scherm_wegbreedte, schaal, cam_z)."""
    cx, cy, cz = wx - camx, wy - camy, wz - camz
    scale = CAM_DEPTH / max(cz, 1e-3)
    return (W / 2 + scale * cx * W / 2,
            H / 2 - scale * cy * H / 2,
            scale * ROAD_W * W / 2,
            scale,
            cz)


# --------------------------------------------------------------------------
# Sprites (alles met code getekend, geen plaatjes nodig)
# --------------------------------------------------------------------------
def draw_car(surf, cx, by, w, color):
    """Auto van achteren gezien. (cx, by) = midden onderkant, w = breedte in px."""
    if w < 2:
        return
    cx, by, w = int(cx), int(by), int(w)
    h = int(w * 0.55)
    if w < 7:
        pygame.draw.rect(surf, color, (cx - w // 2, by - h, w, h))
        return
    dark = tuple(int(c * 0.55) for c in color)
    # schaduw
    pygame.draw.ellipse(surf, (28, 28, 28),
                        (cx - int(w * 0.55), by - int(h * 0.14), int(w * 1.1), int(h * 0.28)))
    # onderkant carrosserie
    pygame.draw.rect(surf, color, (cx - w // 2, by - int(h * 0.62), w, int(h * 0.5)),
                     border_radius=max(2, w // 14))
    # cabine + raam
    top = by - h
    pygame.draw.polygon(surf, dark, [(cx - w * 0.38, by - h * 0.6), (cx - w * 0.27, top),
                                     (cx + w * 0.27, top), (cx + w * 0.38, by - h * 0.6)])
    pygame.draw.polygon(surf, (30, 45, 70), [(cx - w * 0.31, by - h * 0.64), (cx - w * 0.23, top + h * 0.1),
                                             (cx + w * 0.23, top + h * 0.1), (cx + w * 0.31, by - h * 0.64)])
    # wielen
    ww, wh = max(2, int(w * 0.15)), max(2, int(h * 0.4))
    pygame.draw.rect(surf, (18, 18, 18), (cx - w // 2 - ww // 3, by - wh, ww, wh), border_radius=2)
    pygame.draw.rect(surf, (18, 18, 18), (cx + w // 2 - ww + ww // 3, by - wh, ww, wh), border_radius=2)
    # achterlichten + kenteken
    lw, lh = max(2, int(w * 0.2)), max(2, int(h * 0.12))
    ly = by - int(h * 0.52)
    pygame.draw.rect(surf, (255, 40, 40), (cx - int(w * 0.42), ly, lw, lh))
    pygame.draw.rect(surf, (255, 40, 40), (cx + int(w * 0.42) - lw, ly, lw, lh))
    pygame.draw.rect(surf, (235, 235, 235), (cx - int(w * 0.1), ly, max(2, int(w * 0.2)), lh))


def draw_tree(surf, x, by, w, var):
    if w < 3 or w > 1500:
        return
    x, by, w = int(x), int(by), int(w)
    h = int(w * 1.8)
    tw = max(1, int(w * 0.14))
    pygame.draw.rect(surf, (90, 60, 30), (x - tw // 2, by - int(h * 0.35), tw, int(h * 0.35)))
    g = int(110 + var * 60)
    pygame.draw.polygon(surf, (20, g - 30, 30), [(x - w // 2, by - int(h * 0.25)),
                                                 (x + w // 2, by - int(h * 0.25)),
                                                 (x, by - int(h * 0.7))])
    pygame.draw.polygon(surf, (30, g, 40), [(x - int(w * 0.4), by - int(h * 0.5)),
                                            (x + int(w * 0.4), by - int(h * 0.5)),
                                            (x, by - h)])


def draw_sign(surf, x, by, w, direction):
    """Waarschuwingsbord voor scherpe bochten (direction: +1 rechts, -1 links)."""
    if w < 4 or w > 900:
        return
    x, by, w = int(x), int(by), int(w)
    h = int(w * 0.9)
    pw = max(1, w // 10)
    pygame.draw.rect(surf, (200, 200, 200), (x - pw // 2, by - h, pw, h))
    bw, bh = w, int(w * 0.6)
    top = by - h - bh // 2
    pygame.draw.rect(surf, (210, 30, 30), (x - bw // 2, top, bw, bh))
    pygame.draw.rect(surf, (255, 255, 255), (x - bw // 2, top, bw, bh), max(1, w // 14))
    d = direction
    pygame.draw.lines(surf, (255, 255, 255), False,
                      [(x - d * bw * 0.18, top + bh * 0.2), (x + d * bw * 0.18, top + bh * 0.5),
                       (x - d * bw * 0.18, top + bh * 0.8)], max(1, w // 12))


# --------------------------------------------------------------------------
# Circuit
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
    def __init__(self):
        self.segs = []
        self.last_y = 0.0
        self._build()
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
        s(100)                      # start/finish rechte stuk
        s(90, 3, 10)                # lichte bocht rechts, beetje omhoog
        s(80, 0, 30)                # klim
        s(90, -5, 0)                # scherpe bocht links op de top
        s(90, 0, -35)               # afdaling
        s(100, 2, 0)
        s(60, -4); s(60, 4); s(60, -3); s(60, 5)     # slingers
        s(120)
        s(100, -3, -10)
        s(70, 0, 20); s(70, 0, -20); s(70, 0, 30); s(70, 0, -30)   # achtbaan
        s(140, 5, 0)                # lange scherpe bocht
        s(80)
        s(90, -2, -self.last_y / SEG_LEN)   # terug naar hoogte 0
        self.segs[-1].y2 = 0.0

    def _dress(self):
        rng = random.Random(7)
        for seg in self.segs:
            i = seg.index
            if i % 4 == 0:
                for side in (-1, 1):
                    if rng.random() < 0.7:
                        seg.props.append((side * (2.3 + rng.random() * 2.5), "tree", rng.random()))
            if abs(seg.curve) >= 3.5 and i % 6 == 0:
                outer = -1 if seg.curve > 0 else 1
                seg.props.append((outer * 1.45, "sign", -outer))

    def find(self, z):
        return self.segs[int((z % self.length) // SEG_LEN)]

    def index_of(self, z):
        return int((z % self.length) // SEG_LEN)


# --------------------------------------------------------------------------
# Auto's
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
        self.finish_time = None


class Inp:
    def __init__(self, up=False, down=False, left=False, right=False):
        self.up, self.down, self.left, self.right = up, down, left, right


# --------------------------------------------------------------------------
# Spel
# --------------------------------------------------------------------------
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Turbo Racer 3D")
        self.screen = pygame.display.set_mode((W, H))
        self.clock = pygame.time.Clock()
        self.f_big = pygame.font.Font(None, 120)
        self.f_title = pygame.font.Font(None, 84)
        self.f_med = pygame.font.Font(None, 36)
        self.f_small = pygame.font.Font(None, 26)
        self.track = Track()
        self._make_background()
        self.points = {}
        self.paused = False
        self.reset()

    # ---- opbouw ----------------------------------------------------------
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
        sky = pygame.Surface((W, H))
        for y in range(H // 2 + 1):
            t = y / (H / 2)
            pygame.draw.line(sky, [int(lerp(SKY_TOP[i], SKY_BOT[i], t)) for i in range(3)], (0, y), (W, y))
        pygame.draw.circle(sky, (255, 245, 200), (W - 220, 110), 46)
        rng = random.Random(3)
        for _ in range(7):
            cx, cy = rng.randint(0, W), rng.randint(30, 180)
            for dx, dy, r in ((0, 0, 28), (30, 6, 22), (-30, 8, 20), (12, -10, 22)):
                pygame.draw.ellipse(sky, (250, 252, 255), (cx + dx - r * 1.6, cy + dy - r * 0.7, r * 3.2, r * 1.4))
        self.sky = sky
        self.hills_far = self._make_hills((95, 125, 185), [(1, 30, 0.5), (3, 18, 1.3), (7, 8, 2.1)], 55)
        self.hills_near = self._make_hills((40, 120, 70), [(2, 22, 2.0), (5, 12, 0.7), (11, 6, 1.1)], 28)
        self.bg_off = 0.0

    def reset(self):
        L = self.track.length
        self.cars = []
        specs = [("Daan", (225, 45, 45), 0.93), ("Sanne", (245, 205, 30), 0.90),
                 ("Ruben", (40, 185, 80), 0.87), ("Fenna", (175, 80, 205), 0.84)]
        rows = [(0, -0.5), (0, 0.5), (1, -0.5), (1, 0.5)]
        self.ai = []
        for (name, col, skill), (row, off) in zip(specs, rows):
            c = Car(name, col, -SEG_LEN * (4 + 5 * row), off, skill + random.uniform(-0.015, 0.015))
            c.lane = random.choice([-0.6, -0.25, 0.25, 0.6]) if row else off
            self.ai.append(c)
        self.player = Car("JIJ", (35, 100, 235), -SEG_LEN * (4 + 5 * 2), -0.5, player=True)
        self.cars = [self.player] + self.ai
        self.state = "ready"        # ready / countdown / racing / finished
        self.cd = 3.99
        self.race_time = 0.0
        self.go_timer = 0.0
        self.lap_start = 0.0
        self.last_lap = None
        self.best_lap = None
        self.shake = 0.0
        self.final_order = []
        self.race_points = {}
        self.order = list(self.cars)

    # ---- hulp ------------------------------------------------------------
    def signed(self, d):
        L = self.track.length
        return ((d + L / 2) % L) - L / 2

    def camera_pos(self):
        return (self.player.dist - PLAYER_Z) % self.track.length

    def standings(self):
        return sorted(self.cars, key=lambda c: (0, c.finish_time) if c.finish_time is not None else (1, -c.dist))

    # ---- logica ----------------------------------------------------------
    def update(self, dt, inp):
        if self.paused or self.state == "ready":
            return
        if self.state == "countdown":
            self.cd -= dt
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
        if can_drive and inp.up:
            p.speed += ACCEL * dt
        elif can_drive and inp.down:
            p.speed += BRAKE * dt
        else:
            p.speed += (DECEL if can_drive else DECEL * 2) * dt
        if (p.offset < -1 or p.offset > 1) and p.speed > OFFROAD_LIMIT:
            p.speed += OFFROAD_DECEL * dt
        p.offset = clamp(p.offset, -2.0, 2.0)
        p.speed = clamp(p.speed, 0, MAX_SPEED)
        p.dist += p.speed * dt

    def update_ai(self, car, dt):
        L = self.track.length
        seg = self.track.find(car.dist)
        if car.finish_time is not None:
            target = MAX_SPEED * 0.55
        else:
            target = MAX_SPEED * car.skill * (1 - 0.06 * max(0.0, abs(seg.curve) - 2))
            gap = self.signed(self.player.dist - car.dist)          # >0: speler voor
            target *= 1 + 0.05 * clamp(gap / (L * 0.25), -1, 1)     # lichte rubber-band
            target = min(target, MAX_SPEED * 0.97)

        # verkeer vooruit
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
        car.speed = clamp(car.speed, 0, MAX_SPEED)
        car.dist += car.speed * dt

    def collisions(self):
        p = self.player
        for a in self.ai:
            dz = self.signed(a.dist - p.dist)
            if abs(dz) < 500 and abs(a.offset - p.offset) < CAR_W:
                self.shake = 0.25
                if dz > 0:       # speler rijdt achterop
                    p.speed = min(p.speed, a.speed * 0.8)
                    p.dist = a.dist - 500
                else:            # AI rijdt op speler
                    a.speed = min(a.speed, p.speed * 0.8)
                    a.dist = p.dist - 500

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
                    self.best_lap = t if self.best_lap is None else min(self.best_lap, t)
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

    # ---- tekenen ---------------------------------------------------------
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
        track, segs, N = self.track, self.track.segs, self.track.n
        L = track.length
        p = self.player

        # achtergrond
        scr.blit(self.sky, (0, 0))
        for layer, f in ((self.hills_far, 0.3), (self.hills_near, 0.7)):
            off = int(self.bg_off * f) % W
            scr.blit(layer, (-off, 0))
            scr.blit(layer, (W - off, 0))
        scr.fill(ROAD_COL[0]["grass"], (0, H // 2, W, H - H // 2))

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
            col = ROAD_COL[seg.col]
            # gras
            gy2, gy1 = int(y2), int(y1)
            scr.fill(col["grass"], (0, gy2, W, gy1 - gy2))
            # rand / rumble
            r1, r2 = w1 / max(6, 2 * LANES), w2 / max(6, 2 * LANES)
            poly(scr, col["rumble"], [(x1 - w1 - r1, y1), (x1 - w1, y1), (x2 - w2, y2), (x2 - w2 - r2, y2)])
            poly(scr, col["rumble"], [(x1 + w1 + r1, y1), (x1 + w1, y1), (x2 + w2, y2), (x2 + w2 + r2, y2)])
            # weg
            poly(scr, col["road"], [(x1 - w1, y1), (x1 + w1, y1), (x2 + w2, y2), (x2 - w2, y2)])
            # startlijn
            if seg.index < 2:
                for c in range(8):
                    cc = (235, 235, 235) if (c + seg.index) % 2 == 0 else (25, 25, 25)
                    a, b = c / 8, (c + 1) / 8
                    poly(scr, cc, [(x1 - w1 + 2 * w1 * a, y1), (x1 - w1 + 2 * w1 * b, y1),
                                   (x2 - w2 + 2 * w2 * b, y2), (x2 - w2 + 2 * w2 * a, y2)])
            elif col["lane"]:
                lw1, lw2 = w1 / max(32, 8 * LANES), w2 / max(32, 8 * LANES)
                lane_w1, lane_w2 = w1 * 2 / LANES, w2 * 2 / LANES
                lx1, lx2 = x1 - w1 + lane_w1, x2 - w2 + lane_w2
                for _ in range(1, LANES):
                    poly(scr, col["lane"], [(lx1 - lw1 / 2, y1), (lx1 + lw1 / 2, y1),
                                            (lx2 + lw2 / 2, y2), (lx2 - lw2 / 2, y2)])
                    lx1 += lane_w1
                    lx2 += lane_w2
            maxy = y1

        # sprites van ver naar dichtbij
        buckets = {}
        for c in self.ai:
            buckets.setdefault(track.index_of(c.dist), []).append(c)
        for n in range(DRAW_DIST - 1, -1, -1):
            seg = segs[(base.index + n) % N]
            s1, s2 = seg.s1, seg.s2
            cars_here = buckets.get(seg.index)
            if not seg.props and not cars_here and seg.index != 0:
                continue
            scr.set_clip((0, 0, W, max(0, int(seg.clip))))
            if s1[4] > 200:
                for off, kind, var in seg.props:
                    sx = s1[0] + s1[3] * off * ROAD_W * W / 2
                    if kind == "tree":
                        draw_tree(scr, sx, s1[1], s1[3] * 1300 * W / 2, var)
                    else:
                        draw_sign(scr, sx, s1[1], s1[3] * 520 * W / 2, var)
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
                    draw_car(scr, sx, sy, scale * CAR_W * ROAD_W * W / 2, c.color)
        scr.set_clip(None)

        # speler
        scale = CAM_DEPTH / PLAYER_Z
        py = H / 2 - scale * (player_y - cam_y) * H / 2 - 14
        shake = random.uniform(-4, 4) if self.shake > 0 else 0
        bounce = random.uniform(0, 2 + (4 if abs(p.offset) > 1 else 0)) * (p.speed / MAX_SPEED)
        draw_car(scr, W / 2 + shake, py - bounce, scale * CAR_W * ROAD_W * W / 2, p.color)

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

    def draw_hud(self):
        p = self.player
        pos_idx = self.order.index(p) + 1
        lap = clamp(p.laps_done + 1, 1, TOTAL_LAPS)

        # linkerpaneel
        self.panel((10, 10, 250, 138))
        self.text(f"RONDE  {lap}/{TOTAL_LAPS}", self.f_med, (255, 255, 255), (22, 18))
        self.text(f"POSITIE  {pos_idx}/{len(self.cars)}", self.f_med, (255, 220, 80), (22, 46))
        self.text(f"TIJD  {fmt_time(self.race_time)}", self.f_small, (230, 230, 230), (22, 80))
        self.text("BESTE  " + (fmt_time(self.best_lap) if self.best_lap else "--"), self.f_small, (150, 255, 160), (22, 104))
        self.text("LAATSTE  " + (fmt_time(self.last_lap) if self.last_lap else "--"), self.f_small, (230, 230, 230), (22, 126 - 0))

        # scorebord rechts
        bx, by, bw = W - 280, 10, 270
        self.panel((bx, by, bw, 40 + 30 * len(self.order)))
        self.text("SCOREBORD", self.f_small, (255, 255, 255), (bx + 12, by + 8))
        leader = self.order[0]
        for i, c in enumerate(self.order):
            y = by + 38 + i * 30
            if c.player:
                pygame.draw.rect(self.screen, (255, 255, 255), (bx + 4, y - 3, bw - 8, 28), 2, border_radius=4)
            self.text(str(i + 1), self.f_small, (255, 255, 255), (bx + 14, y))
            pygame.draw.rect(self.screen, c.color, (bx + 38, y + 2, 16, 16), border_radius=3)
            self.text(c.name, self.f_small, (255, 255, 255), (bx + 62, y))
            if c.finish_time is not None:
                right = fmt_time(c.finish_time)
            elif c is leader:
                right = f"R{clamp(c.laps_done + 1, 1, TOTAL_LAPS)}  LEIDER"
            else:
                right = f"R{clamp(c.laps_done + 1, 1, TOTAL_LAPS)}  +{int((leader.dist - c.dist) * M_PER_UNIT)}m"
            self.text(right, self.f_small, (210, 230, 255), (bx + bw - 12, y), "topright")

        # voortgangsbalk
        px, py_, pw = W // 2 - 220, 22, 440
        self.panel((px - 10, py_ - 12, pw + 20, 26), 110)
        pygame.draw.line(self.screen, (200, 200, 200), (px, py_), (px + pw, py_), 3)
        L = self.track.length
        for c in sorted(self.cars, key=lambda c: c.player):
            fx = px + pw * ((c.dist % L) / L)
            pygame.draw.circle(self.screen, c.color, (fx, py_), 8 if c.player else 5)
            if c.player:
                pygame.draw.circle(self.screen, (255, 255, 255), (fx, py_), 8, 2)

        # snelheid
        kmh = int(p.speed * KMH)
        self.text(f"{kmh}", self.f_title, (255, 255, 255), (W - 130, H - 40), "bottomright")
        self.text("km/u", self.f_med, (220, 220, 220), (W - 20, H - 46), "bottomright")
        pygame.draw.rect(self.screen, (40, 40, 40), (W - 260, H - 30, 240, 12), border_radius=6)
        pygame.draw.rect(self.screen, (255, 90 + int(120 * (1 - p.speed / MAX_SPEED)), 40),
                         (W - 260, H - 30, int(240 * p.speed / MAX_SPEED), 12), border_radius=6)

    def draw_overlays(self):
        cx = W // 2
        if self.state == "ready":
            self.panel((cx - 300, 110, 600, 330), 190)
            self.text("TURBO RACER 3D", self.f_title, (255, 215, 60), (cx, 150), "midtop")
            self.text(f"{TOTAL_LAPS} ronden  -  4 tegenstanders", self.f_med, (255, 255, 255), (cx, 230), "midtop")
            lines = ["Pijltjes / WASD: gas, rem en sturen", "P: pauze     R: opnieuw     ESC: stoppen",
                     "Blijf op het asfalt, gras kost snelheid!"]
            for i, l in enumerate(lines):
                self.text(l, self.f_small, (210, 220, 235), (cx, 285 + i * 28), "midtop")
            if pygame.time.get_ticks() // 500 % 2:
                self.text("Druk op ENTER om te starten", self.f_med, (120, 255, 150), (cx, 395), "midtop")
        elif self.state == "countdown":
            n = int(self.cd) + 1 if self.cd > 0 else 0
            self.text(str(min(n, 3)), self.f_big, (255, 255, 255), (cx, H // 3), "center")
        elif self.state == "racing" and self.go_timer > 0:
            self.text("GO!", self.f_big, (90, 255, 120), (cx, H // 3), "center")
        elif self.state == "finished":
            self.draw_results()
        if self.paused:
            self.panel((0, 0, W, H), 130)
            self.text("PAUZE", self.f_title, (255, 255, 255), (cx, H // 2), "center")

    def draw_results(self):
        cx = W // 2
        x0, y0, w, h = cx - 290, 90, 580, 80 + 5 * 42 + 70
        self.panel((x0, y0, w, h), 205)
        self.text("UITSLAG", self.f_title, (255, 215, 60), (cx, y0 + 12), "midtop")
        hy = y0 + 78
        for label, x, anc in (("#", x0 + 20, "topleft"), ("NAAM", x0 + 60, "topleft"), ("TIJD", x0 + 340, "topright"),
                              ("PUNTEN", x0 + 440, "topright"), ("TOTAAL", x0 + w - 20, "topright")):
            self.text(label, self.f_small, (160, 180, 210), (x, hy), anc, shadow=False)
        for i, c in enumerate(self.final_order):
            y = hy + 30 + i * 38
            if c.player:
                pygame.draw.rect(self.screen, (255, 255, 255), (x0 + 8, y - 4, w - 16, 34), 2, border_radius=5)
            self.text(str(i + 1), self.f_med, (255, 255, 255), (x0 + 20, y))
            pygame.draw.rect(self.screen, c.color, (x0 + 55, y + 4, 18, 18), border_radius=3)
            self.text(c.name, self.f_med, (255, 255, 255), (x0 + 82, y))
            t = fmt_time(c.finish_time) if c.finish_time is not None else "onderweg..."
            self.text(t, self.f_small, (230, 230, 230), (x0 + 340, y + 4), "topright")
            self.text(f"+{self.race_points.get(c.name, 0)}", self.f_med, (150, 255, 160), (x0 + 440, y), "topright")
            self.text(str(self.points.get(c.name, 0)), self.f_med, (255, 220, 80), (x0 + w - 20, y), "topright")
        if pygame.time.get_ticks() // 500 % 2:
            self.text("ENTER: nieuwe race", self.f_med, (120, 255, 150), (cx, y0 + h - 42), "midtop")

    def draw(self):
        self.render_world()
        self.draw_hud()
        self.draw_overlays()

    # ---- hoofdlus --------------------------------------------------------
    def start_race(self):
        self.reset()
        self.state = "countdown"

    def run(self):
        while True:
            dt = min(self.clock.tick(FPS) / 1000.0, 1 / 30)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    return
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        return
                    if e.key == pygame.K_RETURN and self.state in ("ready", "finished"):
                        self.start_race()
                    elif e.key == pygame.K_r:
                        self.start_race()
                    elif e.key == pygame.K_p and self.state in ("racing", "countdown"):
                        self.paused = not self.paused
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