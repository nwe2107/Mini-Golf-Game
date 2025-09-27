import math
from dataclasses import dataclass
from typing import List, Tuple
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

# ---------- Level (edit these) ----------
# Rectangles: (x, y, w, h) in screen/world coords; y grows downward.
PLATFORMS: List[Tuple[int, int, int, int]] = [
    (0, H - 60, W, 60),              # ground
    (260, H - 180, 160, 20),         # ledge 1
    (540, H - 260, 140, 20),         # ledge 2
    (760, H - 120, 120, 20),         # near-hole ledge
    (420, H - 120, 40, 100),         # vertical blocker
]
START_POS = (80, H - 90)
HOLE_POS = (880, H - 140)            # set on the near-hole ledge
HOLE_R = 18

# ---------------------------------------

@dataclass
class Ball:
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    on_ground: bool = False
    def speed(self): return math.hypot(self.vx, self.vy)
    def rect(self):  return pygame.Rect(int(self.x - BALL_R), int(self.y - BALL_R), BALL_R*2, BALL_R*2)

def circle_rect_resolve(ball: Ball, r: pygame.Rect):
    """Resolve circle-rect overlap; push out along minimum axis and reflect velocity."""
    cx, cy, rad = ball.x, ball.y, BALL_R
    # closest point on rect to circle center
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

    # reflect velocity along collision normal
    vn = ball.vx*nx + ball.vy*ny
    ball.vx -= (1 + REST_BOUNCE) * vn * nx
    ball.vy -= (1 + REST_BOUNCE) * vn * ny

    # standing test: normal mostly upward (screen y increases downward)
    if ny < -0.6:
        ball.on_ground = True
        # prevent tiny jitter into platform
        ball.vy = min(ball.vy, 0)

def integrate(ball: Ball, dt: float):
    # gravity
    ball.vy += GRAVITY * dt
    # air drag ~ v^2
    sp = ball.speed()
    if sp > 0:
        drag = AIR_DRAG * sp * sp
        if drag > 0:
            ball.vx -= (ball.vx / sp) * drag * dt
            ball.vy -= (ball.vy / sp) * drag * dt
    # integrate
    ball.x += ball.vx * dt
    ball.y += ball.vy * dt

def draw_level(screen: pygame.Surface):
    # sky
    screen.fill(SKY)
    # platforms (dirt + grass lip)
    for (x, y, w, h) in PLATFORMS:
        pygame.draw.rect(screen, DIRT, (x, y, w, h))
        # grass strip along top if shallow
        if h <= 60:
            pygame.draw.rect(screen, GRASS, (x, y - 8, w, 12))

def predict_path(ball: Ball, vx0: float, vy0: float, steps=34, step_dt=1/30):
    """Simple prediction of the arc for UI preview."""
    x, y = ball.x, ball.y
    vx, vy = vx0, vy0
    pts = []
    for _ in range(steps):
        # physics
        sp = math.hypot(vx, vy)
        vy += GRAVITY * step_dt
        if sp > 0:
            drag = AIR_DRAG * sp * sp
            vx -= (vx / sp) * drag * step_dt
            vy -= (vy / sp) * drag * step_dt
        x += vx * step_dt
        y += vy * step_dt
        pts.append((x, y))
        # stop preview if would hit a platform
        for (px, py, pw, ph) in PLATFORMS:
            if pygame.Rect(px, py, pw, ph).collidepoint(x, y + BALL_R):
                return pts
    return pts

def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Side-View Golf")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 26)
    big = pygame.font.SysFont(None, 54)

    ball = Ball(*START_POS)
    strokes = 0
    sunk = False
    aiming = False
    drag_start = (0, 0)

    def reset():
        nonlocal ball, strokes, sunk, aiming
        ball = Ball(*START_POS)
        strokes = 0
        sunk = False
        aiming = False

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        ball.on_ground = False

        # -------- Input --------
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE: running = False
                elif e.key == pygame.K_r:     reset()
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and not sunk:
                mx, my = e.pos
                if ball.speed() < STOP_SPEED and ball.rect().collidepoint(mx, my):
                    aiming = True
                    drag_start = (mx, my)
            elif e.type == pygame.MOUSEBUTTONUP and e.button == 1 and aiming and not sunk:
                mx, my = e.pos
                dx, dy = mx - drag_start[0], my - drag_start[1]
                power = min(MAX_POWER, math.hypot(dx, dy) * POWER_SCALE)
                if power > AIM_MIN_DRAG:
                    ang = math.atan2(dy, dx)
                    # shoot opposite to drag
                    ball.vx = -math.cos(ang) * power
                    ball.vy = -math.sin(ang) * power
                    strokes += 1
                aiming = False

        # -------- Physics --------
        if not sunk:
            integrate(ball, dt)

            # collide with platforms
            br = ball.rect()
            for (x, y, w, h) in PLATFORMS:
                r = pygame.Rect(x, y, w, h)
                if r.colliderect(br):
                    circle_rect_resolve(ball, r)
                    br = ball.rect()  # update proxy after resolve

            # ground friction if resting on a surface
            if ball.on_ground and ball.speed() > 0:
                keep = pow(GROUND_FRICTION, dt)    # per-second → per-frame
                ball.vx *= keep
                # clamp tiny vertical jitter
                if abs(ball.vy) < 10: ball.vy = 0

            if ball.on_ground and ball.speed() < STOP_SPEED:
                ball.vx = ball.vy = 0

            # world bounds
            if ball.x < BALL_R:
                ball.x = BALL_R; ball.vx = -ball.vx * REST_BOUNCE
            if ball.x > W - BALL_R:
                ball.x = W - BALL_R; ball.vx = -ball.vx * REST_BOUNCE
            if ball.y < BALL_R:
                ball.y = BALL_R; ball.vy = -ball.vy * REST_BOUNCE
            if ball.y > H + 200:   # fell below level → reset
                reset()

            # hole check (must be close and not screaming fast)
            dx = ball.x - HOLE_POS[0]
            dy = ball.y - HOLE_POS[1]
            if dx*dx + dy*dy <= (HOLE_R - 2)**2 and ball.speed() < 320:
                sunk = True
                ball.vx = ball.vy = 0
                ball.x, ball.y = HOLE_POS

        # -------- Draw --------
        draw_level(screen)
        # hole
        pygame.draw.circle(screen, (30, 30, 40), (HOLE_POS[0], HOLE_POS[1] + 2), HOLE_R + 3)
        pygame.draw.circle(screen, (10, 10, 16), (HOLE_POS[0], HOLE_POS[1]), HOLE_R)

        # aim preview
        if aiming:
            mx, my = pygame.mouse.get_pos()
            dx, dy = mx - drag_start[0], my - drag_start[1]
            power = min(MAX_POWER, math.hypot(dx, dy) * POWER_SCALE)
            ang = math.atan2(dy, dx)
            vx, vy = -math.cos(ang) * power, -math.sin(ang) * power
            pts = predict_path(ball, vx, vy)
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
        hud = font.render(f"Strokes: {strokes}  •  R to reset", True, UI)
        screen.blit(hud, (14, 12))
        if sunk:
            msg = big.render(f"🏁 Sunk in {strokes}!", True, UI)
            screen.blit(msg, msg.get_rect(center=(W//2, 60)))

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()