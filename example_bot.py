"""Oval Survivor V2: navigation-aware, threat-avoidant Mech Royale bot.
Python stdlib only; reads the world map if available. Config-driven where possible.
"""
import heapq
import json
import math
import os

import mechfight as mf

PI = math.pi


def norm(x, y):
    d = math.hypot(x, y)
    return (x / d, y / d) if d > 0.00001 else (0.0, 0.0)


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def diff(a, b):
    return (a - b + PI) % (2 * PI) - PI


def toward(a, b):
    return norm(b[0] - a[0], b[1] - a[1])


class Navigator:
    """Coarse ground-level navigation grid for avoiding building footprints."""
    def __init__(self, map_dir):
        self.ok = False
        try:
            with open(os.path.join(map_dir, 'v2', 'world.json')) as f:
                w = json.load(f)
            b = w['bounds']
            self.step = 9.0
            self.xmin, self.ymin = b['minX'], b['minY']
            self.nx = int((b['maxX'] - self.xmin) / self.step) + 1
            self.ny = int((b['maxY'] - self.ymin) / self.step) + 1
            self.solid = bytearray(self.nx * self.ny)
            # Solid structures only; ignore bridges because they may be passable underneath.
            for p in w['prisms']:
                if p['kind'] not in ('building', 'stadium'):
                    continue
                ring = p.get('ring', [])
                if len(ring) < 6:
                    continue
                # Stadium prisms include elevated walkway pieces. Blocking their footprint
                # is conservative (safe) even though some may be passable below.
                xy = [(ring[i], ring[i + 1]) for i in range(0, len(ring), 2)]
                holes = [[(h[k], h[k + 1]) for k in range(0, len(h), 2)] for h in p.get('holes', [])]
                lo_x = max(0, int((min(x for x, y in xy) - self.xmin - 5) / self.step))
                hi_x = min(self.nx - 1, int((max(x for x, y in xy) - self.xmin + 5) / self.step) + 1)
                lo_y = max(0, int((min(y for x, y in xy) - self.ymin - 5) / self.step))
                hi_y = min(self.ny - 1, int((max(y for x, y in xy) - self.ymin + 5) / self.step) + 1)
                for j in range(lo_y, hi_y + 1):
                    cy = self.ymin + j * self.step
                    off = j * self.nx
                    for i in range(lo_x, hi_x + 1):
                        cx = self.xmin + i * self.step
                        if self.in_or_near(cx, cy, xy, 3.7):
                            # An internal courtyard/opening is walkable if the cell
                            # is comfortably clear of its perimeter.
                            if not any(self.inside(cx, cy, h) and not self.near_edge(cx, cy, h, 3.7) for h in holes):
                                self.solid[off + i] = 1
            self.ok = True
        except (OSError, ValueError, TypeError, KeyError):
            self.ok = False

    @staticmethod
    def inside(x, y, ring):
        result = False
        ax, ay = ring[-1]
        for bx, by in ring:
            if (by > y) != (ay > y) and x < (ax - bx) * (y - by) / (ay - by) + bx:
                result = not result
            ax, ay = bx, by
        return result

    @staticmethod
    def near_edge(x, y, ring, pad):
        ax, ay = ring[-1]
        for bx, by in ring:
            dx, dy = bx - ax, by - ay
            dd = dx * dx + dy * dy
            if dd > 0:
                t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / dd))
                if (x - (ax + t * dx)) ** 2 + (y - (ay + t * dy)) ** 2 < pad ** 2:
                    return True
            ax, ay = bx, by
        return False

    @staticmethod
    def in_or_near(x, y, ring, pad):
        inside = False
        prev_x, prev_y = ring[-1]
        rr = pad * pad
        for next_x, next_y in ring:
            ax, ay = prev_x, prev_y
            dx, dy = next_x - ax, next_y - ay
            length_sq = dx * dx + dy * dy
            if length_sq:
                u = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / length_sq))
                px, py = ax + u * dx, ay + u * dy
                if (x - px) ** 2 + (y - py) ** 2 < rr:
                    return True
            if (next_y > y) != (prev_y > y):
                if x < (prev_x - next_x) * (y - next_y) / (prev_y - next_y) + next_x:
                    inside = not inside
            prev_x, prev_y = next_x, next_y
        return inside

    def cell(self, pt):
        i = int(round((pt[0] - self.xmin) / self.step))
        j = int(round((pt[1] - self.ymin) / self.step))
        return (max(1, min(self.nx - 2, i)), max(1, min(self.ny - 2, j)))

    def xy(self, p):
        return (self.xmin + p[0] * self.step, self.ymin + p[1] * self.step)

    def free(self, i, j):
        return 0 < i < self.nx - 1 and 0 < j < self.ny - 1 and not self.solid[j * self.nx + i]

    def reachable_cell(self, pt):
        i, j = self.cell(pt)
        if self.free(i, j):
            return (i, j)
        for r in range(1, 7):
            options = []
            for di in range(-r, r + 1):
                for dj in (-r, r):
                    if self.free(i + di, j + dj):
                        options.append((di * di + dj * dj, i + di, j + dj))
            for dj in range(-r + 1, r):
                for di in (-r, r):
                    if self.free(i + di, j + dj):
                        options.append((di * di + dj * dj, i + di, j + dj))
            if options:
                _, a, b = min(options)
                return (a, b)
        return (i, j)

    def clear(self, a, b):
        if not self.ok:
            return True
        d = dist(a, b)
        n = max(1, int(d / 5))
        for k in range(1, n + 1):
            r = k / n
            i, j = self.cell((a[0] + (b[0] - a[0]) * r, a[1] + (b[1] - a[1]) * r))
            if not self.free(i, j):
                return False
        return True

    def route(self, a, b):
        if not self.ok or self.clear(a, b):
            return [b[:2]]
        start = self.reachable_cell(a)
        goal = self.reachable_cell(b)
        if start == goal:
            return [self.xy(goal)]
        if not self.free(*start) or not self.free(*goal):
            return [b[:2]]
        heap = [(0, 0, start)]
        prev = {start: None}
        costs = {start: 0}
        best = start
        best_h = math.hypot(start[0] - goal[0], start[1] - goal[1])
        steps = ((1,0,1),(-1,0,1),(0,1,1),(0,-1,1),
                 (1,1,1.4142),(1,-1,1.4142),(-1,1,1.4142),(-1,-1,1.4142))
        expanded = 0
        while heap and expanded < 1700:
            _, cost, cur = heapq.heappop(heap)
            if cost > costs.get(cur, 1e20) + 0.0001:
                continue
            expanded += 1
            h = math.hypot(cur[0] - goal[0], cur[1] - goal[1])
            if h < best_h:
                best, best_h = cur, h
            if cur == goal:
                best = cur
                break
            i, j = cur
            for di, dj, step_cost in steps:
                ni, nj = i + di, j + dj
                if not self.free(ni, nj):
                    continue
                if di and dj and (not self.free(i + di, j) or not self.free(i, j + dj)):
                    continue
                node = (ni, nj)
                c = cost + step_cost
                if c < costs.get(node, 1e20):
                    costs[node] = c
                    prev[node] = cur
                    heapq.heappush(heap, (c + math.hypot(ni - goal[0], nj - goal[1]), c, node))
        route = []
        while best is not None and len(route) < 300:
            route.append(self.xy(best))
            best = prev.get(best)
        route.reverse()
        if route:
            route = route[1:]
        if not route:
            return [b[:2]]
        if dist(route[-1], b) < 15 and self.clear(route[-1], b):
            route.append(b[:2])
        return route


class Bot:
    name = 'Oval Survivor V2'

    def __init__(self, hello: mf.Hello):
        c = hello['config']
        self.nav = Navigator(hello['map']['dir'])
        self.pick_range = c['loot']['pickup_radius']
        self.cube_range = c['cubes']['pickup_radius']
        self.side = 1 if hello['slot'] % 2 else -1
        self.last_xy = None
        self.stuck = 0
        self.path = []
        self.path_goal = None
        self.last_plan = -1000
        self.last_goal = None
        self.scan_angle = (hello['slot'] * 2.39996) % (2 * PI)

    @staticmethod
    def upgrade(offer, me):
        hp = me['hp'] / max(1, me['max_hp'])
        ratings = {
            'nanites': 11 if hp < 0.9 else 9, 'armor': 10, 'plating': 9,
            'servos': 9, 'jets': 8, 'reactor': 7, 'capacitor': 6,
            'gun_damage': 6, 'gun_rate': 6, 'gyros': 5,
            'laser_damage': 6, 'laser_charge': 5, 'lightning_range': 5,
            'gun_mag': 3, 'gun_velocity': 3, 'sensors': 2,
        }
        return max(range(len(offer['choices'])), key=lambda i: ratings.get(offer['choices'][i]['id'], 1))

    def act(self, obs: mf.Observation) -> mf.Action:
        me = obs['self']
        x, y, z = me['pos']
        pos = (x, y)
        tick = obs['tick']
        tm = obs['t']
        hp = me['hp'] / max(1, me['max_hp'])
        zone = obs['zone']
        nc = zone['next_center']
        center = zone['center']
        current_r = zone['radius']
        next_r = zone['next_radius']
        enemies = [m for m in obs['mechs'] if m['kind'] == 'mech']
        enemies.sort(key=lambda a: dist(pos, a['pos']))
        near_enemy = dist(pos, enemies[0]['pos']) if enemies else 1e5
        act: mf.Action = {'tick': tick}
        if obs.get('offer'):
            act['pick'] = self.upgrade(obs['offer'], me)

        # Detect prolonged lack of movement while actually commanding motion.
        if self.last_xy is not None and dist(pos, self.last_xy) < 0.22:
            self.stuck += 1
        else:
            self.stuck = max(0, self.stuck - 2)
        self.last_xy = pos
        if self.stuck > 22:
            self.side *= -1
            self.stuck = 8
            self.path = []

        # Avoid waiting until the zone actually starts dealing damage.
        dnext = dist(pos, nc)
        dcurrent = dist(pos, center)
        safety_margin = max(8, min(35, next_r * 0.12))
        inside_next = dnext < max(8, next_r - safety_margin)
        outside = not me.get('in_zone', True) or dcurrent > current_r - 5
        # If the planned next circle is far away, begin moving early.
        time_left = max(0, zone['shrink_end'] - tm)
        travel_time = max(0, dnext - max(3, next_r - safety_margin)) / max(8, me['stats'].get('walk_speed', 11))
        urgent = outside or (not inside_next and (travel_time + 12 > time_left or next_r < 110))

        # Threat avoidance. Its magnitude grows very rapidly inside 70 m.
        repel_x = repel_y = 0.0
        stress = 0.0
        for en in enemies[:8]:
            d = max(1, dist(pos, en['pos']))
            if d >= 180:
                continue
            dx, dy = norm(x - en['pos'][0], y - en['pos'][1])
            v = max(0.0, (165 - d) / 165) ** 2
            if d < 85:
                v *= 2.5
            if d < 40:
                v *= 2.0
            if 'lightning' in en.get('weapons', []) and d < 75:
                v *= 1.3
            repel_x += dx * v
            repel_y += dy * v
            stress += v
            # Move sideways from enemies explicitly aiming at us.
            if d < 125 and en.get('charging'):
                bearing_from_en = math.atan2(y - en['pos'][1], x - en['pos'][0])
                if abs(diff(en['aim'][0], bearing_from_en)) < 0.43:
                    repel_x += -dy * self.side * 0.85
                    repel_y += dx * self.side * 0.85
                    stress += 0.8

        # Choose a safe zone anchor AWAY from enemy concentrations, not just its center.
        target_x, target_y = nc
        if next_r > 55:
            away_x = away_y = 0.0
            for en in enemies[:8]:
                dd = dist(en['pos'], nc)
                if dd < next_r + 135:
                    weight = 1.0 / max(45, dd)
                    away_x += (nc[0] - en['pos'][0]) * weight
                    away_y += (nc[1] - en['pos'][1]) * weight
            ax, ay = norm(away_x, away_y)
            if ax or ay:
                radius = min(next_r * 0.42, 90)
                target_x += ax * radius
                target_y += ay * radius

        # If already comfortably safe, avoid crossing the map to reach an anchor.
        if inside_next and dnext < next_r * 0.78 and not outside and stress < 0.5:
            # Gentle patrol in a circle to avoid being completely stationary.
            phase = tm * 0.10 + self.scan_angle
            target_x = x + 19 * math.cos(phase)
            target_y = y + 19 * math.sin(phase)
            if dist((target_x, target_y), nc) > max(8, next_r - safety_margin):
                target_x, target_y = nc

        goal = (target_x, target_y)
        kind = 'safety'
        obj = None
        can_loot = inside_next and not outside and not urgent and near_enemy > 115 and stress < 0.30
        if can_loot:
            options = []
            if me['weapons'][1] is None:
                for p in obs['pickups']:
                    d = dist(pos, p['pos'])
                    if p['kind'] != 'gun' and d < 95 and abs(p['pos'][2] - z) < 5:
                        if dist(p['pos'], nc) < max(10, next_r - 5):
                            desirability = {'laser': 18, 'mortar': 12, 'lightning': 10}.get(p['kind'], 0)
                            options.append((d - desirability, 'weapon', p))
            for c in obs['cubes']:
                d = dist(pos, c['pos'])
                if d < 55 and abs(c['pos'][2] - z) < 5 and dist(c['pos'], nc) < max(10, next_r - 3):
                    options.append((d - 22, 'cube', c))
            for c in (obs['crates'] if hp > 0.88 else []):
                d = dist(pos, c['pos'])
                if d < 85 and abs(c['pos'][2] - z) < 4 and dist(c['pos'], nc) < max(10, next_r - 3):
                    options.append((d + 12, 'crate', c))
            for n in (obs['mechs'] if hp > 0.88 else []):
                if n['kind'] == 'npc':
                    d = dist(pos, n['pos'])
                    if d < 95 and dist(n['pos'], nc) < max(10, next_r - 3):
                        options.append((d + 25, 'npc', n))
            if options:
                best_score, kind, obj = min(options, key=lambda item: item[0])
                if best_score < 70:
                    goal = obj['pos'][:2]
                else:
                    kind, obj = 'safety', None

        if kind == 'weapon' and obj:
            if dist(pos, obj['pos']) <= self.pick_range - 0.15 and abs(obj['pos'][2] - z) <= 3.8:
                act['take'] = obj['id']
        if kind == 'crate' and obj and dist(pos, obj['pos']) < 50:
            # Hold at gun range; avoid pressing against an unpassable crate.
            if dist(pos, obj['pos']) < 24:
                back = toward(obj['pos'], pos)
                goal = (x + back[0] * 12, y + back[1] * 12)
        if kind == 'npc' and obj and dist(pos, obj['pos']) < 52:
            back = toward(obj['pos'], pos)
            goal = (x + back[0] * 12, y + back[1] * 12)

        # Recover from blocked paths using cached A* route; calculate only periodically.
        desired = goal
        should_route = self.nav.ok and not self.nav.clear(pos, goal)
        if should_route:
            replan = not self.path or self.path_goal is None or dist(goal, self.path_goal) > 20
            replan |= tick - self.last_plan > 30 or self.stuck > 10
            if replan:
                self.path = self.nav.route(pos, goal)
                self.path_goal = goal
                self.last_plan = tick
            while len(self.path) > 1 and dist(pos, self.path[0]) < 8:
                self.path.pop(0)
            if self.path:
                # Skip unnecessary waypoints when line of travel is free.
                for waypoint in self.path[:7][::-1]:
                    if self.nav.clear(pos, waypoint):
                        desired = waypoint
                        break
                else:
                    desired = self.path[0]
        else:
            self.path = []

        mvx, mvy = toward(pos, desired)
        # Opponent squad fights together; prioritize moving away from large clusters.
        if enemies and not outside:
            danger_multiplier = 2.8 if (hp < 0.65 or near_enemy < 50) else 1.8
            if urgent:
                danger_multiplier *= 0.45
            mvx, mvy = norm(mvx + repel_x * danger_multiplier,
                             mvy + repel_y * danger_multiplier)
            # Repulsion must not leave the zone when the circle is small.
            future = (x + mvx * 14, y + mvy * 14)
            if dist(future, nc) > max(6, next_r - 5) and dnext > max(5, next_r - 25):
                ix, iy = toward(pos, nc)
                mvx, mvy = norm(mvx * 0.15 + ix, mvy * 0.15 + iy)

        # Incoming bullets: dodge if their projected path approaches our position.
        danger_shot = False
        dodge_x = dodge_y = 0.0
        for projectile in obs.get('projectiles', [])[:36]:
            p, v = projectile['pos'], projectile['vel']
            vv = v[0] ** 2 + v[1] ** 2
            if vv < 10:
                continue
            horizon = 0.95 if projectile.get('kind') == 'mortar' else 0.42
            dt = max(0, min(horizon, ((x - p[0]) * v[0] + (y - p[1]) * v[1]) / vv))
            px, py = p[0] + v[0] * dt, p[1] + v[1] * dt
            hz = p[2] + v[2] * dt
            if projectile.get('kind') == 'mortar':
                hz -= 11 * dt * dt
            size = 13 if projectile.get('kind') == 'mortar' else 5.8
            if dt > 0.04 and math.hypot(px - x, py - y) < size and abs(hz - (z + 4)) < 12:
                dx, dy = norm(-v[1], v[0])
                # Pick side based on actual miss distance (max separation).
                side = 1 if (x - px) * dx + (y - py) * dy >= 0 else -1
                dodge_x += dx * side
                dodge_y += dy * side
                danger_shot = True
        if danger_shot:
            vx, vy = norm(dodge_x, dodge_y)
            mvx, mvy = norm(mvx * 0.6 + vx * 1.8, mvy * 0.6 + vy * 1.8)

        # Collision recovery: sidestep and jet; do not repeatedly push into a wall.
        if self.stuck > 7:
            mvx, mvy = norm(mvx - mvy * self.side * 1.3,
                             mvy + mvx * self.side * 1.3)
        if dist(pos, goal) < 4 and kind in ('weapon', 'cube'):
            mvx, mvy = (mvx * 0.5, mvy * 0.5)
        act['move'] = [mvx, mvy]
        act['boost'] = bool(me['energy'] > (22 if outside else 46) and
                            (outside or urgent or near_enemy < 85 or (danger_shot and near_enemy < 130)))
        act['jump'] = bool(me['grounded'] and ((self.stuck > 10 and tick % 7 == 0) or
                                              (danger_shot and tick % 9 == 0) or
                                              (near_enemy < 23 and tick % 23 == 0)))

        # Attack ONLY enemies that threaten us, and farm safe crates/NPCs.
        target = None
        healing = hp < 0.83 and near_enemy > 58
        if healing:
            pass  # Refrain from dealing damage so out-of-combat regen can activate.
        elif enemies and near_enemy < (175 if hp > 0.67 else 110):
            target = enemies[0]
        elif not healing and kind in ('crate', 'npc') and obj and dist(pos, obj['pos']) < 165:
            target = obj
        else:
            nearby_npcs = [n for n in obs['mechs'] if n['kind'] == 'npc' and dist(pos, n['pos']) < 65]
            if not healing and near_enemy > 120 and nearby_npcs and hp > 0.88:
                target = min(nearby_npcs, key=lambda p: dist(pos, p['pos']))

        weapons = me['weapons']
        act['fire'] = [False, False]
        gun = weapons[0] if weapons else None
        sec = weapons[1] if len(weapons) > 1 else None
        if target:
            tp = target['pos']
            tv = target.get('vel', [0, 0, 0])
            d = dist(pos, tp)
            is_enemy = target.get('kind') == 'mech'
            is_npc = target.get('kind') == 'npc'
            # Don't keep firing at a remembered mech behind walls.
            unobstructed = self.nav.clear(pos, tp)
            # Stationary crates, moving mechs and drones need different hit heights.
            height = (3.5 if is_npc else (1.6 if 'hp' in target and not target.get('kind') else 4.5))
            if is_enemy:
                height *= 1 + target.get('cubes', 0) * 0.025
            target_height = tp[2] + height
            muzzle = z + me['stats'].get('muzzle_height', 7)
            gun_speed = (gun or {}).get('stats', {}).get('speed', 252)
            rx, ry, rz = tp[0] - x, tp[1] - y, target_height - muzzle
            vv = tv[0] * tv[0] + tv[1] * tv[1] + tv[2] * tv[2]
            a = vv - gun_speed * gun_speed
            b = 2 * (rx * tv[0] + ry * tv[1] + rz * tv[2])
            c = rx * rx + ry * ry + rz * rz
            discriminant = b * b - 4 * a * c
            flight = d / max(10, gun_speed)
            if discriminant >= 0 and abs(a) > 0.01:
                t1 = (-b - math.sqrt(discriminant)) / (2 * a)
                t2 = (-b + math.sqrt(discriminant)) / (2 * a)
                hits = [t for t in (t1, t2) if t > 0]
                if hits:
                    flight = min(hits)
            flight = min(1.4, flight)
            px = tp[0] + tv[0] * flight
            py = tp[1] + tv[1] * flight
            pz = target_height + tv[2] * flight
            gun_yaw = math.atan2(py - y, px - x)
            gun_pitch = math.atan2(pz - muzzle, math.hypot(px - x, py - y))
            yaw, pitch = gun_yaw, gun_pitch
            aim_secondary = False
            if sec and unobstructed:
                if sec['kind'] == 'laser' and d < sec['stats'].get('range', 280) - 10:
                    # Charge even while aiming, then release only when precisely aligned.
                    aim_secondary = True
                    yaw = math.atan2(tp[1] + tv[1] * 0.10 - y, tp[0] + tv[0] * 0.10 - x)
                    pitch = math.atan2(target_height + tv[2] * 0.10 - muzzle, max(1, d))
                elif sec['kind'] == 'mortar' and 32 < d < 175:
                    speed = sec['stats'].get('speed', 72)
                    gravity = 22.0
                    advance = min(2.2, d / max(1, speed))
                    tx, ty = tp[0] + tv[0] * advance, tp[1] + tv[1] * advance
                    rad = math.hypot(tx - x, ty - y)
                    ht = target_height - (z + 9.5)
                    disc = speed ** 4 - gravity * (gravity * rad * rad + 2 * ht * speed * speed)
                    if disc >= 0 and rad > 1:
                        yaw = math.atan2(ty - y, tx - x)
                        pitch = math.atan2(speed * speed - math.sqrt(disc), gravity * rad)
                        aim_secondary = True
                elif sec['kind'] == 'lightning' and d < sec['stats'].get('range', 45) - 3:
                    aim_secondary = True
            pitch = max(-0.69, min(1.28, pitch))
            act['aim'] = [yaw, pitch]
            err = abs(diff(me['aim'][0], yaw))
            pitch_err = abs(diff(me['aim'][1], pitch))
            aligned = err < 0.12 and pitch_err < 0.13
            if aim_secondary and sec:
                kind2 = sec['kind']
                if kind2 == 'laser':
                    charge = sec.get('charge', 0)
                    max_charge = sec['stats'].get('charge', 0.75)
                    # When fully charged, wait for alignment rather than overshooting.
                    act['fire'][1] = charge < max(0.17, max_charge - 0.06) or not aligned
                elif kind2 == 'mortar':
                    act['fire'][1] = aligned and d > 32
                elif kind2 == 'lightning':
                    act['fire'][1] = err < 0.22 and me['energy'] > 18
                # Gun can share fire only if target is inside its firing cone.
                if abs(diff(gun_yaw, yaw)) < 0.11 and abs(gun_pitch - pitch) < 0.13:
                    act['fire'][0] = aligned and d < (gun or {}).get('stats', {}).get('range', 230) and unobstructed
            else:
                act['fire'][0] = aligned and unobstructed and d < (gun or {}).get('stats', {}).get('range', 230)
        else:
            # Scan slowly for visible targets when the area is otherwise safe.
            act['aim'] = [self.scan_angle + tm * 0.48, 0.0]
            # Release a charged laser rather than remaining slowed indefinitely.
            if sec and sec['kind'] == 'laser':
                act['fire'][1] = False

        if gun and gun['kind'] == 'gun':
            act['reload'] = bool(gun.get('reload', 0) == 0 and (gun.get('ammo', 0) == 0 or
                                 (gun.get('ammo', 0) <= 4 and (not target or near_enemy > 80))))
        return act


mf.run(Bot)
