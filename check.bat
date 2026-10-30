@echo off
python -c "
import re
content = open('output.csv').read()
statuses = {}
for m in re.finditer(r'\"(COMPLETE|INCOMPLETE|NOT_APPLICABLE)\"', content):
    s = m.group(1)
    statuses[s] = statuses.get(s, 0) + 1
print('Status counts:', statuses)
empty_count = content.count('\"steps_json\": []')
print('Empty steps_json: [] count:', empty_count)
deletation_count = content.count('\"DELETATION\"')
print('DELETATION count:', deletation_count)
"