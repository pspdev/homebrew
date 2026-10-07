import copy
import hashlib
import http.client
import importlib.util
import io
import json
import tempfile
import unittest
import urllib.request
import zipfile
from pathlib import Path
from unittest import mock

from homebrew_database.homebrew import get_homebrew_from_json_data

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("scanner", ROOT / "scan-releases.py")
scanner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scanner)


def archive(entries=None, icon=b""):
    offsets = [40, 40] + [40 + len(icon)] * 6
    eboot = (
        b"\x00PBP"
        + b"\x00\x00\x01\x00"
        + b"".join(offset.to_bytes(4, "little") for offset in offsets)
        + icon
        + b"payload"
    )
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as zipped:
        for name, data in (entries or {"PSP/GAME/App/EBOOT.PBP": eboot}).items():
            zipped.writestr(name, data)
    return out.getvalue()


def release(tag="v2.0", date="2026-10-01T12:00:00Z", name="psp.zip", content=None):
    content = archive() if content is None else content
    return {
        "tag_name": tag,
        "published_at": date,
        "draft": False,
        "prerelease": False,
        "body": "Release notes",
        "assets": [
            {
                "name": name,
                "size": len(content),
                "browser_download_url": f"https://github.com/test/app/releases/download/{tag}/{name}",
                "digest": "sha256:" + hashlib.sha256(content).hexdigest(),
            }
        ],
    }


def entry():
    return {
        "name": "App",
        "summary": "Curated summary",
        "author": "Author",
        "ai_used": False,
        "requires_additional_files": False,
        "category": "application",
        "tags": ["tools"],
        "source": "https://github.com/test/app",
        "scan_releases": True,
        "media": {"screenshots": ["custom.png"], "icon": "icons/app.png"},
        "releases": [
            {
                "tag": "1.0",
                "published_at": "2026-09-01",
                "size": 1,
                "url": "https://github.com/test/app/releases/download/v1.0/psp.zip",
                "sha256": "a" * 64,
                "eboot_md5": "b" * 32,
            }
        ],
    }


def network(items, content=None):
    content = archive() if content is None else content

    def get(url):
        if url.startswith("https://api.github.com/"):
            return json.dumps(items).encode()
        return content

    return get


class ScannerTests(unittest.TestCase):
    def test_invalid_historical_package_does_not_block_new_releases(self):
        invalid = b"old invalid package"
        older = release("v0.9", date="2026-08-01T12:00:00Z", content=invalid)
        good = release()

        def fetcher(url):
            if "api.github.com" in url:
                return json.dumps([good, older]).encode()
            return invalid if "/v0.9/" in url else archive()

        with self.assertLogs(scanner.LOGGER, level="WARNING"):
            updated, _ = scanner.prepare(entry(), fetcher)
        self.assertEqual([r["tag"] for r in updated["releases"]], ["v2.0", "1.0"])

    def test_newest_icon_uses_existing_filename_and_unicode_ids(self):
        png = (ROOT / "resources" / "icons" / "pspdx.png").read_bytes()
        content = archive(icon=png)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            path = root / "data" / "app_日本語.json"
            data = entry()
            data["name"] = "日本語"
            path.write_text(json.dumps(data))
            icon = root / "resources" / "icons" / "app_日本語.png"
            icon.parent.mkdir(parents=True)
            icon.write_bytes(b"previous icon")
            newest = release(content=content)
            self.assertEqual(scanner.scan(root, network([newest], content)), (1, []))
            updated = json.loads(path.read_text())
            self.assertEqual(updated["media"]["icon"], "icons/app_日本語.png")
            self.assertEqual(icon.read_bytes(), png)
            self.assertEqual(list(icon.parent.iterdir()), [icon])
            self.assertEqual(path.read_text(), json.dumps(updated, indent=2))
            older = release("v0.9", date="2026-08-01T12:00:00Z", content=content)
            newest_bytes = path.read_bytes()
            self.assertEqual(scanner.scan(root, network([newest], content)), (0, []))
            self.assertEqual(path.read_bytes(), newest_bytes)
            self.assertEqual(
                scanner.scan(root, network([newest, older], content)), (1, [])
            )
            self.assertEqual(icon.read_bytes(), png)

    def test_backfill_does_not_replace_existing_icon(self):
        png = (ROOT / "resources" / "icons" / "pspdx.png").read_bytes()
        content = archive(icon=png)
        older = release("v0.9", date="2026-08-01T12:00:00Z", content=content)
        updated, icon = scanner.prepare(entry(), network([older], content))
        self.assertIsNone(icon)
        self.assertEqual(updated["media"], entry()["media"])

    def test_public_metadata_omits_ci_settings(self):
        model = get_homebrew_from_json_data("app", entry())
        self.assertNotIn("scan_releases", model.to_dict())
        self.assertIs(model.to_dict(include_ci=True)["scan_releases"], True)

    def test_ambiguous_release_does_not_block_a_usable_release(self):
        ambiguous = release("v3.0")
        ambiguous["assets"].append(copy.deepcopy(ambiguous["assets"][0]))
        updated, _ = scanner.prepare(entry(), network([ambiguous, release()]))
        self.assertEqual([r["tag"] for r in updated["releases"]], ["v2.0", "1.0"])

    def test_invalid_package_is_skipped_without_changing_the_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            path = root / "data" / "app.json"
            path.write_text(json.dumps(entry()))
            before = path.read_bytes()
            corrupt = b"not a zip"
            changed, errors = scanner.scan(
                root, network([release(content=corrupt)], corrupt)
            )
            self.assertEqual((changed, errors), (0, []))
            self.assertEqual(path.read_bytes(), before)

    def test_failed_atomic_replace_keeps_original_and_removes_temporary_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "entry.json"
            path.write_bytes(b"original")
            with (
                mock.patch.object(
                    scanner.os, "replace", side_effect=OSError("read only")
                ),
                self.assertRaises(OSError),
            ):
                scanner.atomic_write(path, b"updated")
            self.assertEqual(path.read_bytes(), b"original")
            self.assertEqual(list(root.iterdir()), [path])

    def test_invalid_opt_in_is_reported_without_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            data = entry()
            data["scan_releases"] = "true"
            (root / "data" / "app.json").write_text(json.dumps(data))
            changed, errors = scanner.scan(root, lambda url: self.fail(url))
            self.assertEqual((changed, len(errors)), (0, 1))

    def test_new_releases_preserve_curated_fields_and_history(self):
        original = entry()
        updated, icon = scanner.prepare(original, network([release()]))
        self.assertEqual(original, entry())
        for key in original.keys() - {"releases"}:
            self.assertEqual(updated[key], original[key])
        self.assertEqual(updated["releases"][1], original["releases"][0])
        self.assertEqual(
            updated["releases"][0]["sha256"], hashlib.sha256(archive()).hexdigest()
        )
        self.assertEqual(updated["releases"][0]["changelog"], "Release notes")
        self.assertIsNone(icon)

    def test_known_tag_with_leading_v_is_not_downloaded_or_duplicated(self):
        known = release("v1.0")
        known["assets"][0]["digest"] = "sha256:" + "a" * 64

        def get(url):
            self.assertIn("api.github.com", url)
            return json.dumps([known]).encode()

        updated, _ = scanner.prepare(entry(), get)
        self.assertEqual(updated, entry())

    def test_known_asset_replacement_is_reported_without_blocking_updates(self):
        with self.assertLogs(scanner.LOGGER, level="WARNING") as logs:
            updated, _ = scanner.prepare(entry(), network([release("v1.0"), release()]))
        self.assertIn("known release asset changed", logs.output[0])
        self.assertEqual([r["tag"] for r in updated["releases"]], ["v2.0", "1.0"])
        self.assertEqual(updated["releases"][1], entry()["releases"][0])

    def test_drafts_and_prereleases_are_ignored(self):
        draft, preview = release(), release("v3.0")
        draft["draft"], preview["prerelease"] = True, True
        self.assertEqual(
            scanner.prepare(entry(), network([draft, preview]))[0], entry()
        )

    def test_pagination_reads_history_and_sorts_by_publication(self):
        first = [release(f"v{i}") for i in range(100)]
        last = release("v100", date="2026-10-02T12:00:00Z")

        def get(url):
            return json.dumps(first if url.endswith("page=1") else [last]).encode()

        fetched = scanner.fetch_releases("test/app", get)
        self.assertEqual(len(fetched), 101)
        self.assertEqual(fetched[0]["tag_name"], "v100")

    def test_same_day_backfill_stays_behind_the_known_newest_release(self):
        data = entry()
        data["releases"][0]["published_at"] = "2026-10-01"
        newest = release("v1.0", date="2026-10-01T18:00:00Z")
        newest["assets"][0]["digest"] = "sha256:" + "a" * 64
        older = release("v0.9", date="2026-10-01T08:00:00Z")
        updated, _ = scanner.prepare(data, network([older, newest]))
        self.assertEqual([r["tag"] for r in updated["releases"]], ["1.0", "v0.9"])

    def test_truncated_download_is_isolated_to_its_entry(self):

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            bad = entry()
            bad["source"] = "https://github.com/test/bad"
            path = root / "data" / "bad.json"
            path.write_text(json.dumps(bad))
            before = path.read_bytes()
            (root / "data" / "good.json").write_text(json.dumps(entry()))

            def get(url):
                if "/test/bad/" in url:
                    raise http.client.IncompleteRead(b"partial", 100)
                return network([release()])(url)

            changed, errors = scanner.scan(root, get)
            self.assertEqual((changed, len(errors)), (1, 1))
            self.assertEqual(path.read_bytes(), before)

    def test_zip_selection_requires_a_unique_match(self):
        r = release()
        r["assets"] += [copy.deepcopy(r["assets"][0])]
        self.assertIsNone(scanner.select_asset(r))
        r["assets"][1]["name"] = "linux.zip"
        self.assertEqual(scanner.select_asset(r)["name"], "psp.zip")

    def test_wrong_size_digest_and_download_host_are_rejected(self):
        for field, value in [
            ("size", 1),
            ("digest", "sha256:" + "0" * 64),
            ("browser_download_url", "https://example.org/app.zip"),
        ]:
            with self.subTest(field=field):
                r = release()
                r["assets"][0][field] = value
                with self.assertRaises(scanner.ScanError):
                    scanner.prepare(entry(), network([r]))

    def test_unsafe_ambiguous_and_invalid_packages_are_rejected(self):
        for entries in [
            {"../EBOOT.PBP": b"x"},
            {"EBOOT.PBP": b"x"},
            {"a/EBOOT.PBP": b"x", "b/EBOOT.PBP": b"x"},
            {"EBOOT.PBP": b"x", "eboot.pbp": b"x"},
        ]:
            with self.subTest(entries=entries), self.assertRaises(scanner.ScanError):
                scanner.inspect_package(archive(entries))

    def test_corrupt_non_eboot_resource_is_rejected(self):
        eboot = b"\x00PBP" + b"\x00\x00\x01\x00" + (40).to_bytes(4, "little") * 8
        content = archive(
            {"EBOOT.PBP": eboot, "resource.dat": b"unique resource bytes"}
        )
        damaged = content.replace(b"unique resource bytes", b"broken resource bytes", 1)
        with self.assertRaisesRegex(scanner.ScanError, "CRC"):
            scanner.inspect_package(damaged)

    def test_release_without_zip_does_not_block_other_releases(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            path = root / "data" / "app.json"
            path.write_text(json.dumps(entry()))
            older = release("v1.5", date="2026-09-15T12:00:00Z")
            older["assets"] = []
            changed, errors = scanner.scan(root, network([release(), older]))
            self.assertEqual((changed, errors), (1, []))
            self.assertEqual(
                [r["tag"] for r in json.loads(path.read_text())["releases"]],
                ["v2.0", "1.0"],
            )

    def test_redirects_drop_authentication_and_refuse_http(self):

        req = urllib.request.Request(
            "https://api.github.com/start", headers={"Authorization": "Bearer secret"}
        )
        redirect = scanner.Redirect()
        redirected = redirect.redirect_request(
            req, None, 302, "Found", {}, "https://other.example/end"
        )
        self.assertFalse(redirected.has_header("Authorization"))
        with self.assertRaises(scanner.ScanError):
            redirect.redirect_request(
                req, None, 302, "Found", {}, "http://other.example/end"
            )

    def test_only_opted_in_entries_are_requested(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            for flag in [None, False]:
                data = entry()
                if flag is None:
                    del data["scan_releases"]
                else:
                    data["scan_releases"] = flag
                (root / "data" / "app.json").write_text(json.dumps(data))
                self.assertEqual(
                    scanner.scan(root, lambda url: self.fail(url)), (0, [])
                )

    def test_failed_entry_is_unchanged_while_other_entry_updates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            bad, good = root / "data" / "bad.json", root / "data" / "good.json"
            broken = entry()
            broken["source"] = "https://example.org/"
            bad.write_text(json.dumps(broken))
            before = bad.read_bytes()
            good.write_text(json.dumps(entry()))
            changed, errors = scanner.scan(root, network([release()]))
            self.assertEqual(changed, 1)
            self.assertEqual(len(errors), 1)
            self.assertEqual(bad.read_bytes(), before)
            self.assertEqual(json.loads(good.read_text())["releases"][0]["tag"], "v2.0")

    def test_dry_run_and_second_scan_do_not_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            path = root / "data" / "app.json"
            path.write_text(json.dumps(entry()))
            before = path.read_bytes()
            self.assertEqual(scanner.scan(root, network([release()]), True), (1, []))
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(scanner.scan(root, network([release()])), (1, []))
            after = path.read_bytes()
            self.assertEqual(scanner.scan(root, network([release()])), (0, []))
            self.assertEqual(path.read_bytes(), after)

    def test_ci_controls_survive_existing_enrichment_script_round_trip(self):
        for flag in [True, False]:
            data = entry()
            data["scan_releases"] = flag
            updated = get_homebrew_from_json_data("app", data).to_dict(include_ci=True)
            self.assertIs(updated["scan_releases"], flag)


if __name__ == "__main__":
    unittest.main()
