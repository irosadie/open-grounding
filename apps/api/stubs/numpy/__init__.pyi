"""Minimal static surface for optional NumPy consumers used by Qdrant."""

from typing import Any


class ndarray: ...


def __getattr__(name: str) -> Any: ...
