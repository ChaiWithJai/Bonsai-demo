# Head-to-Head Comparisons

The `/comparison` route runs the same bounded task against two configured local
OpenAI-compatible llama-server origins. Defaults are Bonsai on
`http://127.0.0.1:8081` and a Qwen control on `http://127.0.0.1:8082`.

Before generation, the comparison API verifies both servers, renders each exact
chat template, tokenizes both prompts, and refuses prompts that exceed the shared
context budget. Runs are sequential by default so a single GPU is not forced to
serve two 27B models at once.

The grant-research task allows browser tools through isolated BrowserOS MCP
sessions. It rejects private URLs, records tool evidence, audits citations against
retrieved public text, and bounds repair attempts.

These comparisons are demonstrations, not benchmarks. Cache state, quantization,
prompt templates, and system load all affect timings. Use the `timings` object in
each response for local evidence on your hardware.
