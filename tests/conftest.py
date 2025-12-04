"""Pytest configuration and fixtures.

Loads environment variables from .env file for local testing.
"""

import os
import sys
from pathlib import Path

import pytest

# Add src/functions to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "functions"))


def pytest_configure(config):
    """Load .env file before tests run."""
    try:
        from dotenv import load_dotenv

        # Load from project root .env file
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            print(f"\n[OK] Loaded environment from {env_path}")
        else:
            print(f"\n[WARN] No .env file found at {env_path}")
            print("  Copy .env.example to .env and fill in your values for integration tests")
    except ImportError:
        pass  # python-dotenv not installed, skip


@pytest.fixture
def env_vars():
    """Fixture to check required environment variables.

    Use this fixture in integration tests that need real Azure resources.
    """
    required = [
        "DOC_INTEL_ENDPOINT",
        "DOC_INTEL_API_KEY",
        "COSMOS_ENDPOINT",
    ]

    missing = [var for var in required if not os.getenv(var)]

    if missing:
        pytest.skip(f"Missing required environment variables: {', '.join(missing)}")

    return {var: os.getenv(var) for var in required}
