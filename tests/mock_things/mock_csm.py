"""This testing submodule contains mock camera stage mapping things.

These mocks are designed to be inserted as dependencies to give specific
functionality and returns.

The mocks do not subclass, and instead return very specific defined answers
to functions
"""


class MockCSMThing:
    image_resolution = (123, 456)
