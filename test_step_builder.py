import sys
sys.path.insert(0, r'C:\Users\usamah\Desktop\Hackerrank_hackathon')
from core.step_builder import build_steps_json

# Test building steps for a COMPLETE case
findings = [
    {'operation': 'REPORT_REMAINING_RECORD', 'system_id': 'account_service', 'resource_id': 'rec_001'},
    {'operation': 'REPORT_EXPOSED_PII', 'system_id': 'account_service', 'resource_id': 'rec_001'},
]
remediations = [
    {'operation': 'DISABLE_DATA_FLOW', 'system_id': 'account_service', 'resource_id': 'rec_001'},
    {'operation': 'BLOCK_RESTORE', 'system_id': 'account_service', 'resource_id': 'rec_001'},
]
verifications = [
    {'operation': 'VERIFY_RECORD_ABSENT', 'system_id': 'account_service', 'resource_id': 'rec_001'},
]

steps = build_steps_json(
    case_id='case_01',
    deletion_status='COMPLETE',
    findings=findings,
    remediations=remediations,
    verifications=verifications,
    evidence_id='evidence_01'
)

print('Step builder test (COMPLETE):')
for step in steps:
    print(f"  step_no={step['step_no']}, phase={step['phase']}, operation={step['operation']}, system_id={step['system_id']}, resource_id={step['resource_id']}, state={step['state']}, evidence_id={step['evidence_id']}")

# Test NOT_APPLICABLE
steps_nap = build_steps_json(
    case_id='case_02',
    deletion_status='NOT_APPLICABLE',
    findings=[],
    remediations=[],
    verifications=[],
    evidence_id=''
)
print(f"\nNOT_APPLICABLE steps: {steps_nap} (should be empty list)")

# Test INCOMPLETE
steps_inc = build_steps_json(
    case_id='case_03',
    deletion_status='INCOMPLETE',
    findings=[
        {'operation': 'REPORT_REMAINING_RECORD', 'system_id': 'account_service', 'resource_id': 'rec_002'}
    ],
    remediations=[
        {'operation': 'DISABLE_DATA_FLOW', 'system_id': 'account_service', 'resource_id': 'rec_002', 'evidence_id': ''}
    ],
    verifications=[
        {'operation': 'VERIFY_RECORD_PRESENT', 'system_id': 'account_service', 'resource_id': 'rec_002', 'evidence_id': ''}
    ]
)
print(f"\nINCOMPLETE steps count: {len(steps_inc)}")
for step in steps_inc[:3]:
    print(f"  step_no={step['step_no']}, phase={step['phase']}, operation={step['operation']}")