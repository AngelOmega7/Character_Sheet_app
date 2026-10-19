# Development handoff

## Goal and current state

Build a fully offline Python/Flet RPG character manager for Android and Windows, migrated from a multi-sheet Google workbook. The workbook is initial source/reference only: the installed app must never connect to or modify Google Sheets.

Implemented: local reference catalogs, stat calculation, ability ownership, per-attack previews, combat/repair rules, conversion tools, and tests. No Flet UI, SQLite persistence integration, or Android/Windows packages yet. Current baseline: **93 tests passing**. Python 3.10+ is required; all current code uses the standard library.

## Where to start

- `docs/data-and-rules.md`: current calculation rules, resolved issues, remaining discrepancies.
- `docs/ability-review.md`: ability decisions and remaining work.
- `docs/apps-script-migration.md`: original scripts and owner-confirmed changes.
- `docs/conversion-specification.md`: overall migration milestones.
- `zoids_app/stats.py`, `abilities.py`, `attacks.py`, `combat.py`: implemented rules.
- `tools/convert_reference_data.py`: authoritative repeatable data conversion. Change it when changing reference data so regeneration preserves corrections.
- `source/character_sheet.xlsx`, original Apps Script TXT files, and `docs/generated/`: preserved migration source/audit.

## Latest decisions

- Each weapon receives the strongest matching active bonus among Laser, Missile, Particle, Melee, and Rifle Expert. **Anti-Air Pro is an exception and adds on top** for Anti-Air-tagged weapons. Expert ranks 3/4 grant no advantage.
- Ranged Piercing becomes Bullet; Rifle Expert requires Ranged + Bullet. Melee Piercing stays as a player-managed label.
- Anti-Ait becomes Anti-Air. Slashing/Bludgeon removed. Freeze/Electric/Electrical/Lighting combined into Electrical. Tags have no automatic damage/status effects; they still support ability matching.
- Legacy NdM damage becomes N × M, including descriptions. Burst counts remain separate.
- One active size ability; exact size matching, explicit multi-size lists. Higher ability ranks permanently replace lower ranks within ownership. Other owned abilities remain inactive.
- Size and activated Organoid percentages affect all eight weapons' to-hit. Fixed weapon upgrades apply only to slots 1–4, with flat to-hit upgrades after percentage rounding.
- Equipment bonuses apply independently: passive while equipped, active only while activated.
- Fleet Footed applies while active. Sniper applies only to Long Range ranged attacks. Exactly half maximum range is Normal; melee ignores range controls.
- Comeback ranks grant 20/30/40/50% damage at current health <=20% of current derived maximum health.
- Wimp, Cross Eyed, Slowpoke, Bad Armor and all ranks retired.
- True Tank applies per defensive item; Evasion Master adds Armor per reaction-boosting item; Shield Master adds once to combined positive Shield HP from any source.
- Economized Shooting adds 1 maximum heat while active. Heat counters persist independently; firing at/above capacity works once then breaks the weapon.
- Rest clears heat without healing or repairing broken weapons. Weapon repair costs 10,000g and clears heat/broken status. Health repair costs 10g per point. Weapon repair requires confirmation if more than 25% of health is missing.
- Multi Attack, Smoke Master, Armor Breaker, Weapon Breaker, Counter Attack are tracked but player-managed.
- GIFs deferred. Remaining Dashboard-origin discrepancies are deferred unless needed for a gameplay requirement; preserve the Dashboard source.

## Resume

From the repository root:

```sh
python -m unittest discover -s tests -v
python -m zoids_app.preview --snapshot
```

On Linux, use `python3` if `python` is unavailable. On Windows, `py -3` also works when the Python launcher is installed.

Private GitHub repository: https://github.com/AngelOmega7/zoids-character-app. The shared branch is `main`. Continue the remaining rule review in `docs/data-and-rules.md`, then proceed to the first playable Flet interface and local saves.

Git tracks project files, not OpenCode conversation history or machine-local configuration. A fresh conversation can resume by reading this handoff and the linked documents.
