"""This testing submodule contains mock autofocus things.

These mocks are designed to be inserted as dependencies to give specific
functionality and returns.

The mocks do not subclass, and instead return very specific defined answers
to functions
"""


class MockAutoFocusThing:
    # Counter for checking functions were called
    mock_call_count = {"looping_autofocus": 0}

    def looping_autofocus(self, dz: int = 2000, start: str = "centre") -> None:  # noqa: ARG002
        """This function mocks autofocus with no return"""
        self.mock_call_count["looping_autofocus"] += 1
