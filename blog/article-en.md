# Cracking aText's Proprietary Format: How I Freed 773 Snippets from a Binary Blob

**TL;DR:** aText's `.atext` files are JSON header + null byte + LZ4-compressed JSON. I wrote a Python tool to export them to CSV, JSON, and Espanso YAML. [Get the tool on GitHub.](https://github.com/dlepold/atext2csv)

---

## The Problem

I've been using [aText](https://www.trankynam.com/atext/) as a text expander for years. 773 snippets — email templates, code patterns, standard text blocks — all locked inside aText's proprietary `.atext` files.

Then I needed to migrate to Linux. aText doesn't run on Linux. And the Windows version doesn't have a CSV export.

I needed those snippets out.

## Dead Ends

**Wine/Bottles:** aText is a .NET/WPF application. Wine can't run WPF apps. Tried Bottles with various runners — same story. WPF depends on DirectX rendering that Wine doesn't properly support.

**Asking the developer:** The macOS version has CSV export (it's the original platform). The Windows version doesn't, and it's a one-person shop — no response to feature requests on a reasonable timeline.

So I did what any developer would do: I opened the binary file in a hex editor.

## The First Clue

Opening `Data.atext` in a hex editor showed something encouraging:

```
EF BB BF 7B 22 30 22 3A 22 64 32 61 62 ...
```

That's a UTF-8 BOM followed by `{"0":"d2a...` — it starts with JSON! The header is a small JSON object:

```json
{"0":"d2aba433-91e9-4b3d-a2c9-fb60c2e3f6d8","1":true}
```

After that: a null byte (`00`), then... binary gibberish. Clearly compressed or encrypted data.

## The Breakthrough

aText's Windows version is built on .NET. And .NET assemblies are inspectable. Using PowerShell:

```powershell
$asm = [System.Reflection.Assembly]::LoadFile("C:\path\to\aText.exe")
$asm.GetReferencedAssemblies() | Select-Object Name
```

In the list of referenced assemblies: **`K4os.Compression.LZ4`**.

That's [a well-known .NET LZ4 compression library](https://github.com/MiloszKrajewski/K4os.Compression.LZ4). LZ4 is a fast compression algorithm with a well-documented frame format. The frame always starts with magic bytes: `04 22 4D 18`.

Looking at my hex dump again:

```
...74 72 75 65 7D 00 04 22 4D 18 ...
         t r u e }  ·  ·  " M ·
                    ↑     ↑↑↑↑↑↑
               null byte  LZ4 magic!
```

There it was. Everything after the null byte is an LZ4-compressed frame.

## The 15-Line Solution

```python
import json, lz4.frame
from pathlib import Path

raw = Path("Data.atext").read_bytes()

# Find LZ4 frame by its magic bytes
magic_pos = raw.find(b'\x04\x22\x4D\x18')

# Decompress everything from the magic onwards
decompressed = lz4.frame.decompress(raw[magic_pos:])
data = json.loads(decompressed)

# data is now a list of snippet/group objects
for item in data:
    if item.get("99") == 1:  # It's a group
        print(f"Group: {item.get('2')}")
    else:
        print(f"  {item.get('1')} → {item.get('4', '')[:50]}")
```

`pip install lz4`, and you're done. The decompressed data is clean JSON — a nested tree of groups and snippets.

## The JSON Schema

aText uses numeric string keys (probably for compactness):

| Key | Meaning |
|-----|---------|
| `"0"` | UUID |
| `"1"` | Trigger abbreviations (array) |
| `"2"` | Name / label |
| `"3"` | Type: `t`=text, `s`=script, `r`=rich text, `p`=picture, `h`=HTML |
| `"4"` | Plain text content |
| `"5"` | Rich text content (HTML) |
| `"8"` | Hotkey |
| `"10"` | Tags (array) |
| `"12"` | Created timestamp (Unix) |
| `"13"` | Modified timestamp (snippets) OR children array (groups) |
| `"99"` | Group marker (1 = is a group) |

The dual-purpose `"13"` field is the trickiest part: for snippets it's a Unix timestamp, for groups it's an array of child items. You differentiate by checking `"99"` or whether `"13"` is an array.

## The Full Tool

I turned this into a proper CLI tool: **[atext2csv](https://github.com/dlepold/atext2csv)**

```bash
pip install lz4
python atext2csv.py                     # auto-finds Data.atext, all formats
python atext2csv.py --csv               # CSV only
python atext2csv.py backup.atext --json # specific file, JSON output
python atext2csv.py --espanso           # Espanso YAML for Linux migration
```

Four output formats:

- **CSV** (UTF-8 BOM for Excel) — for spreadsheet review, mass editing, importing elsewhere
- **JSON** — for programmatic use
- **Espanso YAML** — drop-in config for the excellent open-source [Espanso](https://espanso.org/) text expander on Linux
- **TXT** — human-readable summary

The tool auto-detects the default `Data.atext` location on Windows and macOS. Works with backup files (`AutoBackup-*.atext`) too.

## Migrating to Espanso on Linux

This was my original goal. The workflow:

```bash
# On Windows/macOS — export
python atext2csv.py --espanso -o /tmp/

# On Linux — install Espanso and drop in the config
sudo snap install espanso --classic
cp /tmp/atext_espanso.yml ~/.config/espanso/match/atext.yml
espanso restart
```

Note: only plain text snippets transfer cleanly. Rich text, scripts, and image snippets need manual attention.

## Lessons Learned

1. **Check the runtime first.** Before trying to reverse-engineer a binary format from scratch, check what framework the app is built on. .NET assemblies are goldmines of information — referenced libraries, type names, and method signatures are all accessible.

2. **Magic bytes are your friend.** Compression algorithms and file formats almost always start with known magic bytes. Finding `04 22 4D 18` instantly identified the compression method.

3. **Proprietary doesn't mean encrypted.** Many "proprietary formats" are just standard compression or serialization with a custom header. Always check before assuming the worst.

4. **One dependency is all it takes.** The entire solution depends on a single Python package (`lz4`). Sometimes the simplest approach is the best one.

---

*Have you reverse-engineered a file format? Running into issues with the tool? [Open an issue on GitHub](https://github.com/dlepold/atext2csv/issues) or drop a comment below.*

---

**Tags:** atext, text-expander, reverse-engineering, python, lz4, espanso, csv-export, data-migration, file-format
