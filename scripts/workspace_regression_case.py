"""Check a frozen development case against compiled source data, without inference."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

DEFAULT_SUITE = Path(__file__).resolve().parents[1] / 'research/harness-alignment/fixtures/desktop-regressions/suite.json'


def load_case(suite_path, case_id):
    suite = json.loads(suite_path.read_text())
    case = next(case for case in suite['cases'] if case['id'] == case_id)
    content = (suite_path.parent / case['file']).read_bytes()
    if hashlib.sha256(content).hexdigest() != case['sha256']:
        raise ValueError('Frozen source checksum mismatch')
    return case


def assess(case, compiled):
    fields = list(case['expected_records'][0])
    def value_key(value):
        if type(value) in (int,float):return ('number',value)
        return (type(value).__name__,json.dumps(value,sort_keys=True))
    def keyed(rows):
        return Counter(tuple(value_key(row.get(field)) for field in fields) for row in rows)
    expected_view = case['expected_view']
    actual_view = compiled['plan']['view']
    checks = {
        'record_values': keyed([row['data'] for row in compiled['rows']]) == keyed(case['expected_records']),
        'view_mapping': all(actual_view.get(key) == value for key,value in expected_view.items()),
        'no_excluded_records': compiled['excluded_record_ids'] == [],
    }
    return {'case_id':case['id'],'scope':'Exact development regression contract, not semantic accuracy',
            'checks':checks,'passed':all(checks.values()),
            'not_assessed':['Rendered geometry','Citation support','Human acceptance','Interpretation completeness'],
            'field_policy':'Exact expected field names; equivalent renamed fields require review'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite',type=Path,default=DEFAULT_SUITE)
    parser.add_argument('--case',required=True)
    parser.add_argument('--compiled',type=Path)
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    case = load_case(args.suite,args.case)
    result = assess(case,json.loads(args.compiled.read_text())) if args.compiled else {'case_id':case['id'],'source_sha256':case['sha256'],'integrity':'verified','request':case['request']}
    text = json.dumps(result,indent=2)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(text)
    print(text,end='')
    if result.get('passed') is False:raise SystemExit(1)


if __name__ == '__main__':main()
