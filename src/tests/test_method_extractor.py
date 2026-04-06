from pathlib import Path

import config as gl
import fl_eval.util.run_external_cmd as run_cmd
from fl_eval.core import method_extractor as me


def test_extract_method_uses_dedicated_disk_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(gl, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(me, "_find_executable", lambda *_args, **_kwargs: Path("/tmp/fake_exec"))

    file_path = tmp_path / "sample.dfy"
    file_path.write_text("method M() {}\n", encoding="utf-8")

    call_count = {"n": 0}

    def fake_run(_cmd):
        call_count["n"] += 1
        return (run_cmd.Status.OK, "Method 'M': spans lines 10 to 20\n", "")

    monkeypatch.setattr(run_cmd, "run_external_cmd", fake_run)

    me.clear_cache()
    first = me.extract_method_containing_line(file_path, 12)
    assert first == ("M", 10, 20)
    assert call_count["n"] == 1

    # Clear only in-memory cache; second call should hit disk cache and skip external command.
    me.clear_cache()
    second = me.extract_method_containing_line(file_path, 12)
    assert second == ("M", 10, 20)
    assert call_count["n"] == 1

    cache_dir = tmp_path / "method_lines"
    assert cache_dir.exists()
    assert any(path.suffix == ".json" for path in cache_dir.iterdir())


def test_extract_method_caches_empty_spans_on_disk(tmp_path, monkeypatch):
    monkeypatch.setattr(gl, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(me, "_find_executable", lambda *_args, **_kwargs: Path("/tmp/fake_exec"))

    file_path = tmp_path / "no_methods.dfy"
    file_path.write_text("const x := 1\n", encoding="utf-8")

    call_count = {"n": 0}

    def fake_run(_cmd):
        call_count["n"] += 1
        return (run_cmd.Status.OK, "", "")

    monkeypatch.setattr(run_cmd, "run_external_cmd", fake_run)

    me.clear_cache()
    first = me.extract_method_containing_line(file_path, 1)
    assert first is None
    assert call_count["n"] == 1

    me.clear_cache()
    second = me.extract_method_containing_line(file_path, 1)
    assert second is None
    # No second external call expected because empty result is cached on disk.
    assert call_count["n"] == 1
