import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(BASE, "shots")

META = {
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
