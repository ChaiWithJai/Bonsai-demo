"""Validate and apply a model-proposed replacement for the retained Pelican fork.

This is a bounded output repair, not a benchmark rerun or a weight update.
The replacement is model output; this gate never invents replacement content.
"""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from svg_output import inspect_svg

FAILED_ELEMENT = '<line x1="110" y2="100" x2="120" y2="100"/>'


def apply_validated_patch(original: str, model_patch: str) -> dict:
    before = inspect_svg(original)
    if before.get('valid') or original.count(FAILED_ELEMENT) != 1:
        raise ValueError('Expected one known invalid fork element')
    patch = model_patch.strip()
    element = ET.fromstring(patch)
    expected = {'x1': '110', 'y1': '100', 'x2': '120', 'y2': '100'}
    if element.tag != 'line' or element.attrib != expected or len(element) or element.text:
        raise ValueError('Patch must preserve fork coordinates with unique valid attributes')
    corrected = original.replace(FAILED_ELEMENT, patch, 1)
    after = inspect_svg(corrected)
    if not after.get('valid'):
        raise ValueError(f'Full SVG validation failed: {after.get("error")}')
    return {'original_validation': before, 'corrected_validation': after,
            'before_element': FAILED_ELEMENT, 'model_patch': patch,
            'corrected_output': corrected, 'corrected_svg': after['source']}
