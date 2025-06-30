"""This testing submodule contains mock background detect things.

These mocks are designed to be inserted as dependencies to give specific
functionality and returns.

The mocks do not subclass, and instead return very specific defined answers
to functions
"""

from openflexure_microscope_server.things.background_detect import ChannelDistributions


class MockBackgoundDetectThing:
    background_distributions = ChannelDistributions(
        means=[128.0, 128.0, 128.0],
        standard_deviations=[3.0, 3.0, 3.0],
        colorspace="LUV",
    )
