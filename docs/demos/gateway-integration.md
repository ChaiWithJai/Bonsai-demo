# Gateway adapter

The Python harness can call `workspace_gateway.gateway_request` to invoke the pinned AI SDK in a child Node process. This adds no listening port. It preserves the local Bonsai provider and its tool loop.

The adapter currently has two operations:

| Operation | Model | Result |
| --- | --- | --- |
| `evaluate_evidence` | `typesafe-ai/jev` | Supported, conflicting, or insufficient classification, requiring review |
| `narrate` | `fish-audio/s2.1-pro-free` | Audio bytes encoded as base64, with language and voice identity |

Set `AI_GATEWAY_API_KEY` in the backend environment, or use Vercel OIDC authentication. Never place credentials in frontend environment variables or requests. Set `BONSAI_DOLLY_VOICE_ID` to the verified Dolly library ID before narration. No default voice is substituted. The six requested narration language codes are `zh`, `fa`, `pt`, `hi`, `kn`, and `fr`; accepting a language code does not verify voice quality or provider support.

Install dependencies with `npm ci --prefix scripts/workspace-tools`. The bridge uses `node` on the backend PATH. A static-only deployment cannot execute it; the Python backend needs a reachable service with Node installed. Gateway authentication occurs there.

Example Python call, using explicitly selected material for cloud evaluation:

```python
from workspace_gateway import gateway_request

result = gateway_request({
    'operation': 'evaluate_evidence',
    'claim': 'Payment has completed.',
    'evidence': 'The board proposed payment next month.',
})
```

Requests cannot choose another model or voice. Calls have no automatic retries and have a bounded timeout. Provider errors are redacted before returning to the harness. Source text remains untrusted evidence. The classifier does not approve a finding, execute tools, or replace a human decision.

Verification so far covers adapter routing, configuration failures, the actual installed SDK's request serialization and response parsing through a mocked HTTP transport, and the Python process boundary. No authenticated Gateway call, Dolly synthesis, or language listening review has completed. Workstream actions, persisted Gateway results, and MLflow linkage remain to be connected before this is a finished product integration.

Official contracts: [Jev integration](https://vercel.com/i/jev-integrations), [Fish Audio on Gateway](https://vercel.com/ai-gateway/models/s2.1-pro-free).
