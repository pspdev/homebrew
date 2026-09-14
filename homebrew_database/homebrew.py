from dataclasses import dataclass, field
import datetime
import os
import json
import glob
import logging


class HomebrewProcessingException(Exception):
    pass


@dataclass
class Release:
    tag: str
    download_link: str
    published_at: datetime.date
    sha256: str | None = None
    eboot_md5: str | None = None
    changelog: str | None = None
    size: int | None = None

    def __gt__(self, other: 'Release') -> bool:
        return self.published_at > other.published_at

    def to_dict(self) -> dict:
        return_dict = {
            "tag": self.tag,
            "download_link": self.download_link,
            "published_at": self.published_at.isoformat(),
            "size": self.size,
        }
        if self.sha256 is not None:
            return_dict["sha256"] = self.sha256
        if self.eboot_md5 is not None:
            return_dict["eboot_md5"] = self.eboot_md5
        if self.changelog is not None:
            return_dict["changelog"] = self.changelog
        if self.size is not None:
            return_dict["size"] = self.size
        return return_dict


@dataclass
class Homebrew:
    name: str
    id: str
    summary: str
    author: str
    screenshots: list[str]
    ai_used: bool
    requires_additional_files: bool
    category: str
    description: str | None = None
    website: str | None = None
    author_link: str | None = None
    source: str | None = None
    license: str | None = None
    license_link: str | None = None
    releases: list[Release] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    icon: str = None

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
            "id": self.id,
            "summary": self.summary,
            "author": self.author,
            "screenshots": self.screenshots,
            "ai_used": self.ai_used,
            "requires_additional_files": self.requires_additional_files,
            "category": self.category,
            "releases": [],
            "tags": self.tags,
        }

        if self.description is not None:
            return_dict["description"] = self.description
        if self.website is not None:
            return_dict["website"] = self.website
        if self.author_link is not None:
            return_dict["author_link"] = self.author_link
        if self.source is not None:
            return_dict["source"] = self.source
        if self.license is not None:
            return_dict["license"] = self.license
        if self.license_link is not None:
            return_dict["license_link"] = self.license_link
        if self.icon is not None:
            return_dict["icon"] = self.icon
        
        self.releases.sort(reverse=True)
        for release in self.releases:
            return_dict["releases"].append(release.to_dict())

        return return_dict


def get_homebrew_from_json_data(id: str, data: dict) -> Homebrew:
    if not data:
        raise HomebrewProcessingException(f"No data to read found in {id}")

    try:
        releases = []
        for release_data in data["releases"]:
            releases.append(
                Release(
                    tag=release_data["tag"],
                    download_link=release_data["download_link"],
                    changelog=release_data.get("changelog", None),
                    published_at=datetime.date.fromisoformat(release_data["published_at"]),
                    sha256=release_data.get("sha256", None),
                    eboot_md5=release_data.get("eboot_md5", None),
                    size=release_data.get("size", None),
                )
            )

        homebrew = Homebrew(
          name=data["name"],
          id=id,
          summary=data["summary"],
          author=data["author"],
          screenshots=data["screenshots"],
          ai_used=data["ai_used"],
          requires_additional_files=data["requires_additional_files"],
          category=data["category"],
          description=data.get("description", None),
          website=data.get("website", None),
          author_link=data.get("author_link", None),
          source=data.get("source", None),
          license=data.get("license", None),
          license_link=data.get("license_link", None),
          releases=releases,
          tags=data.get("tags", list()),
          icon=data.get("icon", None)
        )
    except (KeyError, ValueError) as e:
        raise HomebrewProcessingException(f"Could not process json data for {id}") from e

    return homebrew


def get_homebrew_list(data_dir: str) -> list[Homebrew]:
    homebrew_list = []
    failed_to_load = []
    for file_name in glob.iglob(f"{data_dir}/**", recursive=True):
        if not file_name.endswith(".json"):
            continue
        if not os.path.isfile(file_name):
            continue
        with open(file_name, "r") as fd:
            try:
                data = json.loads(fd.read())
                id = os.path.splitext(os.path.basename(file_name))[0]
                homebrew = get_homebrew_from_json_data(id=id, data=data)
                homebrew_list.append(homebrew)
            except (json.JSONDecodeError, TypeError, HomebrewProcessingException):
                logging.error("Could no load the content of %s as json", file_name, exc_info=True)
                failed_to_load.append(file_name)
                continue
    if len(failed_to_load) > 0:
        raise HomebrewProcessingException(f"Failed to process {','.join(failed_to_load)}")

    homebrew_list.sort(reverse=True)
    return homebrew_list
