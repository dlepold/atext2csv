# atext2csv

Export [aText](https://www.trankynam.com/atext/) snippets to CSV, JSON, Espanso YAML, or plain text.

aText is a very useful and popular text expander for Windows and macOS by Tran Ky Nam. Its `.atext` files use a proprietary binary format, unfortunately with no built-in CSV export (on Windows). This tool was born out of necessity — a migration to Linux. It decodes that specific `.atext` format and exports your snippets to open, portable formats. It's also educational, so I share it. 🧑‍🎓

## Quick Start

```bash
pip install lz4
python atext2csv.py
```

That's it. The tool auto-detects your `Data.atext` file and exports all four formats to the current directory.

## Usage

```
python atext2csv.py [input.atext] [-o output_dir] [--csv] [--json] [--espanso] [--txt] [-q]
```

| Flag | Description |
|------|-------------|
| `input` | Path to `.atext` file (auto-detected if omitted) |
| `-o DIR` | Output directory (default: current directory) |
| `--csv` | Export as CSV (UTF-8 with BOM, Excel-compatible) |
| `--json` | Export as JSON |
| `--espanso` | Export as Espanso YAML match file |
| `--txt` | Export as human-readable text |
| `-q` | Quiet mode (no progress output) |

If no format flags are given, all four formats are exported.

### Examples

```bash
# Auto-detect and export everything
python atext2csv.py

# Export only CSV from a backup file
python atext2csv.py "AutoBackup-2024-01-15.atext" --csv

# Export Espanso config to a specific directory
python atext2csv.py --espanso -o ~/.config/espanso/match/

# Quiet mode, JSON only
python atext2csv.py --json -q
```

### Auto-Detection Paths

| OS | Default Location |
|----|-----------------|
| Windows | `%LOCALAPPDATA%\com.trankynam.aText\Data\Data.atext` |
| macOS | `~/Library/Application Support/com.trankynam.aText/Data.atext` |

Backup files (`AutoBackup-*.atext`) use the same format and work too.

## Output Formats

### CSV
Standard CSV with UTF-8 BOM for direct opening in Excel. Columns: trigger, content, type, type_label, group, name, hotkey, tags, created, modified, rich_content, uuid.

### JSON
A flat array of snippet objects with all fields, for programmatic use.

### Espanso YAML
A ready-to-use [Espanso](https://espanso.org/) match file. Only plain text snippets are included (rich text, scripts, and images are skipped). Copy to `~/.config/espanso/match/atext.yml` on Linux/macOS.

### TXT
Human-readable summary grouped by folder, useful for review or printing.

## The `.atext` File Format

The format was reverse-engineered by inspecting aText.exe's .NET assembly, which revealed a dependency on [K4os.Compression.LZ4](https://github.com/MiloszKrajewski/K4os.Compression.LZ4).

### Structure

```
┌──────────────────────────────────────────────────────────┐
│  UTF-8 BOM (3 bytes): EF BB BF                          │
├──────────────────────────────────────────────────────────┤
│  JSON Header (variable length)                           │
│  {"0":"<uuid>","1":true}                                 │
├──────────────────────────────────────────────────────────┤
│  Null separator: 00                                      │
├──────────────────────────────────────────────────────────┤
│  LZ4 Frame (rest of file)                                │
│  Magic: 04 22 4D 18                                      │
│  ... compressed JSON body ...                            │
└──────────────────────────────────────────────────────────┘
```

### Hex Dump (from a real file)

```
Offset    Hex                                             ASCII
────────  ──────────────────────────────────────────────  ────────────────
00000000  EF BB BF 7B 22 30 22 3A 22 64 32 61 62 61 34  ...{"0":"d2aba4
00000010  33 33 2D 39 31 65 39 2D 34 62 33 64 2D 61 32  33-91e9-4b3d-a2
00000020  63 39 2D 66 62 36 30 63 32 65 33 66 36 64 38  c9-fb60c2e3f6d8
00000030  22 2C 22 31 22 3A 74 72 75 65 7D 00 04 22 4D  ","1":true}.."M
00000040  18 ...                                         .
                                        ↑↑ ↑↑↑↑↑↑↑↑
                                   null byte  LZ4 magic

          (...4.8 MB of LZ4-compressed JSON...)

          Decompressed, a snippet looks like this in the JSON stream:

          22 31 22 3A 5B 22 77 77 77 6E 68 76 22 5D 2C 22  "1":["wwwnhv"],"
          33 22 3A 22 74 22 2C 22 34 22 3A 22 77 77 77 2E  3":"t","4":"www.
          4E 61 63 68 68 69 6C 66 65 2D 56 65 72 6D 69 74  Nachhilfe-Vermit
          74 6C 75 6E 67 2E 63 6F 6D 22                    tlung.com"
```

### Decompressed JSON Structure

The body is a JSON array of snippet/group objects. Keys are numeric strings:

| Key | Type | Meaning |
|-----|------|---------|
| `"0"` | string | UUID |
| `"1"` | string[] | Trigger abbreviations |
| `"2"` | string | Name / label |
| `"3"` | string | Type: `t`=text, `s`=script, `r`=rich text, `p`=picture, `h`=HTML |
| `"4"` | string | Content (plain text) |
| `"5"` | string | Rich text content (HTML) |
| `"8"` | string | Hotkey binding |
| `"10"` | string[] | Tags |
| `"12"` | number | Created timestamp (Unix epoch) |
| `"13"` | number \| array | Modified timestamp (snippets) OR children array (groups) |
| `"99"` | number | Group marker (`1` = this item is a group/folder) |

Groups contain their children in the `"13"` field as a nested array, creating a tree structure.

## Migrating to Espanso (Linux)

If you're moving from aText on Windows/macOS to Linux, [Espanso](https://espanso.org/) is an excellent open-source text expander:

```bash
# 1. Export from aText
python atext2csv.py --espanso -o /tmp/

# 2. Install Espanso (https://espanso.org/install/)
# On Ubuntu/Debian:
sudo snap install espanso --classic

# 3. Copy the generated file
cp /tmp/atext_espanso.yml ~/.config/espanso/match/atext.yml

# 4. Restart Espanso
espanso restart
```

Note: Only plain text snippets are migrated. Rich text, scripts, and image snippets need manual conversion.

## How We Cracked the Format

aText's Windows version is a .NET application. Using PowerShell's reflection capabilities, we listed the assembly's referenced libraries:

```powershell
[System.Reflection.Assembly]::LoadFile("C:\path\to\aText.exe") |
  ForEach-Object { $_.GetReferencedAssemblies() } |
  Select-Object Name
```

This revealed `K4os.Compression.LZ4` — a .NET LZ4 compression library. From there, it was straightforward: find the LZ4 frame magic bytes (`04 22 4D 18`) in the file, decompress everything after it, and the result is pure JSON.

## Requirements

- Python 3.9+
- `lz4` package (`pip install lz4`)

## License

MIT - see [LICENSE](LICENSE).
