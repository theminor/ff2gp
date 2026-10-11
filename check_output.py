import csv

rows = list(csv.reader(open('garmin_import.csv', encoding='utf-8')))
hdr = rows[0]
cols = {h: i for i, h in enumerate(hdr)}

def show(r, keys):
    print({k: r[cols[k]] for k in keys if r[cols[k]]})

print("=== row with approaches + circle + passengers ===")
for r in rows[1:]:
    if 'Circled' in r[cols['Remarks']] or (r[cols['Approaches']] and 'Passengers' in r[cols['Remarks']]):
        show(r, ['Date','Aircraft ID','Aircraft Type','Approaches','Remarks','Instructor Name'])
        break

print("\n=== ILS OR LOC row ===")
for r in rows[1:]:
    if "'ILS'" in r[cols['Approaches']]:
        show(r, ['Date','Approaches','Remarks'])

print("\n=== VOR-A row ===")
for r in rows[1:]:
    if 'VOR' in r[cols['Approaches']]:
        show(r, ['Date','Approaches'])

print("\n=== ground training row ===")
for r in rows[1:]:
    if not r[cols['Aircraft ID']]:
        show(r, ['Date','Aircraft ID','Aircraft Type','Ground Instruction Duration','Remarks','Departure','Destination'])
        break

print("\n=== endorsement rows ===")
for r in rows[1:]:
    if 'Checkride' in r[cols['Remarks']] or 'Flight Review' in r[cols['Remarks']]:
        show(r, ['Date','Aircraft ID','Aircraft Type','Remarks'])

print("\n=== mismatch row 2026-05-10 ===")
for r in rows[1:]:
    if r[cols['Date']] == '2026-05-10':
        show(r, ['Date','Day Takeoffs','Day Landings','Total Duration'])

print("\n=== 2022 student row (manual counts fallback) ===")
for r in rows[1:]:
    if r[cols['Date']] == '2022-08-05' and 'First Solo' in r[cols['Remarks']]:
        show(r, ['Date','Aircraft ID','Aircraft Type','Day Takeoffs','Day Landings','Dual Received Duration','Remarks','Instructor Name'])

print("\n=== rows with Total Duration but no Aircraft Type ===")
bad = [r[cols['Date']] for r in rows[1:] if r[cols['Total Duration']] and not r[cols['Aircraft Type']]]
print(bad)

print("\n=== multi-approach row ===")
n = 0
for r in rows[1:]:
    if r[cols['Approaches']].count('(') > 1 and n < 3:
        n += 1
        show(r, ['Date','Approaches'])

print("\n=== partial-panel note row ===")
for r in rows[1:]:
    if 'partial panel' in r[cols['Remarks']]:
        show(r, ['Date','Approaches','Remarks'])
        break

print("\nrow count:", len(rows) - 1)
