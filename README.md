# PSP Homebrew Database

This repo contains the source for a Playstation Portable homebrew database.

## Building the website

To build the website you need Python 3 to be installed. To set up your environment for building you can execute the following commands:

```
git clone https://github.com/sharkwouter/psp-homebrew-database.git
cd psp-homebrew-database
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

After having done the step above once, the website can be build with the following commands:

```
source venv/bin/activate
./build.py
```

The resulting website can be found in the newly created `dist` directory.

## Adding new homebrew

New entries go in the `data` directory using the following json format:

```
{
  "name": "Name of Homebrew",
  "summary": "Short description, 1 sentence",
  "description": "Full description, optional. Can be many sentences long.",
  "author": "name of the author",
  "ai_used": false,
  "requires_additional_files": false,
  "category": "game",
  "releases": [
    {
      "tag": "v1.0",
      "url": "https://example.com/",
      "published_at": "2026-07-23",
      "changelog": "Added something new"
    }
  ],
  "tags": [
    ""
  ],
  "source": "https://example.com/",
  "license": "GPLv3",
  "website": "https://example.com"
  "media": {
    "screenshots": [
      "https://example.com/"
    ]
  }
}
```

The name of the file should match the name of the file without capital letters special characters other than `_`. 

Here a description of each field:

| Field | Description | Required |
|------|-------------|----------|
| name | Name of the homebrew | Yes |
| summary | Max 60 character description about what the homebrew is | Yes |
| description | Full description | No |
| author | Name of the author of the homebrew | Yes |
| screenshots | A list of links to screenshots | Yes, but can be empty |
| ai_used | Was the homebrew made with AI | Yes |
| requires_additional_files | Set to true if the homebrew requires the user to add additional files for it to work | Yes |
| category | Category the homebrew belongs to. Should be set to `game`, `application` or `emulator` | Yes |
| tags | Tags that fit the homebrew, should always be lower case. Try to match with other existing tags if possible | Yes |
| source | A link to the location where the source code of the homebrew can be found | No |
| license | The name of the license the homebrew was released under | No |
| website | The website for the homebrew | No |
| languages | List of 2 letter codes for supported languages (think en, de, ch) | No |
| media | A json object containing an attribute called screenshots with a list of screenshots | Yes |
| releases | Contains download information per tag. See the table below | Yes |

Here is a description for each field in a release:

| Field | Description | Required |
|------|-------------|----------|
| tag | Name of the release tag, for example `1.0` | Yes |
| url | Link to the `.zip` archive or `EBOOT.PBP` file | Yes |
| published_at | Release data of this tag | Yes |
| changelog | What was change with the new release. This can be longer and contain newline characters | No |

After creating the file, run the `add-resources-and-info.py` script once. This will add the icon and information like the md5 checksum of the `EBOOT.PBP` and the sha256 checksum and sie of the archive for each release. If this wasn't done, the build will fail.

## Using the homebrew database data in applications

The PSP Homebrew Database supports a couple of formats for applications like homebrew stores to use. Below they will be listed with a description of how to use each.

### PKGi format

The [PKGi PSP application](https://github.com/bucanero/pkgi-psp/) has its own custom format that the PSP Homebrew Database supports as well. The specification for it can be found [here](https://github.com/bucanero/pkgi-psp/tree/main#db-formats). The following files belong to it:

- pkgi.txt
- pkgi_games.txt
- pkgi_emulators.txt
- pkgi_applications.txt
- config.txt

The `pkgi.txt` file contains all homebrews, the other `pkgi_*.txt` files contain only one category of homebrew. The `config.txt` contains where to find `pkgi.txt`, which can be used by PKGi PSP.

### PSPDX Format

The `catalog.json` file is a format from the [PSPDX standard](https://chriopter.github.io/pspdx/). The full schema for it can be found in [resources/schemas/catalog.schema.json](resources/schemas/catalog.schema.json).

### Custom Binary Catalog

This is the most compact format offered by the PSP Homebrew Database. It is completely custom an available in the following files:

- catalog.bin
- catalog.bin.gz

The `.gz` version contains the same data but gzipped. 

This format represented as a C struct would look like this:

```
typedef struct __attribute__((__packed__)) {
   uint8_t category; // can be 1 for game, 2 for emulator, 3 for application
   uint8_t id_length;
   uint32_t id_offset;
   uint8_t name_length;
   uint32_t name_offset;
   uint8_t summary_length;
   uint32_t summary_offset;
   uint8_t author_length;
   uint32_t author_offset;
   uint8_t tag_length;
   uint32_t tag_offset;
   uint8_t url_length;
   uint32_t url_offset;
   uint32_t published_at;
   uint32_t download_size;
} homebrew;

typedef struct {
   uint32_t homebrew_count;
   homebrew * homebrew_list;
   uint8_t * homebrew_strings;
} catalog;
```

There is no padding anywhere. Strings are appended at the end of the binary at the offset listed in the homebrew struct. Lengths are in bytes, not characters, as this format has full utf-8 support. All offsets are from the beginning of the file.

## License

This repo is licensed under the unlicense: 

```
This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or
distribute this software, either in source code form or as a compiled
binary, for any purpose, commercial or non-commercial, and by any
means.

In jurisdictions that recognize copyright laws, the author or authors
of this software dedicate any and all copyright interest in the
software to the public domain. We make this dedication for the benefit
of the public at large and to the detriment of our heirs and
successors. We intend this dedication to be an overt act of
relinquishment in perpetuity of all present and future rights to this
software under copyright law.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

For more information, please refer to <http://unlicense.org/>
```
