"""Restore missing archived files only. Default is a read-only preview."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--category", choices=["generated", "wip"], default="generated")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    data = json.loads(Path(__file__).with_name("verified_manifest.json").read_text("utf-8"))
    root = Path(data["root"]).resolve()
    archive = Path(data["archive"] if args.category == "generated" else data["wip_archive"])
    expected = data["archive_sha256"] if args.category == "generated" else data["wip_archive_sha256"]
    entries = data["files"] if args.category == "generated" else data["wip_files"]
    if sha(archive) != expected:
        raise RuntimeError("Archive SHA mismatch")
    missing = []
    with zipfile.ZipFile(archive) as z:
        for entry in entries:
            path = Path(entry["path"])
            if not path.resolve().is_relative_to(root) or path.resolve() != path.absolute():
                raise RuntimeError("Unsafe or linked destination")
            if path.exists():
                if sha(path) != entry["sha256"]:
                    raise RuntimeError("Existing file differs; not overwritten: " + str(path))
                continue
            key = entry["relative"]
            if args.category == "wip":
                key = key.removeprefix("deliverables/")
            content = z.read(key)
            if hashlib.sha256(content).hexdigest() != entry["sha256"]:
                raise RuntimeError("Member SHA mismatch")
            missing.append((path, key, entry))
        if args.apply:
            for path, key, entry in missing:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("xb") as f:
                    f.write(z.read(key))
                if sha(path) != entry["sha256"]:
                    raise RuntimeError("Restored file verification failed")
    print(json.dumps({"category": args.category, "missing_files": len(missing),
                      "restored": args.apply, "overwritten": 0}))


if __name__ == "__main__":
    main()
