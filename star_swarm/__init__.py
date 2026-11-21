# a shoot-em-up that plays itself. a swarm of aliens flies in and settles into ranks at the
# top, then they peel off one or a few at a time and dive at the ship, shooting as they come.
# the ship is flown by a pilot of the chosen skill, who dodges what they notice in time and
# shoots at what they can line up. each wave dives more often and faster
import math
import random
import time

from plugin_config import plugin_config

cfg = plugin_config("star_swarm", {
    "skill": "average",  # one of SKILLS
    "speed": "normal",  # one of SPEEDS
    "score": "on",  # on or off: the score, the wave and the ships left
})
skill = cfg["skill"]
speed = cfg["speed"]
score_shown = cfg["score"]

# each pilot's
#   px a second the ship moves
#   seconds between looks at what's going on
#   seconds ahead they see a shot or a diving alien coming
#   share of those they notice at all
#   px they misjudge where one will cross the ship's row, either way
#   px off their target they'll still shoot from
#   share of a target's movement they allow for when aiming
#   seconds between shots at the quickest
SKILLS = {
    "beginner": (42, 0.34, 0.45, 0.55, 9, 8, 0.0, 0.55),
    "average": (56, 0.22, 0.75, 0.82, 5, 5, 0.5, 0.42),
    "skilled": (72, 0.12, 1.1, 0.95, 2, 3, 0.9, 0.32),
    "expert": (92, 0.05, 1.7, 1.0, 0, 2, 1.0, 0.26),
}
if skill not in SKILLS:
    skill = "average"
SHIP_SPEED, LOOK, AHEAD, NOTICED, MISJUDGE, LOOSE, LEAD, RELOAD = SKILLS[skill]

# each speed's share of real time
SPEEDS = {
    "slow": 0.7,
    "normal": 1.0,
    "fast": 1.35,
}
if speed not in SPEEDS:
    speed = "normal"
PACE = SPEEDS[speed]

# the ranks: columns and rows of them, px between them, where the middle of the top rank
# is, and how far and how fast they sway from side to side
COLUMNS = 8
ACROSS = 12
DOWN = 10
TOP = 17
SWAY = 9
SWAY_RATE = 0.8
# the row the ship's middle is on, and how near the edges it goes
SHIP_Y = 111
SHIP_MIN = 6
SHIP_MAX = 121
# the ship's shots: px a second, and how many can be in the air
SHOT_SPEED = 175
SHOTS = 2
# ships at the start of a game
SHIPS = 3
# seconds an alien takes to fly in, and between one and the next in its group
ENTER = 2.3
STAGGER = 0.14
# seconds a dive's first turn out of the ranks takes, and how wide it is
TURN = 0.45
TURN_PX = 7
# divers stop steering for the ship below this row, and don't shoot below this one
STEER_ABOVE = 90
FIRE_ABOVE = 84
# px a second a diver can move across to follow the ship
STEER = 34.0
# seconds before a diver reaches the ship's row that the pilot gets out of its way
DODGE = 0.6
# px a second an alien flies back to its place
RETURN_SPEED = 62
# with this few left they dive again without going back to their places
FEW = 4
# seconds: a lost ship's wait for the next, how long that one can't be hurt, a cleared
# wave's pause, and how long the end of a game shows
RESPAWN = 2.0
SAFE = 1.6
CLEARED = 1.8
OVER = 4.0

# what an alien is doing
WAIT, ENTERING, RANKED, DIVING, RETURNING, DEAD = range(6)

BLACK = color.rgb(0, 0, 0)
INK = {
    # the drifter: a jelly with trailing threads
    "a": color.rgb(60, 200, 255), "b": color.rgb(200, 245, 255), "c": color.rgb(230, 90, 220),
    # the shard: a crystal with fins
    "d": color.rgb(255, 190, 40), "e": color.rgb(255, 250, 220), "f": color.rgb(255, 100, 30),
    # the warden: an eye in a shell, and the same once it's been hit
    "g": color.rgb(90, 220, 90), "h": color.rgb(240, 255, 240), "i": color.rgb(255, 40, 60),
    "j": color.rgb(170, 90, 255), "k": color.rgb(225, 205, 255),
    # the ship
    "p": color.rgb(120, 235, 215), "q": color.rgb(255, 225, 70), "r": color.rgb(255, 130, 40),
    "s": color.rgb(40, 130, 150),
}
SHOT_INK = color.rgb(190, 255, 240)
BOLT_INK = color.rgb(255, 90, 90)
BOLT_CORE = color.rgb(255, 230, 200)
TEXT_INK = color.rgb(235, 235, 245)
DIM_INK = color.rgb(120, 130, 170)
BURST_INKS = (color.rgb(255, 255, 255), color.rgb(255, 235, 120), color.rgb(255, 150, 40),
              color.rgb(230, 60, 30), color.rgb(120, 30, 40))


# a picture from rows of letters, each letter one of INK and a dot for nothing
def sprite(rows, swap=None):
    tile = image(len(rows[0]), len(rows))
    memoryview(tile)[:] = bytes(len(rows[0]) * len(rows) * 4)
    for y, line in enumerate(rows):
        for x, mark in enumerate(line):
            if mark != ".":
                tile.pen = INK[swap.get(mark, mark) if swap else mark]
                tile.rectangle(x, y, 1, 1)
    return tile


DRIFTER = (
    ("..aaaaa..",
     ".abbaaaa.",
     "aab.a.aaa",
     "aaaaaaaaa",
     ".aaaaaaa.",
     ".c.c.c.c.",
     "c..c.c..c"),
    ("..aaaaa..",
     ".abbaaaa.",
     "aab.a.aaa",
     "aaaaaaaaa",
     ".aaaaaaa.",
     ".c.c.c.c.",
     ".c.c.c.c."),
)
SHARD = (
    ("....d....",
     "...ded...",
     "f.ddedd.f",
     "ffddeddff",
     "f.ddedd.f",
     "...ded...",
     "....d...."),
    ("....d....",
     "f..ded..f",
     "ffddeddff",
     ".fddeddf.",
     "..ddedd..",
     "...ded...",
     "....d...."),
)
WARDEN = (
    ("...ggggg...",
     "..ggggggg..",
     ".gghhhhhgg.",
     "ggghhihhggg",
     "ggghiiihggg",
     ".gghhihhgg.",
     "g.ggggggg.g",
     "g..g...g..g"),
    ("...ggggg...",
     "..ggggggg..",
     ".gghhhhhgg.",
     "ggghhihhggg",
     "ggghiiihggg",
     ".gghhihhgg.",
     "..ggggggg..",
     ".g.g...g.g."),
)
SHIP = (
    "....p....",
    "....p....",
    "...pqp...",
    "..spqps..",
    ".sppqpps.",
    "spp.p.pps",
    "ps..r..sp",
)
SMALL_SHIP = (
    "..p..",
    ".pqp.",
    "ppspp",
)
HURT = {"g": "j", "h": "k"}

# the kinds of alien: drifter, shard, warden, and a warden that's been hit once. each has
# two pictures it swaps between
KINDS = (
    tuple(sprite(rows) for rows in DRIFTER),
    tuple(sprite(rows) for rows in SHARD),
    tuple(sprite(rows) for rows in WARDEN),
    tuple(sprite(rows, HURT) for rows in WARDEN),
)
# what each is worth in the ranks, and when it's shot down flying
WORTH = ((50, 100), (80, 160), (150, 400), (150, 400))
SHIP_TILE = sprite(SHIP)
SHIP_FLAME = sprite(SHIP[:-1] + ("....q....",))
SMALL_TILE = sprite(SMALL_SHIP)


# an explosion's pictures: dots flying out from the middle, cooling as they go
def burst(size, frames, spokes):
    tiles = []
    middle = size // 2
    for frame in range(frames):
        tile = image(size, size)
        memoryview(tile)[:] = bytes(size * size * 4)
        reach = (frame + 1) / frames * middle
        for ring, share in enumerate((1.0, 0.55)):
            tile.pen = BURST_INKS[min(len(BURST_INKS) - 1, frame * len(BURST_INKS) // frames + ring)]
            for spoke in range(spokes):
                angle = (spoke + ring * 0.5) * 2 * math.pi / spokes
                tile.rectangle(int(middle + math.cos(angle) * reach * share),
                               int(middle + math.sin(angle) * reach * share), 1, 1)
        tiles.append(tile)
    return tiles


POP = burst(11, 5, 8)
BOOM = burst(21, 9, 12)
# seconds each of an explosion's pictures shows
POP_TIME = 0.07

# the stars far off, which don't move, are part of the background. the nearer ones drift down
BACKDROP = image(screen.width, screen.height)
BACKDROP.pen = color.rgb(2, 2, 10)
BACKDROP.clear()
BACKDROP.pen = color.rgb(40, 44, 70)
for _ in range(40):
    BACKDROP.rectangle(random.randrange(128), random.randrange(128), 1, 1)
# each layer's colour, px a second, and where its stars are when it hasn't drifted
STARS = (
    (color.rgb(80, 90, 130), 9, [(random.randrange(128), random.randrange(128)) for _ in range(12)]),
    (color.rgb(170, 180, 220), 22, [(random.randrange(128), random.randrange(128)) for _ in range(8)]),
)

# the paths aliens fly in on, each four points of a curve, which they leave for their own
# place over its last third. every other group flies the same one mirrored
PATHS = (
    ((38, -10), (20, 75), (112, 104), (98, 44)),
    ((-10, 98), (56, 104), (78, 58), (30, 40)),
    ((64, -10), (64, 66), (16, 84), (40, 42)),
)
# the groups a wave flies in as: the path each takes, whether it's mirrored, and the
# (column, row) of each of its aliens in the order they come
GROUPS = (
    (0, False, [(c, r) for c in (3, 4, 2, 5) for r in (3, 4)]),
    (0, True, [(c, r) for c in (3, 4, 2, 5) for r in (0, 1)]),
    (1, False, [(c, r) for c in (1, 6, 0, 7) for r in (1, 2)]),
    (1, True, [(c, r) for c in (3, 4, 2, 5) for r in (2,)] + [(c, 3) for c in (1, 6, 0, 7)]),
    (2, False, [(c, 4) for c in (1, 6, 0, 7)]),
)
# seconds between one group setting off and the next
GROUP_GAP = 1.9


class Alien:
    def __init__(self, kind, column, row, path, mirrored, delay):
        self.kind = kind
        self.column = column
        self.row = row
        self.path = path
        self.mirrored = mirrored
        # seconds until it sets off, then seconds into what it's doing
        self.clock = -delay
        self.state = WAIT
        self.x = -20.0
        self.y = -20.0
        self.vx = 0.0
        self.vy = 0.0
        # where a dive began and which way it turns out, the rows it shoots at, and
        # whether the pilot has noticed it coming
        self.from_x = 0.0
        self.from_y = 0.0
        self.side = 1
        self.fire_at = ()
        self.noticed = True


aliens = []
# the ship's shots as [x, y], the aliens' as [x, y, vx, vy, noticed], and explosions as
# [x, y, seconds old, pictures]
shots = []
bolts = []
bursts = []

# the last game's score and wave, and how many games there have been
last_score = 0
last_wave = 0
games = 0


def new_wave():
    global phase, phase_clock, dive_clock, formed
    del aliens[:]
    del bolts[:]
    for group, (path, mirrored, places) in enumerate(GROUPS):
        for index, (column, row) in enumerate(places):
            kind = 2 if row == 0 else 1 if row < 3 else 0
            aliens.append(Alien(kind, column, row, PATHS[path], mirrored, group * GROUP_GAP + index * STAGGER))
    phase = "play"
    phase_clock = 0.0
    dive_clock = 0.0
    formed = False


def new_game():
    global score, wave, ships, ship_x, goal_x, ship_state, ship_clock, look_clock, reload_clock, aim, sway_clock
    score = 0
    wave = 1
    ships = SHIPS
    ship_x = 64.0
    goal_x = 64.0
    # the ship is "flying", "safe" just after it appears, or "gone"
    ship_state = "safe"
    ship_clock = 0.0
    look_clock = 0.0
    reload_clock = 0.0
    aim = None
    sway_clock = 0.0
    del shots[:]
    del bursts[:]
    new_wave()


# the pilot's look at what's going on: picks the alien to shoot at and where to be, away
# from whatever they've noticed coming
def look():
    global aim, goal_x
    aim = None
    best = 1e9
    for alien in aliens:
        state = alien.state
        if state == DEAD or state == WAIT or alien.y < 2 or alien.y > SHIP_Y - 12:
            continue
        gap = SHIP_Y - alien.y
        at = alien.x + alien.vx * LEAD * gap / (SHOT_SPEED + alien.vy)
        cost = abs(at - ship_x) + gap * 0.3
        if cost < best:
            best = cost
            aim = alien
            want = at
    if aim is None:
        want = 64.0

    # what's coming: the stretch of the ship's row each will pass over, from and to, the
    # seconds until it gets there and until it's gone by, and how wide it is. a diver
    # follows the ship, which a pilot who allows for a target's movement knows, and it's
    # something to shoot at until it's near: running from it sooner only ends in a corner
    threats = []
    for bolt in bolts:
        if bolt[4]:
            due = (SHIP_Y - bolt[1]) / bolt[3]
            if -0.1 < due < AHEAD:
                gone = due + 6 / bolt[3]
                first = bolt[0] + bolt[2] * max(due, 0.0) + random.uniform(-MISJUDGE, MISJUDGE)
                last = first + bolt[2] * (gone - max(due, 0.0))
                threats.append((min(first, last), max(first, last), max(due, 0.0), gone, 6))
    for alien in aliens:
        if alien.state == DIVING and alien.noticed and alien.vy > 0 and alien.y < SHIP_Y + 9:
            due = (SHIP_Y - alien.y) / alien.vy
            if due < AHEAD and due < DODGE:
                gone = due + 9 / alien.vy
                turn = STEER * LEAD * max(0.0, STEER_ABOVE - alien.y) / alien.vy
                first = alien.x + alien.vx * max(due, 0.0) * (0.6 + 0.4 * LEAD) + random.uniform(-MISJUDGE, MISJUDGE)
                last = first + alien.vx * (gone - max(due, 0.0))
                threats.append((min(first, last) - turn, max(first, last) + turn, max(due, 0.0), gone, 10))
    want = min(SHIP_MAX, max(SHIP_MIN, want))
    if not threats:
        goal_x = want
        return
    best = 1e9
    for spot in range(SHIP_MIN, SHIP_MAX + 1, 5):
        # the edges are where the ship gets trapped
        cost = abs(spot - want) * 0.15 + abs(spot - ship_x) * 0.05 + max(0, abs(spot - 64) - 42) * 0.8
        for first, last, due, gone, wide in threats:
            # a spot the ship can't get to in time is no safer than where it'll be by then
            reach = SHIP_SPEED * gone
            there = spot if abs(spot - ship_x) <= reach else ship_x + (reach if spot > ship_x else -reach)
            clear = (first - there if there < first else there - last if there > last else 0.0) - wide
            # and nor is one on the other side of it, once there's no time to cross
            middle = (first + last) / 2
            if due < 0.3 and (ship_x < middle) != (there < middle):
                clear = -wide
            if clear < 5:
                cost += (6 - clear) * 40 / (due + 0.12)
        if cost < best:
            best = cost
            goal_x = spot


def lose_ship():
    global ship_state, ship_clock, ships
    bursts.append([ship_x, SHIP_Y, 0.0, BOOM])
    ship_state = "gone"
    ship_clock = 0.0
    ships -= 1


def shoot_down(alien, flying):
    global score
    if alien.kind == 2:
        # a warden takes two
        alien.kind = 3
        return
    score += WORTH[alien.kind][1 if flying else 0]
    alien.state = DEAD
    bursts.append([alien.x, alien.y, 0.0, POP])


def dive(alien):
    alien.state = DIVING
    alien.clock = 0.0
    alien.from_x = alien.x
    alien.from_y = alien.y
    alien.side = 1 if ship_x > alien.x else -1
    alien.noticed = random.random() < NOTICED
    rows = [random.uniform(alien.y + 14, 58)]
    if wave >= 3:
        rows.append(random.uniform(62, FIRE_ABOVE))
    if wave >= 6:
        rows.append(random.uniform(40, FIRE_ABOVE))
    alien.fire_at = sorted(rows)


def step(dt):
    global phase, phase_clock, dive_clock, formed, sway_clock, wave, score
    global ship_x, ship_state, ship_clock, look_clock, reload_clock, aim
    global last_score, last_wave, games
    phase_clock += dt
    sway_clock += dt
    sway = SWAY * math.sin(sway_clock * SWAY_RATE)
    sway_speed = SWAY * SWAY_RATE * math.cos(sway_clock * SWAY_RATE)
    dive_speed = min(96, 48 + 5 * wave)
    bolt_speed = min(118, 58 + 6 * wave)
    here = ship_state != "gone"

    left = 0
    ranked = 0
    diving = 0
    for alien in aliens:
        state = alien.state
        if state == DEAD:
            continue
        left += 1
        home_x = 64 + (alien.column - 3.5) * ACROSS + sway
        home_y = TOP + alien.row * DOWN
        was_x = alien.x
        was_y = alien.y
        alien.clock += dt
        if state == RANKED:
            ranked += 1
            alien.x = home_x
            alien.y = home_y
            alien.vx = sway_speed
            alien.vy = 0.0
            continue
        if state == WAIT:
            if alien.clock < 0:
                continue
            alien.state = state = ENTERING
        if state == ENTERING:
            along = alien.clock / ENTER
            if along >= 1:
                alien.state = RANKED
                alien.x = home_x
                alien.y = home_y
                continue
            (ax, ay), (bx, by), (cx, cy), (dx, dy) = alien.path
            back = 1 - along
            a = back * back * back
            b = 3 * back * back * along
            c = 3 * back * along * along
            d = along * along * along
            x = a * ax + b * bx + c * cx + d * dx
            y = a * ay + b * by + c * cy + d * dy
            if alien.mirrored:
                x = 128 - x
            if along > 0.66:
                share = (along - 0.66) / 0.34
                share = share * share * (3 - 2 * share)
                x += (home_x - x) * share
                y += (home_y - y) * share
            alien.x = x
            alien.y = y
        elif state == DIVING:
            diving += 1
            if alien.clock < TURN:
                angle = math.pi * alien.clock / TURN
                alien.x = alien.from_x + alien.side * TURN_PX * (1 - math.cos(angle))
                alien.y = alien.from_y - TURN_PX * math.sin(angle)
            else:
                y = alien.y + dive_speed * dt
                if y < STEER_ABOVE and here:
                    want = ship_x + 16 * math.sin(alien.clock * 4 + alien.column)
                    alien.x += max(-STEER, min(STEER, (want - alien.x) * 2.5)) * dt
                else:
                    alien.x += alien.vx * dt
                for row in alien.fire_at:
                    if alien.y < row <= y and here and row < FIRE_ABOVE:
                        fall = (SHIP_Y - y) / bolt_speed
                        bolts.append([alien.x, y + 4, max(-26.0, min(26.0, (ship_x - alien.x) / fall)),
                                      bolt_speed, random.random() < NOTICED])
                alien.y = y
                if y > 136:
                    if left <= FEW:
                        # round again from the top
                        alien.y = -8.0
                        alien.x = min(118.0, max(10.0, home_x + random.uniform(-30, 30)))
                        alien.clock = TURN
                        alien.noticed = random.random() < NOTICED
                        alien.fire_at = (random.uniform(20, 50), random.uniform(55, FIRE_ABOVE))
                    else:
                        alien.state = RETURNING
                        alien.x = home_x
                        alien.y = -8.0
                    alien.vx = alien.vy = 0.0
                    continue
        else:
            # flying back to its place
            dx = home_x - alien.x
            dy = home_y - alien.y
            far = math.sqrt(dx * dx + dy * dy)
            move = RETURN_SPEED * dt
            if far <= move:
                alien.state = RANKED
                alien.x = home_x
                alien.y = home_y
                continue
            alien.x += dx / far * move
            alien.y += dy / far * move
        if dt > 0:
            alien.vx = (alien.x - was_x) / dt
            alien.vy = (alien.y - was_y) / dt

    # the ranks send one diving every so often once they've all arrived, more of them at
    # a time and more often each wave
    if ranked == left:
        formed = True
    if phase == "play" and formed and here and ranked:
        dive_clock += dt
        gap = max(0.5, 2.1 - 0.17 * wave) if left > FEW else 0.5
        if dive_clock >= gap and diving < min(6, 1 + (wave + 1) // 2):
            dive_clock = 0.0
            pick = random.randrange(ranked)
            for alien in aliens:
                if alien.state == RANKED:
                    if pick == 0:
                        dive(alien)
                        break
                    pick -= 1

    # the ship's shots
    for shot in shots:
        shot[1] -= SHOT_SPEED * dt
        if shot[1] < -4:
            shot[1] = -100.0
            continue
        x = shot[0]
        y = shot[1]
        for alien in aliens:
            state = alien.state
            if state != DEAD and state != WAIT and abs(alien.x - x) < 5.5 and abs(alien.y - y) < 5.5:
                shoot_down(alien, state != RANKED)
                shot[1] = -100.0
                break
    for index in range(len(shots) - 1, -1, -1):
        if shots[index][1] < -50:
            del shots[index]

    # the aliens' shots, and the aliens themselves, against the ship
    for bolt in bolts:
        bolt[0] += bolt[2] * dt
        bolt[1] += bolt[3] * dt
        if ship_state == "flying" and abs(bolt[0] - ship_x) < 4 and abs(bolt[1] - SHIP_Y) < 5:
            bolt[1] = 200.0
            lose_ship()
    for index in range(len(bolts) - 1, -1, -1):
        if bolts[index][1] > 130:
            del bolts[index]
    if ship_state == "flying":
        for alien in aliens:
            if alien.state == DIVING and abs(alien.x - ship_x) < 7.5 and abs(alien.y - SHIP_Y) < 6.5:
                alien.kind = 0 if alien.kind == 0 else 1 if alien.kind == 1 else 3
                shoot_down(alien, True)
                lose_ship()
                break

    for index in range(len(bursts) - 1, -1, -1):
        bursts[index][2] += dt
        if bursts[index][2] >= POP_TIME * len(bursts[index][3]):
            del bursts[index]

    # the pilot
    ship_clock += dt
    if ship_state == "gone":
        if phase == "play" and ship_clock >= RESPAWN:
            if ships > 0:
                ship_state = "safe"
                ship_clock = 0.0
                ship_x = 64.0
                look_clock = LOOK
            else:
                phase = "over"
                phase_clock = 0.0
                last_score = score
                last_wave = wave
                games += 1
    else:
        if ship_state == "safe" and ship_clock >= SAFE:
            ship_state = "flying"
        look_clock += dt
        if look_clock >= LOOK:
            look_clock = 0.0
            look()
        move = SHIP_SPEED * dt
        if abs(goal_x - ship_x) <= move:
            ship_x = goal_x
        else:
            ship_x += move if goal_x > ship_x else -move
        reload_clock += dt
        if aim is not None and reload_clock >= RELOAD and len(shots) < SHOTS:
            if aim.state == DEAD:
                aim = None
            else:
                gap = SHIP_Y - aim.y
                at = aim.x + aim.vx * LEAD * gap / (SHOT_SPEED + aim.vy)
                if abs(at - ship_x) <= LOOSE and gap > 8:
                    shots.append([ship_x, SHIP_Y - 6])
                    reload_clock = 0.0

    if phase == "play" and left == 0 and here:
        phase = "cleared"
        phase_clock = 0.0
    elif phase == "cleared" and phase_clock >= CLEARED:
        wave += 1
        new_wave()
    elif phase == "over" and phase_clock >= OVER:
        new_game()


def words(text, y, ink):
    screen.pen = ink
    screen.text(text, (128 - screen.measure_text(text)[0]) // 2, y)


def draw(now):
    screen.blit(BACKDROP, 0, 0)
    for ink, drift, stars in STARS:
        screen.pen = ink
        fallen = now * drift // 1000
        for x, y in stars:
            screen.rectangle(x, (y + fallen) % 128, 1, 1)

    flap = (now // 380) & 1
    for alien in aliens:
        state = alien.state
        if state != DEAD and state != WAIT:
            tile = KINDS[alien.kind][flap if state == RANKED else (now // 120) & 1]
            screen.blit(tile, int(alien.x) - tile.width // 2, int(alien.y) - tile.height // 2)

    screen.pen = SHOT_INK
    for shot in shots:
        screen.rectangle(int(shot[0]), int(shot[1]) - 2, 1, 4)
    for bolt in bolts:
        x = int(bolt[0])
        y = int(bolt[1])
        screen.pen = BOLT_INK
        screen.rectangle(x - 1, y - 1, 3, 3)
        screen.pen = BOLT_CORE
        screen.rectangle(x, y - 1, 1, 3)

    # a ship that's just appeared blinks until it can be hurt
    if ship_state == "flying" or (ship_state == "safe" and (now // 110) & 1):
        screen.blit(SHIP_FLAME if (now // 90) & 1 else SHIP_TILE, int(ship_x) - 4, SHIP_Y - 3)

    for x, y, age, tiles in bursts:
        tile = tiles[min(len(tiles) - 1, int(age / POP_TIME))]
        screen.blit(tile, int(x) - tile.width // 2, int(y) - tile.height // 2)

    screen.font = rom_font.sins
    if score_shown == "on":
        screen.pen = TEXT_INK
        screen.text(str(score), 1, 0)
        label = "W" + str(wave)
        screen.pen = DIM_INK
        screen.text(label, 127 - screen.measure_text(label)[0], 0)
        for spare in range(ships - (0 if ship_state == "gone" else 1)):
            screen.blit(SMALL_TILE, 1 + spare * 7, 124)
    if phase == "over":
        words("GAME OVER", 52, TEXT_INK)
        words(str(score), 64, DIM_INK)
    elif phase == "cleared" or (phase == "play" and phase_clock < 1.6 and not formed):
        words("WAVE " + str(wave + (1 if phase == "cleared" else 0)), 58, TEXT_INK)


new_game()
last_ticks = time.ticks_ms()


def update():
    global last_ticks
    now = time.ticks_ms()
    # the time since the last frame, less if it was a long one, as it is when another
    # plugin has had the screen
    passed = min(50, time.ticks_diff(now, last_ticks))
    last_ticks = now
    step(passed * PACE / 1000)
    draw(now)
