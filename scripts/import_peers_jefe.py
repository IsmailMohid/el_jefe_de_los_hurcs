#!/usr/bin/env python3
"""
El Jefe import_peers.py — reads a CSV exported from the HURC ESP32 Mac Address Google Sheet
and updates the team_names[] and address_list[] arrays in main.cpp.

Usage:
    python scripts/import_peers.py <responses.csv> [src/main.cpp]

If main.cpp is not specified, it defaults to src/main.cpp in the PlatformIO project.
The original file is backed up as src/main.cpp.bak before changes are made.
"""

import csv
import sys
import re
import shutil
from pathlib import Path
from datetime import datetime

COL_TIMESTAMP = "Timestamp"
COL_TEAM_NUM  = "What is your team number?"
COL_TEAM_NAME = "Create a team name."
MAC_COL_HINT  = "xx:xx:xx:xx:xx:xx"

DEBUG_ENTRY = {
    "label":   "debug",
    "name":    "debug test",
    "address": [0xec, 0xe3, 0x34, 0x21, 0x8c, 0xa0],
}


def parse_timestamp(ts: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M:%S"):
        try:
            return datetime.strptime(ts.strip(), fmt)
        except ValueError:
            continue
    return datetime.min


def find_mac_indices(headers: list[str]) -> list[int]:
    """
    Return the indices of the 6 MAC byte columns.
    Works whether Google Sheets exports them all with the same name
    or with numbered suffixes — we just find the first matching column
    and take 6 consecutive columns from there.
    """
    first = None
    for i, h in enumerate(headers):
        if MAC_COL_HINT in h:
            first = i
            break
    if first is None:
        sys.exit(f"ERROR: Could not find MAC address columns (looking for '{MAC_COL_HINT}' in headers).\n"
                 f"Headers found: {headers}")
    indices = list(range(first, first + 6))
    return indices


def parse_mac(row_values: list[str], mac_indices: list[int]) -> list[int] | None:
    try:
        return [int(row_values[i].strip(), 16) for i in mac_indices]
    except (IndexError, ValueError):
        return None


def mac_to_c(bytes_: list[int]) -> str:
    return "{" + ", ".join(f"0x{b:02x}" for b in bytes_) + "}"


def team_key(team_num: str) -> tuple:
    t = team_num.strip().upper()
    if t == "SOMTECH":
        return (1, 0, "")
    try:
        return (0, int(t), "")
    except ValueError:
        return (0, 999, t)


def load_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        headers = next(reader)
        rows = list(reader)
    return headers, rows


def deduplicate(headers, rows, mac_indices) -> list[dict]:
    num_idx  = headers.index(COL_TEAM_NUM)
    name_idx = headers.index(COL_TEAM_NAME)
    ts_idx   = headers.index(COL_TIMESTAMP)

    best: dict[tuple, dict] = {}
    for row in rows:
        if len(row) <= max(num_idx, name_idx, ts_idx):
            continue
        num  = row[num_idx].strip()
        name = row[name_idx].strip()
        mac  = parse_mac(row, mac_indices)
        if not num or not name or mac is None:
            continue

        key = (num.upper(), name.lower()) if num.upper() == "SOMTECH" else (num, "")
        ts  = parse_timestamp(row[ts_idx])
        if key not in best or ts > parse_timestamp(best[key]["row"][ts_idx]):
            best[key] = {"row": row, "num": num, "name": name, "mac": mac}

    return list(best.values())


def build_entries(headers, rows, mac_indices) -> list[dict]:
    deduped = deduplicate(headers, rows, mac_indices)
    entries = []
    for e in deduped:
        num   = e["num"]
        name  = e["name"]
        mac   = e["mac"]
        label = f"SOMTECH ({name})" if num.upper() == "SOMTECH" else str(num)
        entries.append({"label": label, "name": name, "address": mac, "_num": num})

    entries.sort(key=lambda e: team_key(e["_num"]))
    return [DEBUG_ENTRY] + entries


def build_c_arrays(entries: list[dict]) -> tuple[str, str]:
    names = ["const char* team_names[address_count] PROGMEM = {\n"]
    addresses = ["const uint8_t address_list[address_count][6] PROGMEM = {\n"]
    for e in entries:
        name = e["name"].replace("\\", "\\\\").replace('"', '\\"')
        names.append(f'  "{name}", // {e["label"]}\n')
        addresses.append(f'  {mac_to_c(e["address"])}, // {e["label"]}\n')
    names.append("};")
    addresses.append("};")
    return "".join(names), "".join(addresses)


_COUNT_RE = re.compile(r"const\s+(?:int|size_t)\s+address_count\s*=\s*\d+\s*;[^\n]*")
_NAMES_RE = re.compile(r"const\s+char\s*\*\s*team_names\s*\[\s*address_count\s*\]\s*PROGMEM\s*=\s*\{.*?\};", re.DOTALL)
_ADDR_RE = re.compile(r"const\s+uint8_t\s+address_list\s*\[\s*address_count\s*\]\s*\[\s*6\s*\]\s*PROGMEM\s*=\s*\{.*?\};", re.DOTALL)


def patch_cpp(source: str, entries: list[dict]) -> str:
    names, addresses = build_c_arrays(entries)
    for label, pattern in (("address_count", _COUNT_RE), ("team_names", _NAMES_RE), ("address_list", _ADDR_RE)):
        if len(pattern.findall(source)) != 1:
            raise ValueError(f"Expected exactly one {label} declaration in src/main.cpp")
    source = _COUNT_RE.sub(f"const int address_count = {len(entries)}; // total number of addresses in the list", source, count=1)
    source = _NAMES_RE.sub(lambda _: names, source, count=1)
    source = _ADDR_RE.sub(lambda _: addresses, source, count=1)
    return source


def main():
    if len(sys.argv) not in (2, 3):
        sys.exit("Usage: python scripts/import_peers.py <responses.csv> [src/main.cpp]")

    project_root = Path(__file__).resolve().parent.parent
    csv_path = Path(sys.argv[1]).resolve()
    cpp_path = Path(sys.argv[2]).resolve() if len(sys.argv) == 3 else project_root / "src" / "main.cpp"
    if not csv_path.is_file():
        sys.exit(f"ERROR: CSV not found: {csv_path}")
    if not cpp_path.is_file():
        sys.exit(f"ERROR: C++ file not found: {cpp_path}")

    try:
        headers, rows = load_csv(csv_path)
        mac_indices = find_mac_indices(headers)
        if mac_indices[-1] >= len(headers):
            raise ValueError("CSV has fewer than six MAC columns")
        entries = build_entries(headers, rows, mac_indices)
        # Never silently write invalid byte values or overlong names.
        for entry in entries:
            if any(not 0 <= b <= 255 for b in entry["address"]):
                raise ValueError(f"Invalid MAC byte for {entry['label']}")
            if len(entry["name"].encode("utf-8")) > 31:
                print(f"WARNING: {entry['label']} name exceeds TeamInfo's 31-byte limit and will be truncated on the controller")
        source = cpp_path.read_text(encoding="utf-8")
        patched = patch_cpp(source, entries)
    except (ValueError, KeyError, StopIteration, UnicodeError) as exc:
        sys.exit(f"ERROR: {exc}")

    if patched == source:
        print(f"No changes needed: {cpp_path}")
        return
    backup = cpp_path.with_suffix(cpp_path.suffix + ".bak")
    shutil.copy2(cpp_path, backup)
    cpp_path.write_text(patched, encoding="utf-8")
    print(f"Backed up original to {backup}")
    print(f"Updated {cpp_path} with {len(entries)} entries:")
    for e in entries:
        mac_str = ":".join(f"{b:02x}" for b in e["address"])
        print(f"  [{e['label']:>12}]  {e['name']:<40}  {mac_str}")


if __name__ == "__main__":
    main()
