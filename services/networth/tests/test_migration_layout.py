from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_networth_runtime_and_test_paths_are_service_owned():
    assert (ROOT / "services/networth/app/main.py").is_file()
    assert (ROOT / "services/networth/tests/conftest.py").is_file()
    assert not (ROOT / "backend/app").exists()
    assert not (ROOT / "backend/tests").exists()


def test_legacy_backend_packaging_and_scripts_are_removed():
    legacy_artifacts = [
        ROOT / "backend/Dockerfile",
        ROOT / "backend/requirements.txt",
        ROOT / "backend/.dockerignore",
        ROOT / "backend/openapi.json",
        ROOT / "backend/scripts",
    ]
    assert not [path for path in legacy_artifacts if path.exists()]


def test_ci_and_readme_use_networth_service_paths():
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "services/networth/requirements.txt" in ci
    assert "services/networth/app" in ci
    assert "services/networth/tests" in ci
    assert "PYTHONPATH=services/networth" in ci
    assert "backend/" not in ci

    assert "services/networth" in readme
    assert "backend/" not in readme
