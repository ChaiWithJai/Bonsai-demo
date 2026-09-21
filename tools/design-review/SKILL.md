---
name: design-review
description: Run the A+ design-review tooling from ChaiWithJai/aplus-video at commit 1467d3cfa8588f84be903d36c501ec5951fbe1cb. Use when reviewing the A+ production site with screenshot capture, annotation, journey, progress, and failure-mode workflows.
---

# A+ Design Review

This skill contains the local A+ design-review tool from `ChaiWithJai/aplus-video` pinned to commit `1467d3cfa8588f84be903d36c501ec5951fbe1cb`.

## Use

- Read `README.md` before running the tool.
- From the original A+ repository root, prefer the repository scripts when available:

```sh
npm run review
```

- The underlying workflow is:

```sh
npm run review:capture
npm run review:build
npm run review:serve
```

- The review server is `app.py` and listens on `http://localhost:8377`.
- `capture/capture.spec.ts` captures review surfaces.
- `build_samples.py` creates `samples.json` from `shots/`.
- `index.html` is the annotation UI.

## Notes

Generated review state is local and should not be committed unless explicitly requested: `shots/`, `samples.json`, `annotations.json`, `patterns.json`, and `suggestions.json`.
