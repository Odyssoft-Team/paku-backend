"""IAM application use cases.

This module is intentionally kept as a thin facade to preserve existing imports
from the API router. The detailed TECH/BUSINESS comments were kept with the
actual implementations under `use_cases_impl/`.
"""

from app.modules.iam.app.use_cases_impl.auth import LoginUser
from app.modules.iam.app.use_cases_impl.profile import GetMe, RegisterUser, UpdateProfile

__all__ = [
    "GetMe",
    "LoginUser",
    "RegisterUser",
    "UpdateProfile",
]
