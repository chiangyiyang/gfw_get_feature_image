import argparse
import base64
import json
from pathlib import Path
from typing import Iterable, List, Tuple


def find_bin_files(folder: Path) -> List[Path]:
    return sorted(folder.glob("*.bin"))


def decode_entry(entry: dict) -> Tuple[str, bytes]:
    """Return output filename and decoded bytes from a single JSON entry."""
    name = entry.get("name") or "image.png"
    name = Path(name).name  # avoid nested paths
    if not name.lower().endswith(".png"):
        name = f"{name}.png"

    data_field = entry.get("data") or ""
    # Expect format like "image/png;base64,<payload>"
    if "," in data_field:
        _, _, b64_data = data_field.partition(",")
    else:
        b64_data = data_field
    try:
        decoded = base64.b64decode(b64_data)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Failed to decode base64 for {name}: {exc}") from exc
    return name, decoded


def convert_file(bin_path: Path, output_dir: Path) -> List[Path]:
    content = json.loads(bin_path.read_text())
    if not isinstance(content, list):
        raise ValueError(f"{bin_path} does not contain a JSON array")

    output_paths: List[Path] = []
    for entry in content:
        if not isinstance(entry, dict):
            continue
        try:
            filename, decoded = decode_entry(entry)
        except ValueError as exc:
            print(exc)
            continue
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / filename
        out_path.write_bytes(decoded)
        output_paths.append(out_path)
    return output_paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert images/*.bin JSON payloads to .png files."
    )
    parser.add_argument(
        "--input-dir",
        default="images",
        help="Directory containing .bin files (default: images).",
    )
    parser.add_argument(
        "--output-dir",
        default="images",
        help="Directory to write .png files (default: images).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    bin_files = find_bin_files(input_dir)
    if not bin_files:
        print(f"No .bin files found in {input_dir}")
        return

    total_written = 0
    for bin_file in bin_files:
        try:
            outputs = convert_file(bin_file, output_dir)
            print(f"{bin_file} -> {len(outputs)} file(s)")
            total_written += len(outputs)
        except Exception as exc:  # noqa: BLE001
            print(f"Failed to convert {bin_file}: {exc}")
    print(f"Done. Wrote {total_written} file(s) to {output_dir}")


if __name__ == "__main__":
    main()
