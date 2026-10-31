# manager/src/auth/modes.py
from enum import Enum


class AuthMode(str, Enum):
    LOCAL = "local"                    # JWT + Bcrypt (разработка)
    WINDOWS_INTEGRATED = "windows_integrated"  # SPNEGO (production AD)
    HYBRID = "hybrid"                  # SPNEGO → fallback JWT
