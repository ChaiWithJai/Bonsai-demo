#!/usr/bin/env python3
"""Resolve exact Hub files locally before downloading; never copy model weights."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import fnmatch
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sys


def search_roots(project: Path) -> list[Path]:
    """Bounded discovery: model folders, not a recursive scan of the whole machine."""
    home = Path.home()
    roots = [project / "models", home / "models", home / "model-store" / "local"]
    for parent in (home, home / "Documents" / "code", home / "code", home / "Projects"):
        if parent.is_dir():
            roots.extend(parent.glob("*/models"))
    config = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config")) / "bonsai/model-paths.json"
    if config.exists():
        configured = json.loads(config.read_text())
        if not isinstance(configured, list) or not all(isinstance(p, str) for p in configured):
            raise ValueError(f"{config} must contain a JSON array of model-folder paths")
        roots.extend(Path(p).expanduser() for p in configured)
    roots.extend(Path(p).expanduser() for p in os.environ.get("BONSAI_MODEL_PATHS", "").split(os.pathsep) if p)
    return list(dict.fromkeys(p.resolve() for p in roots if p.is_dir()))


def candidates_by_size(roots: list[Path], sizes: set[int]) -> dict[int, list[Path]]:
    candidates: dict[int, list[Path]] = {}
    seen = set()
    for root in roots:
        for base, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in {".cache", ".git", "node_modules", ".venv"})
            for name in sorted(files):
                if name.endswith((".incomplete", ".lock")) or name.startswith("._"):
                    continue
                path = Path(base) / name
                try:
                    stat = path.stat()
                except OSError:
                    continue
                identity = (stat.st_dev, stat.st_ino)
                if stat.st_size in sizes and identity not in seen and path.is_file():
                    seen.add(identity)
                    candidates.setdefault(stat.st_size, []).append(path.resolve())
    return candidates


def file_digest(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    if algorithm == "sha1":
        # Non-LFS Hub objects use the Git blob hash, not raw SHA-1.
        digest.update(f"blob {path.stat().st_size}\0".encode())
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def matches(path: Path, spec: dict, hashes: dict) -> bool:
    try:
        before = path.stat()
        if not path.is_file() or before.st_size != spec["size"]:
            return False
        key = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns, spec["algorithm"])
        if key not in hashes:
            value = file_digest(path, spec["algorithm"])
            after = path.stat()
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                return False
            hashes[key] = value
        return hashes[key] == spec["digest"]
    except OSError:
        return False


def select_files(info, patterns: list[str], destination: Path) -> tuple[list[dict], bool]:
    siblings = info.siblings or []
    selected = [s for s in siblings if not patterns or any(fnmatch.fnmatchcase(s.rfilename, p) for p in patterns)]
    official_q2 = False
    if "Ternary-Bonsai" in info.id and info.id.endswith("-gguf"):
        is_weight = lambda s: s.rfilename.endswith(".gguf") and not any(x in s.rfilename for x in ("mmproj", "dspark", "kv-bias"))
        if not any(is_weight(s) for s in selected):
            fallback = [s for s in siblings if fnmatch.fnmatchcase(s.rfilename, "*-Q2_0.gguf")]
            selected.extend(fallback)
            official_q2 = bool(fallback)
    projectors = [s for s in selected if "mmproj" in s.rfilename and s.rfilename.endswith(".gguf")]
    if len(projectors) > 1:
        # Preserve an installed projector; otherwise prefer BF16. Verify below.
        projectors.sort(key=lambda s: (not (destination / s.rfilename).is_file(), "BF16" not in s.rfilename, s.rfilename))
        selected = [s for s in selected if s not in projectors[1:]]
    specs = []
    for sibling in selected:
        name = PurePosixPath(sibling.rfilename)
        if name.is_absolute() or ".." in name.parts:
            raise ValueError(f"Invalid Hub filename: {name}")
        lfs = sibling.lfs
        digest = lfs.sha256 if lfs else sibling.blob_id
        if sibling.size is None or not digest:
            raise ValueError(f"Missing content hash/size for {name}; refusing unverified reuse")
        specs.append({"name": str(name), "size": sibling.size, "digest": digest, "algorithm": "sha256" if lfs else "sha1"})
    if not specs:
        raise ValueError("No files match the requested model patterns")
    return specs, official_q2


@contextmanager
def destination_lock(destination: Path, plan: bool):
    if plan:
        yield
        return
    folder = destination / ".cache" / "bonsai"
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "setup.lock").open("a") as handle:
        print(f"[models] Waiting for setup lock: {destination}", flush=True)
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def resolve(repo: str, destination: Path, patterns: list[str], roots: list[Path], *, plan=False, revision=None, token=None, api=None, cached=None, download=None):
    if api is None or cached is None or download is None:
        from huggingface_hub import HfApi, hf_hub_download, try_to_load_from_cache
        api = api or HfApi()
        cached = cached or try_to_load_from_cache
        download = download or hf_hub_download

    with destination_lock(destination, plan):
        info = api.model_info(repo, revision=revision, files_metadata=True, token=token)
        specs, official_q2 = select_files(info, patterns, destination)
        candidates = candidates_by_size(roots, {s["size"] for s in specs})
        hashes = {}
        actions = []
        print(f"[models] {repo} @ {info.sha}", flush=True)
        # Build the entire plan before downloading or linking anything.
        for spec in specs:
            target = destination / spec["name"]
            if target.exists():
                if not matches(target, spec, hashes):
                    raise ValueError(f"Existing file differs from requested revision: {target}. Preserved; use a separate destination for this revision.")
                action, source = "KEEP", target.resolve()
            else:
                hit = cached(repo, spec["name"], revision=info.sha)
                options = ([Path(hit)] if isinstance(hit, str) else []) + candidates.get(spec["size"], [])
                source = next((p for p in options if matches(p, spec, hashes)), None)
                action = "REUSE" if source else "DOWNLOAD"
            actions.append({"action": action, "source": str(source) if source else None, **spec})
            print(f"[models] {action:8} {spec['name']} ({spec['size'] / 1024**3:.3f} GiB)" + (f" <- {source}" if source else " -> shared Hugging Face cache"), flush=True)
        total = sum(a["size"] for a in actions if a["action"] == "DOWNLOAD")
        print(f"[models] Weight/file downloads needed: {total / 1024**3:.3f} GiB", flush=True)
        if plan:
            return actions
        for action in actions:
            if action["action"] == "KEEP":
                continue
            target = destination / action["name"]
            source = Path(action["source"]) if action["source"] else Path(download(repo, action["name"], revision=info.sha, token=token))
            if not matches(source, action, hashes):
                raise ValueError(f"Content verification failed: {source}")
            target.parent.mkdir(parents=True, exist_ok=True)
            # Never overwrite an existing file (including one created by an older downloader).
            if target.is_symlink() and not target.exists():
                target.unlink()
            try:
                target.symlink_to(source.resolve())
            except FileExistsError:
                if not matches(target, action, hashes):
                    raise ValueError(f"Destination changed during setup: {target}")
            action["source"] = str(source.resolve())
        if official_q2:
            (destination / ".official-q2_0").touch()
        manifest = destination / ".cache" / "bonsai" / "manifest.json"
        temporary = manifest.with_suffix(".tmp")
        temporary.write_text(json.dumps({"repo": repo, "revision": info.sha, "files": actions}, indent=2) + "\n")
        temporary.replace(manifest)
        return actions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo")
    parser.add_argument("destination", type=Path)
    parser.add_argument("--patterns", default="")
    parser.add_argument("--plan", action="store_true", help="Show reuse/download decisions without modifying files or downloading weights")
    args = parser.parse_args()
    try:
        resolve(args.repo, args.destination.resolve(), [p for p in args.patterns.split(",") if p], search_roots(Path(__file__).resolve().parents[1]), plan=args.plan, revision=os.environ.get("BONSAI_MODEL_REVISION"), token=os.environ.get("BONSAI_TOKEN") or None)
    except (OSError, ValueError) as exc:
        print(f"[models] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
