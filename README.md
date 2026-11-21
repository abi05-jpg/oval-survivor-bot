# Oval Survivor V3 — cautious iteration based on V1

V1 scored **1.77** on your practice submission. V2 scored **0.98**. V3
returns to V1's basic direction and combat model, with only small changes.

What changed:
- Avoid V2's A* planner and strong threat repulsion (both unproven).
- Reach the upcoming zone when necessary rather than always sprinting to its center.
- Prefer reachable nearby cubes and secondary weapons without dangerous detours.
- Shoot nearby crates when enemies aren't threatening (for upgrades).
- Select defensive upgrades by their actual IDs.
- Boost away from extremely close enemies if damaged.
- Use a more careful laser trigger and reloading policy.

**Not a guaranteed performance improvement.** The official `check.py` is a
protocol test, not an actual fight. Submit to measure whether V3 beats 1.77.
Keep your previous best commit on GitHub; you can return to it if V3 scores lower.

## Upload

Put the **three files** `example_bot.py`, `mechfight.py` and `Dockerfile` at
the root of your GitHub repository and commit. Do not upload the map.
Submit the repository URL at https://joinbuilders.org/buildathon.

## Local protocol test

From the supplied mechfight-kit directory, run:

```sh
python3 check/check.py -- python3 -u /path/to/oval_survivor_v3/example_bot.py
```

If you have Docker, also run the kit's sandbox check described in its README.
