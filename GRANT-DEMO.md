# Grant Research Demo

The grant workflow demonstrates model-owned browser research rather than a canned
answer. Each model receives the same prompt and optional project context, may call
the configured BrowserOS MCP tools, and must cite public evidence retrieved during
the run.

The implementation keeps separate MCP sessions per model, retains raw evidence in
local artifacts, rejects private or local target pages for research, and performs a
bounded citation audit. If the audit finds unsupported claims, the model gets a
bounded repair turn with the audit findings included.

Use this mode only with public web pages unless you intentionally keep the entire
recording directory private. Browser text, screenshots, rendered prompts, and model
outputs can contain sensitive information.
