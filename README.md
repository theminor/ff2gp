# ff2gp — ForeFlight → Garmin Pilot logbook converter

A single-file Python script that converts a **ForeFlight logbook CSV export**
into the **Garmin Pilot / flyGarmin logbook import template**. No dependencies
beyond the Python standard library.

Built because the two formats don't import cleanly into each other and no
existing converter was found (GitHub repo and code search, October 2026).

> **As-is tool.** Tested against one real export (253 entries, 2022–2026) and
> the 2026 flyGarmin template. No compatibility guarantee, no maintenance
> promise. Verify your totals before and after import (the script prints both).

## Usage

```bash
python3 ff2gp.py foreflight_export.csv Log_Entries_Template.csv -o garmin_import.csv
```

1. Export your logbook from **plan.foreflight.com** → Logbook → Export (CSV).
   Keep the original file untouched.
2. Download Garmin's current import template from **fly.garmin.com** →
   Logbook → Setup → Import (login required). Pass it as the second argument;
   the script writes output with exactly that header row.
3. Run the converter. It prints a **totals audit** (source vs. output hours
   per category). Every line should say `OK`.
4. Import through the **flyGarmin web page** (Logbook → Setup → Import).
   Never the mobile app, and **never open the CSV in Excel first** — Excel
   silently reformats dates and corrupts the file.
5. After import, compare Garmin's totals against the audit numbers. Row count
   matching is not success; totals matching is.

### Options

| Flag | Purpose |
|---|---|
| `--type TAIL=TYPE` | Force the aircraft type code for a tail. Use the exact string already entered in Garmin Pilot (e.g. `--type N4563W=C812`) so imported entries attach to your existing aircraft instead of creating a duplicate. Repeatable. |
| `--skip-ground-training` | Drop rows with no aircraft instead of importing them with Ground Instruction Duration. |
| `--landings total\|full-stop` | Garmin has no full-stop/touch-and-go split. `total` (default) imports every landing, matching ForeFlight's AllLandings; `full-stop` imports only full-stop landings. |
| `--no-remarks` | Don't fold passengers, circling notes, or endorsement flags into Remarks. |

## What gets converted

- All duration columns (total, PIC, SIC, solo, night, cross-country, actual/
  simulated instrument, dual received/given, ground instruction), times, Hobbs/
  tach, departure/destination/route, distance, holds.
- **Aircraft type**: joined from the Aircraft Table at the top of the
  ForeFlight export (Garmin requires tail *and* type per row).
- **Approaches**: ForeFlight's six packed columns (`count;name;runway;airport;…`)
  are rewritten into Garmin's format: `'KAAA' 'RNAV' '32' (1); 'KAAA' 'ILS' '14' (1)`.
  `ILS OR LOC` collapses to `ILS`; `RNAV (GPS)` becomes `RNAV`.
- **Remarks**: your pilot comments, instructor comments (labeled), passenger
  names, circling/partial-panel approach notes, and FAA endorsement flags
  (Flight Review / Checkride) so those entries are findable for manual
  re-entry of signatures.
- **Instructor name**: unpacked from ForeFlight's packed field.

## What does NOT transfer (true for any CSV migration)

- **Endorsements, instructor signatures, photos, and track logs do not export
  from ForeFlight at all.** Keep the ForeFlight PDF export as your signature
  archive and re-enter endorsement entries by hand. The script flags those
  entries in Remarks so you can find them.
- Circling approaches have no representation in Garmin's approach field (the
  script notes them in Remarks instead).
- Full-stop vs. touch-and-go landing split: Garmin has one landing count (see
  `--landings`).
- Custom fields and passenger contact details (emails/phones) don't map; names
  go to Remarks.
- Complex/TAA/high-performance flags live on the aircraft record in Garmin,
  not in the CSV — set them when you create the aircraft.

## Ground training

Garmin's template has a `Ground Instruction Duration` column, so ground time
is representable. By default the script imports ground-training rows with that
field filled and no aircraft. If Garmin's importer rejects rows without an
aircraft, either re-enter those few entries by hand in the app (it has a
dedicated Ground Instruction section) or run with `--skip-ground-training`.

## Files

- `ff2gp.py` — the converter (stdlib only)
- `Log_Entries_Template.csv` — the 2026 flyGarmin import template (Garmin's
  file; re-download your own copy from flyGarmin)
- `sample_foreflight_export.csv` — small synthetic ForeFlight export for testing
- `check_output.py` — spot-check helper used during development

## Verify, always

The script prints per-category totals before and after conversion. Write them
down. After importing, check Garmin's totals against them. If Garmin's import
fails, it reports only a generic error with no per-row reason — import a small
batch first, confirm it looks right, then run the full file.

## License

MIT. ForeFlight is a trademark of Boeing; Garmin Pilot is a trademark of Garmin.
This project is unaffiliated with either.
