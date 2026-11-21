# Oval Survivor V7 — target-priority experiment

V3 remains the best measured version at **1.88**. V6 scored **1.73**.
V7 is derived **directly from V3**, undoing V6's aim threshold changes.

## One change

V3 targets any visible enemy within 200 m before a nearby crate, even when
it has already moved to that crate. V7 aims at the nearby crate when its
closest enemy is **120+ m away** (and V3's existing loot logic has chosen the
crate). Enemies closer than 120 m still take priority. Everything else
(including all movement, boosts, dodge, reloading, upgrades and gun aiming)
is unchanged. This could collect more early cubes/upgrades, but is unproven.

## Test and submit

Copy `example_bot.py`, `mechfight.py`, and `Dockerfile` to the root of the
existing public GitHub repo; commit the files. Keep old commits accessible.
Submit the new commit hash or leave blank if `main` is on V7.

Run from the supplied kit directory:

```bash
python3 check/check.py -- python3 -u /path/to/mech_v7/example_bot.py
```

The checker validates protocol messages, not combat results. You may keep
your best V3 commit as the selected entry when scoring closes.
