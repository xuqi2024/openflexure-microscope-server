"""Testing submodule with mocks StageThings.

These mocks are designed to be inserted as dependencies to provide specific
functionality and return values.

The mocks do not subclass existing Things. Instead, they return predefined
answers to functions.
"""


class MockStageThing:
    position = (111, 222, 333)
