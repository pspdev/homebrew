#!/usr/bin/env python3

from dataclasses import dataclass, field
import datetime
import glob
import os
import json
import logging
import shutil

import jinja2


DATA_DIR = "data"
DIST_DIR = "dist"
RESOURCE_DIR = "resources"
TEMPLATE_DIR = "templates"


class HomebrewProcessingException(Exception):
    pass


@dataclass
class Release:
    version: str
    download_link: str
    date: datetime.date
    checksum: str
    changelog: str | None = None

    def __gt__(self, other: 'Release') -> bool:
        return self.date > other.date

    def to_dict(self) -> dict:
        return_dict = {
            "version": self.version,
            "download_link": self.download_link,
            "date": self.date.isoformat(),
            "checksum": self.checksum 
        }
        if self.changelog is not None:
            return_dict["changelog"] = self.changelog
        return return_dict


@dataclass
class Homebrew:
    name: str
    slug: str
    summary: str
    creator: str
    screenshots: list[str]
    ai_used: bool
    description: str | None = None
    website: str | None = None
    creator_link: str | None = None
    source_link: str | None = None
    license: str | None = None
    license_link: str | None = None
    releases: list[Release] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def __gt__(self, other: 'Homebrew') -> bool:
        self_last_release = self.get_last_release()
        other_last_release = other.get_last_release()
        if other_last_release is None:
            return self
        if self_last_release is None:
            return other
        return self.get_last_release() > other.get_last_release()

    def get_last_release(self) -> Release | None:
        if len(self.releases) == 0:
            return None
        return sorted(self.releases)[0]

    def to_dict(self) -> dict:
        return_dict = {
            "name": self.name,
            "slug": self.slug,
            "description": self.summary,
            "creator": self.creator,
            "screenshots": self.screenshots,
            "ai_used": self.ai_used,
            "releases": [],
            "tags": self.tags,
        }

        if self.description is not None:
            return_dict["description"] = self.description
        if self.website is not None:
            return_dict["website"] = self.website
        if self.creator_link is not None:
            return_dict["creator_link"] = self.creator_link
        if self.source_link is not None:
            return_dict["source_link"] = self.source_link
        if self.license is not None:
            return_dict["license"] = self.license
        if self.license_link is not None:
            return_dict["license_link"] = self.license_link
        
        self.releases.sort(reverse=True)
        for release in self.releases:
            return_dict["releases"].append(release.to_dict())

        return return_dict


def get_homebrew_from_json_data(slug: str, data: dict) -> Homebrew:
    if not data:
        raise HomebrewProcessingException(f"No data to read found in {slug}")

    try:
        releases = []
        for release_data in data["releases"]:
            releases.append(
                Release(
                    version=release_data["version"],
                    download_link=release_data["download_link"],
                    changelog=release_data.get("changelog", None),
                    date=datetime.date.fromisoformat(release_data["date"]),
                    checksum=release_data["checksum"],
                )
            )

        homebrew = Homebrew(
          name=data["name"],
          slug=slug,
          summary=data["summary"],
          creator=data["creator"],
          screenshots=data["screenshots"],
          ai_used=data["ai_used"],
          description=data.get("description", None),
          website=data.get("website", None),
          creator_link=data.get("creator_link", None),
          source_link=data.get("source_link", None),
          license=data.get("license", None),
          license_link=data.get("license_link", None),
          releases=releases,
          tags=data.get("tags", list()),
        )
    except (KeyError, ValueError) as e:
        raise HomebrewProcessingException(f"Could not process json data for {slug}") from e

    return homebrew


def get_homebrew_list() -> list[Homebrew]:
    homebrew_list = []
    failed_to_load = []
    for file_name in glob.iglob(f"{DATA_DIR}/**", recursive=True):
        if not file_name.endswith(".json"):
            continue
        if not os.path.isfile(file_name):
            continue
        with open(file_name, "r") as fd:
            try:
                data = json.loads(fd.read())
                slug = os.path.splitext(os.path.basename(file_name))[0]
                homebrew = get_homebrew_from_json_data(slug=slug, data=data)
                homebrew_list.append(homebrew)
            except (json.JSONDecodeError, TypeError, HomebrewProcessingException):
                logging.error("Could no load the content of %s as json", file_name, exc_info=True)
                failed_to_load.append(file_name)
                continue
    if len(failed_to_load) > 0:
        raise HomebrewProcessingException(f"Failed to process {','.join(failed_to_load)}")

    homebrew_list.sort(reverse=True)
    return homebrew_list


def create_dist_dir() -> None:
    if os.path.isdir(DIST_DIR):
        for file_name in os.listdir(DIST_DIR):
            if not os.path.isdir(file_name):
              os.remove(os.path.join(DIST_DIR, file_name))
        os.rmdir(DIST_DIR)
    os.mkdir(DIST_DIR)


def create_homebrew_list_json_file(homebrew_list: list[Homebrew]) -> None:
    homebrew_dicts = []
    for homebrew in homebrew_list:
        homebrew_dicts.append(homebrew.to_dict())

    with open(os.path.join(DIST_DIR, "homebrew.json"), "w") as fd:
        fd.write(json.dumps(homebrew_dicts))
    

def create_index_page(homebrew_list: list[Homebrew]) -> None:
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATE_DIR))

    index_file_name = "index.html"
    index_template = env.get_template(index_file_name)

    with open(os.path.join(DIST_DIR, index_file_name), "w") as fd:
        fd.write(
            index_template.render(
                homebrew_list=homebrew_list
            )
        )

    homebrew_template = env.get_template("homebrew.html")
    for homebrew in homebrew_list:
        with open(os.path.join(DIST_DIR, f"{homebrew.slug}.html"), "w") as fd:
            fd.write(
                homebrew_template.render(
                    homebrew=homebrew
                )
            )


def copy_resources() -> None:
    for file_name in os.listdir(RESOURCE_DIR):
        shutil.copy2(os.path.join(RESOURCE_DIR, file_name), DIST_DIR)


def main() -> None:
    create_dist_dir()

    homebrew_list = get_homebrew_list()
    create_homebrew_list_json_file(homebrew_list=homebrew_list)
    create_index_page(homebrew_list=homebrew_list)
    copy_resources()

if __name__ == "__main__":
    main()
