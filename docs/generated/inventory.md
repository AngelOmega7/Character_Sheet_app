# Workbook inventory

Generated from a local XLSX export. Values are cached source values, not recalculated results.

| Sheet | Populated cells | Formula cells | Validation rules |
|---|---:|---:|---:|
| Zoid | 273 | 158 | 7 |
| Pilot | 55 | 25 | 7 |
| Zoid Upgrades | 91 | 44 | 0 |
| Dashboard (DO NOT TOUCH) | 181 | 145 | 0 |
| Stats | 2424 | 20 | 1 |
| Zoid List | 5179 | 1 | 0 |
| Armaments | 1275 | 21 | 1 |
| Organoid | 1095 | 0 | 0 |
| Zoid Abilities | 602 | 39 | 0 |
| Zoid_Gifs | 461 | 0 | 0 |
| Feats | 18 | 0 | 0 |

Total formula cells: 453

## Formula function tokens

Counts are lexical, including formulas embedded in compatibility-wrapper strings.

- `VLOOKUP`: 517
- `IF`: 118
- `DASHBOARD`: 117
- `IFERROR`: 105
- `ISNUMBER`: 100
- `SEARCH`: 99
- `INDEX`: 40
- `MATCH`: 40
- `IFS`: 35
- `ROUND`: 32
- `FALSE`: 18
- `ROUNDUP`: 14
- `RANDBETWEEN`: 8
- `__XLUDF.DUMMYFUNCTION`: 7
- `OR`: 7
- `TO_PERCENT`: 5
- `SUM`: 3
- `ARD`: 3
- `SPARKLINE`: 2
- `H`: 1

## Export limitations

- Shared formula followers retain their shared-formula metadata; their expressions are not expanded by this tool.
- Google-specific formulas may be compatibility wrappers. Verify their original semantics before translation.
- Checkbox formatting, validation rules, scripts, buttons, and images may not survive XLSX export completely.
- Non-formula cells are candidates for inputs or reference data, not automatically editable fields.
- Numeric values retain their XML text to avoid precision loss; normalization is a later conversion step.
