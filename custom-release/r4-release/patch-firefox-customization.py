#!/usr/bin/env python3
"""Apply the manifest-pinned null guard to the local Firefox omni.ja archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import zipfile


ENTRY = "moz-src/browser/components/customizableui/CustomizableUI.sys.mjs"
NEEDLE = "  serializerHelper(_aKey, aValue) {\n"
INSERT = "    if (aValue === null) {\n      return null;\n    }\n"
DEFAULT_ARCHIVE = Path("/opt/camofox-cache/camoufox/omni.ja")


class PatchError(RuntimeError):
    """The archive did not match the exact pinned patch contract."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _metadata(info: zipfile.ZipInfo) -> tuple[object, ...]:
    return (
        info.filename,
        info.date_time,
        info.compress_type,
        info.comment,
        info.extra,
        info.create_system,
        info.create_version,
        info.extract_version,
        info.reserved,
        info.flag_bits,
        info.volume,
        info.internal_attr,
        info.external_attr,
    )


def _source_bytes(path: Path) -> tuple[bytes, list[zipfile.ZipInfo], bytes]:
    with zipfile.ZipFile(path, "r") as archive:
        if archive.testzip() is not None:
            raise PatchError("Archive CRC check failed")
        infos = archive.infolist()
        if len({info.filename for info in infos}) != len(infos):
            raise PatchError("Duplicate ZIP entry names are ambiguous")
        matches = [info for info in infos if info.filename == ENTRY]
        if len(matches) != 1:
            raise PatchError("Pinned source entry is missing or ambiguous")
        return archive.read(matches[0]), infos, archive.comment


def _write_candidate(source_path: Path, destination: Path, patched_source: bytes) -> None:
    with zipfile.ZipFile(source_path, "r") as source, zipfile.ZipFile(destination, "w") as output:
        output.comment = source.comment
        for info in source.infolist():
            data = patched_source if info.filename == ENTRY else source.read(info)
            output.writestr(info, data)


def _verify_candidate(
    original: Path,
    candidate: Path,
    patched_source: bytes,
    expected_source_hash: str,
) -> None:
    with zipfile.ZipFile(original, "r") as before, zipfile.ZipFile(candidate, "r") as after:
        old_infos, new_infos = before.infolist(), after.infolist()
        if [info.filename for info in old_infos] != [info.filename for info in new_infos]:
            raise PatchError("ZIP entry ordering changed")
        if before.comment != after.comment:
            raise PatchError("ZIP archive comment changed")
        changed: list[str] = []
        for old, new in zip(old_infos, new_infos):
            old_data, new_data = before.read(old), after.read(new)
            if _metadata(old) != _metadata(new):
                raise PatchError(f"ZIP metadata changed for {old.filename}")
            if old_data != new_data:
                changed.append(old.filename)
                if old.filename != ENTRY or new_data != patched_source:
                    raise PatchError(f"Unexpected ZIP entry content change: {old.filename}")
            elif old.CRC != new.CRC:
                raise PatchError(f"CRC changed for unchanged ZIP entry: {old.filename}")
        if changed != [ENTRY]:
            raise PatchError("Expected exactly the pinned customization source to change")
        if after.testzip() is not None:
            raise PatchError("Patched archive CRC check failed")
        if sha256(after.read(ENTRY)) != expected_source_hash:
            raise PatchError("Patched customization source hash mismatch")


def patch_archive(archive_path: Path, manifest_path: Path) -> str:
    """Patch one exact baseline archive; return 'patched' or 'already-patched'."""
    archive_path = Path(archive_path)
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if archive_path.is_symlink() or not archive_path.is_file():
        raise PatchError("Archive target must be a regular local file")

    original_bytes = archive_path.read_bytes()
    archive_hash = sha256(original_bytes)
    source, infos, _comment = _source_bytes(archive_path)
    source_hash = sha256(source)

    if archive_hash == manifest["patchedArchiveSha256"]:
        if source_hash != manifest["patchedSourceSha256"]:
            raise PatchError("Patched archive hash matched but source did not")
        return "already-patched"
    if archive_hash != manifest["originalArchiveSha256"]:
        raise PatchError("Archive hash is not the pinned original")
    if source_hash != manifest["originalSourceSha256"]:
        raise PatchError("Customization source hash is not the pinned original")
    if len([info for info in infos if info.filename == ENTRY]) != 1:
        raise PatchError("Pinned source entry is missing or ambiguous")

    try:
        original_text = source.decode("utf-8")
    except UnicodeDecodeError as error:
        raise PatchError("Customization source is not UTF-8") from error
    if original_text.count(NEEDLE) != 1:
        raise PatchError("Expected one exact serializerHelper insertion point")
    patched_source = original_text.replace(NEEDLE, NEEDLE + INSERT, 1).encode("utf-8")
    if sha256(patched_source) != manifest["patchedSourceSha256"]:
        raise PatchError("Patched customization source does not match the manifest")

    initial_stat = archive_path.stat()
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{archive_path.name}.", suffix=".tmp", dir=archive_path.parent, delete=False
        ) as temporary:
            temp_name = temporary.name
        candidate = Path(temp_name)
        _write_candidate(archive_path, candidate, patched_source)
        _verify_candidate(archive_path, candidate, patched_source, manifest["patchedSourceSha256"])
        if sha256(candidate.read_bytes()) != manifest["patchedArchiveSha256"]:
            raise PatchError("Generated archive hash does not match the manifest")

        if hasattr(os, "chown"):
            try:
                os.chown(candidate, initial_stat.st_uid, initial_stat.st_gid)
            except PermissionError as error:
                raise PatchError("Could not preserve archive ownership") from error
        os.chmod(candidate, stat.S_IMODE(initial_stat.st_mode))
        with candidate.open("rb+") as handle:
            os.fsync(handle.fileno())

        current_stat = archive_path.stat()
        if (current_stat.st_dev, current_stat.st_ino) != (initial_stat.st_dev, initial_stat.st_ino):
            raise PatchError("Archive target changed during patching")
        if sha256(archive_path.read_bytes()) != manifest["originalArchiveSha256"]:
            raise PatchError("Archive contents changed during patching")
        os.replace(candidate, archive_path)
        temp_name = None
        return "patched"
    finally:
        if temp_name is not None:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).with_name("firefox-customization-nullguard.json"),
    )
    args = parser.parse_args()
    print(patch_archive(args.archive, args.manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
