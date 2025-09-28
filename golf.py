import math
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any
import pygame

# ---------- Window / World ----------
W, H = 1000, 600        # window == world (no scrolling)
FPS = 60

# ---------- Colors ----------
SKY = (142, 204, 255)
DIRT = (145, 108, 78)
GRASS = (96, 186, 74)
WHITE = (245, 245, 245)
DARK = (20, 24, 28)
UI = (30, 30, 30)
FLAG_RED = (220, 40, 40)
POLE = (210, 210, 210)

# ---------- Physics ----------
GRAVITY = 2000.0            # px/s^2 downward
AIR_DRAG = 0.0008           # ~ v^2 drag
GROUND_FRICTION = 0.82      # per-second keep factor
REST_BOUNCE = 0.25          # bounciness on impacts
STOP_SPEED = 40.0           # below = considered resting
BALL_R = 12

# Shot tuning
POWER_SCALE = 10.0          # pixels of drag -> speed
MAX_POWER = 1800.0          # speed cap
AIM_MIN_DRAG = 6.0

# ---------------- Level Data ----------------
# Each level has: platforms [(x,y,w,h)], start (x,y), hole_anchor_x
LEVELS = [
    {
        "name": "Warm-up",
        "platforms": [
            (0, H - 60, W, 60),
            (260, H - 180, 160, 20),
            (540, H - 260, 140, 20),
            (760, H - 120, 120, 20),
            (420, H - 120, 40, 100),
        ],
        "start": (80, H - 90),
        "hole_x": 820,
    },
    {
        "name": "Over the Gap",
        "platforms": [
            (0, H - 60, 400, 60),
            (560, H - 60, 440, 60),        # gap between 400..560
            (250, H - 200, 120, 18),
            (720, H - 220, 160, 18),
            (460, H - 180, 40, 120),
            (610, H - 140, 40, 80),
        ],
        "start": (100, H - 90),
        "hole_x": 820,
    },

    # --- NEW LEVEL 3 ---
    {
        "name": "Stairway",
        "platforms": [
            (0,   H - 60, W, 60),            # ground
            (180, H - 160, 130, 18),
            (340, H - 220, 130, 18),
            (500, H - 280, 130, 18),
            (660, H - 340, 130, 18),
            (820, H - 200, 120, 18),         # final landing below
            (430, H - 120, 40, 60),          # blocker under steps
        ],
        "start": (90, H - 90),
        "hole_x": 690,                       # on the 4th “step”
    },

    # --- NEW LEVEL 4 ---
    {
        "name": "Cave Ceiling",
        "platforms": [
            (0,   H - 60, 360, 60),          # left ground
            (640, H - 60, 360, 60),          # right ground
            (360, H - 260, 280, 20),         # “ceiling” over the gap
            (220, H - 170, 80, 18),          # small approach ledge
            (700, H - 170, 80, 18),          # small landing ledge
            (500, H - 120, 40, 120),         # tall pillar in the gap
        ],
        "start": (120, H - 90),
        "hole_x": 700,                       # small landing ledge on right
    },

    # --- NEW LEVEL 5 ---
    {
        "name": "High Plateau",
        "platforms": [
            (0,   H - 60, W, 60),            # ground
            (260, H - 260, 160, 18),
            (480, H - 320, 160, 18),
            (720, H - 240, 180, 18),         # high plateau near hole
            (380, H - 140, 40, 80),          # blocker
            (600, H - 180, 40, 120),         # blocker
        ],
        "start": (80, H - 90),
        "hole_x": 790,                       # on the high plateau
    },
]

HOLE_R = 18
FLAG_HEIGHT = 70
FLAG_LENGTH = 36

# --------------------------------------------------------

@dataclass
class Ball:
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    on_ground: bool = False
    def speed(self): return math.hypot(self.vx, self.vy)
    def rect(self):  return pygame.Rect(int(self.x - BALL_R), int(self.y - BALL_R), BALL_R*2, BALL_R*2)
    def copy(self):  return Ball(self.x, self.y, self.vx, self.vy, self.on_ground)

def circle_rect_resolve(ball: Ball, r: pygame.Rect):
    """Resolve circle-rect overlap; push out along minimum axis and reflect velocity."""
    cx, cy, rad = ball.x, ball.y, BALL_R
    qx = max(r.left,  min(cx, r.right))
    qy = max(r.top,   min(cy, r.bottom))
    dx, dy = cx - qx, cy - qy
    d2 = dx*dx + dy*dy
    if d2 > rad*rad:
        return
    d = math.sqrt(d2) if d2 > 0 else 1e-6
    nx, ny = dx/d, dy/d
    overlap = rad - d
    ball.x += nx * overlap
    ball.y += ny * overlap
    vn = ball.vx*nx + ball.vy*ny
    ball.vx -= (1 + REST_BOUNCE) * vn * nx
    ball.vy -= (1 + REST_BOUNCE) * vn * ny
    if ny < -0.6:
        ball.on_ground = True
        ball.vy = min(ball.vy, 0)

def integrate(ball: Ball, dt: float):
    ball.vy += GRAVITY * dt
    sp = ball.speed()
    if sp > 0:
        drag = AIR_DRAG * sp * sp
        if drag > 0:
            ball.vx -= (ball.vx / sp) * drag * dt
            ball.vy -= (ball.vy / sp) * drag * dt
    ball.x += ball.vx * dt
    ball.y += ball.vy * dt

def draw_level(screen: pygame.Surface, platforms: List[Tuple[int,int,int,int]]):
    screen.fill(SKY)
    for (x, y, w, h) in platforms:
        pygame.draw.rect(screen, DIRT, (x, y, w, h))
        if h <= 60:
            pygame.draw.rect(screen, GRASS, (x, y - 8, w, 12))

def predict_path(ball: Ball, platforms, vx0: float, vy0: float, steps=34, step_dt=1/30):
    x, y = ball.x, ball.y
    vx, vy = vx0, vy0
    pts = []
    for _ in range(steps):
        sp = math.hypot(vx, vy)
        vy += GRAVITY * step_dt
        if sp > 0:
            drag = AIR_DRAG * sp * sp
            vx -= (vx / sp) * drag * step_dt
            vy -= (vy / sp) * drag * step_dt
        x += vx * step_dt
        y += vy * step_dt
        pts.append((x, y))
        for (px, py, pw, ph) in platforms:
            if pygame.Rect(px, py, pw, ph).collidepoint(x, y + BALL_R):
                return pts
    return pts

def surface_y_at_x(platforms, x: float) -> int:
    candidates = [py for (px, py, pw, ph) in platforms if px <= x <= px + pw]
    if candidates:
        return min(candidates)
    # Fallback: highest (smallest y) surface among all
    return min(py for (_, py, _, _) in platforms)

def simulate_to_rest(ball: Ball, platforms, hole_pos, hole_r, stop_speed=STOP_SPEED):
    """Offline-simulate physics until the ball settles (or sinks/falls)."""
    b = ball.copy()
    sunk = False
    hx, hy = hole_pos

    SIM_DT = 1/300.0
    MAX_SIM_TIME = 8.0
    MAX_STEPS = int(MAX_SIM_TIME / SIM_DT)
    settled_frames_needed = int(0.15 / SIM_DT)

    settled_counter = 0

    for _ in range(MAX_STEPS):
        b.on_ground = False
        integrate(b, SIM_DT)

        br = pygame.Rect(int(b.x - BALL_R), int(b.y - BALL_R), BALL_R*2, BALL_R*2)
        for (x, y, w, h) in platforms:
            r = pygame.Rect(x, y, w, h)
            if r.colliderect(br):
                circle_rect_resolve(b, r)
                br = pygame.Rect(int(b.x - BALL_R), int(b.y - BALL_R), BALL_R*2, BALL_R*2)

        if b.x < BALL_R:
            b.x = BALL_R; b.vx = -b.vx * REST_BOUNCE
        if b.x > W - BALL_R:
            b.x = W - BALL_R; b.vx = -b.vx * REST_BOUNCE
        if b.y < BALL_R:
            b.y = BALL_R; b.vy = -b.vy * REST_BOUNCE
        if b.y > H + 200:
            return Ball(*START_POS), False

        if b.on_ground and b.speed() > 0:
            keep = pow(GROUND_FRICTION, SIM_DT)
            b.vx *= keep
            if abs(b.vy) < 10: b.vy = 0

        dx = b.x - hx
        dy = b.y - hy
        if dx*dx + dy*dy <= (hole_r - 2)**2 and b.speed() < 320 and b.y >= hy - BALL_R - 2:
            b.vx = b.vy = 0
            b.x, b.y = hx, hy
            sunk = True
            break

        if b.on_ground and b.speed() < stop_speed:
            settled_counter += 1
            if settled_counter >= settled_frames_needed:
                b.vx = b.vy = 0
                break
        else:
            settled_counter = 0

    return b, sunk

def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Side-View Golf — Multi-Level")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 26)
    big = pygame.font.SysFont(None, 54)

    level_index = 0

    def load_level(i: int):
        nonlocal level_index, PLATFORMS, START_POS, HOLE_POS, hole_surface_y
        level_index = max(0, min(i, len(LEVELS)-1))
        PLATFORMS = LEVELS[level_index]["platforms"]
        START_POS = LEVELS[level_index]["start"]
        hole_x = LEVELS[level_index]["hole_x"]
        hole_surface_y = surface_y_at_x(PLATFORMS, hole_x)
        HOLE_POS = (hole_x, hole_surface_y)
        return PLATFORMS, START_POS, HOLE_POS, hole_surface_y

    PLATFORMS: List[Tuple[int,int,int,int]]
    START_POS: Tuple[int,int]
    HOLE_POS: Tuple[int,int]
    hole_surface_y: int
    PLATFORMS, START_POS, HOLE_POS, hole_surface_y = load_level(level_index)

    ball = Ball(*START_POS)
    strokes = 0
    sunk = False
    aiming = False
    drag_start = (0, 0)
    course_complete = False

    def reset_ball_only():
        nonlocal ball, strokes, sunk, aiming
        ball = Ball(*START_POS)
        strokes = 0
        sunk = False
        aiming = False

    def next_level():
        nonlocal course_complete
        if level_index < len(LEVELS) - 1:
            load_level(level_index + 1)
            reset_ball_only()
        else:
            course_complete = True

    def prev_level():
        if level_index > 0:
            load_level(level_index - 1)
            reset_ball_only()

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        ball.on_ground = False

        # -------- Input --------
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    running = False
                elif e.key == pygame.K_r:
                    reset_ball_only()
                elif e.key == pygame.K_f:
                    predicted, will_sink = simulate_to_rest(ball, PLATFORMS, HOLE_POS, HOLE_R)
                    ball = predicted
                    sunk = sunk or will_sink
                elif e.key == pygame.K_n:   # manual next level
                    next_level()
                elif e.key == pygame.K_p:   # manual previous level
                    prev_level()
                elif e.key == pygame.K_RETURN and sunk and not course_complete:
                    next_level()
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and not sunk and not course_complete:
                mx, my = e.pos
                if ball.speed() < STOP_SPEED and ball.rect().collidepoint(mx, my):
                    aiming = True
                    drag_start = (mx, my)
            elif e.type == pygame.MOUSEBUTTONUP and e.button == 1 and aiming and not sunk and not course_complete:
                mx, my = e.pos
                dx, dy = mx - drag_start[0], my - drag_start[1]
                power = min(MAX_POWER, math.hypot(dx, dy) * POWER_SCALE)
                if power > AIM_MIN_DRAG:
                    ang = math.atan2(dy, dx)
                    ball.vx = -math.cos(ang) * power
                    ball.vy = -math.sin(ang) * power
                    strokes += 1
                aiming = False

        # -------- Physics --------
        if not sunk and not course_complete:
            integrate(ball, dt)

            br = ball.rect()
            for (x, y, w, h) in PLATFORMS:
                r = pygame.Rect(x, y, w, h)
                if r.colliderect(br):
                    circle_rect_resolve(ball, r)
                    br = ball.rect()

            if ball.on_ground and ball.speed() > 0:
                keep = pow(GROUND_FRICTION, dt)
                ball.vx *= keep
                if abs(ball.vy) < 10: ball.vy = 0
            if ball.on_ground and ball.speed() < STOP_SPEED:
                ball.vx = ball.vy = 0

            if ball.x < BALL_R:
                ball.x = BALL_R; ball.vx = -ball.vx * REST_BOUNCE
            if ball.x > W - BALL_R:
                ball.x = W - BALL_R; ball.vx = -ball.vx * REST_BOUNCE
            if ball.y < BALL_R:
                ball.y = BALL_R; ball.vy = -ball.vy * REST_BOUNCE
            if ball.y > H + 200:
                reset_ball_only()

            # Sink check (on-surface)
            dx = ball.x - HOLE_POS[0]
            dy = ball.y - HOLE_POS[1]
            near = (dx*dx + dy*dy) <= (HOLE_R - 2)**2
            at_surface = ball.y >= hole_surface_y - BALL_R - 2
            slow = ball.speed() < 320
            if near and at_surface and slow:
                sunk = True
                ball.vx = ball.vy = 0
                ball.x, ball.y = HOLE_POS

        # -------- Draw --------
        draw_level(screen, PLATFORMS)

        # hole + flag
        hx, hy = HOLE_POS
        pygame.draw.circle(screen, (30, 30, 40), (hx, hy + 2), HOLE_R + 3)
        pygame.draw.circle(screen, (10, 10, 16), (hx, hy), HOLE_R)
        pygame.draw.circle(screen, (70, 70, 70), (hx, hy), HOLE_R, 2)
        pole_top_y = hy - FLAG_HEIGHT
        pygame.draw.line(screen, POLE, (hx, hy - 1), (hx, pole_top_y), 3)
        flag_pts = [(hx, pole_top_y),
                    (hx + FLAG_LENGTH, pole_top_y + 8),
                    (hx, pole_top_y + 16)]
        pygame.draw.polygon(screen, FLAG_RED, flag_pts)

        # aim preview
        if aiming:
            mx, my = pygame.mouse.get_pos()
            dx, dy = mx - drag_start[0], my - drag_start[1]
            power = min(MAX_POWER, math.hypot(dx, dy) * POWER_SCALE)
            ang = math.atan2(dy, dx)
            vx, vy = -math.cos(ang) * power, -math.sin(ang) * power
            pts = predict_path(ball, PLATFORMS, vx, vy)
            for i, (px, py) in enumerate(pts[::2]):
                a = max(60, 220 - i * 8)
                s = max(2, 6 - i // 5)
                dot = pygame.Surface((s*2, s*2), pygame.SRCALPHA)
                pygame.draw.circle(dot, (255, 255, 255, a), (s, s), s)
                screen.blit(dot, (px - s, py - s))
            pygame.draw.line(screen, (255, 255, 255), (ball.x, ball.y), (mx, my), 2)

        # ball
        pygame.draw.circle(screen, (0, 0, 0), (int(ball.x + 2), int(ball.y + 2)), BALL_R)
        pygame.draw.circle(screen, WHITE, (int(ball.x), int(ball.y)), BALL_R)

        # UI
        title = LEVELS[level_index]["name"]
        hud = font.render(f"Level {level_index+1}/{len(LEVELS)} — {title}  |  Strokes: {strokes}", True, UI)
        screen.blit(hud, (14, 12))
        controls = font.render("Drag: aim  •  F: fast-forward  •  R: reset  •  N/P: next/prev  •  Enter: next when sunk", True, UI)
        screen.blit(controls, (14, 40))

        if sunk and not course_complete:
            msg = big.render(f"🏁 Sunk in {strokes}! Press Enter for next level.", True, UI)
            screen.blit(msg, msg.get_rect(center=(W//2, 90)))

        if course_complete:
            done = big.render("🎉 Course complete! Press P to revisit previous levels.", True, UI)
            screen.blit(done, done.get_rect(center=(W//2, 90)))

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()