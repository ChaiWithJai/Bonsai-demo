"""Bounded, caller-supplied browser checks. These are not model self-evaluations."""
import copy
import json


def validate_checks(value):
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 20:
        raise ValueError('Supply at most 20 request checks')
    for step in value:
        if not isinstance(step, dict) or set(step) != {'target', 'action', 'value'}:
            raise ValueError('Each request check needs target, action and value')
        target = step['target']
        if not isinstance(target, dict) or not (set(target) == {'test_id'} or set(target) == {'role', 'name'}):
            raise ValueError('Target an exact role and name, or a test ID')
        if any(not isinstance(v, str) or not v.strip() or len(v) > 200 for v in target.values()):
            raise ValueError('Request check targets must be bounded nonempty strings')
        action, expected = step['action'], step['value']
        if action == 'click':
            valid = expected is None
        elif action in ('visible', 'pressed'):
            valid = type(expected) is bool
        elif action == 'text':
            valid = isinstance(expected, str) and len(expected) <= 2000
        elif action == 'count':
            valid = type(expected) is int and 0 <= expected <= 100000
        else:
            valid = False
        if not valid:
            raise ValueError('Unsupported request check action or value')
    if value and not any(s['action'] != 'click' for s in value):
        raise ValueError('Request checks need at least one assertion')
    if len(json.dumps(value).encode()) > 16000:
        raise ValueError('Request checks exceed 16 KB')
    return copy.deepcopy(value)
