import csv

rows = list(csv.reader(open('garmin_import_ground_only.csv')))
cols = {h: i for i, h in enumerate(rows[0])}
print("header Total Duration index:", cols['Total Duration'])
for r in rows[1:]:
    print(r[0],
          "Total:", repr(r[cols['Total Duration']]),
          "Ground:", repr(r[cols['Ground Instruction Duration']]),
          "Aircraft ID:", repr(r[cols['Aircraft ID']]),
          "Aircraft Type:", repr(r[cols['Aircraft Type']]),
          "Departure:", repr(r[cols['Departure']]),
          "Destination:", repr(r[cols['Destination']]))
