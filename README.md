# PSP Homebrew Database

This repo contains the source for a Playstation Portable homebrew database.

New entries go in the `data` directory using the following json format:

```
{
  "name": "",
  "summary": "",
  "description": "",
  "creator": "",
  "creator_link": "",
  "source_link": "",
  "website": "",
  "license": "MIT",
  "license_link": "",
  "screenshots":[
    ""
  ],
  "ai_used": false,
  "releases": [
    {
      "version": "1.0",
      "changelog": "",
      "download_link": "",
      "checksum": "",
      "date": "2024-12-20"
    }
  ],
  "tags": [
    "game"
  ]
}
```

The fields `description`, `website`, `creator_link`, `source_link`, `license`, `license_link` and `tags` are optional, but please use them if possible. In the releases part `changelog` is optional. The `checksum` is a sha256 hash.

Building can be done with the `build.py` script, make sure the packages in the `requirements.txt` are installed. The completed build will be saved to the `dist` directory.

This repo is licensed under the unlicense.