"""Exercise the distributed wheel's actual get/context entry points."""

import json
import shutil
import os
import subprocess
import sys
import zipfile
from pathlib import Path


def test_shared_contract_generation_is_current():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "scripts/check_context_contracts.py"), "--check"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_installed_wheel_reads_exact_sections_and_preserves_contract(tmp_path):
    root = Path(__file__).resolve().parents[1]
    source_root = tmp_path / "source"
    source_root.mkdir()
    for name in ["almanac", "memento"]:
        shutil.copytree(root / name, source_root / name, ignore=shutil.ignore_patterns("__pycache__"))
    for name in ["pyproject.toml", "README.md", "LICENSE", "VERSION"]:
        shutil.copy2(root / name, source_root / name)
    built = subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--no-isolation", "--outdir", str(tmp_path / "dist")],
        cwd=source_root,
        capture_output=True,
        text=True,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    installed = tmp_path / "installed"
    with zipfile.ZipFile(next((tmp_path / "dist").glob("*.whl"))) as wheel:
        wheel.extractall(installed)
    vault = tmp_path / "vault"
    (vault / "notes").mkdir(parents=True)
    (vault / "notes" / "n.md").write_text(
        "---\ntitle: Note\n---\n# Applicability\nOnly with a snapshot.\n# Other\nOther."
    )
    env = {key: value for key, value in os.environ.items() if not key.startswith(("ALMANAC_", "MEMENTO_"))}
    env["ALMANAC_VAULT_PATH"] = str(vault)
    program = "import sys; sys.path.insert(0, sys.argv.pop(1)); import almanac; assert almanac.__file__.startswith(sys.path[0]); from almanac.__main__ import main; raise SystemExit(main())"
    result = subprocess.run(
        [sys.executable, "-c", program, str(installed), "get", "n#applicability"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    source = json.loads(result.stdout)
    assert "snapshot" in source["content"] and "# Other" not in source["content"]
    assert source["revision"].startswith("sha256:")
    preview = subprocess.run(
        [
            sys.executable,
            "-c",
            program,
            str(installed),
            "context-preview",
            "--profile",
            "orientation",
            "--token-budget",
            "1",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert preview.returncode == 0, preview.stderr
    assert json.loads(preview.stdout)["schema"] == "almanac-context/v1"
