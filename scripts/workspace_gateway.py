"""Server-side bridge from the Python harness to the pinned Vercel AI SDK."""
import json
from pathlib import Path
import subprocess


class GatewayError(RuntimeError):
    pass


def gateway_request(request):
    script = Path(__file__).parent / 'workspace-tools' / 'gateway.mjs'
    payload = json.dumps(request, allow_nan=False)
    if len(payload.encode()) > 150000:
        raise ValueError('Gateway request is too large')
    try:
        completed = subprocess.run(['node', str(script)], input=payload, text=True,
                                   capture_output=True, timeout=130, check=False)
    except subprocess.TimeoutExpired as exc:
        raise GatewayError('Gateway operation timed out') from exc
    if completed.returncode:
        raise GatewayError('Gateway operation failed; check server credentials and provider availability')
    try:
        return json.loads(completed.stdout)
    except (ValueError, TypeError) as exc:
        raise GatewayError('Gateway returned an invalid result') from exc
