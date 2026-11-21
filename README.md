# Oval Survivor V6 — precision-aim experiment

**Baseline:** V3 scored 1.88 in your competition practice runs. V5 scored 0.42. V6 is a direct modification of V3, *not* V5.

**Hypothesis:** V3 sometimes fires gun bullets with its torso as much as 0.14 radians away from the target's predicted position. At distance, that is a very large miss. Calculate the projectile intercept with a moving target and require an aim error that scales with distance before firing. This may save ammo and improve damage; only an actual match score can confirm it.

Changes in V6:
- Constant-velocity interception solution for the standard gun (3D).
- Distance-sensitive aim tolerance for gun firing.
- V3's movement, boosting, zone logic, loot, upgrades, and reloading preserved.
- V3's laser/lightning logic preserved other than a potentially slightly different target aim direction.

## Files to put in the GitHub repository ROOT

- `example_bot.py`
- `mechfight.py`
- `Dockerfile`

`README.md` is optional. These files should be at the root, not inside another folder.

## How to check locally

With the official kit extracted, from the kit root:

```
python3 check/check.py -- python3 -u /path/to/v6/example_bot.py
```

If Docker is installed:

```
docker build -t oval-survivor-v6 /path/to/v6
python3 check/check.py --map-dir /arena -- docker run --rm -i --network none --cpus 1 --memory 512m --read-only --tmpfs /tmp:rw,size=64m --user 65534:65534 -v "$PWD/arena:/arena:ro" oval-survivor-v6
```

## Tests actually run in this development environment

- Python syntax compilation: passed.
- Official checker with 300 recorded observations: 300/300 valid, 0 late.
- Comparison with V3 on the same *recorded observations*: all 300 decisions for movement, boost, jump, reload, loot and upgrade choice identical. Gun trigger on 144 ticks in V3 versus 127 in V6. Observations do not react to actions, so these numbers are **not** a performance score.
- Mathematical interception unit checks: passed.
- Docker sandbox / live competition matches: **not run** here.

## What score to compare

Submit the new commit to the Builders Buildathon and compare with **1.88**. Preserve the V3 commit so you can revert if V6 is worse. Do not infer improvement from the protocol test alone.
