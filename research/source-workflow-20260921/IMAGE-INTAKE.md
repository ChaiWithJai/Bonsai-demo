# Image text evidence

PNG, JPEG, and WebP uploads now run local Apple Vision OCR. Each recognized region becomes a source record with text, OCR confidence, and normalized bounding coordinates measured from the bottom left. The original bytes and OCR output are retained. Image records require model structuring before a visualization proposal can be accepted.

This is extraction, not Bonsai visual inference. Chart values, image semantics, and diagram relationships remain unsupported. Empty OCR and invalid regions fail explicitly. Originals survive failure and extraction can be retried. Confidence refers to text recognition, not truth.

The real first-page render from S82065.pdf produced six text regions containing the title Five Bottlenecks, Five Fixes. Original bytes matched after extraction. MLflow extraction run: e2a9568cefd04d56b9a36de7f11364f5, experiment 32. The browser upload was also exercised on desktop and mobile using the real page render, without starting model inference.

Validation: 161 Python tests passed with TMPDIR=/private/tmp, Svelte checks and autofixer reported no issues, production build passed, and two browser checks passed. The initial test invocation omitted the canonical temporary directory and failed four existing path-alias assertions; that output is retained. No model-quality claim follows from these intake checks.

The live PDF proposal remains awaiting user confirmation. The full backup initiated at the preceding collection checkpoint is still running and does not establish a verified backup of this later image change.
