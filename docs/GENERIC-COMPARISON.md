# Generic text comparison with official Qwen BF16

On the MacBook, use the existing SSH tunnel and open http://127.0.0.1:8088/.
The comparison sends the same prompt, optional shared context, and sampling
controls to Bonsai on server port 8081 and official Qwen on server port 8083.
Reuse healthy running services; do not launch duplicate servers.

Start Bonsai with `./scripts/start_released_demo.sh`. With the pinned official
Qwen/Qwen3.8-27B snapshot already in the local Hugging Face cache, start Qwen:

```sh
.venv/bin/python scripts/research/official_server.py --port 8083 --records /path/to/research-records
```

The Qwen endpoint uses CUDA BF16, offline cache lookup and shard verification.
It binds to loopback and needs sufficient GPU/unified memory for the full model.
The recording UI must read the same research-records directory. Its existing
8088 deployment supplies the comparison and observability pages; launching this
model endpoint does not start the recording UI or MLflow. Use the existing
research PyTorch/Transformers environment and MLflow logging environment.

The comparison runs sequentially, supports text only, and keeps thinking off.
Shared controls include temperature, top-p, top-k, min-p, seed, repetition penalty
and output limit. Tools and vision are unsupported by this Qwen endpoint. The
API requires verified official provenance and does not substitute port 8082's
quantized control.

Qwen captures selected decoder layers 0, 31 and 63 during the original inference,
including the final prefill position. Bonsai's separate 32-step instrumented
replay uses its recorded request; these are new replay activations, not original
answer activations. Observability checks request, output and checkpoint binding
before attaching Qwen's capture.

Timing includes instrumentation. BF16 Transformers and native packed ternary
llama.cpp differ in precision, kernels and capture paths: this is not a fair
production benchmark. Same seeds and settings do not ensure identical draws.
Activation coordinates across models are not aligned or causal explanations.
