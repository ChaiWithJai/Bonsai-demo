import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(BASE, "shots")

META = {
    "49-model-family-graph": ("workstreams", "Constrained model-family graph with categorical membership and source links"),
    "48-three-stage-video": ("workstreams", "Generated three-stage records with timestamped source video inspection"),
    "47-workstream-sidebar": ("workstreams", "Compact roles and conversations with searchable saved views and file activity"),
    "46-video-timestamp": ("workstreams", "Speech from video retains video playback at a nonzero timestamp"),
    "46-audio-timestamp": ("workstreams", "Standalone audio seeks to a cited transcript timestamp"),
    "45-inline-source-media": ("workstreams", "Selected video evidence plays beside record notes"),
    "44-finding-evidence": ("workstreams", "Readable per-source finding evidence and targeted correction draft"),
    "43-dropped-files": ("workstreams", "Dropped development file with extraction count and retained first message"),
    "42-first-message": ("workstreams", "Role-based first message with adjacent composer and persistent section navigation"),
    "41-video-evidence-graph": ("workstreams", "Corrected narrated-video evidence groups with original values, citations and notes"),
    "40-video-speech": ("workstreams", "Separate visual observations and timestamped speech from one development video"),
    "39-selection-checks": ("workstreams", "Ordered click and selection expectations retained after an intercepted development request"),
    "38-recovered-workstream": ("workstreams", "Persisted conversation and attached proposal reopened without browser draft storage"),
    "36-intake-conversation": ("workstreams", "Real Bonsai reply before attachment, restored from saved development conversation"),
    "37-intake-handoff": ("workstreams", "Development CSV proposal preserves prior conversation and waits for confirmation"),
    "35-workstream-composer": ("workstreams", "Role cards, separate tools, conversation tabs and focused message composer"),
    "34-proposal-review": ("workstreams", "Development interpretation judgment excluded from human example export"),
    "33-comparison-context": ("workstreams", "Historical comparison with display-only missing-configuration disclosure"),
    "32-node-zoom": ("workstreams", "Zoomed Semiotic nodes retain source membership and full labels"),
    "31-date-exploration": ("workstreams", "Synthetic release records filtered by parameter node and inclusive dates"),
    "30-generated-coverage": ("workstreams", "Isolated generated-view disclosure with explicit omitted-file warning"),
    "29-proposal-coverage": ("workstreams", "Display-only scenario showing an attachment omitted from model context"),
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
