import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(BASE, "shots")

META = {
    "76-presentation-coverage": ("workspace", "PowerPoint upload with slide citations and explicit unread coverage"),
    "75-embedded-workstream-exploration": ("workspace", "Embedded preview search, source passages, and return through workspace tabs"),
    "74-recorded-model-configuration": ("workspace", "Saved result configuration remains independent of composer choices"),
    "73-source-model-settings": ("workspace", "Proposal profile persists with attached-file draft"),
    "72-editor-model-settings": ("workspace", "Per-edit model configuration with server-default fallback"),
    "71-discussion-and-verification-notes": ("workspace", "Discussion notes stay visible while automated verification notes are collapsed"),
    "70-proposed-chart-preview": ("workspace", "Inspect a proposed chart before confirming a build"),
    '68-record-retention-draft': ('workspace', 'Explicit retention requirement persists in draft and can be cleared'),
    '69-record-retention-proposal': ('workspace', 'Saved proposal displays frozen retention requirement'),
    '67-structured-source-coverage': ('workspace', 'Data citation coverage reveals omitted email and drafts a correction without sending'),
    '66-proposal-page-scope': ('workspace', 'Scope coverage fixture distinguishes selected records from records outside the request'),
    '65-page-scoped-draft': ('workspace', 'Explicit PDF page scope persists in the draft and can be cleared before sending'),
    '64-recovered-proposal': ('workspace', 'Saved response revalidation restores a proposal for review without model calls or build confirmation'),
    '63-wide-timing-table': ('workspace', 'Eight-field saved timing proposal tested in an intercepted development preview'),
    '62-pdf-visual-observation': ('workspace', 'Selected PDF page observations stay separate from OCR and marked unreviewed'),
    '61-original-pdf-page': ('workspace', 'Original PDF page rendered on demand beside searchable extracted text'),
    '60-source-content-search': ('workspace', 'Read-only PDF content search finds a later-page measurement with its original record position'),
    '59-source-pagination': ('workspace', 'Development fixture: source inspection reaches the final records and returns to earlier pages'),
    '58-pdf-refresh': ('workspace', 'Development failure fixture: explicit PDF refresh keeps previous extraction available'),
    '57-requested-page-coverage': ('workspace', 'Development fixture: requested pages shown, omitted and not found; follow-up remains a draft'),
    "56-proposal-view-choice": ("workstreams", "Draft a different visualization choice before submitting a revision"),
    "55-email-thread": ("workstreams", "Corrected email timeline with per-message citations and original mailbox download"),
    "54-timeline-inspection": ("workstreams", "Clickable timeline observations with selected-record note drafts"),
    "53-dated-series": ("workstreams", "Two dated series with zero values, full chart and inspectable records"),
    "52-saved-build-retry": ("workstreams", "Browser fixture: retry a failed build with a saved project"),
    "51-scanned-pdf-record": ("workstreams", "Scanned PDF structured into a project record with page evidence"),
    "50-record-title": ("workstreams", "Source-derived model title and matching selected-note context"),
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
