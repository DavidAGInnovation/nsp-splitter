## NSP Splitter Script

This repository contains `scripts/split_nsp.py`, a lightweight Python utility for splitting Nintendo Switch NSP/NSZ/XCI dumps into FAT32-friendly chunks.  The script mirrors the file naming conventions used by community tools such as NxSplit so Atmosphere, Tinfoil, DBI, and similar homebrew apps recognise the parts automatically.

### Why split NSP files?

Many Switch SD cards are formatted as FAT32, which cannot store files larger than 4 GiB.  Large games can exceed this limit, so they must be split before copying to the SD card.  Splitting into 4 GB (decimal) parts keeps each file well under the FAT32 limit (~3.73 GiB) while still minimising the number of pieces.

### Requirements

- Python 3.8 or newer (`python3 --version` to check).
- Enough free disk space to hold the generated parts.

### Usage

```bash
# Split a single NSP in-place (prompt appears if you omit the path)
python3 scripts/split_nsp.py "/path/to/game.nsp"

# Split all NSPs in a directory recursively, sending parts to another folder
python3 scripts/split_nsp.py --recursive --output "/Volumes/SDCARD" games/

# Dry run to verify how many parts will be created
python3 scripts/split_nsp.py --dry-run "/path/to/game.nsp"

# Force overwrite if .nsp.00 files already exist
python3 scripts/split_nsp.py --overwrite "/path/to/game.nsp"
```

If you run the script without arguments it will prompt for a file or directory path.  Arguments support glob expansion, so quoting is recommended when paths contain spaces.

### Options

- `--chunk-size SIZE` — Size of each part (default: `4GB`).  Accepts suffixes such as `MB`, `GB`, `MiB`, or raw bytes (e.g. `4294967295`).  Using `4GB` leaves a safety margin under FAT32’s 4 GiB limit.  If you need binary sizes, use `4GiB` instead.
- `--output DIR` — Directory for the generated parts.  Defaults to the same directory as each source file.
- `--recursive` — Search provided directories recursively for supported files.
- `--overwrite` — Replace existing `.nsp.00`, `.nsp.01`, … files without prompting.
- `--dry-run` — Print the intended actions without writing any files.

### Output format

Parts follow the conventional `<filename>.nsp.00`, `.01`, etc. naming scheme.  Each chunk is written sequentially, streaming data in 8 MiB blocks to keep memory usage low.  When copying to your SD card, transfer the base `.nsp` file alongside the numbered parts.

### Notes

- Supported extensions: `.nsp`, `.nsz`, `.xci`.
- The script refuses to overwrite existing split parts unless `--overwrite` is provided or you confirm at runtime.
- Copy the resulting files to your `switch/` or installation directory as required by your installer.

### License

This script is provided as-is for personal archival use.  Ensure you comply with local laws and own the content you process.

