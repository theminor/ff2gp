#!/usr/bin/env python3
"""
ff2gp.py — Convert a ForeFlight logbook CSV export to the Garmin Pilot
(flyGarmin) logbook import template.

Usage:
    python3 ff2gp.py foreflight_export.csv garmin_template.csv -o garmin_import.csv

Options:
    -o OUT                output file (default: garmin_import.csv)
    --type TAIL=TYPE      override the aircraft type code for a tail number
                          (repeatable). Use the exact string already entered
                          in Garmin Pilot for that aircraft, e.g.
                          --type N4563W=C812
    --skip-ground-training  drop rows that have no aircraft (ground training)
                          instead of importing them with Ground Instruction
                          Duration filled in.
    --landings total|full-stop
                          Garmin has no full-stop/touch-and-go split. 'total'
                          (default) imports every landing, matching ForeFlight's
                          AllLandings total; 'full-stop' imports only full-stop
                          landings.
    --no-remarks          do not fold passengers / circling notes / endorsement
                          flags into the Remarks column.

Requires only the Python standard library. Tested against one ForeFlight
export (2022-2026) and the 2026 flyGarmin template. Provided as-is with no
compatibility guarantee. See README.md.
"""

import argparse
import csv
import sys

# ---------------------------------------------------------------------------
# ForeFlight export parsing
# ---------------------------------------------------------------------------

def load_foreflight(path):
    """Return (aircraft_table, flights_header, flight_rows) from a ForeFlight
    logbook export. The export contains an Aircraft Table section followed by
    a Flights Table section; both are located by their header rows."""
    with open(path, newline='', encoding='utf-8-sig') as f:
        rows = list(csv.reader(f))

    ac_hdr_i = next((i for i, r in enumerate(rows)
                     if r and r[0].strip() == 'AircraftID'), None)
    fl_hdr_i = next((i for i, r in enumerate(rows)
                     if r and r[0].strip() == 'Date'), None)
    if ac_hdr_i is None or fl_hdr_i is None:
        sys.exit("error: file does not look like a ForeFlight logbook export "
                 "(no 'AircraftID' or 'Date' header row found)")

    aircraft = {}
    i = ac_hdr_i + 1
    while i < len(rows) and rows[i] and rows[i][0].strip():
        r = rows[i]
        aircraft[r[0].strip()] = {
            'type': r[1].strip() if len(r) > 1 else '',
            'make': r[3].strip() if len(r) > 3 else '',
            'model': r[4].strip() if len(r) > 4 else '',
        }
        i += 1

    fl_hdr = [h.strip() for h in rows[fl_hdr_i]]
    flights = [r for r in rows[fl_hdr_i + 1:] if r and r[0].strip()]
    return aircraft, fl_hdr, flights


def field(row, cols, name):
    """Raw string value of a ForeFlight column ('' if absent)."""
    j = cols.get(name)
    if j is None or j >= len(row):
        return ''
    return row[j].strip()


def num_str(row, cols, name):
    """Numeric value as a clean string; '' for empty or zero (Garmin treats
    blank as zero and blank is what the template's unused cells look like)."""
    v = field(row, cols, name)
    if not v:
        return ''
    try:
        f = float(v)
    except ValueError:
        return v  # non-numeric: pass through unchanged
    if f == 0:
        return ''
    if f == int(f):
        return str(int(f))
    return f"{f:.1f}"


def meters_str(sm_value):
    """Convert a statute-miles value to meters (Garmin's Distance unit).
    '' passes through; non-numeric passes through unchanged."""
    if not sm_value:
        return ''
    try:
        f = float(sm_value)
    except ValueError:
        return sm_value
    return f"{f * 1609.344:.1f}"


def unquote_comment(s):
    """ForeFlight wraps some comments in literal quote characters; strip them."""
    s = s.strip()
    while len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        s = s[1:-1].strip()
    return s


# ---------------------------------------------------------------------------
# Approach conversion:  ForeFlight 'count;name;runway;airport;suffix;CIRCLE'
#                    -> Garmin  "'AIRPORT' 'TYPE' 'RUNWAY' (count)"
# ---------------------------------------------------------------------------

def normalize_approach_type(name):
    n = name.upper()
    if n.startswith('RNAV'):
        return 'RNAV'
    if n.startswith('ILS'):
        return 'ILS'          # 'ILS OR LOC' collapses to ILS (Garmin requires one)
    if n.startswith('LOC'):
        return 'LOC'
    if n.startswith('LDA') or n.startswith('SDF'):
        return 'ILS'
    if n.startswith('VOR'):
        return 'VOR'
    if n.startswith('NDB'):
        return 'NDB'
    if n.startswith('TACAN'):
        return 'TACAN'
    if n.startswith('GPS'):
        return 'RNAV'
    return name               # unknown: keep as-is


def convert_approaches(row, cols):
    """Return (garmin_approaches_string, notes_list)."""
    entries, notes = [], []
    for k in ('Approach1', 'Approach2', 'Approach3',
             'Approach4', 'Approach5', 'Approach6'):
        raw = field(row, cols, k)
        if not raw:
            continue
        parts = raw.split(';')
        count = parts[0].strip() or '1'
        name = parts[1].strip() if len(parts) > 1 else ''
        rwy = parts[2].strip() if len(parts) > 2 else ''
        airport = parts[3].strip() if len(parts) > 3 else ''
        suffix = parts[4].strip() if len(parts) > 4 else ''
        circle = (parts[5].strip().upper() == 'CIRCLE') if len(parts) > 5 else False
        atype = normalize_approach_type(name)
        entries.append(f"'{airport}' '{atype}' '{rwy}' ({count})")
        if circle:
            notes.append(f"Circled to land RWY {rwy} at {airport}")
        if suffix:
            notes.append(f"Approach {name} {suffix.lower()}")
    return '; '.join(entries), notes


# ---------------------------------------------------------------------------
# Packed person field:  'Name;Role;email;phone'
# ---------------------------------------------------------------------------

def parse_person(raw):
    parts = [p.strip() for p in raw.split(';')]
    if not parts or not parts[0]:
        return None
    name = parts[0]
    role = parts[1] if len(parts) > 1 else ''
    return {'name': name, 'role': role}


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------

def convert(aircraft, fl_hdr, flights, template_header, type_overrides,
           keep_ground_training, with_remarks, landing_mode='total',
           pic_name='Self', pic_fallback=False):
    cols = {h: j for j, h in enumerate(fl_hdr) if h}
    out_rows = []
    stats = {'flights': 0, 'ground': 0, 'skipped_ground': 0, 'pic_fallback': 0}

    def pic_value(row):
        """PIC hours to write. With pic_fallback, flights that have
        TotalTime but NO pilot category at all (PIC/SIC/PICUS/Dual all
        blank or zero) and no instructor listed are treated as the
        account holder flying their own airplane: PIC = TotalTime.
        Student flights with an instructor aboard are NOT touched (dual
        received with the CFI as PIC is correct logging)."""
        pic = num_str(row, cols, 'PIC')
        if pic:
            return pic
        if not pic_fallback:
            return ''
        total = num_str(row, cols, 'TotalTime')
        if not total:
            return ''
        for cat in ('SIC', 'PICUS', 'DualReceived', 'DualGiven', 'GroundTraining'):
            if num_str(row, cols, cat):
                return ''
        people = ' '.join(field(row, cols, k) for k in ('Person1', 'Person2', 'Person3'))
        if 'Instructor' in people or field(row, cols, 'InstructorName'):
            return ''
        stats['pic_fallback'] += 1
        stats['pic_fallback_hours'] = round(stats.get('pic_fallback_hours', 0.0) + float(total), 1)
        return total

    for row in flights:
        tail = field(row, cols, 'AircraftID')
        date = field(row, cols, 'Date')
        ac = aircraft.get(tail, {'type': '', 'make': '', 'model': ''})
        ac_type = type_overrides.get(tail, ac['type'])

        is_ground = not tail and num_str(row, cols, 'GroundTraining')
        if is_ground and not keep_ground_training:
            stats['skipped_ground'] += 1
            continue

        approaches, approach_notes = convert_approaches(row, cols)

        # ---- remarks assembly --------------------------------------------
        remarks_parts = []
        pc = unquote_comment(field(row, cols, 'PilotComments'))
        if pc:
            remarks_parts.append(pc)
        ic = unquote_comment(field(row, cols, 'InstructorComments'))
        if ic:
            remarks_parts.append(f"Instructor: {ic}")

        # packed person columns: passengers -> remarks; instructor fallback
        instructor = field(row, cols, 'InstructorName')
        # ForeFlight's instructor column is sometimes packed like Person
        # columns ('Name;Role;email;phone'); keep just the name.
        if ';' in instructor:
            instructor = instructor.split(';')[0].strip()
        passengers = []
        for k in ('Person1', 'Person2', 'Person3', 'Person4', 'Person5', 'Person6'):
            p = parse_person(field(row, cols, k))
            if not p:
                continue
            if p['role'].lower() == 'instructor' and not instructor:
                instructor = p['name']
            elif p['role'].lower() == 'passenger':
                passengers.append(p['name'])
        if passengers and with_remarks:
            remarks_parts.append("Passengers: " + ", ".join(passengers))
        if approach_notes and with_remarks:
            remarks_parts.extend(approach_notes)
        for flag_col, label in (('Flight Review (FAA)', 'FAA Flight Review'),
                                ('IPC (FAA)', 'IPC'),
                                ('Checkride (FAA)', 'FAA Checkride'),
                                ('FAA 61.58 (FAA)', 'FAA 61.58'),
                                ('NVG Proficiency (FAA)', 'NVG Proficiency')):
            if field(row, cols, flag_col).upper() == 'TRUE' and with_remarks:
                remarks_parts.append(label)

        # ---- landing/takeoff counts --------------------------------------
        # ForeFlight's auto-computed columns (DayTakeoffs, NightTakeoffs,
        # AllLandings, Day/NightLandingsFullStop) are the ones ForeFlight's
        # totals page displays; the manual-entry columns are sparse leftovers.
        # Garmin has no full-stop/touch-and-go split, so 'total' mode imports
        # every landing (matching AllLandings); 'full-stop' mode imports only
        # full-stop landings.
        day_to = num_str(row, cols, 'DayTakeoffs')
        night_to = num_str(row, cols, 'NightTakeoffs')
        all_land = float(field(row, cols, 'AllLandings') or 0)
        night_fs = float(field(row, cols, 'NightLandingsFullStop') or 0)
        day_fs = float(field(row, cols, 'DayLandingsFullStop') or 0)
        if all_land > 0:
            night_land = night_fs
            day_land = (all_land - night_fs) if landing_mode == 'total' else day_fs
        else:
            # rows logged manually (no auto counts): fall back to manual columns
            day_land = float(field(row, cols, 'Landing Full-Stop Day') or 0)
            night_land = night_fs
            if landing_mode == 'total':
                day_land += float(field(row, cols, 'Landing Touch-and-Go Day') or 0)
            day_to = day_to or field(row, cols, 'Takeoff Day')
            night_to = night_to or field(row, cols, 'Takeoff Night')

        def clean_int(x):
            x = float(x or 0)
            return str(int(x)) if x else ''

        # compute PIC once per row (pic_value updates stats)
        pic_out = pic_value(row)

        values = {
            'Date': date,
            'Aircraft ID': tail,
            'Aircraft Type': ac_type,
            'Time Out': field(row, cols, 'TimeOut'),
            'Time Off': field(row, cols, 'TimeOff'),
            'Time On': field(row, cols, 'TimeOn'),
            'Time In': field(row, cols, 'TimeIn'),
            'Hobbs Out': num_str(row, cols, 'HobbsStart'),
            'Hobbs In': num_str(row, cols, 'HobbsEnd'),
            'Tach Out': num_str(row, cols, 'TachStart'),
            'Tach In': num_str(row, cols, 'TachEnd'),
            # Garmin requires a strictly POSITIVE Total Duration on every
            # row: verified live on flyGarmin, both '0.0' and '00:00' are
            # rejected ("expected to be a duration greater than or equal
            # to 0"). For ground-training rows, mirror the ground hours
            # into Total Duration so the row passes validation.
            'Total Duration': num_str(row, cols, 'TotalTime')
                or (num_str(row, cols, 'GroundTraining') if is_ground else ''),
            'Night Duration': num_str(row, cols, 'Night'),
            # PIC Name: who was pilot in command. 'Self' is Garmin's
            # template keyword but the importer stores it literally, so
            # pass the account holder's real name (--pic-name). The field
            # exists for shared logbooks (CFI logging dual given, or a
            # student's logbook where the PIC is the instructor); in a
            # personal logbook it is always the owner.
            'PIC Name': pic_name if pic_out else '',
            'PIC Duration': pic_out,
            'SIC Duration': num_str(row, cols, 'SIC'),
            'Solo Duration': num_str(row, cols, 'Solo'),
            'Cross Country Duration': num_str(row, cols, 'CrossCountry'),
            'Actual Instrument Duration': num_str(row, cols, 'ActualInstrument'),
            'Simulated Instrument Duration': num_str(row, cols, 'SimulatedInstrument'),
            'Dual Received Duration': num_str(row, cols, 'DualReceived'),
            'Dual Given Duration': num_str(row, cols, 'DualGiven'),
            'Ground Instruction Duration': num_str(row, cols, 'GroundTraining'),
            'Departure': field(row, cols, 'From'),
            'Destination': field(row, cols, 'To'),
            'Route': field(row, cols, 'Route'),
            'Day Takeoffs': clean_int(day_to),
            'Night Takeoffs': clean_int(night_to),
            'Day Landings': clean_int(day_land),
            'Night Landings': clean_int(night_land),
            'Approaches': approaches,
            'Holding Patterns': num_str(row, cols, 'Holds'),
            # Garmin's Instrument (FAA) currency engine counts three fields
            # per 61.57(c): Approaches, Holding Patterns, and Track Nav Aid
            # (a TRUE flag for intercepting/tracking courses). ForeFlight's
            # export has no tracking field, but every instrument approach
            # except a PAR involves intercepting and tracking a course, so
            # mark TRUE on any row with a logged approach.
            'Track Nav Aid': 'TRUE' if approaches else '',
            # ForeFlight exports distance in statute miles; Garmin stores
            # meters (verified against a manually-flown entry: 374697.8 for
            # a ~232 SM leg, and the template sample is 204310.3).
            'Distance': meters_str(num_str(row, cols, 'Distance')),
            'Remarks': ' | '.join(remarks_parts),
            'Instructor Name': instructor,
        }
        out_rows.append([values.get(h, '') for h in template_header])
        stats['ground' if is_ground else 'flights'] += 1

    return out_rows, stats


# ---------------------------------------------------------------------------
# Totals audit (source vs output) so the import can be verified
# ---------------------------------------------------------------------------

def audit(fl_hdr, flights, template_header, out_rows, stats=None):
    stats = stats or {}
    src_cols = {h: j for j, h in enumerate(fl_hdr) if h}
    out_cols = {h: j for j, h in enumerate(template_header) if h}

    def sum_src(name):
        j = src_cols.get(name)
        if j is None:
            return 0.0
        total = 0.0
        for r in flights:
            try:
                total += float(r[j] or 0)
            except ValueError:
                pass
        return round(total, 1)

    def sum_out(name):
        j = out_cols.get(name)
        if j is None:
            return 0.0
        total = 0.0
        for r in out_rows:
            try:
                total += float(r[j] or 0)
            except ValueError:
                pass
        return round(total, 1)

    pairs = [
        ('TotalTime', 'Total Duration'),
        ('PIC', 'PIC Duration'),
        ('Night', 'Night Duration'),
        ('Solo', 'Solo Duration'),
        ('CrossCountry', 'Cross Country Duration'),
        ('ActualInstrument', 'Actual Instrument Duration'),
        ('SimulatedInstrument', 'Simulated Instrument Duration'),
        ('DualReceived', 'Dual Received Duration'),
        ('DualGiven', 'Dual Given Duration'),
        ('GroundTraining', 'Ground Instruction Duration'),
    ]
    print("\n=== TOTALS AUDIT (source -> output) ===")
    ok = True
    for s, o in pairs:
        a, b = sum_src(s), sum_out(o)
        # Total Duration intentionally exceeds source TotalTime by the ground
        # hours mirrored onto pure ground-training rows (Garmin rejects a
        # zero Total Duration). Ground time sitting on real flight rows is
        # NOT mirrored (those rows already have a positive TotalTime), so
        # compute the mirrored amount from the output rows themselves.
        if s == 'TotalTime':
            mirrored = 0.0
            for r in out_rows:
                if not r[out_cols['Aircraft ID']].strip():
                    try:
                        mirrored += float(r[out_cols['Total Duration']] or 0)
                    except ValueError:
                        pass
            if abs(b - (a + mirrored)) < 0.05:
                print(f"  {s:<20} {a:>8}  ->  {o:<30} {b:>8}  [OK "
                      f"(+{round(mirrored, 1)} ground hours mirrored onto "
                      f"ground-training rows)]")
                continue
        # --pic-fallback intentionally adds PIC hours to source rows that
        # had a total but no pilot category at all. Account for it.
        if s == 'PIC' and stats.get('pic_fallback'):
            fb = stats.get('pic_fallback_hours', 0.0)
            if abs(b - (a + fb)) < 0.05:
                print(f"  {s:<20} {a:>8}  ->  {o:<30} {b:>8}  [OK "
                      f"(+{round(fb, 1)} PIC hours reconstructed on "
                      f"{stats['pic_fallback']} uncategorized rows via "
                      f"--pic-fallback)]")
                continue
        match = 'OK' if a == b else 'MISMATCH'
        if a != b:
            ok = False
        print(f"  {s:<20} {a:>8}  ->  {o:<30} {b:>8}  [{match}]")

    def int_sum(rows, col):
        j = out_cols.get(col)
        if j is None:
            return 0
        return sum(int(r[j]) for r in rows if r[j].strip().isdigit())
    print(f"  landings: day={int_sum(out_rows,'Day Landings')} "
          f"night={int_sum(out_rows,'Night Landings')}  "
          f"takeoffs: day={int_sum(out_rows,'Day Takeoffs')} "
          f"night={int_sum(out_rows,'Night Takeoffs')}")
    return ok


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument('foreflight_csv')
    ap.add_argument('garmin_template_csv')
    ap.add_argument('-o', '--output', default='garmin_import.csv')
    ap.add_argument('--type', action='append', default=[], metavar='TAIL=TYPE',
                    help='override aircraft type for a tail (repeatable)')
    ap.add_argument('--skip-ground-training', action='store_true')
    ap.add_argument('--landings', choices=['total', 'full-stop'], default='total',
                    help="Garmin has no full-stop/touch-and-go split: 'total' "
                         "(default) imports all landings; 'full-stop' only full-stops")
    ap.add_argument('--no-remarks', action='store_true')
    ap.add_argument('--pic-name', default='Self', metavar='NAME',
                    help="value for the PIC Name column on rows with PIC "
                         "time (the account holder's full name, e.g. "
                         "'John Minor'; 'Self' is Garmin's template "
                         "placeholder and imports literally)")
    ap.add_argument('--pic-fallback', action='store_true',
                    help="when a flight has TotalTime but no PIC/SIC/PICUS/"
                         "Dual category at all and no instructor aboard, "
                         "treat the account holder as PIC (PIC = TotalTime). "
                         "Repairs ForeFlight rows logged with only a total.")
    args = ap.parse_args()

    overrides = {}
    for spec in args.type:
        if '=' not in spec:
            sys.exit(f"error: --type expects TAIL=TYPE, got {spec!r}")
        tail, ttype = spec.split('=', 1)
        overrides[tail.strip()] = ttype.strip()

    aircraft, fl_hdr, flights = load_foreflight(args.foreflight_csv)
    with open(args.garmin_template_csv, newline='', encoding='utf-8-sig') as f:
        template_header = next(csv.reader(f))
    template_header = [h.strip() for h in template_header]

    out_rows, stats = convert(aircraft, fl_hdr, flights, template_header,
                              overrides, not args.skip_ground_training,
                              not args.no_remarks, args.landings,
                              args.pic_name, args.pic_fallback)

    with open(args.output, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(template_header)
        w.writerows(out_rows)

    print(f"source rows: {len(flights)}  "
          f"(flights: {stats['flights']}, ground training: {stats['ground']}, "
          f"skipped: {stats['skipped_ground']})")
    print(f"wrote {len(out_rows)} rows -> {args.output}")
    audit(fl_hdr, flights, template_header, out_rows, stats)


if __name__ == '__main__':
    main()
