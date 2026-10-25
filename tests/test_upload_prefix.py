"""upload_to_r2 --prefix: versioned keys, prefixed ETag comparison. S3 is fully mocked."""
import hashlib
import importlib.util
import logging
import sys
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def up(tmp_path, monkeypatch):
    pytest.importorskip("boto3")
    spec = importlib.util.spec_from_file_location("upload_to_r2", ROOT / "scripts" / "upload_to_r2.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    data = tmp_path / "data"
    (data / "journals").mkdir(parents=True)
    (data / "journals" / "aging-cell.json").write_text('{"a": 1}')
    (data / "index.json").write_text("[]")
    monkeypatch.setattr(mod, "WEBSITE_DATA_DIR", str(data))
    monkeypatch.setattr(mod, "R2_PUBLIC_URL", "https://cdn.example")
    client = mock.MagicMock()
    monkeypatch.setattr(mod, "get_client", lambda: client)
    mod.client = client
    mod.data = data
    return mod


def run(up, monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["upload_to_r2.py", *argv])
    up.main()


def uploaded_keys(up):
    return sorted(c.args[2] for c in up.client.upload_file.call_args_list)


def test_prefix_flag_prefixes_keys(up, monkeypatch):
    monkeypatch.setattr(up, "list_remote_etags", lambda c, p="": {})
    run(up, monkeypatch, "--prefix", "v2")
    assert uploaded_keys(up) == ["v2/index.json", "v2/journals/aging-cell.json"]


def test_default_uses_config_prefix(up, monkeypatch):
    monkeypatch.setattr(up, "R2_DATA_PREFIX", "v9")
    monkeypatch.setattr(up, "list_remote_etags", lambda c, p="": {})
    run(up, monkeypatch)
    assert uploaded_keys(up) == ["v9/index.json", "v9/journals/aging-cell.json"]


def test_config_default_is_v2():
    sys.path.insert(0, str(ROOT))
    from src.pipeline import config
    assert config.R2_DATA_PREFIX == "v2"


def test_empty_prefix_is_bucket_root(up, monkeypatch):
    monkeypatch.setattr(up, "list_remote_etags", lambda c, p="": {})
    run(up, monkeypatch, "--prefix", "")
    assert uploaded_keys(up) == ["index.json", "journals/aging-cell.json"]


def test_slashes_normalized(up, monkeypatch):
    monkeypatch.setattr(up, "list_remote_etags", lambda c, p="": {})
    run(up, monkeypatch, "--prefix", "/v2/")
    assert uploaded_keys(up) == ["v2/index.json", "v2/journals/aging-cell.json"]


def test_etag_compares_prefixed_keys_and_lists_by_prefix(up, monkeypatch):
    seen = []
    md5 = lambda p: hashlib.md5(p.read_bytes()).hexdigest()
    remote = {
        "v2/journals/aging-cell.json": md5(up.data / "journals" / "aging-cell.json"),
        "v2/index.json": md5(up.data / "index.json"),
        # unprefixed (legacy) keys must not matter
        "journals/aging-cell.json": "stale",
    }

    def fake_list(client, prefix=""):
        seen.append(prefix)
        return remote

    monkeypatch.setattr(up, "list_remote_etags", fake_list)
    run(up, monkeypatch, "--prefix", "v2")
    assert seen == ["v2"]
    up.client.upload_file.assert_not_called()


def test_list_remote_etags_passes_prefix_to_s3(up):
    pager = mock.MagicMock()
    pager.paginate.return_value = [{"Contents": [{"Key": "v2/x.json", "ETag": '"AB"'}]}]
    up.client.get_paginator.return_value = pager
    assert up.list_remote_etags(up.client, "v2") == {"v2/x.json": "ab"}
    assert pager.paginate.call_args.kwargs["Prefix"] == "v2/"
    up.list_remote_etags(up.client, "")
    assert "Prefix" not in pager.paginate.call_args.kwargs


def test_dry_run_prints_prefixed_keys(up, monkeypatch, caplog):
    monkeypatch.setattr(up, "list_remote_etags", lambda c, p="": {})
    with caplog.at_level(logging.INFO, logger="upload_r2"):
        run(up, monkeypatch, "--prefix", "v2", "--dry-run")
    assert "[dry-run] v2/journals/aging-cell.json" in caplog.text
    up.client.upload_file.assert_not_called()


def test_live_url_uses_prefix(up, monkeypatch, caplog):
    monkeypatch.setattr(up, "list_remote_etags", lambda c, p="": {})
    with caplog.at_level(logging.INFO, logger="upload_r2"):
        run(up, monkeypatch, "--prefix", "v2")
    assert "Live at: https://cdn.example/v2/index.json" in caplog.text
