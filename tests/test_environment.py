import importlib
import subprocess
import sys

import pytest


@pytest.mark.smoke
def test_python_version() -> None:
    assert sys.version_info[:2] == (3, 10)


@pytest.mark.smoke
@pytest.mark.parametrize(
    "module_name",
    ["requests", "jsonschema", "yaml", "pymysql", "redis"],
)
def test_required_package_can_be_imported(module_name: str) -> None:
    assert importlib.import_module(module_name) is not None


@pytest.mark.smoke
def test_locust_can_start_in_an_isolated_process() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "locust", "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "locust" in result.stdout.lower()
