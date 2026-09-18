"""Extract and validate model SVG without executing or rewriting its drawing."""
import re
import xml.etree.ElementTree as ET

ALLOWED = {'svg','g','path','circle','ellipse','rect','line','polyline','polygon','text','tspan','defs','title','desc','style','linearGradient','radialGradient','stop','clipPath','mask','use','symbol','marker','textPath','pattern','filter','feGaussianBlur','feOffset','feMerge','feMergeNode','feBlend','feColorMatrix','feComposite','feFlood','feDropShadow'}

def inspect_svg(content):
    if not isinstance(content, str) or len(content) > 512000:
        return {'valid': False, 'error': 'SVG output exceeds the preview limit'}
    if re.search(r'<!DOCTYPE|<!ENTITY', content, re.I):
        return {'valid': False, 'error': 'Document declarations are not supported'}
    match = re.search(r'<svg\b[\s\S]*?</svg\s*>', content, re.I)
    if not match:
        return {'valid': False, 'error': 'No complete SVG found; inspect the original output'}
    source = match.group(0)
    try:
        root = ET.fromstring(source)
        if root.tag != '{http://www.w3.org/2000/svg}svg':
            raise ValueError('SVG namespace is required')
        nodes = list(root.iter())
        if len(nodes) > 10000:
            raise ValueError('SVG contains too many elements')
        for node in nodes:
            if not node.tag.startswith('{http://www.w3.org/2000/svg}') or node.tag.split('}')[-1] not in ALLOWED:
                raise ValueError('Unsupported SVG element')
            for key, value in node.attrib.items():
                name = key.split('}')[-1].lower()
                if name.startswith('on') or name in ('src', 'base'):
                    raise ValueError('Active SVG attributes are not supported')
                if name == 'href' and not re.fullmatch(r'#[A-Za-z_][\w:.-]*', value.strip()):
                    raise ValueError('External SVG resources are not supported')
            css = ' '.join(node.attrib.values()) + ' ' + (node.text or '')
            if re.search(r'\\|@import|@font-face|javascript\s*:|expression\s*\(', css, re.I):
                raise ValueError('Active SVG content is not supported')
            for target in re.findall(r'url\s*\((.*?)\)', css, re.I):
                if not target.strip().strip('\"\'').startswith('#'):
                    raise ValueError('External SVG resources are not supported')
        return {'valid': True, 'source': source, 'elements': len(nodes), 'scope': 'Syntax and preview safety only; visual quality is judged separately'}
    except (ET.ParseError, ValueError) as exc:
        return {'valid': False, 'error': str(exc)}
