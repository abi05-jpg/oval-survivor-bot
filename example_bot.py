"""Oval Survivor V3 — conservative evolution of the higher-scoring V1.

No map loading or expensive search: the 50ms decision budget is precious.
The goal is survival with opportunistic loot and more reliable combat.
"""
import math
import mechfight as mf


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def unit(dx, dy):
    d = math.hypot(dx, dy)
    return (dx / d, dy / d) if d > 1e-8 else (0.0, 0.0)


def delta(a, b):
    return (a - b + math.pi) % (2.0 * math.pi) - math.pi


def choice(offer):
    # Exact IDs from the game are better than guessing substrings.
    scores = {
        'armor': 12, 'nanites': 11, 'plating': 10, 'servos': 9,
        'reactor': 7, 'jets': 7, 'gun_damage': 7, 'gun_rate': 7,
        'capacitor': 6, 'gyros': 5, 'laser_damage': 6,
        'laser_charge': 5, 'lightning_range': 5, 'gun_velocity': 4,
        'gun_mag': 3, 'sensors': 3,
    }
    return max(range(len(offer['choices'])),
               key=lambda i: scores.get(offer['choices'][i]['id'], 1))


class Bot:
    name = 'Oval Survivor V3'

    def __init__(self, hello: mf.Hello):
        self.reach = hello['config']['loot']['pickup_radius']
        self.side = -1 if hello['slot'] % 2 == 0 else 1
        self.last_pos = None
        self.stuck = 0
        self.last_goal = None
        self.last_damage_time = -999

    def act(self, obs: mf.Observation) -> mf.Action:
        me = obs['self']
        x, y, z = me['pos']
        pos = (x, y)
        t = obs['t']
        tick = obs['tick']
        hp = me['hp'] / max(1, me['max_hp'])
        energy = me['energy']
        zone = obs['zone']
        center = zone['center']
        next_center = zone['next_center']
        radius = zone['next_radius']
        dist_next = distance(pos, next_center)
        outside = not me['in_zone']
        opponents = sorted((m for m in obs['mechs'] if m['kind'] == 'mech'),
                           key=lambda m: distance(pos, m['pos']))
        nearest = opponents[0] if opponents else None
        enemy_dist = distance(pos, nearest['pos']) if nearest else 1e5
        action: mf.Action = {'tick': tick, 'fire': [False, False]}

        if obs.get('offer'):
            action['pick'] = choice(obs['offer'])
        if any(e['type'] == 'damaged' for e in obs.get('events', [])):
            self.last_damage_time = t

        # Respect the moving zone, but don't rush to the exact middle if safe.
        margin = min(35.0, max(7.0, radius * 0.20))
        inner_radius = max(3.0, radius - margin)
        dist_to_safety = max(0.0, dist_next - inner_radius)
        time_to_end = max(0.0, zone['shrink_end'] - t)
        travel_s = dist_to_safety / max(7.0, me['stats'].get('walk_speed', 11.7))
        urgent = (outside or (dist_to_safety > 0 and
                  (time_to_end < travel_s + 13 or radius < 80)))
        unsafe = dist_next > inner_radius

        goal = next_center
        goal_kind = 'zone'
        farm = None

        # Keep V1's strong bias for the safe zone, but avoid wasting moves when
        # already inside it. Loot only when we have room and no nearby squad.
        can_loot = not outside and not urgent and enemy_dist > 100 and radius > 32
        if can_loot:
            offers = []
            # Cubes are worth +HP and +damage. Low detour threshold is intentional.
            for cube in obs['cubes']:
                d = distance(pos, cube['pos'])
                if d < 52 and abs(cube['pos'][2] - z) < 3.8 and distance(cube['pos'], next_center) < inner_radius:
                    offers.append((d - 20, 'cube', cube))
            if len(me['weapons']) > 1 and me['weapons'][1] is None:
                for pickup in obs['pickups']:
                    d = distance(pos, pickup['pos'])
                    if d < 72 and abs(pickup['pos'][2] - z) < 3.8 and distance(pickup['pos'], next_center) < inner_radius:
                        # Laser and lightning work well without tricky ballistic aiming.
                        bias = {'laser': 17, 'lightning': 14, 'mortar': 6}.get(pickup['kind'], 0)
                        if bias:
                            offers.append((d - bias, 'weapon', pickup))
            if hp > 0.72:
                for crate in obs['crates']:
                    d = distance(pos, crate['pos'])
                    if d < 42 and abs(crate['pos'][2] - z) < 4.5 and distance(crate['pos'], next_center) < inner_radius:
                        offers.append((d + 6, 'crate', crate))
            if offers:
                score, kind, obj = min(offers, key=lambda item: item[0])
                if score < 48:
                    goal_kind, farm = kind, obj
                    goal = obj['pos'][:2]

        # Do not miss a pickup just because the target has changed this tick.
        if len(me['weapons']) > 1 and me['weapons'][1] is None:
            nearby_picks = [p for p in obs['pickups']
                            if p['kind'] != 'gun' and
                            distance(pos, p['pos']) < self.reach - 0.15 and
                            abs(p['pos'][2] - z) < 3.9]
            if nearby_picks:
                weight = {'laser': 3, 'lightning': 2, 'mortar': 1}
                best = max(nearby_picks, key=lambda p: weight.get(p['kind'], 0))
                action['take'] = best['id']

        # For shooting a crate, stay at modest range instead of walking into it.
        if goal_kind == 'crate' and distance(pos, goal) < 24:
            goal = pos

        dx, dy = unit(goal[0] - x, goal[1] - y)
        mx, my = dx, dy
        # Small defensive sidestep, not V2's powerful repulsion that could
        # overpower the safe-zone direction and strand the mech.
        if nearest and enemy_dist < 105 and not outside:
            awayx, awayy = unit(x - nearest['pos'][0], y - nearest['pos'][1])
            if hp < 0.62 or enemy_dist < 42:
                mx, my = unit(dx * (0.6 if urgent else 0.25) + awayx * 0.9,
                              dy * (0.6 if urgent else 0.25) + awayy * 0.9)
            else:
                mx, my = unit(dx * 0.75 - awayy * self.side * 0.55,
                              dy * 0.75 + awayx * self.side * 0.55)
            # Don't flee off the edge of the safe circle.
            if (distance((x + mx * 20, y + my * 20), next_center) > inner_radius
                    and dist_next > inner_radius - 22):
                if urgent or dist_next > inner_radius:
                    mx, my = unit(0.85 * dx + 0.15 * mx, 0.85 * dy + 0.15 * my)

        # Detect getting stuck ONLY when we are asking for real movement.
        commanded = math.hypot(mx, my) > 0.6
        if self.last_pos is not None and commanded and distance(pos, self.last_pos) < 0.20:
            self.stuck += 1
        else:
            self.stuck = max(0, self.stuck - 2)
        self.last_pos = pos
        if self.stuck > 22:
            self.side *= -1
            self.stuck = 10
        if self.stuck > 9:
            mx, my = unit(mx - my * self.side * 1.5, my + mx * self.side * 1.5)
            action['jump'] = bool(me['grounded'] and tick % 8 == 0)

        action['move'] = [mx, my]
        action['boost'] = bool(energy > (24 if outside else 47) and
                               (outside or (urgent and dist_to_safety > 25) or
                                (enemy_dist < 50 and hp < 0.8)))
        if 'jump' not in action:
            action['jump'] = bool(me['grounded'] and nearest and enemy_dist < 35 and tick % 33 == 0)

        # Keep V1's combat approach; improve target selection and aiming.
        # Do not suppress attacks while injured if the enemy is still close.
        target = None
        if nearest and enemy_dist < 200:
            target = nearest
        elif farm and goal_kind == 'crate' and distance(pos, farm['pos']) < 55:
            target = farm
        else:
            # Opportunistic farming, only when opponents cannot immediately engage.
            if enemy_dist > 140 and hp > 0.80:
                crates = [c for c in obs['crates']
                          if distance(pos, c['pos']) < 35 and abs(c['pos'][2] - z) < 4]
                if crates:
                    target = min(crates, key=lambda c: distance(pos, c['pos']))

        gun = me['weapons'][0] if me['weapons'] else None
        sec = me['weapons'][1] if len(me['weapons']) > 1 else None
        if target is not None:
            tp = target['pos']
            target_dist = distance(pos, tp)
            target_is_enemy = target.get('kind') == 'mech'
            v = target.get('vel', [0, 0, 0])
            speed = (gun or {}).get('stats', {}).get('speed', 252.0)
            travel = min(1.0, target_dist / max(15.0, speed))
            tx = tp[0] + v[0] * travel
            ty = tp[1] + v[1] * travel
            height = (4.5 if target_is_enemy else 1.5)
            tz = tp[2] + height + v[2] * travel
            muzzle = z + me['stats'].get('muzzle_height', 7.0)
            yaw = math.atan2(ty - y, tx - x)
            pitch = math.atan2(tz - muzzle, max(1.0, math.hypot(tx - x, ty - y)))
            action['aim'] = [yaw, max(-0.70, min(1.20, pitch))]
            aerr = abs(delta(me['aim'][0], yaw))
            perr = abs(me['aim'][1] - action['aim'][1])
            aligned = aerr < 0.14 and perr < 0.14
            if gun and gun['kind'] == 'gun':
                action['fire'][0] = bool(aligned and target_dist < gun['stats'].get('range', 230) - 8)
            if sec and target_is_enemy:
                if sec['kind'] == 'lightning':
                    action['fire'][1] = bool(aerr < 0.17 and
                        target_dist < sec['stats'].get('range', 45) - 3 and energy > 15)
                elif sec['kind'] == 'laser' and target_dist < sec['stats'].get('range', 280) - 8:
                    # A charged laser fires on RELEASE, not on sustained trigger.
                    charge = sec.get('charge', 0.0)
                    action['fire'][1] = bool(charge < sec['stats'].get('charge', 0.75) - 0.045 or not aligned)
        else:
            # Point toward the next zone to reveal objects in that direction.
            action['aim'] = [math.atan2(next_center[1] - y, next_center[0] - x), 0.0]

        if gun and gun['kind'] == 'gun':
            ammo = gun.get('ammo', 0)
            action['reload'] = bool(gun.get('reload', 0) == 0 and
                                   (ammo == 0 or (ammo <= 3 and enemy_dist > 95)))
        return action


mf.run(Bot)
