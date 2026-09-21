"""Apply MLflow's unchanged built-in tool-efficiency prompt with bounded local inference."""
import os,json,pathlib,signal,hashlib
os.environ['OPENAI_API_KEY']='local-unused'
os.environ['OPENAI_API_BASE']='http://127.0.0.1:5257/v1'
os.environ['MLFLOW_GATEWAY_ROUTE_TIMEOUT_SECONDS']='90'
import mlflow
from mlflow.genai.utils.trace_utils import extract_available_tools_from_trace,extract_request_from_trace,extract_tools_called_from_trace
from mlflow.genai.judges.prompts.tool_call_efficiency import get_prompt
from mlflow.genai.judges.utils.invocation_utils import invoke_judge_model
p=pathlib.Path(__file__).resolve().parent
mlflow.set_tracking_uri('http://127.0.0.1:5210')
tid='tr-a38715d1c5e7f9ce284202dc0cb8a09a'
t=mlflow.get_trace(tid)
(p/'trace.json').write_text(t.to_json())
prompt=get_prompt(request=extract_request_from_trace(t),tools_called=extract_tools_called_from_trace(t),available_tools=extract_available_tools_from_trace(t))
(p/'builtin-judge-prompt.txt').write_text(prompt)
params={'temperature':0.7,'top_p':0.8,'top_k':20,'min_p':0,'presence_penalty':1.5,'repeat_penalty':1.0,'max_tokens':1024,'seed':42,'chat_template_kwargs':{'enable_thinking':False}}
(p/'judge-config.json').write_text(json.dumps({'mlflow_version':mlflow.__version__,'trace_id':tid,'model':'bonsai-ui-public-ternary-bonsai2-27b','inference_params':params,'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(),'execution':'Unchanged built-in prompt and MLflow judge invocation with explicit local transport; not default ToolCallEfficiency.__call__','calibration':'Uncalibrated same-model assessment; deterministic evidence is primary'},indent=2))
def timeout(*args): raise TimeoutError('Single judge invocation exceeded 100 seconds')
signal.signal(signal.SIGALRM,timeout);signal.alarm(100)
try:
 f=invoke_judge_model('openai:/bonsai-ui-public-ternary-bonsai2-27b',prompt,'tool_call_efficiency_local',num_retries=0,inference_params=params,extra_headers={'X-Bonsai-Conversation':'workspace-loop-audit'})
 signal.alarm(0)
 (p/'judge-result.json').write_text(json.dumps(f.to_dictionary(),indent=2,default=str))
 mlflow.log_feedback(trace_id=tid,name='tool_call_efficiency_local',value=f.value,rationale=f.rationale,source=f.source,metadata={'audit':'20260921','calibration':'uncalibrated_same_model','execution':'builtin_prompt_explicit_local_parameters'})
 print((p/'judge-result.json').read_text())
except Exception as e:
 signal.alarm(0);(p/'judge-error.json').write_text(json.dumps({'error':str(e),'no_retry':True},indent=2)); print(type(e).__name__,str(e))
