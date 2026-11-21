# Oval Survivor V5 — evasive/healing experiment

**Aiming for a better competition score is experimental, not guaranteed.**
Measured scores shared so far: V1 **1.77**, V2 **0.98**, V3 **1.88**; V4's score has not been shared. V5 has no measured match score yet.

## Design differences from V3

- **Healing and disengagement:** backs off when damaged, avoids shooting at distant opponents while recovering. The game only regenerates HP after 5s without dealing or taking damage. At close range the bot may still defend itself.
- **Enemy group avoidance:** scores 24 possible movement headings instead of fleeing only the single closest opponent.
- **Safe-zone timing:** doesn't run to the centre at the start; begins moving when the shrink deadline and estimated walk time demand it, with a margin for obstructions.
- **Emergency boosting:** spends energy to escape threatening pursuers rather than only once HP is already low.
- **Combat:** intercept-based gun leading; opportunistic crate/drone farming; laser/lightning/mortar support; avoids unnecessary battles with the coordinated house squad.
- **Less noise:** can remain stationary and scan when safe, which is less audible than walking/boosting.

## Files

Place `example_bot.py`, `mechfight.py` and `Dockerfile` at the ROOT of your existing public GitHub repository. The README is optional. Commit and resubmit using the same repository URL at https://joinbuilders.org/buildathon.

Don't remove V3's older commit: V3's 1.88 is the best **measured** score so far. The competition ranks the best valid entry.

## What has actually been tested

- Python 3.13 syntax check
- Local `check/check.py` protocol check: **PASS**, 300 of 300 responses, 0 late, 0 invalid, max reported response time **0.5 ms** on this machine
- A few synthetic scenarios testing whether it stays put, moves to the zone before shrinking, and escapes when threatened

These tests **do not simulate fights**. There is no match simulator in the kit. I could not test inside a Docker match sandbox. Actual battle performance needs an official submission.

## Testing locally

From the extracted official `mechfight-kit` directory:

```bash
python3 check/check.py -- python3 -u /path/to/oval_survivor_v5/example_bot.py
```

The competition itself performs a similar test and then runs practice matches.
