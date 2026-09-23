"""Fixed SSH transport: camera credentials stay in the server's SSH configuration."""
import json
import subprocess
from gb10_vision_mcp import dispatch as local_dispatch


def dispatch(request):
    # Discovery is local and does not open an SSH connection or the camera.
    if not isinstance(request,dict) or request.get('method') != 'tools/call':
        return local_dispatch(request)
    try:
        response=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','gb10',
                                 'python3','.local/share/bonsai-vision/gb10_vision_mcp.py'],
                                input=json.dumps(request),capture_output=True,text=True,timeout=25)
        if response.returncode or len(response.stdout)>6_000_000:
            raise ValueError('GB10 camera connection failed')
        return json.loads(response.stdout)
    except (ValueError,OSError,subprocess.TimeoutExpired):
        return {'jsonrpc':'2.0','id':request.get('id'),'result':{'isError':True,
                'content':[{'type':'text','text':'GB10 camera is unavailable; check the server SSH connection.'}]}}
