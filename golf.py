import math
import random
from dataclasses import dataclass
import pygame

# --- Config ---
W, H = 900, 600
FPS = 60

GRASS = (34, 139, 34)
GRASS_LIGHT = (44, 164, 44)
WHITE = (245, 245, 245)
UI = (230, 230, 230)
DARK = (18, 20, 22)
SHADOW = (0, 0, 0)

HOLE_R = 16           # visual hole radius
CUP_R = 16            # sink detection radius (cup)
INNER_R = 12          # inner rim to snap quickly when very close
BALL_R = 10

FRICTION = 0.985      # per-frame damping
STOP_SPEED = 8.0      # px/s considered "stopped"
WALL_BOUNCE = 0.65
MAX_POWER = 900.0
AIM_MIN_DRAG = 6

# New: allow sinking when crossing the cup if not crazy fast
MAX_SINK_SPEED = 600.0     # px/s
# New: a soft “suction” toward the hole when nearby
CUP_ATTRACT_RADIUS = 64.0  # start attracting when within this range
CUP_ATTRACT = 240.0        # acceleration strength (px/s^2)

random.seed(1)


@dataclass
class Ball:
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0

    def speed(self) -> float:
        return math.hypot(self.vx, self.vy)

    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x - BALL_R), int(self.y - BALL_R), BALL_R * 2, BALL_R * 2)


def draw_grass(surface: pygame.Surface):
    surface.fill(GRASS)
    stripe_h = 36
    for i in range(0, H, stripe_h):
        s = pygame.Surface((W, stripe_h))
        s.set_alpha(36)
        s.fill(GRASS_LIGHT)
        surface.blit(s, (0, i))
    rng = random.Random(2)
    for _ in range(450):
        x = rng.randrange(W)
        y = rng.randrange(H)
        r = rng.randrange(1, 3)
        pygame.draw.circle(surface, GRASS_LIGHT, (x, y), r)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def seg_hits_circle(p0, p1, c, r) -> bool:
    """
    Return True if the segment p0->p1 intersects circle center c, radius r.
    p0, p1, c are (x, y) tuples.
    """
    (x1, y1), (x2, y2) = p0, p1
    cx, cy = c
    dx, dy = x2 - x1, y2 - y1
    if dx == dy == 0:
        # segment is a point
        return (x1 - cx) ** 2 + (y1 - cy) ** 2 <= r * r
    # project center onto segment
    t = ((cx - x1) * dx + (cy - y1) * dy) / (dx * dx + dy * dy)
    t = clamp(t, 0.0, 1.0)
    qx, qy = x1 + t * dx, y1 + t * dy
    return (qx - cx) ** 2 + (qy - cy) ** 2 <= r * r


def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Mini Golf")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 28)
    font_big = pygame.font.SysFont(None, 64)

    grass = pygame.Surface((W, H))
    draw_grass(grass)

    hole = (int(W * 0.78), int(H * 0.28))
    start = (int(W * 0.18), int(H * 0.72))

    ball = Ball(*start)
    strokes = 0
    sunk = False
    aiming = False
    drag_start = (0, 0)

    def reset():
        nonlocal ball, strokes, sunk, aiming
        ball = Ball(*start)
        strokes = 0
        sunk = False
        aiming = False

    running = True
    while running:
        dt = clock.tick(FPS) / 1_000.0

        # --- Input ---
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
                elif ev.key == pygame.K_r:
                    reset()
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and not sunk:
                mx, my = ev.pos
                if ball.speed() < STOP_SPEED and ball.rect().collidepoint(mx, my):
                    aiming = True
                    drag_start = (mx, my)
            elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1 and aiming and not sunk:
                mx, my = ev.pos
                dx = mx - drag_start[0]
                dy = my - drag_start[1]
                power = math.hypot(dx, dy)
                if power > AIM_MIN_DRAG:
                    angle = math.atan2(dy, dx)
                    speed = clamp(power * 10.0, 0, MAX_POWER)
                    ball.vx = -math.cos(angle) * speed
                    ball.vy = -math.sin(angle) * speed
                    strokes += 1
                aiming = False

        # --- Update physics ---
        if not sunk:
            # remember previous position for continuous checks
            prev = (ball.x, ball.y)

            # gentle attraction when near the cup
            dx = hole[0] - ball.x
            dy = hole[1] - ball.y
            dist = math.hypot(dx, dy)
            if dist < CUP_ATTRACT_RADIUS and dist > 1e-6:
                ax = (dx / dist) * CUP_ATTRACT
                ay = (dy / dist) * CUP_ATTRACT
                ball.vx += ax * dt
                ball.vy += ay * dt

            # integrate
            ball.x += ball.vx * dt
            ball.y += ball.vy * dt

            # walls
            if ball.x - BALL_R <= 0:
                ball.x = BALL_R
                ball.vx = -ball.vx * WALL_BOUNCE
            elif ball.x + BALL_R >= W:
                ball.x = W - BALL_R
                ball.vx = -ball.vx * WALL_BOUNCE
            if ball.y - BALL_R <= 0:
                ball.y = BALL_R
                ball.vy = -ball.vy * WALL_BOUNCE
            elif ball.y + BALL_R >= H:
                ball.y = H - BALL_R
                ball.vy = -ball.vy * WALL_BOUNCE

            # friction
            ball.vx *= FRICTION
            ball.vy *= FRICTION

            # snap to stop
            if ball.speed() < STOP_SPEED:
                ball.vx = ball.vy = 0.0

            # --- Sink detection ---
            # A) segment-circle hit during this frame (prevents tunneling)
            crossed = seg_hits_circle(prev, (ball.x, ball.y), hole, CUP_R)
            if crossed and ball.speed() <= MAX_SINK_SPEED:
                ball.x, ball.y = hole
                ball.vx = ball.vy = 0.0
                sunk = True
            else:
                # B) current position very close AND slow: snap in
                if dist < INNER_R and ball.speed() < STOP_SPEED * 1.2:
                    ball.x, ball.y = hole
                    ball.vx = ball.vy = 0.0
                    sunk = True

        # --- Draw ---
        screen.blit(grass, (0, 0))

        # hole
        pygame.draw.circle(screen, SHADOW, hole, HOLE_R + 3)
        pygame.draw.circle(screen, DARK, hole, HOLE_R)
        pygame.draw.circle(screen, (70, 70, 70), hole, HOLE_R, 2)

        # aim guide
        if aiming:
            mx, my = pygame.mouse.get_pos()
            dx = mx - drag_start[0]
            dy = my - drag_start[1]
            power = clamp(math.hypot(dx, dy), 0, MAX_POWER / 10.0)
            if power > AIM_MIN_DRAG:
                ang = math.atan2(dy, dx)
                ex = ball.x - math.cos(ang) * (power * 1.2)
                ey = ball.y - math.sin(ang) * (power * 1.2)
                pygame.draw.line(screen, UI, (ball.x, ball.y), (ex, ey), 3)
                bar_w, bar_h = 180, 10
                bx, by = 20, 20
                pygame.draw.rect(screen, (0, 0, 0), (bx - 2, by - 2, bar_w + 4, bar_h + 4), border_radius=6)
                pygame.draw.rect(screen, (70, 70, 70), (bx, by, bar_w, bar_h), border_radius=6)
                fill = int((power / (MAX_POWER / 10.0)) * bar_w)
                pygame.draw.rect(screen, (220, 220, 220), (bx, by, fill, bar_h), border_radius=6)

        # ball + tiny shadow
        pygame.draw.circle(screen, (0, 0, 0), (int(ball.x + 2), int(ball.y + 2)), BALL_R, 0)
        pygame.draw.circle(screen, WHITE, (int(ball.x), int(ball.y)), BALL_R, 0)

        # UI
        txt = font.render(f"Strokes: {strokes}   (R to reset)", True, UI)
        screen.blit(txt, (20, H - 36))

        if sunk:
            msg = f"🏁 Sunk in {strokes} stroke{'s' if strokes != 1 else ''}!"
            banner = font_big.render(msg, True, UI)
            screen.blit(banner, banner.get_rect(center=(W // 2, 60)))
            tip = font.render("Press R to play again", True, UI)
            screen.blit(tip, tip.get_rect(center=(W // 2, 100)))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()