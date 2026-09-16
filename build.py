#!/usr/bin/env python3

import datetime
import os
import json
import logging
import shutil

import jinja2
import jsonschema

from homebrew_database.homebrew import Homebrew, get_homebrew_list


DATA_DIR = "data"
DIST_DIR = "dist"
RESOURCE_DIR = "resources"
TEMPLATE_DIR = "templates"
TEMP_DIR = "temp"
SCHEMA_DIR = os.path.join(RESOURCE_DIR, "schemas")


def create_dist_dir() -> None:
    if os.path.isdir(DIST_DIR):
        for file_name in os.listdir(DIST_DIR):
            file_path = os.path.join(DIST_DIR, file_name)
            if not os.path.isdir(file_path):
              os.remove(file_path)
            else:
              shutil.rmtree(file_path)
        os.rmdir(DIST_DIR)
    os.mkdir(DIST_DIR)


def create_json_catalog(homebrew_list: list[Homebrew]) -> None:
    schema_name = "catalog.schema.json"
    generated_at = datetime.datetime.now().replace(microsecond=0)
    homebrew_dict = {
        "schema": f"schemas/{schema_name}",
        "generated_at": generated_at.isoformat() + "Z",
        "apps": []
    }
    for homebrew in homebrew_list:
        homebrew_dict["apps"].append(homebrew.to_dict())

    # Validate the generated dict against the schema
    json_schema_path = os.path.join(SCHEMA_DIR, schema_name)
    with open(json_schema_path, "r") as fd:
        json_schema = json.loads(fd.read())
    json_output = json.dumps(homebrew_dict)
    jsonschema.validate(instance=json.loads(json_output), schema=json_schema)

    with open(os.path.join(DIST_DIR, "catalog.json"), "w") as fd:
        fd.write(json_output)


def create_pkgi_catalogs(homebrew_list: list[Homebrew]) -> None:
    categories = ["game", "emulator", "application"]
    content_per_category = {}
    for category in categories:
        content_per_category[category] = ""

    for homebrew in homebrew_list:
        if homebrew.category == "game":
            pkgi_type = 1
        elif homebrew.category == "emulator":
            pkgi_type = 7
        elif homebrew.category == "application":
            pkgi_type = 8
        else:
            continue

        release = homebrew.releases[0]
        content_per_category[homebrew.category] += f",{pkgi_type},{homebrew.name},\"{homebrew.summary}\",,{release.url},{release.size},{release.sha256}\n"

    for category in categories:
        with open(os.path.join(DIST_DIR, f"pkgi_{category}s.txt"), "w") as fd:
            fd.write(content_per_category[category])

    with open(os.path.join(DIST_DIR, "pkgi.txt"), "w") as fd:
        content = "".join(content_per_category[category] for category in categories)
        fd.write(content)


def create_pkgi_config() -> None:
    # Only create this file if the build is happening from the GitHub CI
    # Otherwise we have no clue what the url should be
    if not os.environ.get("CI"):
        return
    owner,repo = os.environ["GITHUB_REPOSITORY"].split("/")

    config_content = f"url https://{owner}.github.io/{repo}/pkgi.txt"
    with open(os.path.join(DIST_DIR, "config.txt"), "w") as fd:
        fd.write(config_content)


def create_pages(homebrew_list: list[Homebrew]) -> None:
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
        with open(os.path.join(DIST_DIR, f"{homebrew.id}.html"), "w") as fd:
            fd.write(
                homebrew_template.render(
                    homebrew=homebrew
                )
            )


def copy_resources() -> None:
    for file_name in os.listdir(RESOURCE_DIR):
        file_path = os.path.join(RESOURCE_DIR, file_name)
        if os.path.isdir(file_path):
            shutil.copytree(file_path, os.path.join(DIST_DIR, file_name))
        elif os.path.isfile(file_path):
            shutil.copy2(file_path, DIST_DIR)


def configure_logger():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)


def main() -> None:
    configure_logger()

    create_dist_dir()

    homebrew_list = get_homebrew_list(data_dir=DATA_DIR)
    create_pages(homebrew_list=homebrew_list)
    create_json_catalog(homebrew_list=homebrew_list)
    create_pkgi_catalogs(homebrew_list=homebrew_list)
    create_pkgi_config()
    copy_resources()

if __name__ == "__main__":
    main()
