import argparse

API_TAGS = [
    {
        "name": "actions",
        "description": (
            "Actions that can be run on the microscope.  These endpoints represent "
            "actions that many not complete immediately, so they run on the server "
            "as `Action` objects and their status can be queried using the links "
            "embedded in the JSON action description."
        ),
        "externalDocs": {
            "url": "https://iot.mozilla.org/wot/#action-resource",
            "description": "Mozilla's description of Web of Things 'Action' resources.",
        },
    },
    {
        "name": "properties",
        "description": (
            "Properties can be read and/or written to, and affect the "
            "state of the microscope."
        ),
        "externalDocs": {
            "url": "https://iot.mozilla.org/wot/#property-resource",
            "description": "Mozilla's description of Web of Things 'Property' resources.",
        },
    },
    {"name": "captures", "description": ""},
    {"name": "extensions", "description": ""},
    {"name": "events", "description": ""},
]


def add_spec_extras(spec):
    """Add extra documentation and features to the OpenAPI spec"""
    # Add a list of tags, so we can control ordering and add descriptions
    for t in API_TAGS:
        spec.tag(t)


def generate_openapi_from_labthing(labthing):
    parser = argparse.ArgumentParser("Generate an OpenAPI specification document")
    parser.add_argument(
        "-o",
        dest="output",
        default="openapi.yaml",
        help=(
            "Specify the output filename.  If it ends in .json, we output JSON."
            "Use .yml or .yaml for YAML (which is the default"
        ),
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate the API spec, returning an error code if it does not pass.",
    )
    args = parser.parse_args()
    if args.validate:
        import apispec.utils  # Use a lazy import: this is only needed for validation.

        if apispec.utils.validate_spec(labthing.spec):
            print("OpenAPI specification validated OK.")
    fname = args.output
    if fname.endswith(".json"):
        import json

        with open(fname, "w") as fd:
            json.dump(labthing.spec.to_dict(), fd)
    else:
        with open(fname, "w") as fd:
            fd.write(labthing.spec.to_yaml())
