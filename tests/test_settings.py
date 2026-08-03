from pathlib import Path

from most.services import SettingsService


def test_settings_are_stored_in_app_config(tmp_path: Path):
    settings = SettingsService(tmp_path).initialize()
    loaded = SettingsService(tmp_path).load()
    assert loaded["record_type"] == "APPLICATION_SETTINGS"
    assert loaded["application_instance_id"] == settings.application_instance_id
