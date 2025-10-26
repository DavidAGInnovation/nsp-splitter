#!/usr/bin/env python3

"""Split Nintendo Switch NSP files into FAT32-friendly parts.

The script intentionally mirrors the behaviour of community tools such as NxSplit
so that Atmosphere and other homebrew loaders can read the generated parts.  By
default each chunk is 4 GB (~3.73 GiB), which keeps the resulting files within
the FAT32 file-size limit with a small safety margin.  You can optionally adjust
the chunk size for testing or other needs.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Iterable, Iterator, List, Tuple

DEFAULT_CHUNK_SIZE = 4_000_000_000  # 4 GB (decimal) keeps well under FAT32 cap
READ_BUFFER = 8 * 1024**2  # 8 MiB
VALID_EXTENSIONS = {".nsp", ".nsz", ".xci"}


class SplitError(RuntimeError):
    """Raised when splitting fails."""


def iter_targets(paths: Iterable[str], recursive: bool = False) -> Iterator[str]:
    """Yield all NSP-like files found in the provided paths."""
    for raw_path in paths:
        path = os.path.abspath(raw_path)
        if not os.path.exists(path):
            raise SplitError(f"Path not found: {raw_path}")
        if os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                for name in sorted(files):
                    if os.path.splitext(name)[1].lower() in VALID_EXTENSIONS:
                        yield os.path.join(root, name)
                if not recursive:
                    break
        else:
            if os.path.splitext(path)[1].lower() not in VALID_EXTENSIONS:
                raise SplitError(f"Unsupported file type: {raw_path}")
            yield path


def human_readable_size(size: int) -> str:
    """Return a Finder-style representation (decimal KB/MB/GB)."""
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1000 or unit == units[-1]:
            return f"{value:.2f} {unit}"
        value /= 1000
    return f"{size} B"


def parse_size(value: str) -> int:
    """Parse strings such as `'2G'` or `'512M'` into bytes."""
    suffixes = {
        "kib": 1024,
        "mib": 1024**2,
        "gib": 1024**3,
        "tib": 1024**4,
        "kb": 1000,
        "mb": 1000**2,
        "gb": 1000**3,
        "tb": 1000**4,
        "k": 1024,
        "m": 1024**2,
        "g": 1024**3,
        "t": 1024**4,
    }
    stripped = value.strip().lower()
    if stripped.isdigit():
        return int(stripped)
    for suffix in sorted(suffixes, key=len, reverse=True):
        if stripped.endswith(suffix):
            number = float(stripped[: -len(suffix)])
            if number <= 0:
                raise argparse.ArgumentTypeError("size must be positive")
            return int(number * suffixes[suffix])
    raise argparse.ArgumentTypeError(
        "size must be an integer byte count or end with K/M/G/T"
    )


def build_part_name(base_path: str, index: int) -> str:
    """Return the part filename keeping the original extension suffix."""
    stem, ext = os.path.splitext(base_path)
    suffix = f".{index:02d}"
    if ext:
        return f"{stem}{suffix}{ext}"
    return f"{base_path}{suffix}"


def split_file(
    file_path: str,
    output_dir: str | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overwrite: bool = False,
    dry_run: bool = False,
) -> List[str]:
    """Split a single NSP file and return the list of generated parts."""
    file_size = os.path.getsize(file_path)
    if file_size <= chunk_size:
        print(f"[skip] {os.path.basename(file_path)} is already ≤ chunk size.")
        return []

    if output_dir is None:
        output_dir = os.path.dirname(file_path)
    os.makedirs(output_dir, exist_ok=True)

    base_name = os.path.basename(file_path)
    output_base = os.path.join(output_dir, base_name)

    parts: List[str] = []
    total_parts = (file_size + chunk_size - 1) // chunk_size

    print(
        f"[info] Splitting {base_name} ({human_readable_size(file_size)}) "
        f"into {total_parts} parts of {human_readable_size(chunk_size)}."
    )

    if dry_run:
        for index in range(total_parts):
            parts.append(build_part_name(output_base, index))
        print("[info] Dry run: no files were written.")
        return parts

    buffer = bytearray(READ_BUFFER)

    with open(file_path, "rb") as source:
        for index in range(total_parts):
            part_path = build_part_name(output_base, index)
            if os.path.exists(part_path) and not overwrite:
                raise SplitError(
                    f"Refusing to overwrite existing part: {part_path}. "
                    "Use --overwrite to replace."
                )
            part_bytes = 0
            remaining = min(chunk_size, file_size - source.tell())
            with open(part_path, "wb") as target:
                while part_bytes < remaining:
                    to_read = min(len(buffer), remaining - part_bytes)
                    read = source.readinto(memoryview(buffer)[:to_read])
                    if read == 0:
                        raise SplitError("Unexpected end of file")
                    target.write(buffer[:read])
                    part_bytes += read
            parts.append(part_path)
            print(
                f"  [done] {os.path.basename(part_path)} → "
                f"{human_readable_size(part_bytes)}"
            )

    print(f"[info] Finished splitting {base_name}.")
    return parts


def confirm_overwrite(parts: Iterable[str]) -> None:
    """Ask the user to confirm overwriting existing parts."""
    existing = [path for path in parts if os.path.exists(path)]
    if not existing:
        return
    print("[warn] The following parts already exist:")
    for path in existing:
        print(f"       {path}")
    response = input("Overwrite? [y/N]: ").strip().lower()
    if response not in {"y", "yes"}:
        raise SplitError("Operation cancelled by user.")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Split NSP/NSZ/XCI files into FAT32-friendly chunks."
    )
    parser.add_argument(
        "targets",
        nargs="*",
        help="NSP/NSZ/XCI files or directories to process.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Directory for output parts (defaults to each file's directory).",
    )
    parser.add_argument(
        "--chunk-size",
        default=DEFAULT_CHUNK_SIZE,
        type=parse_size,
        help="Chunk size (supports suffixes K/M/G/T with optional B or iB). Default: 4GB (~3.73 GiB).",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Recursively traverse provided directories.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite parts if they already exist.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without writing files.",
    )

    args = parser.parse_args(argv)

    if not args.targets:
        try:
            entered = input(
                "Enter path to NSP/NSZ/XCI file or directory: "
            ).strip()
        except EOFError:
            print("[error] No input received; exiting.", file=sys.stderr)
            return 1
        if not entered:
            print("[error] No path provided; exiting.", file=sys.stderr)
            return 1
        args.targets = [entered]

    try:
        files = list(iter_targets(args.targets, recursive=args.recursive))
    except SplitError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    if not files:
        print("[info] No NSP files found; nothing to do.")
        return 0

    all_parts: List[Tuple[str, List[str]]] = []
    for file_path in files:
        intended_parts = [
            build_part_name(
                os.path.join(args.output or os.path.dirname(file_path), os.path.basename(file_path)),
                index,
            )
            for index in range(
                (os.path.getsize(file_path) + args.chunk_size - 1) // args.chunk_size
            )
        ]
        if not args.dry_run and intended_parts:
            # Skip confirmation when overwrite explicitly requested.
            if not args.overwrite:
                confirm_overwrite(intended_parts)

        try:
            generated_parts = split_file(
                file_path=file_path,
                output_dir=args.output,
                chunk_size=args.chunk_size,
                overwrite=args.overwrite,
                dry_run=args.dry_run,
            )
        except SplitError as exc:
            print(f"[error] {exc}", file=sys.stderr)
            return 1
        all_parts.append((file_path, generated_parts))

    if args.dry_run:
        print("[info] Dry run completed successfully.")
    else:
        print("[info] All files processed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
