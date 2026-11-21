# Oval Survivor V2 — Mech Royale

A survival-oriented Python bot for the Builders Mech Royale challenge.

## Improvements over Oval Survivor V1

- Reads the mounted arena map to route around buildings and stadium walls (coarse A*).
- Avoids approaching enemy groups and seeks safer areas inside the next zone.
- Reacts to approaching projectiles and actively retreats when threatened.
- Allows out-of-combat HP regeneration by avoiding unnecessary fights while injured.
- Leads moving targets with a simple projectile-intercept calculation.
- Can use laser (charge/release), lightning, and mortar (ballistic arc).
- Looks for power cubes, useful weapon pickups, crates and isolated NPCs when safe.
- Chooses upgrades based on defensive value.

## Submit

Upload the files **in this folder** to the root of your existing public GitHub repository, replacing `example_bot.py`, `mechfight.py`, and `Dockerfile` if prompted. The Python wrapper and Dockerfile are compatible with the provided kit.

The server automatically mounts the arena at `/arena` during the match. **Do not add the arena data files** to your repository.

## Run the supplied protocol check locally

From the extracted original `mechfight-kit` folder:

```bash
python3 check/check.py -- python3 -u /path/to/this/folder/example_bot.py
```

Or to test with the official container limits, put the three Python files in a repository folder and build with Docker:

```bash
docker build -t oval-survivor-v2 .
python3 /path/to/mechfight-kit/check/check.py --map-dir /arena -- \
  docker run --rm -i --network none --cpus 1 --memory 512m --read-only \
  --tmpfs /tmp:rw,size=64m --user 65534:65534 \
  -v "/path/to/mechfight-kit/arena:/arena:ro" oval-survivor-v2
```

## Verification

Passed the official recorded-stream checker locally: 300/300 valid on-time actions. A protocol check **does not simulate real matches**, and performance against practice bots remains to be measured through a new submission. No guarantee of a higher game score.
