import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from contextlib import redirect_stdout


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("model_store", ROOT / "scripts/model_store.py")
store = importlib.util.module_from_spec(spec)
spec.loader.exec_module(store)


def sibling(name, content, lfs=True):
    return SimpleNamespace(
        rfilename=name,
        size=len(content),
        lfs=SimpleNamespace(sha256=hashlib.sha256(content).hexdigest()) if lfs else None,
        blob_id=hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest(),
    )


class ModelStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.destination = self.root / "project/models"
        self.existing = self.root / "other/models"
        self.existing.mkdir(parents=True)
        self.content = b"GGUF exact public checkpoint"
        self.name = "Ternary-Bonsai-27B-PQ2_0.gguf"
        self.info = SimpleNamespace(id="prism-ml/Ternary-Bonsai-27B-gguf", sha="pinned-commit", siblings=[sibling(self.name, self.content)])
        self.api = SimpleNamespace(model_info=Mock(return_value=self.info))
        self.cached = Mock(return_value=None)
        self.download = Mock(side_effect=AssertionError("Unexpected weight download"))

    def resolve(self, **kwargs):
        with redirect_stdout(io.StringIO()):
            return store.resolve(self.info.id, self.destination, ["*.gguf"], [self.existing], api=self.api, cached=self.cached, download=self.download, **kwargs)

    def test_renamed_exact_checkpoint_is_linked_and_rerun_keeps_it(self):
        source = self.existing / "renamed.gguf"
        source.write_bytes(self.content)
        self.assertEqual(self.resolve()[0]["action"], "REUSE")
        target = self.destination / self.name
        self.assertTrue(target.is_symlink())
        self.assertEqual(target.resolve(), source)
        self.assertEqual(self.resolve()[0]["action"], "KEEP")
        manifest = json.loads((self.destination / ".cache/bonsai/manifest.json").read_text())
        self.assertEqual(manifest["revision"], "pinned-commit")
        self.download.assert_not_called()

    def test_same_name_and_size_but_wrong_bytes_is_not_reused(self):
        (self.existing / self.name).write_bytes(b"x" * len(self.content))
        self.assertEqual(self.resolve(plan=True)[0]["action"], "DOWNLOAD")
        self.assertFalse(self.destination.exists())
        self.download.assert_not_called()

    def test_incomplete_files_are_never_reused(self):
        (self.existing / "model.incomplete").write_bytes(self.content)
        self.assertEqual(self.resolve(plan=True)[0]["action"], "DOWNLOAD")

    def test_cached_snapshot_reused_without_new_download(self):
        cached = self.root / "cached-model"
        cached.write_bytes(self.content)
        self.cached.return_value = str(cached)
        self.assertEqual(self.resolve()[0]["action"], "REUSE")
        self.cached.assert_called_with(self.info.id, self.name, revision="pinned-commit")

    def test_download_uses_pinned_shared_cache_then_links(self):
        cached = self.root / "downloaded"
        cached.write_bytes(self.content)
        self.download.side_effect = None
        self.download.return_value = str(cached)
        self.resolve()
        self.download.assert_called_once_with(self.info.id, self.name, revision="pinned-commit", token=None)
        self.assertEqual((self.destination / self.name).resolve(), cached)

    def test_existing_mismatched_target_is_preserved(self):
        self.destination.mkdir(parents=True)
        target = self.destination / self.name
        target.write_bytes(b"preview model")
        with self.assertRaisesRegex(ValueError, "Existing file differs"):
            self.resolve()
        self.assertEqual(target.read_bytes(), b"preview model")
        self.download.assert_not_called()

    def test_broken_link_is_repaired_from_verified_source(self):
        self.destination.mkdir(parents=True)
        (self.destination / self.name).symlink_to(self.root / "missing")
        source = self.existing / self.name
        source.write_bytes(self.content)
        self.resolve()
        self.assertEqual((self.destination / self.name).resolve(), source)

    def test_wrong_download_hash_never_becomes_project_model(self):
        cached = self.root / "bad-download"
        cached.write_bytes(b"x" * len(self.content))
        self.download.side_effect = None
        self.download.return_value = str(cached)
        with self.assertRaisesRegex(ValueError, "Content verification failed"):
            self.resolve()
        self.assertFalse((self.destination / self.name).exists())

    def test_plan_verifies_reuse_without_writes(self):
        (self.existing / self.name).write_bytes(self.content)
        before = set(self.root.rglob("*"))
        self.assertEqual(self.resolve(plan=True)[0]["action"], "REUSE")
        self.assertEqual(before, set(self.root.rglob("*")))

    def test_one_projector_prefer_bf16_but_preserve_installed_q8(self):
        bf16 = sibling("mmproj-BF16.gguf", b"bf16")
        q8 = sibling("mmproj-Q8_0.gguf", b"q8")
        self.info.siblings.extend([bf16, q8])
        chosen, _ = store.select_files(self.info, ["*.gguf"], self.destination)
        self.assertEqual([s["name"] for s in chosen if "mmproj" in s["name"]], [bf16.rfilename])
        self.destination.mkdir(parents=True)
        (self.destination / q8.rfilename).write_bytes(b"q8")
        chosen, _ = store.select_files(self.info, ["*.gguf"], self.destination)
        self.assertEqual([s["name"] for s in chosen if "mmproj" in s["name"]], [q8.rfilename])

    def test_metadata_file_uses_git_blob_hash(self):
        content = b'{"model": "bonsai"}'
        self.info.siblings = [sibling("config.json", content, lfs=False)]
        (self.existing / "config.json").write_bytes(content)
        with redirect_stdout(io.StringIO()):
            result = store.resolve(self.info.id, self.destination, [], [self.existing], plan=True, api=self.api, cached=self.cached, download=self.download)
        self.assertEqual(result[0]["action"], "REUSE")

    def test_local_discovery_resolves_project_aliases(self):
        home = self.root / "home"
        models = home / "evidence-lab/models"
        models.mkdir(parents=True)
        alias = home / "Documents/code/alias/models"
        alias.parent.mkdir(parents=True)
        alias.symlink_to(models, target_is_directory=True)
        with patch.object(Path, "home", return_value=home), patch.dict(os.environ, {"XDG_CONFIG_HOME": str(home / ".config"), "BONSAI_MODEL_PATHS": ""}):
            self.assertEqual(store.search_roots(self.root / "project"), [models])

    def test_fallback_marks_plain_q2_only_after_verified_install(self):
        self.info.siblings = [sibling("Ternary-Bonsai-27B-Q2_0.gguf", self.content)]
        (self.existing / "renamed.gguf").write_bytes(self.content)
        with redirect_stdout(io.StringIO()):
            store.resolve(self.info.id, self.destination, ["*g64.gguf"], [self.existing], api=self.api, cached=self.cached, download=self.download)
        self.assertTrue((self.destination / ".official-q2_0").exists())

    def test_partial_mlx_install_cannot_claim_full_install_from_config_alone(self):
        # Resolver checks every selected file, not just the MLX config.
        self.info.id = "prism-ml/Ternary-Bonsai-27B-mlx-2bit"
        self.info.siblings = [sibling("config.json", b"{}", lfs=False), sibling("model.safetensors", self.content)]
        self.destination.mkdir(parents=True)
        (self.destination / "config.json").write_bytes(b"{}")
        with redirect_stdout(io.StringIO()):
            result = store.resolve(self.info.id, self.destination, [], [], plan=True, api=self.api, cached=self.cached, download=self.download)
        self.assertEqual([a["action"] for a in result], ["KEEP", "DOWNLOAD"])


class SetupModelPlanTests(unittest.TestCase):
    def test_setup_plan_bypasses_dependency_install_and_drafter_is_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "bin/cuda").mkdir(parents=True)
            (root / ".venv/bin").mkdir(parents=True)
            for filename in ["setup.sh", "scripts/common.sh", "scripts/download_models.sh"]:
                shutil.copy(ROOT / filename, root / filename)
            python = root / ".venv/bin/python"
            python.write_text('#!/bin/sh\nif [ "$1" = "-c" ]; then exit 0; fi\nprintf "%s\\n" "$@"\n')
            python.chmod(0o755)
            env = {**os.environ, "BONSAI_MODEL": "27B", "BONSAI_FAMILY": "ternary", "BONSAI_SKIP_MLX": "1", "BONSAI_SKIP_GGUF": "0", "BONSAI_SPECULATIVE": "0", "BONSAI_DOWNLOAD_DRAFTER": "0", "BONSAI_TOKEN": ""}
            def run():
                return subprocess.run(["sh", str(root / "setup.sh"), "--model-plan"], env=env, capture_output=True, text=True, timeout=15)
            result = run()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("--plan", result.stdout)
            self.assertIn("*-PQ2_0.gguf,*mmproj*.gguf", result.stdout)
            self.assertNotIn("dspark", result.stdout)
            self.assertNotIn("Installing", result.stdout)
            self.assertFalse((root / "models").exists())
            env["BONSAI_DOWNLOAD_DRAFTER"] = "1"
            self.assertIn("*dspark-bf16*.gguf", run().stdout)
            env["BONSAI_FAMILY"] = "bonsai2"
            result = run()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("prism-ml/Ternary-Bonsai-2-27B-gguf", result.stdout)
            self.assertIn("--plan", result.stdout)
            self.assertNotIn("dspark", result.stdout)
            self.assertFalse((root / "models").exists())


if __name__ == "__main__":
    unittest.main()
