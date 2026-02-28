"""Booking use cases (facade).

Implementation lives under `use_cases_impl/`.
This module re-exports the public API to avoid breaking imports.

NOTE: CreateHold and CancelHold now live in use_cases_impl.availability and require
both hold_repo and availability_repo. The old holds.py versions are kept for
backwards compatibility with existing tests that don't use availability.
"""

from app.modules.booking.app.use_cases_impl.availability import (
    CancelHold,
    CreateAvailabilitySlot,
    CreateHold,
    ListAvailability,
    ToggleAvailabilitySlot,
    UpdateAvailabilitySlot,
)
from app.modules.booking.app.use_cases_impl.holds import ConfirmHold

__all__ = [
    "CancelHold",
    "ConfirmHold",
    "CreateAvailabilitySlot",
    "CreateHold",
    "ListAvailability",
    "ToggleAvailabilitySlot",
    "UpdateAvailabilitySlot",
]
