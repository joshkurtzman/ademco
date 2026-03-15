#!/usr/bin/env python3

"""Compare Ademco Home Assistant registry snapshots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_entity_entries(path: Path) -> list[dict]:
    data = load_json(path)
    return [entry for entry in data["data"]["entities"] if entry.get("platform") == "ademco"]


def load_device_entries(path: Path) -> list[dict]:
    data = load_json(path)
    return data["data"]["devices"]


def key_by(entries: list[dict], field: str) -> dict[str, dict]:
    keyed: dict[str, dict] = {}
    for entry in entries:
        value = entry.get(field)
        if value:
            keyed[value] = entry
    return keyed


def print_entity_changes(before: list[dict], after: list[dict]) -> None:
    before_by_unique = key_by(before, "unique_id")
    after_by_unique = key_by(after, "unique_id")

    removed = sorted(set(before_by_unique) - set(after_by_unique))
    added = sorted(set(after_by_unique) - set(before_by_unique))
    shared = sorted(set(before_by_unique) & set(after_by_unique))

    print("Entity summary")
    print(f"  before: {len(before)}")
    print(f"  after:  {len(after)}")
    print(f"  added:  {len(added)}")
    print(f"  removed:{len(removed)}")
    print()

    if added:
        print("Added entities")
        for unique_id in added:
            entry = after_by_unique[unique_id]
            print(f"  + {unique_id} -> {entry.get('entity_id')}")
        print()

    if removed:
        print("Removed entities")
        for unique_id in removed:
            entry = before_by_unique[unique_id]
            print(f"  - {unique_id} -> {entry.get('entity_id')}")
        print()

    moved = []
    for unique_id in shared:
        before_entry = before_by_unique[unique_id]
        after_entry = after_by_unique[unique_id]
        if before_entry.get("entity_id") != after_entry.get("entity_id"):
            moved.append((unique_id, before_entry.get("entity_id"), after_entry.get("entity_id")))

    if moved:
        print("Entity ID changes")
        for unique_id, before_id, after_id in moved:
            print(f"  * {unique_id}: {before_id} -> {after_id}")
        print()


def print_device_changes(before: list[dict], after: list[dict]) -> None:
    def ademco_devices(entries: list[dict]) -> list[dict]:
        devices = []
        for entry in entries:
            identifiers = entry.get("identifiers") or []
            if any(identifier[0] == "ademco" for identifier in identifiers):
                devices.append(entry)
        return devices

    before_devices = ademco_devices(before)
    after_devices = ademco_devices(after)

    print("Device summary")
    print(f"  before: {len(before_devices)}")
    print(f"  after:  {len(after_devices)}")
    print()

    if after_devices:
        print("Current Ademco devices")
        for device in after_devices:
            identifiers = ",".join(f"{key}:{value}" for key, value in device.get("identifiers", []))
            print(f"  * {device.get('name_by_user') or device.get('name')} [{identifiers}]")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before_entity_registry", type=Path)
    parser.add_argument("after_entity_registry", type=Path)
    parser.add_argument("--before-device-registry", type=Path)
    parser.add_argument("--after-device-registry", type=Path)
    args = parser.parse_args()

    before_entities = load_entity_entries(args.before_entity_registry)
    after_entities = load_entity_entries(args.after_entity_registry)
    print_entity_changes(before_entities, after_entities)

    if args.before_device_registry and args.after_device_registry:
        before_devices = load_device_entries(args.before_device_registry)
        after_devices = load_device_entries(args.after_device_registry)
        print_device_changes(before_devices, after_devices)


if __name__ == "__main__":
    main()
