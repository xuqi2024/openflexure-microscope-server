"""Testing submodule with mock Autofocus Things.

These mocks are designed to be inserted as dependencies to provide specific
functionality and return values.

The mocks do not subclass Things. Instead, they return predefined
answers to functions.
"""


class MockAutoFocusThing:
    """A mock autofocus Thing that imports no code from AutofocusThing.

    The class needs functionality added to it over time as more complex
    mocking is needed. It imports no code from AutofocusThing so that coverage
    is not artificially inflated.
    """

    # Counter for checking functions were called
    mock_call_count = {"looping_autofocus": 0}

    def looping_autofocus(self, dz: int = 2000, start: str = "centre") -> None:  # noqa: ARG002
        """Mock autofocus with no return."""
        self.mock_call_count["looping_autofocus"] += 1
