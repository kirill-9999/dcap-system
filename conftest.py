# conftest.py (корень репозитория)
"""Корневые настройки pytest (DCAP).

BUG-260 (v3.14.3): на Windows pytest по умолчанию использует basetemp в
`%TEMP%\\pytest-of-<user>\\pytest-current`, который лочится антивирусом/IDE →
`PermissionError: [WinError 5]`. Переносим basetemp в проект (git-ignored),
если пользователь не задал его явно через `--basetemp`.
"""

import os

import pytest


def pytest_configure(config: pytest.Config) -> None:
    if os.name == "nt" and not config.option.basetemp:
        config.option.basetemp = os.path.join(os.path.dirname(__file__), ".pytest-tmp")
