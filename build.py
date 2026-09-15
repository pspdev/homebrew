#!/usr/bin/env python3

import datetime
import os
import json
import logging
import shutil
import zoneinfo

import jinja2

from homebrew_database.homebrew import Homebrew, get_homebrew_list


DATA_DIR = "data"
DIST_DIR = "dist"
RESOURCE_DIR = "resources"
TEMPLATE_DIR = "templates"
TEMP_DIR = "temp"


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


def create_homebrew_list_json_file(homebrew_list: list[Homebrew]) -> None:
    generated_at = datetime.datetime.now().replace(microsecond=0)
    homebrew_dict = {
        "generated_at": generated_at.isoformat() + "Z",
        "apps": []
    }
    for homebrew in homebrew_list:
        homebrew_dict["apps"].append(homebrew.to_dict())

    with open(os.path.join(DIST_DIR, "homebrew.json"), "w") as fd:
        fd.write(json.dumps(homebrew_dict))
    

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
    create_homebrew_list_json_file(homebrew_list=homebrew_list)
    copy_resources()

if __name__ == "__main__":
    main()
