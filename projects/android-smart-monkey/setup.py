from __future__ import annotations

from pathlib import Path

from setuptools import find_packages, setup


README = (Path(__file__).parent / "README.md").read_text(encoding="utf-8")

setup(
    name="android-smart-monkey",
    version="0.1.0",
    description="A state-aware smart monkey framework scaffold for Android app testing",
    long_description=README,
    long_description_content_type="text/markdown",
    python_requires=">=3.11",
    packages=find_packages(include=["smart_monkey", "smart_monkey.*"]),
    install_requires=["PyYAML>=6.0"],
)
