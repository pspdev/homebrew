#!/usr/bin/env python3
"""Refresh opted-in database entries from GitHub releases, without .pspdx.

Only releases and, when a newer package supplies one, the icon are changed.
Each entry is prepared completely before writing; failures leave it intact.
"""

import argparse
import copy
import datetime
import hashlib
import http.client
import io
import json
import logging
import os
import re
import stat
import tempfile
import urllib.parse
import urllib.request
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOGGER = logging.getLogger(__name__)
MAX_DOWNLOAD = 256 * 1024 * 1024
MAX_API_RESPONSE = 8 * 1024 * 1024
MAX_UNPACKED = 512 * 1024 * 1024
MAX_EBOOT = 64 * 1024 * 1024
MAX_ICON = 2 * 1024 * 1024


class ScanError(ValueError):
    pass


class PackageError(ScanError):
    pass


class Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme != "https":
            raise ScanError("redirect outside HTTPS")
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None:
            redirected.remove_header("Authorization")
        return redirected


def fetch(url):
    headers = {"User-Agent": "pspdev-homebrew-release-scanner"}
    limit = MAX_DOWNLOAD
    if urllib.parse.urlsplit(url).hostname == "api.github.com":
        headers["Accept"] = "application/vnd.github+json"
        headers["X-GitHub-Api-Version"] = "2022-11-28"
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        limit = MAX_API_RESPONSE
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.build_opener(Redirect()).open(request, timeout=60) as response:
        content = response.read(limit + 1)
    if len(content) > limit:
        raise ScanError("response too large")
    return content


def repository(source):
    if not isinstance(source, str):
        raise ScanError("source must name a GitHub repository")
    match = re.fullmatch(
        r"https://github\.com/([A-Za-z0-9_.-]{1,39})/"
        r"([A-Za-z0-9_.-]{1,100})/?",
        source,
    )
    if not match:
        raise ScanError("source must name a GitHub repository")
    owner, repo = match.groups()
    repo = repo.removesuffix(".git")
    if not any(c.isalnum() for c in owner) or not any(c.isalnum() for c in repo):
        raise ScanError("invalid repository name")
    return f"{owner}/{repo}"


def fetch_releases(repo, fetcher):
    result = []
    for page in range(1, 101):
        batch = json.loads(
            fetcher(
                f"https://api.github.com/repos/{repo}/releases?per_page=100&page={page}"
            )
        )
        if not isinstance(batch, list):
            raise ScanError("GitHub did not return a release list")
        result.extend(r for r in batch if not r["draft"] and not r["prerelease"])
        if len(batch) < 100:
            return sorted(result, key=lambda r: r["published_at"], reverse=True)
    raise ScanError("too many release pages; refusing incomplete history")


def tag_key(tag):
    # Curated entries sometimes spell GitHub's v0.8.5 as 0.8.5.
    return tag[1:] if tag.startswith("v") and len(tag) > 1 and tag[1].isdigit() else tag


def select_asset(release):
    candidates = [a for a in release["assets"] if a["name"].lower().endswith(".zip")]
    if len(candidates) > 1:
        candidates = [a for a in candidates if "psp" in a["name"].lower()]
    return candidates[0] if len(candidates) == 1 else None


def inspect_package(archive):
    # Never extract files or execute code from the downloaded package.
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
            entries = zipped.infolist()
            if len(entries) > 10000 or sum(i.file_size for i in entries) > MAX_UNPACKED:
                raise PackageError("ZIP exceeds unpacked limits")
            names, eboots = set(), []
            for entry in entries:
                name = entry.filename.replace("\\", "/")
                parts = name.rstrip("/").split("/")
                if (
                    name.startswith("/")
                    or any(p in {"", ".", ".."} or ":" in p for p in parts)
                    or any(ord(c) < 32 for c in entry.orig_filename)
                ):
                    raise PackageError("unsafe ZIP path")
                mode = entry.external_attr >> 16
                if (
                    stat.S_IFMT(mode) not in {0, stat.S_IFREG, stat.S_IFDIR}
                    or entry.flag_bits & 1
                ):
                    raise PackageError("special file or encrypted ZIP entry")
                key = name.rstrip("/").casefold()
                if key in names:
                    raise PackageError("duplicate ZIP path")
                names.add(key)
                if not entry.is_dir() and parts[-1].lower() == "eboot.pbp":
                    eboots.append(entry)
            # Deliberately stricter than the client: ambiguous layouts need a
            # curator rather than an unattended guess.
            if len(eboots) != 1:
                raise PackageError("ZIP must contain exactly one EBOOT.PBP")
            if eboots[0].file_size > MAX_EBOOT:
                raise PackageError("EBOOT.PBP too large")
            # Check every payload, not just the PBP: a corrupt resource file
            # must not become an automatically approved package.
            bad = zipped.testzip()
            if bad is not None:
                raise PackageError(f"ZIP CRC mismatch: {bad}")
            eboot = zipped.read(eboots[0])  # zipfile checks this entry's CRC.
    except (zipfile.BadZipFile, RuntimeError, EOFError, zlib.error) as error:
        raise PackageError(f"invalid ZIP: {error}") from error
    if len(eboot) < 40 or eboot[:4] != b"\x00PBP":
        raise PackageError("invalid EBOOT.PBP header")
    offsets = [int.from_bytes(eboot[at : at + 4], "little") for at in range(8, 40, 4)]
    if offsets[0] < 40 or offsets != sorted(offsets) or offsets[-1] > len(eboot):
        raise PackageError("invalid EBOOT.PBP offsets")
    icon = eboot[offsets[1] : offsets[2]]
    if len(icon) > MAX_ICON or (icon and not icon.startswith(b"\x89PNG\r\n\x1a\n")):
        raise PackageError("invalid ICON0.PNG")
    return hashlib.md5(eboot, usedforsecurity=False).hexdigest(), icon


def release_record(repo, release, asset, fetcher):
    url = asset["browser_download_url"]
    if not url.startswith(f"https://github.com/{repo}/releases/download/"):
        raise ScanError("asset does not belong to the approved repository")
    if type(asset["size"]) is not int or not 0 < asset["size"] <= MAX_DOWNLOAD:
        raise ScanError("invalid asset size")
    archive = fetcher(url)
    if len(archive) != asset["size"]:
        raise ScanError("asset size does not match GitHub")
    sha = hashlib.sha256(archive).hexdigest()
    if asset.get("digest") and asset["digest"] != "sha256:" + sha:
        raise ScanError("asset SHA-256 does not match GitHub")
    eboot_md5, icon = inspect_package(archive=archive)
    published = datetime.datetime.fromisoformat(
        release["published_at"].replace("Z", "+00:00")
    )
    if published.tzinfo is None:
        raise ScanError("release timestamp has no timezone")
    date = published.astimezone(datetime.timezone.utc).date().isoformat()
    record = {
        "tag": release["tag_name"],
        "url": url,
        "published_at": date,
        "size": len(archive),
        "sha256": sha,
        "eboot_md5": eboot_md5,
    }
    if release.get("body"):
        record["changelog"] = release["body"]
    return record, icon


def check_known_asset(repo, release, existing):
    # A replacement needs manual review, but must not block newer releases.
    for asset in release["assets"]:
        if asset["browser_download_url"] != existing["url"]:
            continue
        digest = asset.get("digest")
        if (
            digest
            and existing.get("sha256")
            and digest != "sha256:" + existing["sha256"]
        ):
            LOGGER.warning(
                "%s %s: known release asset changed; kept existing record",
                repo,
                release["tag_name"],
            )


def prepare(data, fetcher):
    repo = repository(source=data.get("source"))
    existing = data["releases"]
    if not isinstance(existing, list):
        raise ScanError("releases must be a list")
    known = {tag_key(tag=r["tag"]): r for r in existing}
    # Optional: read the repo's .pspdx here for release selection or metadata updates.
    remote = fetch_releases(repo=repo, fetcher=fetcher)
    added, icon = [], None
    latest_date = max((r["published_at"] for r in existing), default="")
    newest_seen = False
    for release in remote:
        key = tag_key(tag=release["tag_name"])
        if key in known:
            newest_seen = True
            check_known_asset(repo=repo, release=release, existing=known[key])
            continue
        asset = select_asset(release=release)
        if asset is None:
            LOGGER.warning(
                "%s %s: no unique ZIP asset, skipped", repo, release["tag_name"]
            )
            continue
        try:
            record, new_icon = release_record(
                repo=repo, release=release, asset=asset, fetcher=fetcher
            )
        except PackageError as error:
            LOGGER.warning("%s %s: %s, skipped", repo, release["tag_name"], error)
            continue
        if not newest_seen and record["published_at"] >= latest_date:
            icon = new_icon or None
        newest_seen = True
        added.append(record)
        known[key] = record
    updated = copy.deepcopy(data)
    if added:
        # Dates in this database have no time of day. Use GitHub's full
        # timestamp order to keep same-day backfills behind newer releases.
        order = {tag_key(tag=r["tag_name"]): index for index, r in enumerate(remote)}
        updated["releases"] = sorted(
            added + existing,
            key=lambda r: (
                r["published_at"],
                -order.get(tag_key(tag=r["tag"]), len(remote)),
            ),
            reverse=True,
        )
    return updated, icon


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
            name = Path(temporary.name)
            temporary.write(content)
        os.replace(name, path)
    finally:
        if name is not None:
            name.unlink(missing_ok=True)


def scan(root, fetcher=fetch, dry_run=False):
    changed, errors = 0, []
    for path in sorted((root / "data").rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            flag = data.get("scan_releases", False)
            if type(flag) is not bool:
                raise ScanError("scan_releases must be a boolean")
            if not flag:
                continue
            updated, icon = prepare(data=data, fetcher=fetcher)
            if updated == data:
                continue
            icon_path = None
            if icon:
                name = f"icons/{path.stem}.png"
                updated["media"]["icon"] = name
                icon_path = root / "resources" / name
            content = json.dumps(updated, indent=2).encode("utf-8")
            if not dry_run:
                if icon_path:
                    atomic_write(path=icon_path, content=icon)
                atomic_write(path=path, content=content)
            changed += 1
            LOGGER.info(
                "%s: %d releases added",
                path.name,
                len(updated["releases"]) - len(data["releases"]),
            )
        except (
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
            OSError,
            http.client.HTTPException,
        ) as error:
            errors.append(f"{path.name}: {error}")
            LOGGER.error("%s", errors[-1])
    return changed, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="download and check without writing"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    changed, errors = scan(root=ROOT, dry_run=args.dry_run)
    LOGGER.info(
        "%d entries %s, %d errors",
        changed,
        "would change" if args.dry_run else "changed",
        len(errors),
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
