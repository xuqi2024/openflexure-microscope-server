"""Testing submodule with mock Background Detect Things.

These mocks are designed to be inserted as dependencies to provide specific
functionality and return values.

The mocks do not subclass Things. Instead, they return predefined
answers to functions.
"""

from openflexure_microscope_server.things.background_detect import ChannelDistributions


class MockBackgroundDetectThing:
    """A mock background detect Thing that imports no code from BackgroundDetectThing.

    The class needs functionality added to it over time as more complex
    mocking is needed. It imports no code from BackgroundDetectThing so that coverage
    is not artificially inflated.
    """

    background_distributions = ChannelDistributions(
        means=[128.0, 128.0, 128.0],
        standard_deviations=[3.0, 3.0, 3.0],
        colorspace="LUV",
    )
