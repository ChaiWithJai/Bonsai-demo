# Five Bonsai workflow guides

Use [ChaiWithJai/Bonsai-demo](https://github.com/ChaiWithJai/Bonsai-demo) to work from source documents, check a result, and inspect a recorded failure. The guides accompany five edited English demo cuts recorded on September 23, 2026.

| Guide | Task | Companion cut |
| --- | --- | ---: |
| [A bond price starts with the payment schedule](https://gist.github.com/ChaiWithJai/0b8ebfa9f97faa97b7138a20b2cca9ee) | Confirm worksheet inputs and inspect repricing. | 70.6 seconds |
| [The same company has two leverage ratios](https://gist.github.com/ChaiWithJai/f66f84aab4141232083afab7254cfa38) | Compare management and lender definitions. | 85.4 seconds |
| [A contract summary loses the conditions that change the answer](https://gist.github.com/ChaiWithJai/c1c134d1448948fa379b1d62beffce9f) | Preserve exceptions, deadlines, and conditions. | 48.1 seconds |
| [The ratio was correct. The dollar amount was wrong.](https://gist.github.com/ChaiWithJai/ae3046a50213aba9903838256cbec6a8) | Recalculate a wrong amount and inspect its trace. | 65.8 seconds |
| [One termination clause cannot establish every termination right](https://gist.github.com/ChaiWithJai/79df3593a0744961cb49967df56bdb6b) | Bound a conclusion to the supplied evidence. | 52.8 seconds |

Read the financial review before its error guide, or the legal review before its error guide. The bond guide stands alone.

The [editorial review](EDITORIAL-REVIEW.md) records the writing references, changes, and verification scope.

## Run the recording UI

The guides target source revision `bf425c5c4195ac061dddd4e4b31f510366b6f0a6` of the personal fork. Start a fresh checkout with:

```bash
git clone https://github.com/ChaiWithJai/Bonsai-demo.git
cd Bonsai-demo
git checkout bf425c5c4195ac061dddd4e4b31f510366b6f0a6
```

Follow the [model setup](https://github.com/ChaiWithJai/Bonsai-demo/blob/bf425c5c4195ac061dddd4e4b31f510366b6f0a6/README.md#quick-start) in that checkout, then build the branded UI using [Native UI setup](https://github.com/ChaiWithJai/Bonsai-demo/blob/bf425c5c4195ac061dddd4e4b31f510366b6f0a6/NATIVE-UI-WORKFLOW.md#build-the-ui). The builder requires a compatible llama.cpp UI source tree with its Node dependencies installed; setup's prebuilt model server alone is insufficient. Use the matching Prism runtime for Bonsai 2 weights.

The recording dependencies require Python 3.11 or 3.12. Create the environment and storage directory:

```bash
python3 -m venv .venv-recording
. .venv-recording/bin/activate
python -m pip install -e '.[recording]'
mkdir -p .cache/bonsai
```

With the local model already serving on port 8080, start MLflow in one terminal:

```bash
. .venv-recording/bin/activate
mlflow ui --backend-store-uri "sqlite:///$PWD/.cache/bonsai/mlflow.db" \
  --host 127.0.0.1 --port 5210
```

The bond tool backend requires a release manifest that matches the loaded model. After setup has created `models/bonsai2-gguf/27B/.cache/bonsai/manifest.json`, run the following in another terminal. It checks the loaded model against that download manifest and hashes the file again. It stops on a missing path or mismatch.

```bash
. .venv-recording/bin/activate
python3 - <<'PY'
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

download = json.loads(Path(
    'models/bonsai2-gguf/27B/.cache/bonsai/manifest.json'
).read_text())
with urlopen('http://127.0.0.1:8080/props', timeout=5) as response:
    loaded = Path(json.load(response)['model_path']).resolve(strict=True)
entry = next(item for item in download['files']
             if Path(item['source']).resolve() == loaded)
if entry['algorithm'] != 'sha256':
    raise ValueError('Expected a SHA-256 model entry')
with loaded.open('rb') as stream:
    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
if digest != entry['digest']:
    raise ValueError('Loaded model hash differs from download manifest')
release = {'checkpoint': {
    'repo': download['repo'], 'revision': download['revision'],
    'files': [{'path': str(loaded), 'sha256': digest, 'verified': True}]
}}
Path('.cache/bonsai/release-manifest.json').write_text(
    json.dumps(release, indent=2) + '\n'
)
PY
```

Use the manifest from the model directory you actually installed if its location differs. Hashing establishes file identity; it does not certify output quality. The example assumes the model server and recording UI share a filesystem.

Start the recording UI in that terminal:

```bash
. .venv-recording/bin/activate
python3 scripts/recording_ui.py \
  --port 5257 \
  --upstream http://127.0.0.1:8080 \
  --static-dir .cache/bonsai/prism-ui/dist \
  --tracking-uri http://127.0.0.1:5210 \
  --records-dir .cache/bonsai/native-ui-records \
  --release-manifest .cache/bonsai/release-manifest.json \
  --workspace-dir .cache/bonsai/workflow-data
```

Open `http://127.0.0.1:5257/#/` and use **New chat**. The `--workspace-dir` flag enables persistent backend services used by the tools; it does not require using the Workstreams tab. If a service already occupies one of these ports, reuse it or choose a free port and update the command. Do not start a duplicate model server.

The setup commands are checked against the documented interfaces and source revision. A fresh installation was not rerun for this documentation release. The optional [replay setup](https://github.com/ChaiWithJai/Bonsai-demo/blob/bf425c5c4195ac061dddd4e4b31f510366b6f0a6/NATIVE-UI-WORKFLOW.md#optional-replay-setup) needs additional runtime and capture configuration. The automatic capture path has platform limits; the recorded macOS teacher-forced diagnostics used a separate instrumented procedure.

## Understand the evidence

The input documents are synthetic fixtures. The guides distinguish model output, independent arithmetic, proposed corrections, and later diagnostic captures. A new model run need not repeat the recorded wording or failure.

Each guide includes a frame from its edited cut and a screenshot of the recorded app. Crops, comparison graphics, held frames, and editorial trims are part of the cuts. Video duration is not a performance measurement. The [media manifest](media-evidence.json) records file hashes and screenshot timestamps. The MP4s remain companion files; these pages do not provide public video downloads.

The recorded examples used local Bonsai inference. No Gateway key is needed for the documented prompts. No new model inference or speech generation was used to prepare these guides.

The public repository contains fixtures, selected evidence summaries, and screenshots. It does not contain the author's local chat database, raw recording store, or MLflow database. Local trace IDs in historical records are identifiers, not public trace links.

## Documentation review

The writing follows the user-centered approach described in the Linux Foundation's [Secrets of Writing Good Documentation](https://www.linuxfoundation.org/blog/blog/secrets-writing-good-documentation): state prerequisites, give ordered actions, and verify the result from a reader's perspective. The guides are independent project documentation, not Linux Foundation publications or certifications.

Before publication, review each guide for an explicit task, available inputs, named controls, expected results, readable screenshots, working links, and evidence limits. Keep proposed repairs separate from observed behavior. Update the source revision and evidence when the workflow changes.
