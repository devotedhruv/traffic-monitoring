"""Report exact and optional near-duplicate images before any explicit removal."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

try:
    from ml.scripts.common import IMAGE_EXTENSIONS, sha256_file, write_json
except ModuleNotFoundError:
    from common import IMAGE_EXTENSIONS, sha256_file, write_json


def perceptual_hash(path: Path) -> int | None:
    try:
        import cv2
        frame = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if frame is None:
            return None
        sample = cv2.resize(frame, (9, 8), interpolation=cv2.INTER_AREA)
        value = 0
        for bit in (sample[:, 1:] > sample[:, :-1]).flat:
            value = (value << 1) | int(bit)
        return value
    except ImportError:
        return None


def find_groups(root: Path, use_perceptual: bool, threshold: int) -> dict[str, object]:
    images = sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)
    exact: dict[str, list[Path]] = defaultdict(list)
    for image in images:
        exact[sha256_file(image)].append(image)
    exact_groups = [[str(path) for path in paths] for paths in exact.values() if len(paths) > 1]
    near_groups: list[list[str]] = []
    if use_perceptual:
        hashes = [(image, perceptual_hash(image)) for image in images]
        used: set[Path] = set()
        for index, (image, fingerprint) in enumerate(hashes):
            if image in used or fingerprint is None:
                continue
            group = [image]
            for candidate, candidate_hash in hashes[index + 1:]:
                if candidate in used or candidate_hash is None:
                    continue
                if (fingerprint ^ candidate_hash).bit_count() <= threshold:
                    group.append(candidate)
                    used.add(candidate)
            if len(group) > 1:
                used.add(image)
                near_groups.append([str(path) for path in group])
    return {"root": str(root.resolve()), "images": len(images), "exact_groups": exact_groups, "near_groups": near_groups}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find image duplicates; report-only unless --remove is explicitly supplied.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--perceptual", action="store_true", help="Also calculate dHash near-duplicate groups")
    parser.add_argument("--threshold", type=int, default=4, help="Maximum 64-bit dHash distance")
    parser.add_argument("--report", type=Path, help="JSON output path")
    parser.add_argument("--labels", type=Path, help="Optional matching label root to keep removal orphan-free")
    parser.add_argument("--remove", action="store_true", help="Delete all but the first image in each reported group")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.input.is_dir() or not 0 <= args.threshold <= 64:
        raise SystemExit("--input must be a directory and --threshold must be between 0 and 64")
    report = find_groups(args.input, args.perceptual, args.threshold)
    removed: list[str] = []
    if args.remove:
        keep_or_removed: set[Path] = set()
        for group in [*report["exact_groups"], *report["near_groups"]]:
            for value in group[1:]:
                path = Path(value).resolve()
                if path in keep_or_removed:
                    continue
                if args.input.resolve() not in path.parents:
                    raise SystemExit(f"Refusing to remove path outside input: {path}")
                path.unlink()
                removed.append(str(path))
                if args.labels:
                    label = args.labels.resolve() / f"{path.stem}.txt"
                    if label.is_file():
                        label.unlink()
                        removed.append(str(label))
                keep_or_removed.add(path)
        report["removed"] = removed
    if args.report:
        write_json(args.report, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not args.remove:
        print("Report only: no files were removed. Review groups before invoking --remove.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
