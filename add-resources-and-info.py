#!/usr/bin/env python3

import hashlib
import urllib.request
import urllib.parse
import zipfile
import os
import logging
import tempfile
import json

from homebrew_database.homebrew import HomebrewProcessingException, Homebrew, Release, get_homebrew_list


DATA_DIR = "data"
RESOURCE_DIR = "resources"
ICON_DIR = os.path.join(RESOURCE_DIR, "icons")


def get_sha256_hash(file_path: str) -> str:
    with open(file_path, "rb") as f:
        digest = hashlib.file_digest(f, "sha256")
        return digest.hexdigest()


def get_eboot_data_from_zip_archive(file_path: str):
    with zipfile.ZipFile(file_path) as fd:
        eboot_path_in_zip = None
        for file_name in fd.namelist():
            if file_name.lower().endswith("eboot.pbp"):
                eboot_path_in_zip = file_name
                break;
        if eboot_path_in_zip is None:
            raise HomebrewProcessingException(f"No EBOOT.PBP found in file {file_path}")
        return fd.read(eboot_path_in_zip)


def get_eboot_data(archive_path: str) -> bytearray:
    file_extension = os.path.splitext(archive_path)[-1].lower()
    if file_extension not in [".zip", ".pbp"]:
        raise HomebrewProcessingException(f"File format {file_extension} is not supported")
    if file_extension == ".zip":
        return get_eboot_data_from_zip_archive(file_path=archive_path)
    elif file_extension == ".pbp":
        with open(archive_path, "rb") as fd:
          return fd.read()
    raise HomebrewProcessingException(f"Data in EBOOT.PBP in {archive_path} could not be read")


def extract_icon(eboot_data: bytearray, target_path: str) -> None:
    if eboot_data[0:4] != b'\x00PBP':
        raise HomebrewProcessingException(f"No valid EBOOT.PBP found, header doesn't match")
    icon0_offset = int.from_bytes(eboot_data[12:16], byteorder='little')
    if icon0_offset == 0:
        raise HomebrewProcessingException(f"No icon0.png found in EBOOT.PBP")
    icon1_offset = int.from_bytes(eboot_data[16:20], byteorder='little')
    if icon0_offset == icon1_offset:
        raise HomebrewProcessingException(f"EBOOT.PBP has no icon0.png")
    with open(target_path, "wb") as fd:
        fd.write(eboot_data[icon0_offset:icon1_offset])


def download_archive(url: str, target_dir: str) -> str:
      parsed_url = urllib.parse.urlparse(url)
      file_path = os.path.join(target_dir, os.path.basename(parsed_url.path))
      urllib.request.urlretrieve(url=url, filename=file_path)
      return file_path
    

def configure_logger():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)


def main():
    configure_logger()

    homebrew_list = get_homebrew_list(data_dir=DATA_DIR)
    for homebrew in homebrew_list:
        homebrew_json_path = os.path.join(DATA_DIR, f"{homebrew.slug}.json")
        icon_path = os.path.join(ICON_DIR, f"{homebrew.slug}.png")            
        for i, release in enumerate(homebrew.releases):
          if release.sha256 is not None and release.eboot_md5 is not None and homebrew.icon is not None and os.path.exists(icon_path):
              logging.info(f"No actions required for {homebrew.name} {release.version}")
              continue
          with tempfile.TemporaryDirectory() as target_dir:
              logging.info(f"Downloading {homebrew.name} {release.version} archive")
              archive_path = download_archive(url=release.download_link, target_dir=target_dir)
              logging.info(f"Adding sha256 to {homebrew.name} {release.version} archive")
              release.sha256 = get_sha256_hash(file_path=archive_path)
              eboot_data = get_eboot_data(archive_path)
          if i == 0 and (not os.path.exists(icon_path) or homebrew.icon is None):
              logging.info(f"Extracting icon for {homebrew.name} {release.version}")
              extract_icon(eboot_data=eboot_data, target_path=icon_path)
              homebrew.icon = os.path.join(RESOURCE_DIR, os.path.basename(icon_path))
          logging.info(f"Adding md5 for eboot of {homebrew.name} {release.version}")
          release.eboot_md5 = hashlib.md5(data=eboot_data, usedforsecurity=False).hexdigest()

        logging.info(f"Writing {homebrew_json_path}")
        with open(homebrew_json_path, "w") as fd:
            fd.write(json.dumps(homebrew.to_dict(), indent=2))
    logging.info("Done, make sure to add and commit changes to the data and resources directory to git")


if __name__ == "__main__":
    main()
