"""Build and browser-check the starter against synthetic release dates, without inference."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from workspace_data.desktop_plan import compile_plan
from workspace_store import WorkspaceStore
from workspace_tools import WorkspaceTools


def main():
    # Explicit development fixture. These are not claims about real Bonsai releases.
    records = [
        {'size': '8B', 'release': '2026-03-01'},
        {'size': '27B', 'release': '2026-07-01'},
        {'size': '27B', 'release': '2026-09-17'},
        {'size': '27B', 'release': None},
        {'size': '8B', 'release': '2026-09-01'},
    ]
    source = {'status': 'extracted', 'source_id': 'development', 'sha256': 'development',
              'filename': 'synthetic-release-events.json', 'records': [
                  {'id': f'development:{i+1}', 'source_id': 'development',
                   'locator': {'record': i+1}, 'data': data} for i, data in enumerate(records)]}
    compiled = compile_plan(source, {
        'title': 'Development release exploration', 'summary': 'Synthetic dates for interaction verification.',
        'fields': [{'name': 'size', 'type': 'text'}, {'name': 'release', 'type': 'date'}],
        'view': {'component': 'ForceDirectedGraph', 'groupBy': ['size', 'release']}})
    with tempfile.TemporaryDirectory(prefix='bonsai-date-exploration-') as tmp:
        folder = Path(tmp)
        chart = folder / 'chart.json'
        chart.write_text(json.dumps(compiled['chart']))
        subprocess.run(['node', str(ROOT / 'scripts/workspace-tools/render_chart.mjs'), str(chart), str(folder / 'render')], check=True)
        fixture = {'kind': 'desktop', 'compiled': compiled,
                   'render_evidence': json.loads((folder / 'render/render-evidence.json').read_text()),
                   'chart_svg': (folder / 'render/chart.svg').read_text()}
        store = WorkspaceStore(folder / 'store')
        project = store.create('Development date exploration',
                               {'App.svelte': (ROOT / 'examples/workspace/desktop/App.svelte').read_text()}, fixture)
        tools = WorkspaceTools(store, 'http://127.0.0.1:5257')
        try:
            build = tools.build(project, folder / 'build', threading.Event())
            if not build['ok']:
                raise RuntimeError(build)
            preview = tools.preview(project, build)
            subprocess.run(['node', str(ROOT / 'scripts/workspace-tools/node_modules/@playwright/test/cli.js'), 'test',
                            '--config', 'tools/design-review/capture/playwright.config.ts', '--grep',
                            'Generated view combines node selection'], cwd=ROOT, check=True,
                           env={**os.environ, 'DATE_PREVIEW_URL': preview['url'],
                                'NODE_PATH': str(ROOT / 'scripts/workspace-tools/node_modules')})
        finally:
            tools.close()


if __name__ == '__main__':
    main()
