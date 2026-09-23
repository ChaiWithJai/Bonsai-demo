#!/usr/bin/env python3
"""Build a branded copy of the existing llama-ui without changing inference."""
import argparse
import os
import re
from pathlib import Path
import shutil
import subprocess



def stage_workspace_components(root, stage):
    source = root / 'scripts/prism-ui'
    route = stage / 'src/routes/workspace'
    library = stage / 'src/lib'
    route.mkdir(parents=True, exist_ok=True)
    library.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source / 'Workspace.svelte', route / '+page.svelte')
    for component in source.glob('Workspace*.svelte'):
        if component.name != 'Workspace.svelte':
            shutil.copyfile(component, library / component.name)
    shutil.copyfile(source / 'workspace-data-types.ts', library / 'workspace-data-types.ts')


def integrate_chat_features(original):
    greeting = '<ChatScreenGreeting {isEmpty} />'
    if greeting not in original:
        raise ValueError('Upstream greeting integration changed; review before building')
    return original.replace(greeting, '<ChatScreenGreeting {isEmpty} onChoosePrompt={(prompt) => { initialMessage = prompt; }} />')


def main():
    root = Path(__file__).resolve().parents[1]
    candidates = [
        root / "llama.cpp/tools/ui",
        root / "llama.cpp/build/tools/ui/ui-src",
        root / "llama.cpp/build-cuda/tools/ui/ui-src",
    ]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="llama-ui source directory. Defaults to the first known llama.cpp UI path that exists.")
    parser.add_argument("--output", type=Path, default=root / ".cache/bonsai/prism-ui")
    args = parser.parse_args()
    source = (args.source or next((path for path in candidates if path.is_dir()), candidates[0])).resolve()
    output = args.output.resolve()
    if not source.is_dir():
        parser.error("llama-ui source not found; pass --source pointing at llama.cpp/tools/ui or a built ui-src directory")
    dependencies = source / "node_modules"
    if not (dependencies / ".bin/vite").exists():
        parser.error("The source needs its existing npm dependencies installed first; this script does not download dependencies or model weights")
    stage = output / "source"
    if stage == source or source.is_relative_to(output) or output.is_relative_to(source):
        parser.error("Output must be separate from the source directory")
    stage.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, stage, dirs_exist_ok=True, ignore=shutil.ignore_patterns(
        "node_modules", ".svelte-kit", "dist", "build", ".git", "test-results", "playwright-report"))
    link = stage / "node_modules"
    if not link.exists():
        link.symlink_to(dependencies, target_is_directory=True)
    greeting = stage / "src/lib/components/app/chat/ChatScreen/ChatScreenGreeting.svelte"
    shutil.copyfile(root / "scripts/prism-ui/ChatScreenGreeting.svelte", greeting)
    screen = greeting.parent / "ChatScreen.svelte"
    original = screen.read_text()
    screen.write_text(integrate_chat_features(original))
    observability = stage / "src/routes/observability"
    observability.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / "scripts/prism-ui/Observability.svelte", observability / "+page.svelte")
    comparison = stage / "src/routes/comparison"
    comparison.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / "scripts/prism-ui/Comparison.svelte", comparison / "+page.svelte")
    stage_workspace_components(root, stage)
    shutil.copyfile(root / "scripts/prism-ui/SvgPreview.svelte", stage / "src/lib/SvgPreview.svelte")
    shutil.copyfile(root / "scripts/prism-ui/BrowserLiveView.svelte", stage / "src/lib/BrowserLiveView.svelte")
    layout = stage / "src/routes/+layout.svelte"
    layout_text = layout.read_text()
    if "\t<ModeWatcher />" not in layout_text:
        parser.error("Upstream layout integration changed; review before building")
    layout.write_text(layout_text.replace("<script lang=\"ts\">", '<script lang="ts">\n\timport BrowserLiveView from "$lib/BrowserLiveView.svelte";', 1)
                      .replace("\t<ModeWatcher />", "\t<BrowserLiveView />\n\t<ModeWatcher />", 1))
    navigation = stage / "src/lib/constants/ui.constants.ts"
    nav = navigation.read_text()
    settings_anchor = "\t\ttooltip: 'Settings'\n\t}\n];"
    if settings_anchor not in nav or "import { Package," not in nav:
        parser.error("Upstream sidebar integration changed; review before building")
    nav = nav.replace("import { Package,", "import { Workflow, Activity, Columns2, Package,", 1)
    nav = nav.replace(settings_anchor, "\t\ttooltip: 'Settings'\n\t},\n\t{ activeRouteId: '/observability', icon: Activity, route: '#/observability', tooltip: 'Observability' },\n\t{ activeRouteId: '/comparison', icon: Columns2, route: '#/comparison', tooltip: 'Head-to-head' }\n];", 1)
    navigation.write_text(nav)
    nav = nav.replace("tooltip: 'Head-to-head' }", "tooltip: 'Head-to-head' },\n\t{ activeRouteId: '/workspace', icon: Workflow, route: '#/workspace', tooltip: 'Workstreams' }")
    navigation.write_text(nav)
    with (stage / "src/app.css").open("a") as css:
        css.write('\n' + (root / "scripts/prism-ui/prism.css").read_text())
    shutil.copytree(root / "assets/prism-brand", stage / "static/prism-brand", dirs_exist_ok=True)
    logo = (root / "assets/bonsai-logo.svg").read_text()
    # Inline SVG must follow the chosen UI theme, not the device media query.
    logo = re.sub(r'<style>.*?</style>', '', logo, flags=re.S)
    logo = logo.replace('<path ', '<path fill="currentColor" ')
    (stage / "src/lib/assets/logo.svg").write_text(logo)
    env = {**os.environ, "VITE_PUBLIC_APP_NAME": "Prism ML | Bonsai 2",
           "LLAMA_UI_OUT_DIR": str(output / "dist")}
    subprocess.run(["npm", "exec", "--", "vite", "build"], cwd=stage, env=env, check=True)
    print(output / "dist")


if __name__ == "__main__":
    main()
