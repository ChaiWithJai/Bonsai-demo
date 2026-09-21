# The job is collaborative interpretation, not file conversion

The user corrected the product direction on September 21. Success means bringing
files and a question into a conversation, structuring the data for that question,
reviewing the interpretation together, and then building an interactive view that
can be refined with evidence. File counts and a compiled preview do not establish
that outcome.

## The four steps and their acceptance criteria

1. Acquire raw sources from selected local files or requested fetches. Preserve
   originals and show format-specific extraction coverage. Documents, PDFs, message
   exports, and email are first-class sources, not empty media placeholders.
2. Produce a proposed structure for the user's actual question. Show concrete
   findings, proposed records, source passages, and uncertainty. Let the person
   correct the interpretation before confirming the view. Store those corrections
   as part of the conversation and source lineage.
3. Use Bonsai 2 27B in a generative UI harness to build the confirmed view. Support
   complex exploration, source links, record and relationship drilldown, and team
   annotation. Runtime actions and failures must be traceable for analysis and
   improvement; unreviewed model output is not a training label.
4. Keep the working project in the harness. Reuse its source and context for edits,
   verify the resulting interactions, preserve failed attempts, and deploy only a
   verified artifact. A model timeout or schema check is not task completion.

## What this revision establishes

The source composer accepts a question before file selection. Source jobs now
produce a persisted interpretation and proposed structure before any rendering.
The user can discuss a change or confirm the exact proposal version. Revision
requests preserve their parent proposal and feedback. Confirmation creates a
separate linked build trace and does not repeat inference.

Document and text proposals must provide explicit structured records. The harness
checks that cited passages occur in the original source fields (with whitespace
normalization), preserves source IDs and locations, and validates the chart against
those structured fields. This establishes traceability, not factual correctness of
an inferred relationship. The interface labels model-structured records unreviewed.

For the user's S82065.pdf, all 79 page-text records fit in the native 16K context
using short, reversible record references. The first interpretation described a
bottleneck/fix graph while planning raw page-field groups. It is retained as a
needs-revision proposal, not accepted. The revised contract and explicit developer
feedback produced five bottleneck/fix records with ten checked source passages and
an actual bottleneck → fix graph plan. It is waiting for the user's review. No
project has been built or human confirmation recorded for it.

## Evidence and limits

- Context preflight failure: job 06a7534ebdbb44fc92ac4432be1762e5. No inference ran.
- Page-field mismatch: job 1b39cadd016842f1a3513b8f1485d18c, run 1bf0be498e1844208643f4948afc0144.
- Two-minute structuring timeout: job 600d5a77f355457490285bdf256aeecd. Partial output was still writing distinct records, not repeating an action.
- Compact structured proposal: job 2cd051414c0b40839f6a5753e6adb44a, run 60fcaf5ae52f435cb1cb44ce96d8831b.
- The document planner now has a bounded 240-second call limit and two calls at most. Code-edit timeout settings are unchanged.
- 153 Python tests passed. Svelte checks/build and desktop/mobile proposal review checks passed. Browser review did not confirm the proposal.
- The source/PDF checkpoint through commit 2c46c4e has a verified full backup: 2026-09-21T173247748154+0000, restored 120713 files, SQLite integrity ok, verified 2026-09-21T17:43:50.391032+00:00. It predates this collaborative revision.

The entire goal is not complete. Multi-file sessions and fetch ingestion, native
email/message adapters, visual interpretation of document figures, image/audio/video
workflow integration, team identity and shared annotations, and promotion of
reviewed structured records into training datasets remain unfinished. The current
proposal is a working slice of the requested loop, not a claim of V0 parity.

## Long-source prompt coverage repair

A long single-field email could previously exceed the entire packet budget and be omitted, even though extraction succeeded. Source packet preparation now retains verbatim windows from long fields, with original character ranges and explicit partial-coverage reporting. Windows cover the beginning, end, and first question-keyword match. Question-relevant records are selected before the distributed fallback sample. Original records and citation identifiers remain unchanged.

This is bounded lexical selection, not semantic retrieval or full-document understanding. Other matches and omitted text are not read by the model. A limited packet still cannot establish exhaustive coverage. Three regression tests cover an oversized email, a relevant late record under a tight budget, and unchanged zero/null values in a small complete source. All 164 Python tests passed before a bounded performance refinement; the three packet tests also passed after that refinement. No new model-quality claim or human approval is recorded.
