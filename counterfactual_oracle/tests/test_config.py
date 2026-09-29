"""
Tests for centralized settings.
"""

from counterfactual_oracle.src.config import Settings


def test_settings_ignore_unrelated_env_file_keys(tmp_path, monkeypatch):
    """A .env shared with other tools may hold keys Settings doesn't declare."""
    env_file = tmp_path / ".env"
    env_file.write_text("SOME_OTHER_TOOL_API_KEY=unused\n")
    monkeypatch.chdir(tmp_path)

    settings = Settings()

    assert not hasattr(settings, "some_other_tool_api_key")
