# Pre-registration: skip big-stop silver entries early in the day, take later ones (written 2026-10-03, BEFORE the run)

Entries/exits are the live silver v4.1 (RR 3, floor 2.5 / cap 5.0 x ATR, 350-pt day limit, 15-17h excluded), SILVER1! 5m, points net of
0.02%/side. Because the strategy is one-position-at-a-time, a skipped signal simply leaves it flat, so the next valid signal later
in the day is taken - exactly the behaviour asked for. Five variants, nothing added after the run:
E1 no entries before 10:00 | E2 no entries before 11:00 | E3 no entries before 12:00
B1 skip entries with stop > 1500 pts if the signal bar is before 12:00 (wide stops allowed later)
B2 skip entries with stop > 1500 pts if the signal bar is before 15:00
Criteria (pass): PF >= 1.30 over all trades, PF >= 1.15 in each of TRAIN/VALIDATION/HOLDOUT (60/20/20), >= 600 trades, >= 50% positive months,
net >= 80% of the current strategy's. Failing = dropped. 5 more trials on the same data: a pass is a shadow-book candidate only.
