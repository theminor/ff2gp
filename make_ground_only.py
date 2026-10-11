import csv

rows = list(csv.reader(open('garmin_import.csv', encoding='utf-8')))
hdr = rows[0]
cols = {h: i for i, h in enumerate(hdr)}
# only pure ground rows (no aircraft); rows that mix ground time into a real
# flight already import normally with the flight batch
ground = [r for r in rows[1:]
          if r[cols['Ground Instruction Duration']] and not r[cols['Aircraft ID']]]
with open('garmin_import_ground_only.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(hdr)
    w.writerows(ground)
print("ground rows:", len(ground))
for r in ground:
    print(r[cols['Date']], "| Total:", repr(r[cols['Total Duration']]),
          "| Ground:", r[cols['Ground Instruction Duration']],
          "| Remarks:", r[cols['Remarks']][:40])
