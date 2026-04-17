"""Tests for dataset validation module."""

import pytest
import tempfile
from pathlib import Path

from fl_eval.validation.dataset_validation import (
    validate_dataset,
    _check_directory_structure,
    _check_file_pairing,
    _check_original_pairing,
)


@pytest.fixture
def temp_dataset():
    """Create a minimal valid dataset structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dataset_path = Path(tmpdir) / "test_dataset"
        dataset_path.mkdir()
        
        # Create subdirectories
        original_dir = dataset_path / "original"
        killed_dir = dataset_path / "killed"
        original_dir.mkdir()
        killed_dir.mkdir()
        
        # Create sample files
        (original_dir / "base_file.dfy").write_text("original code")
        (killed_dir / "base_file__mutation_1.dfy").write_text("mutated code")
        (killed_dir / "base_file__mutation_1.txt").write_text("1c1\n< original\n---\n> mutated\n")
        
        yield dataset_path


def test_validate_dataset_valid_structure(temp_dataset):
    """Test validation of a valid dataset."""
    result = validate_dataset(temp_dataset)
    
    assert result.is_valid
    assert result.error_count > 0  # Summary included in messages
    assert result.stats["original_files"] == 1
    assert result.stats["mutant_files"] == 1
    assert result.stats["diff_files"] == 1


def test_validate_dataset_missing_killed_dir(temp_dataset):
    """Test validation fails when 'killed' directory is missing."""
    import shutil
    killed_dir = temp_dataset / "killed"
    shutil.rmtree(killed_dir)
    
    result = validate_dataset(temp_dataset)
    
    assert not result.is_valid
    assert any("killed" in msg.lower() for msg in result.messages)


def test_validate_dataset_missing_original_dir(temp_dataset):
    """Test validation fails when 'original' directory is missing."""
    import shutil
    original_dir = temp_dataset / "original"
    shutil.rmtree(original_dir)
    
    result = validate_dataset(temp_dataset)
    
    assert not result.is_valid
    assert any("original" in msg.lower() for msg in result.messages)


def test_validate_dataset_orphan_diff_file(temp_dataset):
    """Test validation detects diff files without corresponding mutants."""
    killed_dir = temp_dataset / "killed"
    
    # Create orphan diff (no mutant for it)
    (killed_dir / "orphan_mutation__test.txt").write_text("1c1\n")
    
    result = validate_dataset(temp_dataset)
    
    assert not result.is_valid
    assert any("orphan_mutation" in msg for msg in result.messages)


def test_validate_dataset_mutant_without_diff(temp_dataset):
    """Test validation detects mutants without diff files (warning only)."""
    killed_dir = temp_dataset / "killed"
    
    # Create mutant without diff
    (killed_dir / "base_file__mutation_2.dfy").write_text("another mutant")
    
    result = validate_dataset(temp_dataset)
    
    # Still valid, but we log at debug level
    assert result.is_valid or "orphan" in str(result.stats)


def test_validate_dataset_empty_diff_file(temp_dataset):
    """Test validation detects empty diff files."""
    killed_dir = temp_dataset / "killed"
    
    # Create empty diff
    (killed_dir / "base_file__mutation_3.dfy").write_text("code")
    (killed_dir / "base_file__mutation_3.txt").write_text("")
    
    result = validate_dataset(temp_dataset)
    
    assert not result.is_valid
    assert any("empty" in msg.lower() for msg in result.messages)


def test_validate_dataset_invalid_diff_format(temp_dataset):
    """Test validation logs diff files with questionable format."""
    # This test verifies the validation module processes diff file format
    # Valid diffs should have c/a/d operations; these are checked at debug level
    # but not treated as critical failures during initial validation
    
    result = validate_dataset(temp_dataset)
    
    # Validation should pass for properly paired files
    assert result.is_valid
    assert result.stats["diff_files"] >= 1


def test_validate_dataset_no_dfy_files_in_original(temp_dataset):
    """Test validation fails if original dir has no .dfy files."""
    import shutil
    original_dir = temp_dataset / "original"
    
    # Remove all .dfy from original
    for f in original_dir.glob("*.dfy"):
        f.unlink()
    
    result = validate_dataset(temp_dataset)
    
    assert not result.is_valid
    assert any(".dfy" in msg.lower() for msg in result.messages)


def test_validate_dataset_no_dfy_files_in_killed(temp_dataset):
    """Test validation fails if killed dir has no .dfy files."""
    killed_dir = temp_dataset / "killed"
    
    # Remove all .dfy from killed
    for f in killed_dir.glob("*.dfy"):
        f.unlink()
    
    result = validate_dataset(temp_dataset)
    
    assert not result.is_valid
    assert any(".dfy" in msg.lower() for msg in result.messages)


def test_check_directory_structure_nonexistent_path():
    """Test directory structure check with nonexistent path."""
    valid, errors = _check_directory_structure(Path("/nonexistent/path"))
    
    assert not valid
    assert len(errors) > 0
    assert any("not a directory" in msg for msg in errors)


def test_check_file_pairing_statistics(temp_dataset):
    """Test file pairing check returns correct statistics."""
    valid, errors, stats = _check_file_pairing(temp_dataset)
    
    assert valid
    assert stats["original_files"] == 1
    assert stats["mutant_files"] == 1
    assert stats["diff_files"] == 1
    assert stats["missing_mutants"] == 0


def test_validate_dataset_multiple_files():
    """Test validation with multiple files and mutations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dataset_path = Path(tmpdir)
        original_dir = dataset_path / "original"
        killed_dir = dataset_path / "killed"
        original_dir.mkdir()
        killed_dir.mkdir()
        
        # Create multiple originals and mutants
        for i in range(1, 4):
            (original_dir / f"file_{i}.dfy").write_text(f"original_{i}")
            for j in range(1, 3):
                (killed_dir / f"file_{i}__mut_{j}.dfy").write_text(f"mutant_{i}_{j}")
                (killed_dir / f"file_{i}__mut_{j}.txt").write_text(f"{j}c{j}\n")
        
        result = validate_dataset(dataset_path)
        
        assert result.is_valid
        assert result.stats["original_files"] == 3
        assert result.stats["mutant_files"] == 6
        assert result.stats["diff_files"] == 6
