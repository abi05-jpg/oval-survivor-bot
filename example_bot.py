"""Survival-first Mech Royale bot. Python standard library only."""
import math
import mechfight as mf


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def unit(dx, dy):
    d = math.hypot(dx, dy)
    return (dx / d, dy / d) if d > 1e-6 else (0.0, 0.0)


def angle_diff(a, b):
    return (a - b + math.pi) % (2 * math.pi) - math.pi


class Bot:
    name = 'Oval Survivor'

    def __init__(self, hello: mf.Hello):
        self.reach = hello['config']['loot']['pickup_radius']
        self.cube_reach = hello['config']['cubes']['pickup_radius']
        self.last_pos = None
        self.stuck_steps = 0
        self.side = 1 if hello['slot'] % 2 else -1

    def act(self, obs: mf.Observation) -> mf.Action:
        me = obs['self']
        pos = me['pos']
        x, y, z = pos
        hp_fraction = me['hp'] / max(1, me['max_hp'])
        zone = obs['zone']
        center, next_center = zone['center'], zone['next_center']
        t = obs['t']
        enemy_mechs = [m for m in obs['mechs'] if m['kind'] == 'mech']
        enemy_mechs.sort(key=lambda m: distance(pos, m['pos']))
        closest = enemy_mechs[0] if enemy_mechs else None
        enemy_dist = distance(pos, closest['pos']) if closest else 9999

        action: mf.Action = {'tick': obs['tick']}

        # Prefer defensive upgrades, and fast movement/energy where offered.
        offer = obs.get('offer')
        if offer:
            ranking = ('armor', 'regen', 'speed', 'energy', 'hp', 'gun_rate', 'gun_damage', 'sensors')
            def score(c):
                ident = c['id'].lower()
                for rank, keyword in enumerate(ranking):
                    if keyword in ident:
                        return len(ranking) - rank
                return 0
            action['pick'] = max(range(len(offer['choices'])), key=lambda i: score(offer['choices'][i]))

        # Detect collisions/being blocked; change path periodically.
        if self.last_pos is not None and distance(pos, self.last_pos) < 0.35:
            self.stuck_steps += 1
        else:
            self.stuck_steps = 0
        self.last_pos = pos[:]
        if self.stuck_steps > 16:
            self.side *= -1
            self.stuck_steps = 0

        # Aim at a moving target's predicted position (gun projectile travel time).
        target = closest
        aim_yaw = me['aim'][0]
        aim_pitch = me['aim'][1]
        if target and enemy_dist < 210:
            gun = me['weapons'][0]
            gun_speed = 252.0
            if gun and gun['kind'] == 'gun':
                gun_speed = gun['stats'].get('speed', gun_speed)
            travel = min(0.9, enemy_dist / max(1, gun_speed))
            p = target['pos']
            v = target['vel']
            tx, ty = p[0] + v[0] * travel, p[1] + v[1] * travel
            tz = p[2] + 4.5 + v[2] * travel
            aim_yaw = math.atan2(ty - y, tx - x)
            aim_pitch = math.atan2(tz - (z + me['stats'].get('muzzle_height', 7)), math.hypot(tx-x, ty-y))
        else:
            # Look where travelling so we can discover pickups.
            aim_yaw = math.atan2(next_center[1] - y, next_center[0] - x)
            aim_pitch = 0.0
        action['aim'] = [aim_yaw, aim_pitch]

        # Prioritise staying in the NEXT safe zone; don't hug its dangerous edge.
        dist_next = distance(pos, next_center)
        next_radius = zone['next_radius']
        safe_margin = min(45.0, next_radius * 0.25)
        unsafe = dist_next > max(8, next_radius - safe_margin)
        outside = not me['in_zone']
        goal = next_center
        goal_kind = 'zone'

        # Grab nearby cubes and weapons when safe, without detouring too far.
        if not unsafe and not outside and (not closest or enemy_dist > 75):
            loot = []
            for cube in obs['cubes']:
                d = distance(pos, cube['pos'])
                if d < 65 and abs(cube['pos'][2] - z) < 8:
                    loot.append((d - 18, 'cube', cube))
            if me['weapons'][1] is None:
                for pickup in obs['pickups']:
                    d = distance(pos, pickup['pos'])
                    if d < 90 and abs(pickup['pos'][2] - z) < 8 and pickup['kind'] != 'gun':
                        loot.append((d - 12, 'weapon', pickup))
            for crate in obs['crates']:
                d = distance(pos, crate['pos'])
                if d < 38 and abs(crate['pos'][2] - z) < 8:
                    loot.append((d + 12, 'crate', crate))
            if loot:
                _, goal_kind, obj = min(loot, key=lambda item: item[0])
                goal = obj['pos']
                if goal_kind == 'weapon' and distance(pos, goal) <= self.reach and abs(goal[2] - z) < 4:
                    action['take'] = obj['id']
                if goal_kind == 'crate' and not target:
                    # Shoot crate if no other target, but don't chase it forever.
                    aim_yaw = math.atan2(goal[1] - y, goal[0] - x)
                    aim_pitch = math.atan2(goal[2] + 1.5 - z - 7, max(1, distance(pos, goal)))
                    action['aim'] = [aim_yaw, aim_pitch]
                    action['fire'] = [True, False]

        # Defensive strafe/retreat rather than charging a visible enemy.
        dx, dy = goal[0] - x, goal[1] - y
        mx, my = unit(dx, dy)
        if closest and enemy_dist < 110 and not outside:
            ex, ey = unit(x - closest['pos'][0], y - closest['pos'][1])
            if hp_fraction < 0.65 or enemy_dist < 37:
                mx, my = unit(mx * 0.3 + ex * 0.95, my * 0.3 + ey * 0.95)
            else:
                mx, my = unit(mx * 0.7 - ey * self.side * 0.7,
                              my * 0.7 + ex * self.side * 0.7)
        if self.stuck_steps > 8:
            mx, my = -my * self.side, mx * self.side
            action['jump'] = bool(me['grounded'])
        action['move'] = [mx, my]
        action['boost'] = bool(me['energy'] > 40 and (outside or (unsafe and dist_next > next_radius + 15)))
        action.setdefault('jump', bool(me['grounded'] and closest and enemy_dist < 40 and obs['tick'] % 35 == 0))

        # Avoid firing while actual turret is rotating away from the target.
        if target and enemy_dist < 200:
            turn_error = abs(angle_diff(aim_yaw, me['aim'][0]))
            gun_ok = turn_error < 0.16 and abs(aim_pitch - me['aim'][1]) < 0.15
            action['fire'] = [gun_ok, False]
            if me['weapons'][0] and me['weapons'][0]['kind'] == 'gun':
                action['reload'] = me['weapons'][0]['ammo'] == 0
            secondary = me['weapons'][1]
            if secondary and gun_ok:
                kind = secondary['kind']
                if kind == 'lightning':
                    action['fire'][1] = enemy_dist < secondary['stats'].get('range', 45) - 3 and me['energy'] > 15
                elif kind == 'laser':
                    # Charge for ~0.75 seconds then release.
                    action['fire'][1] = secondary.get('charge', 0) < secondary['stats'].get('charge', 0.75) - 0.05
                # Mortar intentionally omitted until ballistic aiming is implemented.
        elif me['weapons'][0] and me['weapons'][0]['kind'] == 'gun':
            action['reload'] = me['weapons'][0]['ammo'] < 4

        return action


mf.run(Bot)
