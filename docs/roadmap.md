# Agreed seven-step rollout

| Step | Work | Current status |
|---|---|---|
| 1 | Character export/import and backups | Single-character JSON export/import implemented with validation and collision-safe IDs. Scheduled and full-database backups remain deferred |
| 2 | Remaining pilot fields and feats | Implemented as player-managed tracking: Physical, Social, Personality, general inventory/cargo notes, Zi Database/campaign notes, and seven feat slots with descriptions |
| 3 | Purchasing/building rules | Implemented from the supplied CSV: starter purchases, prerequisites, confirmations, GM override, consumed bases, upgrade costs/refunds, and CAU detachment |
| 4 | Transport gameplay | Implemented: four types, base stats, size/capacity validation, cargo lists, unloading on type change, and notes |
| 5 | Remaining rules review | Current classification/type pass implemented; see `rules-review.md`. Existing Dashboard-origin deferrals remain explicit |
| 6 | UI polish and playtesting | Five-page workflow implemented and regression-tested. Owner playtest/review is next |
| 7 | Windows and Android packages | Next separate stage after owner review: installers, real-device/offline/save tests, and final sign-off |

## Owner-supplied purchasing table

`assets/ZoidNames.txt` contains 138 current names: 134 playable designs (including 51 CAUs) and four Transports. BLOX Zoids are excluded. Refresh it explicitly with `tools/export_zoid_names.py` after reference changes.

The supplied workflow and follow-up decisions are implemented. See `workflow.md` for the authoritative current behavior, CSV corrections, migrations, and verification status. No packaging work has started in this pass.
