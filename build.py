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
    homebrew_by_catergory = {}
    for homebrew in homebrew_list:
        if homebrew.category not in homebrew_by_catergory:
            homebrew_by_catergory[homebrew.category] = [homebrew]
        else:
            homebrew_by_catergory[homebrew.category].append(homebrew)

    if "game" in homebrew_by_catergory and len(homebrew_by_catergory["game"]) > 0:
        game_csv = ""
        for homebrew in homebrew_by_catergory["game"]:
            release = homebrew.releases[0]
            game_csv += f",1,{homebrew.name},\"{homebrew.summary}\",{release.url},{release.size},{release.sha256}\n"

        with open(os.path.join(DIST_DIR, "pkgi_games.txt"), "w") as fd:
            fd.write(game_csv)

    if "emulator" in homebrew_by_catergory and len(homebrew_by_catergory["emulator"]) > 0:
        emulator_csv = ""
        for homebrew in homebrew_by_catergory["emulator"]:
            release = homebrew.releases[0]
            emulator_csv += f",7,{homebrew.name},\"{homebrew.summary}\",{release.url},{release.size},{release.sha256}\n"

        with open(os.path.join(DIST_DIR, "pkgi_emulators.txt"), "w") as fd:
            fd.write(emulator_csv)

    if "application" in homebrew_by_catergory and len(homebrew_by_catergory["application"]) > 0:
        application_csv = ""
        for homebrew in homebrew_by_catergory["application"]:
            release = homebrew.releases[0]
            application_csv += f",8,{homebrew.name},\"{homebrew.summary}\",{release.url},{release.size},{release.sha256}\n"

        with open(os.path.join(DIST_DIR, "pkgi_applications.txt"), "w") as fd:
            fd.write(application_csv)


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
    copy_resources()

if __name__ == "__main__":
    main()
