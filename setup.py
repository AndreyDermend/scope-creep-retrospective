# Compatibility shim for pip < 21.3 (e.g. macOS system Python 3.9).
# Newer pip reads pyproject.toml directly and ignores this file.
from setuptools import setup

setup()
