#!/usr/bin/env python3
"""Verify vendored source archives, optionally extract into a fresh build tree."""
import argparse
import hashlib
import json
import pathlib
import tarfile

ROOT = pathlib.Path(__file__).resolve().parents[1]


def manifest():
    return json.loads((ROOT / "sources/manifest.json").read_text())


def verify():
    for name, info in manifest().items():
        archive = ROOT / "sources" / info["file"]
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        if digest != info["sha256"]:
            raise SystemExit(f"Source checksum mismatch: {archive}")
        print(f"Verified {name}: {info['version']}")


def extract(destination):
    verify()
    for name, info in manifest().items():
        target = destination / name
        target.mkdir(parents=True, exist_ok=False)
        with tarfile.open(ROOT / "sources" / info["file"]) as archive:
            for member in archive.getmembers():
                parts = pathlib.PurePosixPath(member.name).parts
                if len(parts) <= 1:
                    continue
                relative = pathlib.PurePosixPath(*parts[1:])
                if relative.is_absolute() or ".." in relative.parts:
                    raise SystemExit(f"Unsafe archive member: {member.name}")
                if not (member.isfile() or member.isdir()):
                    raise SystemExit(f"Unsupported archive member: {member.name}")
                member.name = relative.as_posix()
                archive.extract(member, target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extract", type=pathlib.Path)
    args = parser.parse_args()
    if args.extract:
        extract(args.extract)
    else:
        verify()
