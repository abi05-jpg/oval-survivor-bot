"""Oval Survivor V5: evasive survival, deliberate healing, and safe-zone timing.

Experimental variant based on the best *measured* bot, V3 (1.88). Unlike the
conformance test, only official match scoring can show whether this performs
better. Python standard library only; decision state resets per match.
"""
import math
import mechfight as mf

TAU = 2.0 * math.pi


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def direction(dx, dy):
    r = math.hypot(dx, dy)
    return (dx / r, dy / r) if r > 1e-8 else (0.0, 0.0)


def angle_diff(a, b):
    return (a - b + math.pi) % TAU - math.pi


def upgrade(offer, frac_hp):
    # Survival and mobility are worth more than raw damage against a squad.
    ratings = {
        'nanites': 14 if frac_hp < 0.92 else 10,
        'armor': 13, 'plating': 12, 'servos': 11,
        'reactor': 9, 'jets': 9, 'capacitor': 8,
        'gun_damage': 7, 'gun_rate': 7,
        'gyros': 6, 'laser_damage': 6, 'laser_charge': 5,
        'lightning_range': 5, 'gun_velocity': 4,
        'gun_mag': 4, 'sensors': 4,
    }
    choices = offer['choices']
    return max(range(len(choices)), key=lambda i: ratings.get(choices[i]['id'], 2))


def intercept(origin, target, velocity, speed):
    """First positive 3D constant-speed intercept, capped against stale data."""
    dx = target[0] - origin[0]
    dy = target[1] - origin[1]
    dz = target[2] - origin[2]
    vx, vy, vz = velocity
    aa = vx * vx + vy * vy + vz * vz - speed * speed
    bb = 2.0 * (dx * vx + dy * vy + dz * vz)
    cc = dx * dx + dy * dy + dz * dz
    seconds = math.sqrt(cc) / max(1.0, speed)
    if abs(aa) > 1e-7:
        disc = bb * bb - 4.0 * aa * cc
        if disc >= 0:
            root = math.sqrt(disc)
            ts = [v for v in ((-bb - root) / (2 * aa), (-bb + root) / (2 * aa)) if v > 0]
            if ts:
                seconds = min(ts)
    elif abs(bb) > 1e-7:
        v = -cc / bb
        if v > 0:
            seconds = v
    seconds = min(1.4, max(0.0, seconds))
    return target[0] + vx * seconds, target[1] + vy * seconds, target[2] + vz * seconds


class Bot:
    name = 'Oval Survivor V5'

    def __init__(self, hello: mf.Hello):
        self.side = 1 if hello['slot'] & 1 else -1
        self.last_pos = None
        self.stuck = 0
        self.last_damage = -999.0
        self.last_attack = -999.0
        self.last_shot_pos = None
        self.last_shot_time = -999.0
        self.pick_radius = hello['config']['loot']['pickup_radius']

    def act(self, obs: mf.Observation) -> mf.Action:
        me = obs['self']
        x, y, z = me['pos']
        p = (x, y)
        tick = obs['tick']
        now = obs['t']
        hp = me['hp'] / max(1.0, me['max_hp'])
        energy = me['energy']
        grounded = me['grounded']
        zone = obs['zone']
        center = zone['center']
        next_center = zone['next_center']
        nr = zone['next_radius']
        cr = zone['radius']
        inner_r = max(4.0, nr - max(7.0, min(30.0, nr * 0.13)))
        next_dist = dist(p, next_center)
        cur_dist = dist(p, center)
        outside = not me['in_zone']
        action: mf.Action = {'tick': tick, 'fire': [False, False]}

        if obs.get('offer'):
            action['pick'] = upgrade(obs['offer'], hp)
        if any(ev.get('type') == 'damaged' for ev in obs.get('events', [])):
            self.last_damage = now

        enemies = sorted((m for m in obs['mechs'] if m['kind'] == 'mech'),
                         key=lambda m: dist(p, m['pos']))
        near = enemies[0] if enemies else None
        nearest_d = dist(p, near['pos']) if near else 1e6
        # A weapon firing far away can draw attention and delay HP regeneration.
        # While hurt, only shoot mechs in immediate self-defence.
        escape = nearest_d < (125 if hp < 0.75 else 90)
        heal_mode = hp < 0.81 and (now - self.last_damage > 0.5 or hp < 0.52)
        combat_permitted = not heal_mode or nearest_d < 37

        # Future-zone safety is a deadline, not a command to rush to its centre.
        # Walking early makes the mech visible/noisy for no strategic benefit.
        travel_distance = max(0.0, next_dist - inner_r)
        move_speed = max(7.0, me['stats'].get('walk_speed', 11.7))
        time_left = max(0.0, zone['shrink_end'] - now)
        travel_time = travel_distance / move_speed
        must_move = outside or cur_dist > cr - 13 or (
            travel_distance > 0 and time_left < travel_time + 32)
        # Once radius is tiny, positioning becomes urgent.
        if nr <= 45 and next_dist > inner_r:
            must_move = True

        # If already comfortably inside the coming ring, don't walk to centre.
        # Loot is only worth a detour when we're genuinely unthreatened.
        goal = p
        task = 'hold'
        obj = None
        if must_move:
            goal = next_center
            task = 'zone'

        if not outside and not escape and not must_move and nearest_d > 135:
            opts = []
            for c in obs['cubes']:
                d = dist(p, c['pos'])
                if d < 49 and abs(c['pos'][2] - z) < 3.8 and dist(c['pos'], next_center) < inner_r:
                    opts.append((d - 18, 'cube', c))
            if len(me['weapons']) > 1 and me['weapons'][1] is None:
                for pickup in obs['pickups']:
                    d = dist(p, pickup['pos'])
                    if d < 62 and abs(pickup['pos'][2] - z) < 3.8 and dist(pickup['pos'], next_center) < inner_r:
                        reward = {'laser': 18, 'lightning': 9, 'mortar': 7}.get(pickup['kind'], 0)
                        if reward:
                            opts.append((d - reward, 'weapon', pickup))
            if hp > 0.88:
                for c in obs['crates']:
                    d = dist(p, c['pos'])
                    if d < 38 and abs(c['pos'][2] - z) < 3.8 and dist(c['pos'], next_center) < inner_r:
                        opts.append((d + 8, 'crate', c))
            if opts:
                v, ty, target = min(opts, key=lambda item: item[0])
                if v < 35:
                    goal, task, obj = target['pos'][:2], ty, target

        weapons = me['weapons']
        gun = weapons[0] if len(weapons) > 0 else None
        second = weapons[1] if len(weapons) > 1 else None
        if second is None:
            pickups = [q for q in obs['pickups']
                       if q['kind'] != 'gun' and dist(p, q['pos']) < self.pick_radius - 0.3
                       and abs(q['pos'][2] - z) < 3.9]
            if pickups:
                best = max(pickups, key=lambda q: {'laser': 3, 'lightning': 2, 'mortar': 1}.get(q['kind'], 0))
                action['take'] = best['id']

        # A crate is best destroyed with gunfire, not by walking into it.
        if task == 'crate' and dist(p, goal) <= 27:
            goal = p

        vx, vy = direction(goal[0] - x, goal[1] - y)
        # Candidate steering evaluates the whole group, not only nearest enemy.
        # This prevents backing directly into a second squad member.
        danger = [m for m in enemies if dist(p, m['pos']) < 160]
        if danger:
            best_val = -1e20
            best_vector = (vx, vy)
            # Candidate headings, including staying still when not being chased.
            for i in range(24):
                ang = (i * TAU / 24) + self.side * 0.04
                hx, hy = math.cos(ang), math.sin(ang)
                # Direction over ~1.3 seconds at walk speed.
                fx, fy = x + hx * 16, y + hy * 16
                val = 0.0
                if task != 'hold':
                    val += (dist(p, goal) - dist((fx, fy), goal)) * (7.0 if must_move else 1.25)
                for enemy in danger:
                    ep = enemy['pos']
                    ev = enemy.get('vel', (0.0, 0.0, 0.0))
                    ed = dist(p, ep)
                    future = (ep[0] + ev[0] * 0.55, ep[1] + ev[1] * 0.55)
                    delta_d = dist((fx, fy), future) - dist(p, future)
                    weight = 3.5 if ed < 65 else 2.0 if ed < 105 else 0.9
                    val += weight * delta_d
                    if dist((fx, fy), future) < 30:
                        val -= 50
                # Don't retreat beyond the current safe zone or the next zone
                # when its shrink deadline is approaching.
                cpred = dist((fx, fy), center)
                if cpred > cr - 5:
                    val -= 130 + max(0.0, cpred - cr) * 30
                npred = dist((fx, fy), next_center)
                if time_left < travel_time + 25 or outside:
                    if npred > inner_r:
                        val -= max(0.0, npred - inner_r) * 12
                elif npred > nr + 20:
                    val -= (npred - nr - 20) * 2
                # If visible incoming projectiles will cross our next step,
                # side-step their horizontal trajectory.
                for bullet in obs['projectiles'][:20]:
                    if bullet.get('kind') not in ('gun', 'npc', 'mortar'):
                        continue
                    bp, bv = bullet['pos'], bullet['vel']
                    if abs(bp[2] - (z + 4.5)) > 17:
                        continue
                    vv = bv[0] * bv[0] + bv[1] * bv[1]
                    if vv < 5:
                        continue
                    tt = max(0.0, min(0.65, ((x - bp[0]) * bv[0] + (y - bp[1]) * bv[1]) / vv))
                    if tt < 0.04:
                        continue
                    bx, by = bp[0] + bv[0] * tt, bp[1] + bv[1] * tt
                    sx, sy = x + hx * 11.7 * tt, y + hy * 11.7 * tt
                    miss = math.hypot(bx - sx, by - sy)
                    if miss < 10:
                        val -= 6.0 * (10 - miss)
                if val > best_val:
                    best_val = val
                    best_vector = (hx, hy)
            vx, vy = best_vector
        elif task == 'hold':
            vx, vy = 0.0, 0.0

        # Stuck recovery and light vertical escape, without a heavy A* planner.
        moving = abs(vx) + abs(vy) > 0.6
        if moving and self.last_pos is not None and dist(p, self.last_pos) < 0.23:
            self.stuck += 1
        else:
            self.stuck = max(0, self.stuck - 2)
        self.last_pos = p
        if self.stuck >= 10:
            vx, vy = direction(vx - vy * self.side * 2.0, vy + vx * self.side * 2.0)
            if self.stuck > 27:
                self.side *= -1
                self.stuck = 12
            if grounded:
                action['jump'] = tick % 4 == 0
        else:
            if nearest_d < 25 and grounded:
                action['jump'] = tick % 29 == 0

        action['move'] = [vx, vy]
        threatened = nearest_d < 95 or self.last_damage > now - 0.9
        action['boost'] = bool(energy > (15 if hp < 0.45 else 37) and (
            outside or (must_move and travel_distance > 23 and time_left < travel_time + 10) or
            (threatened and (escape or hp < 0.8)) or
            (self.stuck >= 12 and not grounded)))

        # Defensive combat: don't trade with the squad at 150–200m while
        # injured; shooting also postpones passive regeneration if it hits.
        target = None
        category = None
        if near and nearest_d < (88 if combat_permitted else 37):
            target, category = near, 'mech'
        elif not escape and nearest_d > 150 and not heal_mode:
            # Farm one resource at a time, with a preference for nearby crates.
            if task == 'crate' and obj is not None and dist(p, obj['pos']) < 60:
                target, category = obj, 'crate'
            else:
                crates = [c for c in obs['crates'] if dist(p, c['pos']) < 39 and abs(c['pos'][2] - z) < 4]
                if crates and hp > 0.88:
                    target, category = min(crates, key=lambda c: dist(p, c['pos'])), 'crate'
                else:
                    drones = [m for m in obs['mechs'] if m['kind'] == 'npc'
                              and dist(p, m['pos']) < 65 and hp > 0.87]
                    if drones:
                        target, category = min(drones, key=lambda m: dist(p, m['pos'])), 'npc'

        if gun and gun['kind'] == 'gun':
            ammo = gun.get('ammo', 0)
            action['reload'] = bool(gun.get('reload', 0) == 0 and
                                   (ammo == 0 or (ammo <= 5 and nearest_d > 95)))

        if target is not None:
            tp = target['pos']
            tdist = dist(p, tp)
            muzzle = (x, y, z + me['stats'].get('muzzle_height', 7.0))
            target_h = 4.5 if category == 'mech' else 1.8 if category == 'npc' else 1.5
            future = intercept(muzzle, (tp[0], tp[1], tp[2] + target_h),
                               target.get('vel', [0.0, 0.0, 0.0]),
                               gun['stats'].get('speed', 252) if gun else 252)
            yaw = math.atan2(future[1] - y, future[0] - x)
            pitch = math.atan2(future[2] - muzzle[2], max(0.5, dist(p, future)))
            secondary_fire = False
            sec_mode = second['kind'] if second else None
            # Prefer an instant laser to a gun only if safe enough to charge.
            if second and category == 'mech' and sec_mode == 'laser' and tdist < second['stats'].get('range', 280) - 8:
                charge = second.get('charge', 0.0)
                if (not heal_mode or nearest_d < 40) and nearest_d > 47:
                    future_laser = (tp[0] + target.get('vel', [0, 0, 0])[0] * 0.08,
                                    tp[1] + target.get('vel', [0, 0, 0])[1] * 0.08,
                                    tp[2] + target_h)
                    yaw = math.atan2(future_laser[1] - y, future_laser[0] - x)
                    pitch = math.atan2(future_laser[2] - muzzle[2], max(1, dist(p, future_laser)))
                    secondary_fire = charge < second['stats'].get('charge', 0.75) - 0.04
            elif second and category == 'mech' and sec_mode == 'lightning':
                if tdist < second['stats'].get('range', 45) - 4 and energy > 16:
                    secondary_fire = True
            elif second and category == 'mech' and sec_mode == 'mortar' and 25 < tdist < 155:
                stats = second['stats']
                shell_speed = stats.get('speed', 72.0)
                gravity = stats.get('gravity', 22.0)
                # Lead using a preliminary travel-time estimate, then solve
                # for the lower of two ballistic trajectories.
                motion = target.get('vel', [0, 0, 0])
                flight_time = tdist / max(20.0, shell_speed * 0.8)
                aim_p = (tp[0] + motion[0] * flight_time,
                         tp[1] + motion[1] * flight_time,
                         tp[2] + 4.0 + motion[2] * flight_time)
                horizontal = dist(p, aim_p)
                height = aim_p[2] - (z + me['stats'].get('muzzle_height', 7.0) + 2.5)
                vv = shell_speed ** 2
                disc = vv ** 2 - gravity * (gravity * horizontal ** 2 + 2 * height * vv)
                if horizontal > 6 and disc >= 0:
                    pitch = math.atan2(vv - math.sqrt(disc), gravity * horizontal)
                    yaw = math.atan2(aim_p[1] - y, aim_p[0] - x)
                    secondary_fire = True
            pitch = max(-0.70, min(1.2, pitch))
            action['aim'] = [yaw, pitch]
            aligned = abs(angle_diff(me['aim'][0], yaw)) < 0.13 and abs(me['aim'][1] - pitch) < 0.13
            if gun and gun['kind'] == 'gun' and aligned and tdist < gun['stats'].get('range', 230) - 9:
                # Gun trajectory differs from mortar, or from a stationary
                # charged laser, so avoid firing simultaneously with those.
                action['fire'][0] = sec_mode not in ('mortar', 'laser') or not secondary_fire
            if second and category == 'mech':
                if sec_mode == 'laser':
                    # Laser charges while held, releases when no fire flag.
                    if nearest_d > 47 and (not heal_mode) and tdist < second['stats'].get('range', 280) - 8:
                        action['fire'][1] = bool(secondary_fire or not aligned)
                elif sec_mode in ('mortar', 'lightning'):
                    action['fire'][1] = bool(secondary_fire and aligned)
        else:
            # Turn to scan for approaching threats while waiting silently.
            if near and nearest_d < 190:
                yaw = math.atan2(near['pos'][1] - y, near['pos'][0] - x)
                action['aim'] = [yaw, 0.0]
            else:
                action['aim'] = [(now * 1.5 + self.side * 1.2) % TAU - math.pi, 0.0]

        return action


mf.run(Bot)
