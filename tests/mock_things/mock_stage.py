"""This testing submodule contains stage things.

These mocks are designed to be inserted as dependencies to give specific
functionality and returns.

The mocks do not subclass, and instead return very specific defined answers
to functions
"""


class MockStageThing:
    position = (111, 222, 333)
