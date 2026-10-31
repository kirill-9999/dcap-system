# manager/src/workers/__init__.py
"""Celery workers (День 36-37)."""

from .celery_app import app as celery_app  # noqa: F401

__all__ = ["celery_app"]