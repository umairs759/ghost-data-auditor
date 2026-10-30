import csv
import sys
csv.field_size_limit(100000000)

sys.path.insert(0, '.')

# Check if case_001 exists in output.csv
with open(r'C:\Users\usamah\Desktop\Hackerrank_hackathon\output.csv', newline='', errors='replace') as f:
    reader = csv.DictReader(f)
    found = False
    for row in reader:
        if row['case_id'] == 'case_001':
            print(f'Found case_001 in output.csv: {row}')
            found = True
            break
    if not found:
        print('case_001 not found in output.csv')

# Check if case_001 exists in deletion_requests.csv
with open(r'C:\Users\usamah\Desktop\Hackerrank_hackathon\dataset\deletion_requests.csv', newline='', errors='replace') as f:
    reader = csv.DictReader(f)
    found = False
    for row in reader:
        if row['case_id'] == 'case_001':
            print(f'Found case_001 in deletion_requests.csv: {row}')
            found = True
            break
    if not found:
        print('case_001 not found in deletion_requests.csv')