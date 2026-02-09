"""
Tests for infrastructure configuration and setup.

This module tests the infrastructure configuration without requiring
AWS services to be running or mocked.
"""

import pytest
from pathlib import Path


def test_cdk_json_exists():
    """Test that cdk.json configuration file exists."""
    cdk_json = Path("cdk.json")
    assert cdk_json.exists(), "cdk.json file should exist"


def test_infrastructure_directory_exists():
    """Test that infrastructure directory exists with required files."""
    infra_dir = Path("infrastructure")
    assert infra_dir.exists(), "infrastructure directory should exist"
    assert (infra_dir / "app.py").exists(), "infrastructure/app.py should exist"
    assert (infra_dir / "stacks").exists(), "infrastructure/stacks directory should exist"
    assert (infra_dir / "stacks" / "krishimitra_stack.py").exists(), "krishimitra_stack.py should exist"


def test_requirements_files_exist():
    """Test that all requirements files exist."""
    assert Path("requirements.txt").exists(), "requirements.txt should exist"
    assert Path("requirements-dev.txt").exists(), "requirements-dev.txt should exist"
    assert Path("infrastructure/requirements.txt").exists(), "infrastructure/requirements.txt should exist"


def test_pyproject_toml_exists():
    """Test that pyproject.toml exists for Poetry configuration."""
    pyproject = Path("pyproject.toml")
    assert pyproject.exists(), "pyproject.toml should exist"


def test_env_example_exists():
    """Test that .env.example exists for environment configuration."""
    env_example = Path(".env.example")
    assert env_example.exists(), ".env.example should exist"


def test_deployment_script_exists():
    """Test that deployment script exists."""
    deploy_script = Path("scripts/deploy.py")
    assert deploy_script.exists(), "scripts/deploy.py should exist"


def test_test_directory_structure():
    """Test that test directory has proper structure."""
    tests_dir = Path("tests")
    assert tests_dir.exists(), "tests directory should exist"
    assert (tests_dir / "conftest.py").exists(), "tests/conftest.py should exist"
    assert (tests_dir / "utils").exists(), "tests/utils directory should exist"
    assert (tests_dir / "utils" / "aws_mocks.py").exists(), "tests/utils/aws_mocks.py should exist"


def test_src_directory_structure():
    """Test that src directory has proper structure."""
    src_dir = Path("src/krishimitra")
    assert src_dir.exists(), "src/krishimitra directory should exist"
    assert (src_dir / "main.py").exists(), "src/krishimitra/main.py should exist"
    assert (src_dir / "core").exists(), "src/krishimitra/core directory should exist"
    assert (src_dir / "api").exists(), "src/krishimitra/api directory should exist"
    assert (src_dir / "agents").exists(), "src/krishimitra/agents directory should exist"
    assert (src_dir / "models").exists(), "src/krishimitra/models directory should exist"


def test_infrastructure_stack_imports():
    """Test that infrastructure stack can be imported."""
    try:
        from infrastructure.stacks.krishimitra_stack import KrishiMitraStack
        assert KrishiMitraStack is not None
    except ImportError as e:
        pytest.fail(f"Failed to import KrishiMitraStack: {e}")


def test_config_module_imports():
    """Test that configuration module can be imported."""
    try:
        from src.krishimitra.core.config import Settings, get_settings
        assert Settings is not None
        assert get_settings is not None
    except ImportError as e:
        pytest.fail(f"Failed to import config module: {e}")


def test_fastapi_app_imports():
    """Test that FastAPI app can be imported."""
    try:
        from src.krishimitra.main import app
        assert app is not None
        assert hasattr(app, 'routes')
    except ImportError as e:
        pytest.fail(f"Failed to import FastAPI app: {e}")
