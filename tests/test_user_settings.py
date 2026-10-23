import json

from peke import config


def test_settings_write_and_read_use_same_canonical_path(tmp_path, monkeypatch):
    path = tmp_path / "Peke" / "peke" / "settings.json"
    monkeypatch.setattr(config, "user_settings_path", lambda: path)
    saved = config.save_user_settings({"MODEL_PATH": str(tmp_path / "tiny.gguf"), "REA_COMMAND": "rea --json"})
    assert saved == path
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["MODEL_PATH"].endswith("tiny.gguf")
    assert raw["REA_COMMAND"] == "rea --json"
    assert path.read_text(encoding="utf-8").endswith("\n")


def test_settings_save_merges_instead_of_erasing_other_pages(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    monkeypatch.setattr(config, "user_settings_path", lambda: path)
    config.save_user_settings({"MODEL_PATH": "/models/local.gguf", "REA_COMMAND": "rea"})
    config.save_user_settings({"REQUEST_DELAY_SECONDS": 2.5})
    values = json.loads(path.read_text(encoding="utf-8"))
    assert values == {
        "MODEL_PATH": "/models/local.gguf",
        "REA_COMMAND": "rea",
        "REQUEST_DELAY_SECONDS": 2.5,
    }


def test_load_settings_reads_rea_command_from_user_config(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"REA_COMMAND": "python fake_rea.py", "REA_CDP_ENDPOINT": "http://127.0.0.1:9333", "N_CTX": 1024}), encoding="utf-8")
    monkeypatch.setattr(config, "user_settings_path", lambda: path)
    monkeypatch.delenv("REA_COMMAND", raising=False)
    monkeypatch.delenv("N_CTX", raising=False)
    settings = config.load_settings()
    assert settings.rea_command == "python fake_rea.py"
    assert settings.rea_cdp_endpoint == "http://127.0.0.1:9333"
    assert settings.n_ctx == 1024
