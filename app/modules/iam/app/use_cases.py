"""IAM application use cases.

Thin facade that re-exports all use cases for convenient importing from the API layer.
"""

from app.modules.iam.app.use_cases_impl.account_linking import AddPassword, LinkSocialIdentity
from app.modules.iam.app.use_cases_impl.auth import LoginUser
from app.modules.iam.app.use_cases_impl.profile import ChangeUserRole, CompleteProfile, GetMe, RegisterUser, UpdateProfile
from app.modules.iam.app.use_cases_impl.social_auth import SocialLogin

__all__ = [
    "AddPassword",
    "ChangeUserRole",
    "CompleteProfile",
    "GetMe",
    "LinkSocialIdentity",
    "LoginUser",
    "RegisterUser",
    "SocialLogin",
    "UpdateProfile",
]
