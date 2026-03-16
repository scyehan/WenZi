"""py2app setup for building WenZi.app (闻字)."""

import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from pathlib import Path
from setuptools import setup

# Read version from pyproject.toml (single source of truth)
with open(Path(__file__).parent / "pyproject.toml", "rb") as f:
    _pyproject = tomllib.load(f)
_version = _pyproject["project"]["version"]

APP = ["src/wenzi/app.py"]
DATA_FILES = []
OPTIONS = {
    "argv_emulation": False,
    "plist": {
        "CFBundleName": "闻字",
        "CFBundleDisplayName": "闻字",
        "CFBundleIdentifier": "io.github.airead.wenzi",
        "CFBundleVersion": _version,
        "CFBundleShortVersionString": _version,
        "LSUIElement": True,  # Hide from Dock (menubar-only app)
        "NSMicrophoneUsageDescription": "闻字 needs microphone access to record speech for transcription.",
        "NSAppleEventsUsageDescription": "闻字 needs accessibility access to type transcribed text.",
    },
    "packages": ["wenzi", "funasr_onnx", "librosa", "sounddevice", "soundfile", "numpy"],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
