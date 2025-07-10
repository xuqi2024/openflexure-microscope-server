"""Testing submodule with mock Camera Stage Mapping Things.

These mocks are designed to be inserted as dependencies to provide specific
functionality and return values.

The mocks do not subclass Things. Instead, they return predefined
answers to functions.
"""


class MockCSMThing:
    image_resolution = (123, 456)
