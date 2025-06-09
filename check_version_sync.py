#! /usr/bin/env python3

"""
A script to check that the npm version string matches the python
version string exactly.
"""

import json
import tomllib
import os

with open("pyproject.toml", "rb") as toml_f:
    pyproject_data = tomllib.load(toml_f)

with open(os.path.join("webapp", "package.json"), "r", encoding="utf-8") as json_f:
    webapp_data = json.load(json_f)

py_ver = pyproject_data["project"]["version"]
js_ver = webapp_data["version"]

assert py_ver == js_ver, (
    "The python and javascript version numbers should match.\n"
    f"Python version: {py_ver}\n"
    f"Javascript version: {js_ver}\n"
    ""
)
