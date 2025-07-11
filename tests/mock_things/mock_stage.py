"""Testing submodule with mocks StageThings.

These mocks are designed to be inserted as dependencies to provide specific
functionality and return values.

The mocks do not subclass existing Things. Instead, they return predefined
answers to functions.
"""


class MockStageThing:
    """A mock Thing for a stage that imports no code from BaseStage.

    The class needs functionality added to it over time as more complex
    mocking is needed. It imports no code from BaseStage so that coverage
    is not artificially inflated.
    """

    position = (111, 222, 333)
