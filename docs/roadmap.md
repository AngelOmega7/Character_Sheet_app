# Agreed seven-step rollout

| Step | Work | Current status |
|---|---|---|
| 1 | Character export/import and backups | Deferred by owner; skip for now |
| 2 | Remaining pilot fields and feats | Implemented as player-managed tracking: Physical, Social, Personality, general inventory/cargo notes, Zi Database/campaign notes, and seven feat slots with descriptions |
| 3 | Purchasing/building rules | Deferred while the owner creates Zoid costs and required building-parts data. Acquisition and upgrade controls still record play decisions without charging gold |
| 4 | Transport gameplay | Deferred while the owner defines the rules. **Transport must be implemented before Step 7 is marked complete**. The current section is reference-only |
| 5 | Remaining rules review | Current classification/type pass implemented; see `rules-review.md`. Existing Dashboard-origin deferrals remain explicit |
| 6 | UI polish and playtesting | Next active work: phone/desktop navigation, controls, and end-to-end play sessions |
| 7 | Windows and Android packages | Pending installers, real-device/offline/save tests, and final sign-off. Transport implementation remains an outstanding prerequisite for completion |

## Owner-supplied purchasing table

`assets/ZoidNames.txt` contains 138 current names, one per line in case-insensitive alphabetical order: 135 playable Zoids (including nine CAU forms) and three Transports. BLOX Zoids are excluded. Display spellings are preserved to support matching the future costs/parts table to the catalogs. This names-only snapshot is not overwritten by normal catalog regeneration.

Purchasing logic and prices await the owner's table. Transport ownership, capacity, loading/unloading, and storage rules await the owner's design; they are not complete merely because a Transport reference section exists.
