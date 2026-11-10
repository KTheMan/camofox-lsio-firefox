import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile


SCRIPT = Path(__file__).with_name("patch-firefox-customization.py")
SPEC = importlib.util.spec_from_file_location("patch_firefox_customization", SCRIPT)
PATCHER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(PATCHER)


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def make_archive(path: Path, source: bytes, extras: dict[str, bytes] | None = None) -> None:
    entries = {"other/first.bin": b"first", PATCHER.ENTRY: source, "other/last.bin": b"last"}
    entries.update(extras or {})
    with zipfile.ZipFile(path, "w") as archive:
        archive.comment = b"pinned test comment"
        for name, data in entries.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 9, 1, 2, 4))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.comment = b"entry comment"
            info.external_attr = 0o100640 << 16
            archive.writestr(info, data)


def fixture_manifest(original: Path, patched_source: bytes, directory: Path) -> Path:
    expected_archive = directory / "expected.ja"
    PATCHER._write_candidate(original, expected_archive, patched_source)
    with zipfile.ZipFile(original) as source_zip:
        original_source = source_zip.read(PATCHER.ENTRY)
    values = {
        "originalArchiveSha256": digest(original.read_bytes()),
        "patchedArchiveSha256": digest(expected_archive.read_bytes()),
        "originalSourceSha256": digest(original_source),
        "patchedSourceSha256": digest(patched_source),
    }
    manifest = directory / "manifest.json"
    manifest.write_text(json.dumps(values), encoding="utf-8")
    return manifest


class PatchFirefoxCustomizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.archive = self.root / "omni.ja"
        self.original_source = (
            b"export const Store = {\n"
            b"  serializerHelper(_aKey, aValue) {\n"
            b"    if (typeof aValue == \"object\" && aValue.constructor.name == \"Map\") {\n"
            b"      let result = {};\n"
            b"      for (let [mapKey, mapValue] of aValue) {\n"
            b"        result[mapKey] = mapValue;\n"
            b"      }\n"
            b"      return result;\n"
            b"    }\n"
            b"    if (typeof aValue == \"object\" && aValue.constructor.name == \"Set\") {\n"
            b"      return Array.from(aValue);\n"
            b"    }\n"
            b"    return aValue;\n"
            b"  },\n"
            b"};\n"
        )
        self.patched_source = self.original_source.replace(
            PATCHER.NEEDLE.encode(), (PATCHER.NEEDLE + PATCHER.INSERT).encode(), 1
        )
        make_archive(self.archive, self.original_source)
        self.manifest = fixture_manifest(self.archive, self.patched_source, self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_patch_changes_only_target_entry_and_is_idempotent(self):
        original_mode = self.archive.stat().st_mode
        with zipfile.ZipFile(self.archive) as original:
            before_names = original.namelist()
            before = {name: (digest(original.read(name)), original.getinfo(name).CRC) for name in before_names}

        self.assertEqual(PATCHER.patch_archive(self.archive, self.manifest), "patched")
        self.assertEqual(PATCHER.patch_archive(self.archive, self.manifest), "already-patched")
        self.assertEqual(self.archive.stat().st_mode, original_mode)
        with zipfile.ZipFile(self.archive) as patched:
            self.assertEqual(patched.namelist(), before_names)
            self.assertIsNone(patched.testzip())
            after = {name: (digest(patched.read(name)), patched.getinfo(name).CRC) for name in before_names}
        self.assertEqual(
            [name for name in before_names if before[name] != after[name]], [PATCHER.ENTRY]
        )
        self.assertEqual(after[PATCHER.ENTRY][0], digest(self.patched_source))

    def test_null_map_and_set_semantics_in_node(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is required for the serializer behavior check")
        self.archive.unlink()
        harness = self.root / "serializer-check.cjs"
        harness.write_text(
            "const assert = require('node:assert/strict');\n"
            "const original = { serializerHelper(_aKey, aValue) {\n"
            "  if (typeof aValue == 'object' && aValue.constructor.name == 'Map') {\n"
            "    let result = {}; for (let [k, v] of aValue) result[k] = v; return result;\n"
            "  }\n"
            "  if (typeof aValue == 'object' && aValue.constructor.name == 'Set') return Array.from(aValue);\n"
            "  return aValue;\n} };\n"
            "const patched = { serializerHelper(_aKey, aValue) {\n"
            "  if (aValue === null) return null;\n"
            "  if (typeof aValue == 'object' && aValue.constructor.name == 'Map') {\n"
            "    let result = {}; for (let [k, v] of aValue) result[k] = v; return result;\n"
            "  }\n"
            "  if (typeof aValue == 'object' && aValue.constructor.name == 'Set') return Array.from(aValue);\n"
            "  return aValue;\n} };\n"
            "assert.throws(() => JSON.stringify({x:null}, original.serializerHelper), TypeError);\n"
            "const values = [null, {x:null,nested:[null,{y:null}]}, new Map([['x',null],['n',new Map([['y',null]])]]), new Set([null,'ok'])];\n"
            "const expected = ['null','{\"x\":null,\"nested\":[null,{\"y\":null}]}','{\"x\":null,\"n\":{\"y\":null}}','[null,\"ok\"]'];\n"
            "values.forEach((value, i) => assert.equal(JSON.stringify(value, patched.serializerHelper), expected[i]));\n",
            encoding="utf-8",
        )
        result = subprocess.run([node, str(harness)], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_refuses_unexpected_archive_without_touching_it(self):
        before = self.archive.read_bytes()
        with zipfile.ZipFile(self.archive, "a") as archive:
            archive.writestr("unexpected", b"change")
        changed = self.archive.read_bytes()
        with self.assertRaisesRegex(PATCHER.PatchError, "pinned original"):
            PATCHER.patch_archive(self.archive, self.manifest)
        self.assertEqual(self.archive.read_bytes(), changed)
        self.assertNotEqual(changed, before)
        self.assertEqual(list(self.root.glob(".omni.ja.*.tmp")), [])

    def test_refuses_wrong_source_without_atomic_replacement(self):
        wrong = self.root / "wrong.ja"
        make_archive(wrong, self.original_source.replace(b"return aValue;", b"return 0;"))
        wrong_manifest = self.root / "wrong-source-manifest.json"
        values = json.loads(self.manifest.read_text(encoding="utf-8"))
        values["originalArchiveSha256"] = digest(wrong.read_bytes())
        wrong_manifest.write_text(json.dumps(values), encoding="utf-8")
        before = wrong.read_bytes()
        with self.assertRaisesRegex(PATCHER.PatchError, "source hash"):
            PATCHER.patch_archive(wrong, wrong_manifest)
        self.assertEqual(wrong.read_bytes(), before)
        self.assertEqual(list(self.root.glob(".wrong.ja.*.tmp")), [])

    def test_refuses_wrong_patch_contract_before_replacement(self):
        values = json.loads(self.manifest.read_text(encoding="utf-8"))
        values["patchedArchiveSha256"] = "0" * 64
        bad_manifest = self.root / "bad-manifest.json"
        bad_manifest.write_text(json.dumps(values), encoding="utf-8")
        before = self.archive.read_bytes()
        with self.assertRaisesRegex(PATCHER.PatchError, "Generated archive hash"):
            PATCHER.patch_archive(self.archive, bad_manifest)
        self.assertEqual(self.archive.read_bytes(), before)
        self.assertEqual(list(self.root.glob(".omni.ja.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
