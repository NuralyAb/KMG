from pathlib import Path

import pytest

from glava_server.config import ConfigError, Settings, settings_from_env


def test_root_defaults_to_parent_of_server_folder() -> None:
    settings = settings_from_env({})

    assert settings.root == Path(__file__).resolve().parents[2]
    assert settings.run_command == ("uv", "run", "glava")
    assert settings.port == 8200


def test_environment_overrides_root_command_and_port(tmp_path: Path) -> None:
    env = {"GLAVA_ROOT": str(tmp_path), "GLAVA_RUN_COMMAND": '["python", "fake.py"]', "GLAVA_PORT": "8300"}

    settings = settings_from_env(env)

    assert (settings.root, settings.run_command, settings.port) == (tmp_path.resolve(), ("python", "fake.py"), 8300)


@pytest.mark.parametrize("env", [
    {"GLAVA_ROOT": "Z:/нет/такой/папки"}, {"GLAVA_RUN_COMMAND": "uv run"}, {"GLAVA_RUN_COMMAND": "[]"}, {"GLAVA_PORT": "много"}, {"GLAVA_PORT": "0"},
])
def test_wrong_environment_is_rejected(env: dict[str, str]) -> None:
    with pytest.raises(ConfigError):
        settings_from_env(env)


def test_settings_are_immutable(tmp_path: Path) -> None:
    settings = Settings(root=tmp_path)

    with pytest.raises(AttributeError):
        settings.port = 1  # type: ignore[misc]
