"""
This sub-package contains utilities that help with testing and debugging.

At the top level are some very basic testing functions, more specific testing
is provided by modules inside the package.
"""

from typing import Protocol, Iterable
from collections.abc import Hashable


class SizedIterableHashable(Iterable[Hashable], Protocol):
    """A protocol for sized iterable of hashable objects"""

    def __len__(self) -> int: ...


def assert_unique_of_length(data: SizedIterableHashable, length: int) -> None:
    """Assert that a list (or other iterable) has unique contents of a given length.

    :param data: A list or other sized iterable of hashable objects. To be checked
    for unique contents and length.
    :param length: The expected length of data
    """
    assert len(data) == len(set(data))
    assert len(data) == length
