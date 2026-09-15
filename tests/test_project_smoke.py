from pathlib import Path


def test_project_declares_test_foundation_metadata() -> None:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"

    assert pyproject_path.exists(), "pyproject.toml is required for the test foundation"

    pyproject = pyproject_path.read_text(encoding="utf-8")

    assert "[project]" in pyproject
    assert 'name = "tip"' in pyproject
    assert "[tool.pytest.ini_options]" in pyproject
    assert 'testpaths = ["tests"]' in pyproject
