import csv, re

TPL = 'Log_Entries_Template.csv'
OUT = 'garmin_import.csv'

tpl_hdr = next(csv.reader(open(TPL, encoding='utf-8-sig')))
rows = list(csv.reader(open(OUT, encoding='utf-8')))
hdr, data = rows[0], rows[1:]

print("header matches template exactly:", [h.strip() for h in hdr] == [h.strip() for h in tpl_hdr])
print("row count:", len(data))

# every row has the right number of columns
bad_len = [r[0] for r in data if len(r) != len(hdr)]
print("rows with wrong column count:", bad_len)

# date format check
bad_dates = [r[0] for r in data if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', r[0])]
print("bad dates:", bad_dates)

# time format check
cols = {h: i for i, h in enumerate(hdr)}
bad_times = []
for r in data:
    for k in ('Time Out', 'Time Off', 'Time On', 'Time In'):
        v = r[cols[k]]
        if v and not re.fullmatch(r'\d{2}:\d{2}', v):
            bad_times.append((r[0], k, v))
print("bad times:", bad_times)

# decimal duration sanity: all numeric, >= 0
bad_dur = []
for r in data:
    for k in ('Total Duration', 'PIC Duration', 'Night Duration', 'Solo Duration',
              'Cross Country Duration', 'Actual Instrument Duration',
              'Simulated Instrument Duration', 'Dual Received Duration',
              'Dual Given Duration', 'Ground Instruction Duration'):
        v = r[cols[k]]
        if v:
            try:
                assert float(v) >= 0
            except Exception:
                bad_dur.append((r[0], k, v))
print("bad durations:", bad_dur)

# aircraft type distribution
from collections import Counter
print("aircraft types:", Counter((r[cols['Aircraft ID']], r[cols['Aircraft Type']]) for r in data))

# approach format check: each entry must match 'APT' 'TYPE' 'RWY' (n)
pat = re.compile(r"^('[A-Z0-9]+' '[A-Z0-9 ()]+' '[A-Z0-9]+' \(\d+\))(; '[A-Z0-9]+' '[A-Z0-9 ()]+' '[A-Z0-9]+' \(\d+\))*$")
bad_app = [(r[0], r[cols['Approaches']]) for r in data if r[cols['Approaches']] and not pat.fullmatch(r[cols['Approaches']])]
print("malformed approach strings:", bad_app)

# total approaches count preserved
n_app = sum(r[cols['Approaches']].count('(') for r in data)
print("approach entries in output:", n_app)

# BOM / encoding check
raw = open(OUT, 'rb').read()
print("starts with BOM:", raw[:3] == b'\xef\xbb\xbf')
print("file size:", len(raw))

# endorsement-flag rows present
for r in data:
    if 'FAA Checkride' in r[cols['Remarks']] or 'FAA Flight Review' in r[cols['Remarks']]:
        print("endorsement row:", r[cols['Date']], r[cols['Aircraft ID']], r[cols['Remarks']][:60])
