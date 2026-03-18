# Receives a directory input and a directory outout and a number of samples to sample
# And samples randomly that number of examples

from pathlib import Path
import argparse
import random
import shutil

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark ALL Fault Localization techniques.")
    parser.add_argument(
        "data_path", 
        type=Path,
        help="Path to the directory containing 'killed' and 'original' folders."
    )

    parser.add_argument(
        "dst_path", 
        type=Path,
        help="Path to the destination where to put the sample dataset"
    )

    parser.add_argument(
        "n_samples", 
        type=int,
        help="Number of samples to randomly use"
    )

    args = parser.parse_args()
    base_path = args.data_path
    dst_path = args.dst_path

    killed_dir = base_path / "killed"
    original_dir = base_path / "original"

    dst_killed_dir = dst_path / "killed"
    dst_original_dir = dst_path / "original"
    
    dst_killed_dir.mkdir(parents=True, exist_ok=True)
    dst_original_dir.mkdir(parents=True, exist_ok=True)

    dafny_paths = list(killed_dir.glob("*.dfy"))

    k = args.n_samples
    if k < len(dafny_paths):
        sampled_dafny = random.sample(dafny_paths, args.n_samples)
    else:
        k = len(dafny_paths)
        sampled_dafny = dafny_paths

    print(f"Sampling {k} examples to {args.dst_path}")

    for dafny_file in sampled_dafny:
        base_name_raw = "__".join(dafny_file.stem.split('__')[:-1])
        original_file = original_dir / f"{base_name_raw}.dfy"
        
        diff_file = killed_dir / f"{dafny_file.stem}.txt"

        if original_file.exists():
            shutil.copy2(original_file, dst_original_dir / original_file.name)
        else:
            print(f"Warning: Original file not found: {original_file}")
        
        if diff_file.exists():
            shutil.copy2(diff_file, dst_killed_dir / diff_file.name)
        else:
            print(f"Warning: Diff file not found: {diff_file}")
        
        shutil.copy2(dafny_file, dst_killed_dir / dafny_file.name)

    print(f"Done! Sampled {k} examples to {args.dst_path}")