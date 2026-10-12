#!/usr/bin/env python3
"""Stage binaries, audit runtime dependencies, and produce redistribution archives."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import zipfile

from sources import ROOT, manifest, verify

TARGETS = ("aarch64-apple-darwin", "x86_64-apple-darwin", "x86_64-pc-windows-msvc")
UNIVERSAL = "universal-apple-darwin"
VERSION = (ROOT / "VERSION").read_text().strip()


def run(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT).strip()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(binary, target):
    if target.endswith("apple-darwin"):
        archs = set(run("lipo", "-archs", str(binary)).split())
        expected = {"arm64", "x86_64"} if target == UNIVERSAL else {
            "arm64" if target.startswith("aarch64") else "x86_64"}
        if archs != expected:
            raise SystemExit(f"Wrong architectures: {archs}, expected {expected}")
        report = run("otool", "-L", str(binary))
        deps = re.findall(r"^\s+(\S+) \(compatibility", report, re.M)
        if not deps or any(not p.startswith(("/usr/lib/", "/System/Library/")) for p in deps):
            raise SystemExit(f"Unexpected dynamic dependency:\n{report}")
    else:
        tool = os.environ.get("CROSS_PREFIX", "x86_64-w64-mingw32-") + "objdump"
        report = run(tool, "-p", str(binary))
        deps = re.findall(r"DLL Name:\s*(\S+)", report)
        allowed = {"advapi32.dll", "bcrypt.dll", "kernel32.dll", "msvcrt.dll", "ntdll.dll",
                   "ole32.dll", "oleaut32.dll", "psapi.dll", "secur32.dll", "shell32.dll",
                   "user32.dll", "ucrtbase.dll", "ws2_32.dll"}
        if not deps or any(p.lower() not in allowed and not p.lower().startswith("api-ms-win-") for p in deps):
            raise SystemExit(f"Non-system DLL dependency: {deps}")
        if "pei-x86-64" not in report:
            raise SystemExit("Expected an x86-64 Windows executable")
        report = "\n".join(line for line in report.splitlines()
                           if "file format" in line or "DLL Name:" in line)
    return {"dependencies": sorted(set(deps)), "report": report}


def build_inputs():
    paths = [ROOT / "VERSION", ROOT / "sources/manifest.json"]
    paths += sorted(p for p in (ROOT / "scripts").iterdir() if p.is_file())
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in paths}


def stage(target):
    work = ROOT / "build" / target
    dest = ROOT / "dist" / target
    if dest.exists():
        shutil.rmtree(dest)
    (dest / "bin").mkdir(parents=True)
    (dest / "licenses").mkdir()
    (dest / "configuration").mkdir()
    name = "ffmpeg.exe" if "windows" in target else "ffmpeg"
    binary = dest / "bin" / name
    shutil.copy2(work / "ffmpeg" / name, binary)
    if "apple" in target:
        # Strip before ad-hoc signing; application distribution must sign again
        # with its own Developer ID before notarization.
        subprocess.run(["strip", "-S", str(binary)], check=True)
        subprocess.run(["codesign", "--force", "--sign", "-", str(binary)], check=True)
    else:
        subprocess.run([os.environ.get("CROSS_PREFIX", "x86_64-w64-mingw32-") + "strip", str(binary)], check=True)
    dependency_info = audit(binary, target)
    for path in (work / "src/ffmpeg").glob("COPYING*"):
        shutil.copy2(path, dest / "licenses" / ("FFmpeg-" + path.name))
    for source, output in [("ffmpeg/LICENSE.md", "FFmpeg-LICENSE.md"),
                           ("x264/COPYING", "x264-COPYING"),
                           ("zlib/LICENSE", "zlib-LICENSE")]:
        shutil.copy2(work / "src" / source, dest / "licenses" / output)
    for source in ["config.h", "config_components.h", "ffbuild/config.mak", "ffbuild/config.log"]:
        shutil.copy2(work / "ffmpeg" / source, dest / "configuration" / Path(source).name)
    shutil.copy2(work / "x264/config.mak", dest / "configuration/x264-config.mak")
    shutil.copytree(ROOT / "docs", dest / "docs")
    for path in ["README.md", "NOTICE.md", "LICENSE", "VERSION", "sources/manifest.json"]:
        shutil.copy2(ROOT / path, dest / Path(path).name)
    info = {"version": VERSION, "target": target, "sources": manifest(),
            "binary_sha256": sha(binary), "binary_bytes": binary.stat().st_size,
            "build_inputs": build_inputs(), "runtime": dependency_info}
    (dest / "BUILD-INFO.json").write_text(json.dumps(info, indent=2) + "\n")


def universal():
    dest = ROOT / "dist" / UNIVERSAL
    if dest.exists():
        shutil.rmtree(dest)
    arm = ROOT / "dist" / TARGETS[0]
    intel = ROOT / "dist" / TARGETS[1]
    slice_info = [json.loads((source / "BUILD-INFO.json").read_text()) for source in (arm, intel)]
    for source, metadata in zip((arm, intel), slice_info):
        if metadata["version"] != VERSION or metadata["binary_sha256"] != sha(source / "bin/ffmpeg"):
            raise SystemExit(f"Stale or modified universal slice: {source}")
    if any(slice_info[0][key] != slice_info[1][key] for key in ("sources", "build_inputs")):
        raise SystemExit("Universal slices must use identical sources and build scripts")
    shutil.copytree(arm, dest)
    shutil.rmtree(dest / "configuration")
    info = {"version": VERSION, "target": UNIVERSAL, "slices": {}}
    for target, source in [(TARGETS[0], arm), (TARGETS[1], intel)]:
        shutil.copytree(source / "configuration", dest / "configuration" / target)
        info["slices"][target] = json.loads((source / "BUILD-INFO.json").read_text())
    binary = dest / "bin/ffmpeg"
    subprocess.run(["lipo", "-create", str(arm / "bin/ffmpeg"), str(intel / "bin/ffmpeg"),
                    "-output", str(binary)], check=True)
    subprocess.run(["codesign", "--force", "--sign", "-", str(binary)], check=True)
    info.update(binary_sha256=sha(binary), binary_bytes=binary.stat().st_size, runtime=audit(binary, UNIVERSAL))
    (dest / "BUILD-INFO.json").write_text(json.dumps(info, indent=2) + "\n")


def checksum(path):
    path.with_name(path.name + ".sha256").write_text(f"{sha(path)}  {path.name}\n")
    print(path)


def archive(target):
    source = ROOT / "dist" / target
    binary = source / "bin" / ("ffmpeg.exe" if "windows" in target else "ffmpeg")
    info = json.loads((source / "BUILD-INFO.json").read_text())
    if info["version"] != VERSION:
        raise SystemExit("VERSION changed since staging; rebuild before packaging")
    if sha(binary) != info["binary_sha256"]:
        raise SystemExit("Binary changed since staging; rebuild before packaging")
    audit(binary, target)
    stem = f"ffmpeg-aa-{VERSION}-{target}"
    if "windows" in target:
        path = ROOT / "dist" / (stem + ".zip")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as output:
            for entry in sorted(source.rglob("*")):
                if entry.is_file():
                    output.write(entry, Path(stem) / entry.relative_to(source))
    else:
        path = ROOT / "dist" / (stem + ".tar.gz")
        with tarfile.open(path, "w:gz") as output:
            output.add(source, arcname=stem)
    checksum(path)


def source_archive():
    verify()
    (ROOT / "dist").mkdir(exist_ok=True)
    stem = f"ffmpeg-aa-{VERSION}-source"
    path = ROOT / "dist" / (stem + ".tar.xz")
    entries = [ROOT / name for name in ["README.md", "NOTICE.md", "LICENSE", "VERSION", ".gitignore"]]
    for name in ["scripts", "sources", "docs", ".github"]:
        entries += sorted(p for p in (ROOT / name).rglob("*")
                          if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")
    with tarfile.open(path, "w:xz") as output:
        for entry in entries:
            output.add(entry, arcname=f"{stem}/{entry.relative_to(ROOT).as_posix()}")
    checksum(path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("universal")
    commands.add_parser("source")
    commands.add_parser("stage").add_argument("target", choices=TARGETS)
    commands.add_parser("archive").add_argument("target", choices=(*TARGETS, UNIVERSAL))
    args = parser.parse_args()
    {"stage": lambda: stage(args.target), "universal": universal,
     "source": source_archive, "archive": lambda: archive(args.target)}[args.command]()
