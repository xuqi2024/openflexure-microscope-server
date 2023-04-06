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
            "url": "https://www.w3.org/TR/wot-thing-description/#actionaffordance",
            "description": "W3C's description of Web of Things 'Action' resources.",
        },
    },
    {
        "name": "properties",
        "description": (
            "Properties can be read and/or written to, and affect the "
            "state of the microscope."
        ),
        "externalDocs": {
            "url": "https://www.w3.org/TR/wot-thing-description/#propertyaffordance",
            "description": "W3C's description of Web of Things 'Property' resources.",
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
