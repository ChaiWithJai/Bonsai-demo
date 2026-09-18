# Pelican SVG comparison

The default Bonsai versus Qwen task uses Simon Willison's prompt:

> Generate an SVG of a pelican riding a bicycle

Source: https://github.com/simonw/pelican-bicycle

Both locally served models receive the exact same prompt and request settings,
without browser tools or project context. The default output budget is 4,096 tokens
so a drawing is not limited by the earlier short text-demo budget. The UI retains
sequential/concurrent execution controls and records settings, original output,
runtime metrics, and each model's checkpoint identity in MLflow.

Each panel renders a complete, validated SVG as an isolated image and offers a
download. Original model output remains available in the source disclosure and
trace. Malformed, incomplete, or active/external SVG content is not rendered; the
reason is displayed. No missing geometry or closing tags are fabricated.

Judge the drawings visually: recognizable pelican, coherent bicycle, rider/bicycle
relationship, and composition. Syntax validation is not a quality score and timing
alone does not select a winner. Instrumented replay remains a separately recorded,
bounded execution associated with each inference, not historical activations.
