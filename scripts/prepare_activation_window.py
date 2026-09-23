"""Prepare a labeled teacher-forced window from recorded answer text; no inference."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request


def streamed_text(raw):
    reasoning, answer = '', ''
    for line in raw.splitlines():
        if not line.startswith('data: {'):
            continue
        chunk = json.loads(line[6:])
        delta = (chunk.get('choices') or [{}])[0].get('delta', {})
        reasoning += delta.get('reasoning_content') or ''
        answer += delta.get('content') or ''
    if not answer:
        raise ValueError('No recorded assistant answer')
    return reasoning, answer


def prepare(record, marker, output, upstream):
    record, output = Path(record), Path(output)
    if output.exists():
        raise ValueError('Use a fresh output directory')
    request = json.loads((record / 'request.bin').read_text())
    reasoning, answer = streamed_text((record / 'response.bin').read_text())
    if answer.count(marker) != 1:
        raise ValueError('Marker must occur exactly once in the recorded answer')
    def post(route, payload):
        req = urllib.request.Request(upstream+route, data=json.dumps(payload).encode(), headers={'Content-Type':'application/json'})
        return json.load(urllib.request.urlopen(req, timeout=30))
    original = post('/apply-template', request)['prompt']
    if not original.endswith('<think>\n'):
        raise ValueError('Unsupported assistant reasoning template; do not guess separators')
    prefix = original + reasoning + '\n</think>\n\n' + answer[:answer.index(marker)]
    # The stream omits token IDs and the channel separator. Preserve this reconstruction
    # explicitly rather than claiming an exact original internal state.
    prompt_tokens = post('/tokenize', {'content':prefix,'add_special':True,'parse_special':True})['tokens']
    forced = post('/tokenize', {'content':answer[answer.index(marker):],'add_special':False,'parse_special':False})['tokens'][:32]
    output.mkdir(parents=True)
    (output / 'rendered-prompt.txt').write_text(prefix)
    (output / 'config.json').write_text(json.dumps({'decode_steps':len(forced),'context':max(4096,((len(prompt_tokens)+len(forced)+1023)//1024)*1024),'n_threads':8,'sampler':'greedy','expected_prompt_tokens':len(prompt_tokens),'forced_tokens':forced},indent=2))
    evidence={'source_record':str(record.resolve()),'source_request_sha256':hashlib.sha256((record/'request.bin').read_bytes()).hexdigest(),'source_response_sha256':hashlib.sha256((record/'response.bin').read_bytes()).hexdigest(),'marker':marker,'prompt_tokens':len(prompt_tokens),'forced_tokens':forced,'scope':'NEW teacher-forced diagnostic on a reconstructed recorded prefix. Not original activations, a regenerated answer, or a causal explanation.','differences':['SSE did not preserve original token IDs or channel separator','Reasoning/answer separator reconstructed as newline, closing think tag, and two newlines','Prefix and window tokenized separately','Observed answer tokens forced; greedy next-token predictions are diagnostic only','Fresh context, no production prefix cache']}
    (output/'provenance.json').write_text(json.dumps(evidence,indent=2))
    return evidence

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record',required=True);parser.add_argument('--marker',required=True)
    parser.add_argument('--output',required=True);parser.add_argument('--upstream',required=True)
    args=parser.parse_args()
    print(json.dumps(prepare(args.record,args.marker,args.output,args.upstream)))
