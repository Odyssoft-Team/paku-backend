"""Booking use cases (facade).

Implementation lives under `use_cases_impl/`.
This module re-exports the public API to avoid breaking imports.

CreateHold y CancelHold viven en use_cases_impl.availability; ConfirmHold en holds.py.
"""

from app.modules.booking.app.use_cases_impl.availability import (
    CancelHold,
    CreateAvailabilitySlot,
    CreateAvailabilitySlotsBulk,
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
    "CreateAvailabilitySlotsBulk",
    "CreateHold",
    "ListAvailability",
    "ToggleAvailabilitySlot",
    "UpdateAvailabilitySlot",
]
