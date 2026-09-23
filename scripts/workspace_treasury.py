"""Fetch and preserve Treasury daily par yields for the bond learning workflow."""
import datetime as dt
import hashlib
import http.client
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

HOST = 'home.treasury.gov'
MAX_BYTES = 4_000_000
NS = {'a': 'http://www.w3.org/2005/Atom',
      'm': 'http://schemas.microsoft.com/ado/2007/08/dataservices/metadata',
      'd': 'http://schemas.microsoft.com/ado/2007/08/dataservices'}


def parse_yields(raw):
    if len(raw) > MAX_BYTES or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('Unsupported Treasury XML payload')
    root = ET.fromstring(raw)
    rows = []
    for properties in root.findall('.//m:properties', NS):
        date = properties.find('d:NEW_DATE', NS)
        if date is None or not date.text:
            raise ValueError('Treasury observation is missing its date')
        observation_date = dt.date.fromisoformat(date.text[:10]).isoformat()
        rates = {}
        for field in properties:
            name = field.tag.split('}')[-1]
            if not re.fullmatch(r'BC_\d+(MONTH|YEAR)', name):
                continue
            if field.get('{'+NS['m']+'}null') == 'true' or not (field.text or '').strip():
                rates[name] = None
            else:
                value = float(field.text)
                if not math.isfinite(value):
                    raise ValueError('Treasury yield must be finite')
                rates[name] = value
        if not rates:
            raise ValueError('Treasury observation contains no par yields')
        rows.append({'observation_date': observation_date, 'yields_percent': rates})
    if not rows:
        raise ValueError('Treasury returned no observations')
    return sorted(rows, key=lambda row: row['observation_date'])


def fetch_yields(year, archive_dir):
    if type(year) is not int or not 1990 <= year <= 9999:
        raise ValueError('Provide a Treasury calendar year from 1990 onward')
    path = ('/resource-center/data-chart-center/interest-rates/pages/xml'
            '?data=daily_treasury_yield_curve&field_tdr_date_value='+str(year))
    connection = http.client.HTTPSConnection(HOST, timeout=20)
    try:
        connection.request('GET', path, headers={'Accept': 'application/xml',
                                                'User-Agent': 'Bonsai-demo Treasury learning workflow'})
        response = connection.getresponse()
        if response.status != 200:
            raise RuntimeError(f'Treasury returned HTTP {response.status}')
        raw = response.read(MAX_BYTES+1)
    finally:
        connection.close()
    rows = parse_yields(raw)
    if any(not row['observation_date'].startswith(str(year)+'-') for row in rows):
        raise ValueError('Treasury response contains observations outside the requested year')
    digest = hashlib.sha256(raw).hexdigest()
    result = {'source_url': 'https://'+HOST+path,
              'fetched_at': dt.datetime.now(dt.timezone.utc).isoformat(),
              'sha256': digest, 'series': 'daily_treasury_par_yield_curve',
              'rate_unit': 'percent', 'latest_observation': rows[-1],
              'observations': rows,
              'usage': 'Daily par-yield context; not spot rates or an executable bond quote'}
    folder = Path(archive_dir)
    folder.mkdir(parents=True, exist_ok=True)
    (folder/(digest+'.xml')).write_bytes(raw)
    # Each retrieval keeps its own timestamp even when the source bytes are unchanged.
    stamp = result['fetched_at'].replace(':', '')
    (folder/(stamp+'.json')).write_text(json.dumps(result, indent=2, allow_nan=False))
    return result
