# Native source workflow checkpoint

Workspace on port 5257 now accepts a source, asks Bonsai for field types and a
Semiotic plan, validates every record, renders the component, and saves an editable
Svelte project. The initial Svelte layout is authored. Bonsai authors the plan and
subsequent code edits. This is a development workflow, not a reliability result.

The source job has two model calls at most. It shares the model reservation with
project edits, preserves failures, and records source bytes, model requests,
responses, validation, rendering, builds, and browser checks in MLflow.

## Observed result

The cached observation file produced a valid parameter-size/runtime graph. The
first browser check failed because an authored select did not have the exact
accessible name expected by the checker. The original failed job remains intact.
Bonsai then applied a focused aria-label edit to the saved project, and the build,
source fidelity, search, group filtering, and note persistence checks passed.
The scaffold is corrected for future projects. A subsequent check also exercises
clicking a graph node to filter its source records.

- Initial source run: 98066c12b7934bf5b5bd1ffe392f9348, failed browser check.
- Incremental edit run: 931072e07eb54637aa6c454001672a45, completed.
- Saved project: 86eb473d0e90458b8c60374947f68665.
- Current revision: 3e1da824c6aa8bc4e5f3eb7f9fb6f0f8c12ed6f378c634a16f79b366786ce4fc.

## PDF correction

The user reported an empty result for S82065.pdf, SHA256
2ab8e898b0f0208138af7e71629e05925b333afe8d13e49953bfad6dfbc1cb93.
The native intake registered PDFs but did not call any extractor. This routing
failure is fixed: PDF uploads now extract embedded text into page-bound records.
An explicit extraction action repairs previously registered PDFs without replacing
the original bytes or losing the previous manifest. Image-only pages use Apple
Vision OCR on this Mac. This fallback is not Bonsai inference.

The reported document contains 79 pages. All 79 yielded embedded text. The original
hash is unchanged. An isolated fresh upload also extracted 79 records automatically.
Desktop and mobile browser checks verify the actual uploaded file, page coverage,
page locators, and title text. OCR independently recovered the title from a rendered
page image. Mixed text/OCR routing and explicit extraction failure are unit-tested.

- User source extraction run: ad4e747d5f33402da65e2a57367d8db4.
- Fresh upload extraction run: c138ab674cea4060950ab3e99bcecdd3.
- 151 Python tests passed. Svelte check and autofixer report no issues. Build passes.

## Incomplete work

PDF diagrams, charts, and tables are not semantically interpreted. Embedded text
on a page does not prove that text inside its images was captured. The coverage
report states this. PDF page text is unreviewed. Text extraction is not semantic
classification. Native image, audio, and video extraction still need connecting.

Field typing is implemented, but semantic record classification and learned
clustering are not yet connected in this native flow. Supplied field groups are
labeled as groups rather than inferred clusters. Model edit reliability remains
unproven; prior W2 failures remain in the diagnosis report. The full goal remains
active.
