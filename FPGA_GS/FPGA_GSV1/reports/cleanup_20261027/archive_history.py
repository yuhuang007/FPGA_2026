"""Archive selected inactive build intermediates; never deletes source files."""
from pathlib import Path
import hashlib
import json
import os
import re
import time
import zipfile

ROOT = Path(r"E:/zhoumian/FPGA/FPGA_GS/FPGA_GSV1").resolve()
OUT = ROOT / "reports/cleanup_20261027"
ARCHIVE_DIR = ROOT.parent / "_archive/cleanup_20261027"
STAGES = {"compile", "device_map", "place_route", "report_timing", "synthesize", "generate_bitstream"}
SUFFIXES = {".db", ".adf", ".vm", ".netlist"}
BUILD_PATTERN = re.compile(r"(?:M1_\d+|M2_\d+|M3_(?:01|02|03|05))_.*")


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def snapshot_published():
    return {p.relative_to(ROOT).as_posix(): digest(p)
            for p in sorted((ROOT / "release").rglob("*")) if p.is_file()}


def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    OUT.mkdir(exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT / "verified_manifest.json"
    if manifest_path.exists():
        raise RuntimeError("Existing cleanup manifest preserved; do not repeat archive operation")
    protected = snapshot_published()
    save("published_before_sha256.json", protected)
    files = []
    for build in sorted((ROOT / "build").iterdir()):
        if not build.is_dir() or not BUILD_PATTERN.fullmatch(build.name):
            continue
        for p in sorted(build.rglob("*")):
            rel = p.relative_to(build)
            if (p.is_file() and not p.is_symlink() and len(rel.parts) >= 2
                    and rel.parts[0] in STAGES and p.suffix.lower() in SUFFIXES):
                if p.resolve() != p.absolute():
                    raise RuntimeError(f"Unexpected linked path: {p}")
                st = p.stat()
                files.append({"path": str(p), "relative": p.relative_to(ROOT).as_posix(),
                              "bytes": st.st_size, "mtime_ns": st.st_mtime_ns,
                              "sha256": digest(p)})
    archive = ARCHIVE_DIR / "early_build_intermediates.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=1,
                         allowZip64=True) as z:
        for entry in files:
            p = Path(entry["path"])
            if p.stat().st_mtime_ns != entry["mtime_ns"] or digest(p) != entry["sha256"]:
                raise RuntimeError(f"File changed during archive: {p}")
            z.write(p, entry["relative"])
    with zipfile.ZipFile(archive) as z:
        for entry in files:
            h = hashlib.sha256()
            with z.open(entry["relative"]) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    h.update(block)
            if h.hexdigest() != entry["sha256"]:
                raise RuntimeError("Archive verification failed: " + entry["relative"])
    wip = ROOT / "deliverables/FPGA_GSV1_M3_05_3_4_WIP_NO_BIT_20261021_104224"
    old_zip = wip.with_suffix(".zip")
    expected = "96a4e006846ce6d507ef18998073eee745e01a74db740b450c9b709849b2f6a4"
    if digest(old_zip) != expected:
        raise RuntimeError("WIP archive identity mismatch")
    wip_files = []
    with zipfile.ZipFile(old_zip) as z:
        for p in sorted(wip.rglob("*")):
            if not p.is_file():
                continue
            if p.is_symlink() or p.resolve() != p.absolute():
                raise RuntimeError("Unexpected WIP linked file")
            key = wip.name + "/" + p.relative_to(wip).as_posix()
            sha = digest(p)
            if hashlib.sha256(z.read(key)).hexdigest() != sha:
                raise RuntimeError("WIP backup mismatch: " + key)
            st = p.stat()
            wip_files.append({"path": str(p), "relative": p.relative_to(ROOT).as_posix(),
                              "bytes": st.st_size, "mtime_ns": st.st_mtime_ns, "sha256": sha})
    if snapshot_published() != protected:
        raise RuntimeError("Published assets changed; abort cleanup")
    manifest = {"status": "archive_verified_ready_for_removal", "root": str(ROOT),
                "created_at_local": time.strftime("%Y-%m-%d %H:%M:%S %z"),
                "archive": str(archive), "archive_sha256": digest(archive),
                "archive_bytes": archive.stat().st_size, "files": files,
                "wip_directory": str(wip), "wip_archive": str(old_zip),
                "wip_archive_sha256": expected, "wip_files": wip_files,
                "published_files_protected": len(protected),
                "scope": "Only old generated build databases/netlists and exact backed-up WIP duplicate. No work/, release/, orangepi/, root source, bitstream, report, environment or service removal.",
                "restore": "Close historical build analysis first. Extract early_build_intermediates.zip to root with paths preserved; restore missing files only. WIP zip extracts to deliverables/. Verify file SHA using this manifest before overwriting anything."}
    save("verified_manifest.json", manifest)
    print(json.dumps({"status": manifest["status"], "generated_files": len(files),
                      "generated_bytes": sum(e["bytes"] for e in files),
                      "archive_bytes": manifest["archive_bytes"], "wip_files": len(wip_files),
                      "published_files_protected": len(protected)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
