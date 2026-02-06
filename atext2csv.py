#!/usr/bin/env python3
"""
atext2csv - Export aText snippets to CSV, JSON, Espanso YAML, or plain text.

aText (.atext) files use an undocumented format: a JSON header, a null byte
separator, and an LZ4-compressed JSON body containing all snippets and groups.

Usage:
    python atext2csv.py                          # auto-find Data.atext, export all formats
    python atext2csv.py backup.atext --csv       # export specific file as CSV only
    python atext2csv.py -o ./exports --espanso   # export Espanso YAML to ./exports/

Requires: pip install lz4
"""

import argparse
import csv
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import lz4.frame
except ImportError:
    print("Error: lz4 package required. Install with: pip install lz4")
    sys.exit(1)

__version__ = "1.0.0"

# ── aText data locations ─────────────────────────────────────────────────────

def find_atext_data() -> Path | None:
    """Auto-detect the default Data.atext location on Windows or macOS."""
    system = platform.system()

    if system == "Windows":
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            path = Path(local) / "com.trankynam.aText" / "Data" / "Data.atext"
            if path.exists():
                return path

    elif system == "Darwin":
        path = Path.home() / "Library" / "Application Support" / "com.trankynam.aText" / "Data.atext"
        if path.exists():
            return path

    return None


# ── File format parsing ──────────────────────────────────────────────────────

LZ4_MAGIC = b'\x04\x22\x4D\x18'


def parse_atext(filepath: Path) -> list[dict]:
    """Parse an .atext file and return the decompressed JSON data."""
    raw = filepath.read_bytes()

    magic_pos = raw.find(LZ4_MAGIC)
    if magic_pos == -1:
        print(f"Error: LZ4 frame magic not found in {filepath}")
        print("This file may not be a valid .atext file.")
        sys.exit(1)

    compressed = raw[magic_pos:]
    decompressed = lz4.frame.decompress(compressed)
    return json.loads(decompressed.decode("utf-8"))


# ── Snippet extraction ───────────────────────────────────────────────────────

TYPE_LABELS = {
    "t": "text",
    "s": "script",
    "r": "rich text",
    "p": "picture",
    "h": "HTML",
}


def extract_snippets(items: list, group_name: str = "") -> list[dict]:
    """Recursively extract snippets from the nested aText structure."""
    results = []

    for item in items:
        if not isinstance(item, dict):
            continue

        children = item.get("13")
        is_group = item.get("99") == 1 or (
            isinstance(children, list)
            and children
            and isinstance(children[0], dict)
        )

        if is_group:
            gname = item.get("2", "Unnamed Group")
            if isinstance(children, list):
                results.extend(extract_snippets(children, gname))
        else:
            triggers = item.get("1", [])
            if isinstance(triggers, str):
                triggers = [triggers]

            content = item.get("4", "")
            rich_content = item.get("5", "")
            snippet_type = item.get("3", "")
            name = item.get("2", "")
            hotkey = item.get("8", "")
            tags = item.get("10", [])
            uuid = item.get("0", "")
            created = item.get("12", "")
            modified = item.get("13", "")

            trigger_str = ", ".join(triggers) if isinstance(triggers, list) else str(triggers)
            tag_str = ", ".join(tags) if isinstance(tags, list) else str(tags)

            # Skip entries with no meaningful data
            if not (trigger_str or content or name):
                continue

            results.append({
                "trigger": trigger_str,
                "content": content,
                "rich_content": rich_content,
                "type": snippet_type,
                "type_label": TYPE_LABELS.get(snippet_type, snippet_type),
                "name": name,
                "group": group_name,
                "hotkey": hotkey,
                "tags": tag_str,
                "uuid": uuid,
                "created": format_timestamp(created),
                "modified": format_timestamp(modified) if isinstance(modified, (int, float)) else "",
            })

    return results


def format_timestamp(ts) -> str:
    """Convert a Unix timestamp to ISO 8601 string, or return empty."""
    if not isinstance(ts, (int, float)) or ts <= 0:
        return ""
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    except (OSError, ValueError):
        return ""


# ── Output writers ───────────────────────────────────────────────────────────

CSV_FIELDS = ["trigger", "content", "type", "type_label", "group", "name",
              "hotkey", "tags", "created", "modified", "rich_content", "uuid"]


def write_csv(snippets: list[dict], output_dir: Path) -> Path:
    """Write snippets to CSV with UTF-8 BOM for Excel compatibility."""
    path = output_dir / "atext_snippets.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(snippets)
    return path


def write_json(snippets: list[dict], output_dir: Path) -> Path:
    """Write snippets as a formatted JSON array."""
    path = output_dir / "atext_snippets.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snippets, f, ensure_ascii=False, indent=2)
    return path


def write_txt(snippets: list[dict], output_dir: Path) -> Path:
    """Write a human-readable text summary."""
    path = output_dir / "atext_snippets.txt"
    groups = {}
    for s in snippets:
        groups.setdefault(s["group"] or "(ungrouped)", []).append(s)

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"aText Snippets Export\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total: {len(snippets)} snippets in {len(groups)} groups\n")
        f.write("=" * 72 + "\n")

        for group_name, items in groups.items():
            f.write(f"\n{'─' * 72}\n")
            f.write(f"  GROUP: {group_name} ({len(items)} snippets)\n")
            f.write(f"{'─' * 72}\n\n")

            for s in items:
                f.write(f"  Trigger:  {s['trigger']}\n")
                if s["name"]:
                    f.write(f"  Name:     {s['name']}\n")
                if s["hotkey"]:
                    f.write(f"  Hotkey:   {s['hotkey']}\n")
                if s["type_label"]:
                    f.write(f"  Type:     {s['type_label']}\n")

                content = s["content"]
                if len(content) > 300:
                    content = content[:300] + "..."
                # Indent multiline content
                lines = content.split("\n")
                f.write(f"  Content:  {lines[0]}\n")
                for line in lines[1:]:
                    f.write(f"            {line}\n")
                f.write("\n")

    return path


def write_espanso(snippets: list[dict], output_dir: Path) -> Path:
    """Write an Espanso-compatible YAML match file."""
    path = output_dir / "atext_espanso.yml"

    # Filter to text snippets with at least one trigger
    text_snippets = [s for s in snippets if s["trigger"] and s["type"] in ("t", "")]

    with open(path, "w", encoding="utf-8") as f:
        f.write("# aText snippets exported for Espanso\n")
        f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Source snippets: {len(text_snippets)} (text-only, from {len(snippets)} total)\n")
        f.write("#\n")
        f.write("# Install: copy to ~/.config/espanso/match/atext.yml\n")
        f.write("# Docs:    https://espanso.org/docs/matches/basics/\n\n")
        f.write("matches:\n")

        current_group = None
        for s in text_snippets:
            if s["group"] != current_group:
                current_group = s["group"]
                f.write(f"\n  # ── {current_group or 'Ungrouped'} ──\n\n")

            # Each trigger becomes a separate match entry
            triggers = [t.strip() for t in s["trigger"].split(",")]
            content = s["content"]

            # Escape for YAML: use block scalar if multiline or has special chars
            needs_block = "\n" in content or '"' in content or "'" in content or "\\" in content

            for trigger in triggers:
                if not trigger:
                    continue

                if s["name"]:
                    f.write(f"  # {s['name']}\n")

                f.write(f"  - trigger: \"{escape_yaml_string(trigger)}\"\n")

                if needs_block:
                    f.write(f"    replace: |+\n")
                    for line in content.split("\n"):
                        f.write(f"      {line}\n")
                else:
                    f.write(f"    replace: \"{escape_yaml_string(content)}\"\n")

                f.write("\n")

    return path


def escape_yaml_string(s: str) -> str:
    """Escape a string for use in double-quoted YAML."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")


# ── CLI ──────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="atext2csv",
        description="Export aText snippets to open formats (CSV, JSON, Espanso YAML, TXT).",
        epilog=(
            "If no input file is specified, the tool auto-detects the default Data.atext\n"
            "location on Windows or macOS. If no format flags are given, all formats are exported."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "input",
        nargs="?",
        help="Path to .atext file (auto-detected if omitted)",
    )
    parser.add_argument(
        "-o", "--output-dir",
        default=None,
        help="Output directory (default: current directory)",
    )
    parser.add_argument("--csv", action="store_true", help="Export as CSV (Excel-compatible UTF-8 with BOM)")
    parser.add_argument("--json", action="store_true", help="Export as JSON")
    parser.add_argument("--espanso", action="store_true", help="Export as Espanso YAML match file")
    parser.add_argument("--txt", action="store_true", help="Export as human-readable text")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress progress output")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    # Resolve input file
    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Error: File not found: {input_path}")
            sys.exit(1)
    else:
        input_path = find_atext_data()
        if not input_path:
            print("Error: Could not auto-detect Data.atext.")
            print("Specify the file path: python atext2csv.py /path/to/Data.atext")
            sys.exit(1)
        if not args.quiet:
            print(f"Auto-detected: {input_path}")

    # Resolve output directory
    output_dir = Path(args.output_dir) if args.output_dir else Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)

    # If no format flags given, export all
    export_all = not (args.csv or args.json or args.espanso or args.txt)

    # Parse
    if not args.quiet:
        print(f"Parsing: {input_path} ({input_path.stat().st_size:,} bytes)")

    data = parse_atext(input_path)
    snippets = extract_snippets(data)

    if not args.quiet:
        groups = set(s["group"] for s in snippets)
        print(f"Found: {len(snippets)} snippets in {len(groups)} groups")

    if not snippets:
        print("Warning: No snippets found in this file.")
        sys.exit(0)

    # Export
    outputs = []

    if export_all or args.csv:
        path = write_csv(snippets, output_dir)
        outputs.append(("CSV", path))

    if export_all or args.json:
        path = write_json(snippets, output_dir)
        outputs.append(("JSON", path))

    if export_all or args.espanso:
        path = write_espanso(snippets, output_dir)
        outputs.append(("Espanso", path))

    if export_all or args.txt:
        path = write_txt(snippets, output_dir)
        outputs.append(("TXT", path))

    # Summary
    if not args.quiet:
        print()
        for label, path in outputs:
            size = path.stat().st_size
            print(f"  {label:8s} -> {path} ({size:,} bytes)")
        print(f"\nDone. Exported {len(snippets)} snippets.")


if __name__ == "__main__":
    main()
