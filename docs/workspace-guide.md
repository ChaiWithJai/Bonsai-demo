# Work with your files in Bonsai Workspace

Open the Workspace tab in the running Bonsai demo. The local development instance uses `http://127.0.0.1:5257/#/workspace`. Start with a question and attach the files that contain the evidence. Saved projects remain available when you return.

## From files to a view

1. Attach up to 20 files, each at most 25 MiB. Inspect the extracted records and the coverage notice. Originals remain available for download. An upload is not proof that extraction succeeded.
2. Explain what you want to understand. Choose **Understand these files**. Bonsai proposes records, cites source passages, explains uncertainty, and suggests a view. Review its findings and field types.
3. Use **Discuss this change** to correct the interpretation or request another view. Use **Yes, build this view** only when the proposed direction fits. Confirmation starts the build; it does not label the findings as correct.
4. Explore the saved interface. Search records, inspect supporting passages, and save evidence notes. Ask for a focused change to edit the existing project. Open **Expected results** to add a heading, button, input label, or record count that the result must contain. Review these checks before sending. The conversation retains the checks after submission and reload. The harness preserves revisions and records model calls, tool results, build errors, browser checks, and loop failures in MLflow.

Charts use Semiotic. A record table is available when a chart would add little information. A table can show selected overview columns while retaining all fields in record details. Grouped nodes currently represent explicit source field values, not learned similarity clusters.

## Review and compare

Use the Evidence tab to review the current saved interface. Enter a reviewer name, choose the review origin, accept the revision or mark it as needing changes, and explain the judgment. Reviewer identity is self-declared locally. A new revision needs its own review.

Export interface reviews to MLflow to preserve the review history and eligible examples. Only the latest human-declared acceptance of the current revision contributes an interface example. Test reviews, Codex reviews, rejections, and unreviewed outputs are excluded. Accepted source-backed examples include the saved files, original source evidence, proposal, and available attempt summaries. Exports have a dataset hash. No weight training runs during review or export.

Record-level extraction corrections have a separate review and export control in the Data panel. Applying those corrections creates a working copy rather than overwriting the original extraction.

Choose two finished attempts in the Evidence tab to compare their outcomes and recorded model, runtime, harness, and sampling configuration. Missing task or model-input hashes prevent a matched-input claim. The comparison is descriptive: cache state, conversation history, and development-example reuse can affect results. A passed browser check does not establish factual correctness or good design. The completion message distinguishes baseline checks from supplied request checks. Baseline checks preserve data and core interactions; they do not prove every requested change was made.

## What intake reads

| Input | Extracted content | Limits to review |
| --- | --- | --- |
| CSV, TSV, JSON arrays, JSONL | Records and supplied fields | Text must be UTF-8; field types still need review |
| Text and Markdown | Nonempty lines | Structure and relationships are model proposals |
| PDF | Page text, with local OCR fallback where needed | Inspect page coverage and OCR results |
| Word `.docx` | Body paragraphs and table cells | Embedded media, headers, footers, notes, comments, text boxes, and tracked-change interpretation are not extracted |
| EML and MBOX | Message headers and bodies | Attachments are listed, not read |
| Images | Local OCR; optional Bonsai visual extraction | Extracted values remain unreviewed |
| Audio | Local English Whisper transcription with segment times | No speaker identification; transcription errors remain possible |
| Video | Bonsai extraction from sampled frames | Unsampled frames and audio are not read by visual extraction |

Media processing is bounded. Check the coverage notice for the actual file rather than assuming the whole source was examined. Audio and video adapters currently limit duration to five minutes. Audio transcription uses a separate local speech model; it is not evidence of native Bonsai audio understanding.

Spreadsheet workbooks, arbitrary URLs, connected inboxes, and every desktop file format are not yet supported. Export a supported format where appropriate. Current verification uses development fixtures, including synthetic audio, and does not establish quality across natural meetings or arbitrary documents.

## Browser checks for harness experiments

The edit API accepts optional `request_checks` alongside `request` and `base_revision`. Each check targets an exact accessible role and name, or a test ID, and performs one action: `visible`, `text`, `count`, or `click`. The checks run in order at desktop and mobile widths. They contain no executable code. At least one assertion is required. The caller fixes the checks before the attempt; Bonsai can read them but cannot change them through its tools.

A failed request check returns diagnostics to the same bounded repair loop and prevents a completed attempt. MLflow stores the contract, its hash, screenshots, and results. Configuration comparisons include the contract hash. With no supplied checks, the attempt explicitly records `request_verification: not_assessed`. Passing supplied checks proves only those assertions, not complete understanding of a free-text request.

The conversational composer exposes visible headings, buttons, inputs, and record counts through **Expected results**. Incomplete checks prevent submission, and a failed submission preserves the draft. API callers can also supply ordered click and text assertions. The composer does not yet propose checks automatically from an arbitrary request. Human review remains necessary for interpretation, design quality, and requirements outside the supplied checks.
