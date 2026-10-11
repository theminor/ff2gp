import csv

# Probe Garmin's importer: which Total Duration encodings does it accept for a
# pure ground-training row (no aircraft)? Three rows, obviously-fake 1999 dates
# so they're easy to find and delete afterwards.
rows = list(csv.reader(open('Log_Entries_Template.csv', encoding='utf-8-sig')))
hdr = [h.strip() for h in rows[0]]
cols = {h: i for i, h in enumerate(hdr)}

def make(date, total, ground):
    r = [''] * len(hdr)
    r[cols['Date']] = date
    r[cols['Total Duration']] = total
    r[cols['Ground Instruction Duration']] = ground
    r[cols['Remarks']] = f"ff2gp probe {date} (delete me)"
    return r

out = [
    hdr,
    make('1999-01-01', '0.0', '2'),      # A: explicit decimal zero
    make('1999-01-02', '00:00', '2'),    # B: HH:MM zero
    make('1999-01-03', '2', '2'),        # C: ground hours mirrored into Total Duration
]
with open('test_ground_variants.csv', 'w', newline='', encoding='utf-8') as f:
    csv.writer(f).writerows(out)
print("wrote test_ground_variants.csv with 3 probe rows")
