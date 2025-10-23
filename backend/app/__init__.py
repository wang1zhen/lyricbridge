"""
LyricBridge backend package.

The goal of this package is to reproduce the behaviour of the original
163MusicLyrics application while exposing the functionality through a FastAPI
service that can be consumed by the Electron front-end.
"""

from .main import create_app

__all__ = ["create_app"]
