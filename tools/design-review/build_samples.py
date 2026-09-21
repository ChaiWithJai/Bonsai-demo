import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(BASE, "shots")

META = {
    "28-revised-workstream": ("workstreams", "Bonsai applies a proposal correction and builds the preserved evidence"),
    "26-role-composer": ("workstreams", "Role-based composer with tabs and explicit attachment requirement"),
    "27-role-attached-message": ("workstreams", "Attached draft persists across tabs and rejected submission"),
    "25-workstream-history": ("workstreams", "Original request and planning conversation remain beside the view"),
    "23-workstreams-start": ("workstreams", "Start a conversation with files and a question"),
    "24-workstreams-conversation": ("workstreams", "Continue a workstream beside its generated view"),
    "22-proposal-source-links": ("workspace", "Inspect original source passages before confirming structured records"),
    '21-retained-upload-failure': ('workspace', 'Failed extraction retains its original file and offers explicit retry'),
    '20-workbook-intake': ('workspace', 'Workbook cell locations, hidden-sheet coverage and missing formula caches'),
    '18-expected-results': ('workspace', 'Review expected results before sending an edit'),
    '19-live-expected-results': ('workspace', 'Fixed expected results remain in the conversation after reload'),
    '17-request-verification': ('workspace', 'Request checks and baseline verification have distinct completion messages'),
    '16-readable-records': ('workspace', 'Mixed source records with readable values, raw data and selected evidence notes'),
    '01-workspace-preview': ('workspace', 'Existing source explorer inside the Bonsai Workspace'),
    '02-workspace-source': ('workspace', 'Saved project source'),
    '03-workspace-evidence': ('workspace', 'Attempt evidence and trace entrypoint'),
    '04-workspace-data': ('workspace', 'Uploaded source and persisted automated review'),
}

files = os.listdir(SHOTS)
samples = []
for i, (slug, (flow, desc)) in enumerate(sorted(META.items())):
    desktop = f"{slug}.desktop.png"
    mobile = f"{slug}.mobile.png"
    if desktop not in files and mobile not in files:
        continue
    samples.append({
        "id": slug,
        "order": i,
        "flow": flow,
        "title": desc,
        "desktop": f"shots/{desktop}" if desktop in files else None,
        "mobile": f"shots/{mobile}" if mobile in files else None,
    })

with open(os.path.join(BASE, "samples.json"), "w", encoding="utf-8") as f:
    json.dump(samples, f, indent=1)
print(f"{len(samples)} samples")
