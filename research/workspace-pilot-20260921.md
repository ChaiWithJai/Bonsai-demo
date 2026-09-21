# Workspace development pilot, September 21, 2026

The experiment moves incremental UI editing into the personal Bonsai demo fork.
The frozen desktop prototype and its earlier scores remain unchanged. The task
starts with its existing 14-record source explorer, rather than a blank project.

## Protocol

The model is the previously verified Bonsai 2 27B PQ2_0 checkpoint, revision
`6ed5e12bf84b7a63069882c91dd9e9218647d17b`, served by Prism runtime
`prism-b10709-9a9394a`. One owned Mac server stays loaded across requests and user
turns under the shared GPU queue. The GB10 preview server is preserved.

W1 adds runtime drilldown beneath parameter-size groups. W2 filters existing
saved notes to the selected source while retaining W1 and persistence. Authored
browser checks inspect exact source membership, values, links, note snapshots,
reload behavior, and mobile overflow. They are development checks, not held-out
quality judgments. Automated notes carry an explicit automated origin.

## Observed failures and changes

1. Run `2486ca6033f54889b02c9de565203048` timed out before applying a patch.
   The transport omitted the earlier harness's per-request
   `chat_template_kwargs.enable_thinking=false`. The raw response contains
   generated reasoning text. The server flag alone did not produce the intended
   request behavior. Provider v2 restored that explicit setting and also recorded
   seed 42 and enabled prompt caching. These settings changed together, so this
   is not an isolated causal measurement of the thinking option.
2. Run `b19ec999a7ac4733857707a083327e63` completed W1 in 87.97 seconds.
   The model mixed old and new Svelte event syntax, received the compiler error,
   patched the syntax, and passed the build and browser checks. The failed build
   remains in the complete attempt artifact.
3. Run `d0fe1c0fdbcf4282a2c3734b6089cfd7` did not complete W2. The browser found
   that the prior record's note remained visible after selection changed. The
   model's repair introduced an unmatched template closing tag. The eight-call
   budget expired after another read. The failed source revision and last good
   preview are preserved separately.

The next harness revision runs preview and browser checks automatically after a
successful build. It returns those diagnostics in the build result while keeping
separate tool spans. The eight-model-call and two-repair limits remain unchanged.
It also carries failed-attempt conversation context forward and fills missing
interrupted tool results with explicit failure records. A fresh W1/W2 trial is
in progress. No completed two-turn result is claimed yet.

## What the evidence supports

Saved revisions and exact-match patches let the model extend an existing project.
Compiler and browser failures provide different feedback. A successful compile
did not prove note-filter behavior. Tool granularity consumed model calls that
could otherwise support repair. Generated reasoning text, complete attempt
traces, and activation traces are distinct evidence. Workspace does not schedule
activation replay between model calls.

The native UI has a conversation panel, source, preview, and evidence views.
Browser reload resumes saved events and never submits a request. The complete
attempt trace links recording-proxy exchange IDs. Distributed trace parentage is
not claimed.

## Remaining scope

The native Workspace still needs the frozen prototype's file intake,
classification review, multimodal adapters, Semiotic view generation, and reviewed
training-candidate export connected to this incremental project workflow. The
harness comparisons in research plan revision 3 remain the basis for the final
postmortem. The pilot does not establish general coding quality or media accuracy.
