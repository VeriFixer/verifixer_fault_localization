from pathlib import Path
from types import SimpleNamespace
import json
import sys

import config as gl
from fl_eval.core.abstract import FLTechnique
from fl_eval.metrics.scoring import compute_exam_score, save_to_file_output, load_from_file_output
import fl_eval.util.run_external_cmd as run_cmd


class DummyTechnique(FLTechnique):
    def get_fault_localization(self, file: Path) -> list[int]:
        return [1, 2]


def test_save_load_rich_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(gl, "CACHE_DIR", tmp_path)

    flt = DummyTechnique(name="dummy")
    gtruth = SimpleNamespace(mutantfile=Path("mutant.dfy"))

    metadata = {
        "status": "OK",
        "command": [Path("/tmp/tool"), "--arg"],
        "stdout": "hello",
        "stderr": "",
    }

    save_to_file_output(flt, gtruth, [3, 4], metadata)
    loaded = load_from_file_output(flt, gtruth)

    assert loaded == [3, 4]

    cache_file = tmp_path / "dummy" / "mutant.dfy.json"
    payload = json.loads(cache_file.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 2
    assert payload["predictions"] == [3, 4]
    # Path serialized via default=str
    assert payload["execution_metadata"]["command"][0] == "/tmp/tool"


def test_load_legacy_cache_list_format(tmp_path, monkeypatch):
    monkeypatch.setattr(gl, "CACHE_DIR", tmp_path)

    flt = DummyTechnique(name="legacy")
    gtruth = SimpleNamespace(mutantfile=Path("legacy.dfy"))

    legacy_file = tmp_path / "legacy" / "legacy.dfy.json"
    legacy_file.parent.mkdir(parents=True, exist_ok=True)
    legacy_file.write_text("[10, 20, 30]", encoding="utf-8")

    loaded = load_from_file_output(flt, gtruth)
    assert loaded == [10, 20, 30]


def test_compute_exam_score_writes_rich_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(gl, "CACHE_DIR", tmp_path)

    flt = DummyTechnique(name="compute")
    gtruth = SimpleNamespace(
        mutantfile=Path("sample.dfy"),
        ground_truth=1,
        startLine=1,
        endLine=5,
    )

    monkeypatch.setattr(
        run_cmd,
        "get_last_execution_metadata",
        lambda: {"status": "OK", "command": [Path("/tmp/fake_tool")], "stdout": "ok", "stderr": ""},
    )

    out = compute_exam_score(flt, gtruth)
    assert out.filename == "sample.dfy"

    payload_file = tmp_path / "compute" / "sample.dfy.json"
    payload = json.loads(payload_file.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 2
    assert payload["execution_metadata"]["status"] == "OK"
    assert payload["execution_metadata"]["command"][0] == "/tmp/fake_tool"


def test_run_external_cmd_records_last_metadata():
    status, stdout, stderr = run_cmd.run_external_cmd([sys.executable, "-c", "print('hello')"])

    assert status == run_cmd.Status.OK
    assert "hello" in stdout
    assert stderr == ""

    meta = run_cmd.get_last_execution_metadata()
    assert meta is not None
    assert meta["status"] == "OK"
    assert "command" in meta
    assert "timestamp_utc" in meta
