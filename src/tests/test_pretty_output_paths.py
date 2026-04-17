from pathlib import Path

import config as gl


def test_get_pretty_output_file_path_uses_dataset_and_technique() -> None:
    mutant = Path("dataset/data/pos_test/killed/foo__mut1.dfy")
    path = gl.get_pretty_output_file_path(mutant, "CNTM")

    assert path == gl.PRETTY_OUTPUTS_DIR / "pos_test" / "CNTM" / "foo__mut1.dfy.json"


def test_get_dataset_pretty_output_dir_uses_dataset_leaf_name(tmp_path: Path) -> None:
    dataset = tmp_path / "custom_dataset"
    dataset.mkdir(parents=True)

    path = gl.get_dataset_pretty_output_dir(dataset)
    assert path == gl.PRETTY_OUTPUTS_DIR / "custom_dataset"
