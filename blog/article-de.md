# Reverse Engineering in der Praxis: Wie man ein proprietäres Dateiformat knackt

*Eine Schritt-für-Schritt-Anleitung am Beispiel eines Text-Expanders — mit Python, Hex-Editoren und einem .NET-Trick.*

---

## Worum geht es?

Bei uns nutzen wir Text-Expander für Standard-Textbausteine und Informationsblöcke im täglichen Betrieb. Das spart enorm viel Zeit: Statt wiederkehrende Texte immer wieder einzutippen, reicht ein Kürzel — und der komplette Textbaustein wird eingefügt.

Das Problem: Der von uns genutzte Text-Expander **aText** speichert alle Daten in einem proprietären Binärformat (`.atext`-Dateien). Es gibt keinen CSV-Export, keine Dokumentation des Formats. Die Daten sind quasi eingesperrt.

In diesem Artikel zeige ich Schritt für Schritt, wie man so ein Format analysiert und die eigenen Daten befreit. Die Methoden sind universell anwendbar — egal ob Text-Expander, CRM-System oder irgendein anderes Programm mit unbekanntem Dateiformat.

## Was du lernst

- Wie binäre Dateiformate aufgebaut sind
- Wie man einen Hex-Editor benutzt, um Strukturen zu erkennen
- Wie man .NET-Programme inspiziert, um Hinweise zu finden
- Wie Datenkompression (LZ4) funktioniert
- Wie man mit Python ein Dateiformat dekodiert

## Schritt 1: Die Datei im Hex-Editor öffnen

Der erste Schritt bei jedem unbekannten Dateiformat: **Schau dir die rohen Bytes an.**

Jede Datei auf deinem Computer besteht aus einer Folge von Bytes (Zahlen von 0 bis 255). Ein Hex-Editor zeigt diese Bytes in hexadezimaler Schreibweise und versucht gleichzeitig, sie als Text darzustellen.

Hier die ersten Bytes unserer `.atext`-Datei:

```
Offset    Hex                                         ASCII
────────  ──────────────────────────────────────────  ────────────────
00000000  EF BB BF 7B 22 30 22 3A 22 64 32 61 62 61  ...{"0":"d2aba
00000010  34 33 33 2D 39 31 65 39 2D 34 62 33 64 2D  433-91e9-4b3d-
00000020  61 32 63 39 2D 66 62 36 30 63 32 65 33 66  a2c9-fb60c2e3f
00000030  36 64 38 22 2C 22 31 22 3A 74 72 75 65 7D  6d8","1":true}
00000040  00 04 22 4D 18                              .."M.
```

Was fällt auf?

**`EF BB BF`** — Das ist ein UTF-8 BOM (Byte Order Mark). Ein Standard-Kennzeichen, das sagt: "Diese Datei enthält UTF-8-kodierten Text."

**`{"0":"d2aba433-...","1":true}`** — Das ist JSON! Ganz normales, lesbares JSON. Ein gutes Zeichen — das Format ist nicht verschlüsselt.

**`00`** — Ein Null-Byte. Das trennt den Header vom Hauptteil.

**`04 22 4D 18`** — Danach beginnen komprimierte Binärdaten. Diese vier Bytes sehen nicht zufällig aus — sie könnten eine sogenannte *Magic Number* sein.

### Was sind Magic Numbers?

Viele Dateiformate beginnen mit festen Byte-Folgen, sogenannten **Magic Numbers** (oder Magic Bytes). Damit können Programme erkennen, um welchen Dateityp es sich handelt:

| Magic Bytes | Format |
|---|---|
| `89 50 4E 47` | PNG-Bild |
| `50 4B 03 04` | ZIP-Archiv |
| `25 50 44 46` | PDF-Dokument |
| `04 22 4D 18` | **LZ4-Frame** |

Unsere unbekannten Bytes (`04 22 4D 18`) sind die Magic Number des **LZ4-Kompressionsformats**!

## Schritt 2: Den Hinweis bestätigen — .NET-Assemblies inspizieren

Woher wissen wir, dass es wirklich LZ4 ist? Hier hilft uns ein Trick: aText für Windows ist eine **.NET-Anwendung**. Und .NET-Programme speichern die Namen aller verwendeten Bibliotheken lesbar in ihrer .exe-Datei.

```powershell
# PowerShell: Referenzierte Bibliotheken auslesen
$exe = [System.Reflection.Assembly]::LoadFile("C:\Pfad\zu\aText.exe")
$exe.GetReferencedAssemblies() | Select-Object Name
```

In der Liste taucht auf: **`K4os.Compression.LZ4`**

Das bestätigt unseren Fund: aText nutzt LZ4-Kompression für den Datenteil.

### Was ist LZ4?

LZ4 ist ein Kompressionsalgorithmus, der auf Geschwindigkeit optimiert ist (ähnlich wie ZIP, aber schneller). Er wird in vielen Anwendungen genutzt — von Datenbanken bis Spieleentwicklung. Die Python-Bibliothek `lz4` kann LZ4-Daten dekomprimieren.

## Schritt 3: Die Datei mit Python dekodieren

Jetzt haben wir genug Wissen, um einen Decoder zu schreiben:

```python
#!/usr/bin/env python3
"""aText-Datei dekomprimieren und als JSON ausgeben."""

import json
import lz4.frame  # pip install lz4
from pathlib import Path

# Datei einlesen
# (alles als Bytes — nicht als Text, weil Binärdaten enthalten sind)
raw = Path("Data.atext").read_bytes()

# LZ4 Magic Bytes suchen
LZ4_MAGIC = b'\x04\x22\x4D\x18'  # Die 4 Erkennungs-Bytes
magic_pos = raw.find(LZ4_MAGIC)

if magic_pos == -1:
    print("Fehler: Keine LZ4-Daten gefunden!")
    exit(1)

print(f"Header:  {raw[:magic_pos]}")     # JSON-Header vor dem LZ4-Block
print(f"LZ4-Start: Byte {magic_pos}")    # Position der komprimierten Daten

# Alles ab den Magic Bytes dekomprimieren
komprimiert = raw[magic_pos:]
dekomprimiert = lz4.frame.decompress(komprimiert)

# Ergebnis ist UTF-8-kodiertes JSON
daten = json.loads(dekomprimiert.decode("utf-8"))
print(f"Gefunden: {len(daten)} Einträge")

# Die ersten 3 Einträge anschauen
for eintrag in daten[:3]:
    print(json.dumps(eintrag, indent=2, ensure_ascii=False)[:200])
```

**Ergebnis:** Der komprimierte Block enthält ein großes JSON-Array mit allen Textbausteinen und Gruppen!

## Schritt 4: Die JSON-Struktur verstehen

Die Daten verwenden numerische Schlüssel (wahrscheinlich zur Platzersparnis):

```json
{
  "0": "a1b2c3d4-...",
  "1": ["mfg"],
  "2": "Mit freundlichen Grüßen",
  "3": "t",
  "4": "Mit freundlichen Grüßen\nDavid Lepold\nNHV - Nachhilfe-Vermittlung",
  "12": 1667690904,
  "13": 1700000000
}
```

Durch Vergleichen vieler Einträge kann man die Bedeutung ableiten:

| Schlüssel | Bedeutung |
|---|---|
| `"0"` | UUID (eindeutige ID) |
| `"1"` | Trigger-Kürzel (Array) — z.B. `["mfg"]` |
| `"2"` | Name / Bezeichnung |
| `"3"` | Typ: `t`=Text, `s`=Skript, `r`=Rich Text, `p`=Bild |
| `"4"` | Inhalt (Klartext) |
| `"5"` | Rich-Text-Inhalt (HTML) |
| `"12"` | Erstellt (Unix-Zeitstempel) |
| `"13"` | Geändert (Zeitstempel) ODER Kinder (bei Gruppen) |
| `"99"` | Gruppen-Markierung (1 = ist eine Gruppe/Ordner) |

Der Schlüssel `"13"` hat eine Doppelbedeutung: Bei normalen Einträgen ist es ein Zeitstempel, bei Gruppen (Ordnern) ist es ein Array mit Kind-Einträgen. So entsteht eine Baumstruktur.

## Schritt 5: Export als CSV

Jetzt können wir die Daten in jedes beliebige Format exportieren:

```python
import csv

def snippets_extrahieren(eintraege, gruppenname=""):
    """Textbausteine rekursiv aus der Baumstruktur extrahieren."""
    ergebnis = []
    for eintrag in eintraege:
        if not isinstance(eintrag, dict):
            continue

        kinder = eintrag.get("13")
        ist_gruppe = eintrag.get("99") == 1

        if ist_gruppe and isinstance(kinder, list):
            # Rekursiv in die Gruppe hineinschauen
            name = eintrag.get("2", "Unbenannt")
            ergebnis.extend(snippets_extrahieren(kinder, name))
        else:
            # Normaler Textbaustein
            trigger = eintrag.get("1", [])
            if isinstance(trigger, list):
                trigger = ", ".join(trigger)
            ergebnis.append({
                "trigger": trigger,
                "inhalt": eintrag.get("4", ""),
                "gruppe": gruppenname,
                "name": eintrag.get("2", ""),
            })
    return ergebnis

# In CSV schreiben (mit BOM für Excel)
snippets = snippets_extrahieren(daten)
with open("export.csv", "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=["trigger", "inhalt", "gruppe", "name"])
    writer.writeheader()
    writer.writerows(snippets)

print(f"{len(snippets)} Textbausteine exportiert!")
```

**Wichtig:** Das `utf-8-sig`-Encoding fügt einen BOM (Byte Order Mark) ein. Ohne diesen zeigt Excel Umlaute falsch an.

## Das fertige Tool

Das Ganze habe ich zu einem fertigen Kommandozeilen-Tool ausgebaut: **[atext2csv](https://github.com/dlepold/atext2csv)**

Es kann:
- Die aText-Datei automatisch finden (Windows & macOS)
- In 4 Formate exportieren: CSV, JSON, Espanso-YAML, Klartext
- Mit Backup-Dateien umgehen

```bash
pip install lz4
python atext2csv.py          # Findet Data.atext automatisch
python atext2csv.py --csv    # Nur CSV-Export
python atext2csv.py --espanso  # Für Linux-Migration zu Espanso
```

## Was lässt sich daraus lernen?

### 1. Proprietär ≠ Verschlüsselt
Viele "proprietäre" Formate sind gar nicht verschlüsselt — sie verwenden Standard-Kompression oder -Serialisierung mit einem eigenen Header. Immer erst prüfen, bevor man aufgibt.

### 2. Die Werkzeuge sind da
- **Hex-Editor** — HxD (Windows), xxd (Linux), oder online: hexed.it
- **Magic-Number-Datenbanken** — [filesignatures.net](https://www.filesignatures.net/), Wikipedia "List of file signatures"
- **.NET-Inspektion** — PowerShell-Reflection, ILSpy, dotPeek
- **Python-Bibliotheken** — Für fast jedes Kompressionsformat gibt es eine Bibliothek

### 3. Reverse Engineering ist eine Kernkompetenz
Ob Datenformate, APIs oder Protokolle — die Fähigkeit, Unbekanntes systematisch zu analysieren, ist eine der wertvollsten Fähigkeiten in der Softwareentwicklung.

### 4. Deine Daten gehören dir
Wenn eine Software keinen Export bietet, heißt das nicht, dass du auf deine Daten verzichten musst. Mit den richtigen Werkzeugen und etwas Geduld lässt sich fast jedes Format aufschlüsseln.

---

## Zum Ausprobieren

Wer das selbst nachvollziehen möchte, braucht nur:

1. **Python 3** (≥ 3.9) — [python.org](https://www.python.org/)
2. **pip install lz4** — die einzige Abhängigkeit
3. Eine `.atext`-Datei — oder einfach [das Tool ausprobieren](https://github.com/dlepold/atext2csv)
4. Einen Hex-Editor — [HxD](https://mh-nexus.de/de/hxd/) (Windows) oder `xxd` (Linux/macOS)

---

*Dieser Artikel ist Teil unseres Technik-Blogs bei [NHV Nachhilfe-Vermittlung](https://nachhilfe-vermittlung.com). Wir schreiben regelmäßig über Themen aus Softwareentwicklung, IT und digitalem Lernen.*
