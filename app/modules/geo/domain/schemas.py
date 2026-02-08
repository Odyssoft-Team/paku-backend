"""Domain schemas for the Geo module.

Public output contracts for the geo catalog endpoints.
"""

from typing import Optional
from pydantic import BaseModel


class DistrictOut(BaseModel):
    """Output DTO for district data.
    
    Used to serialize district information for API responses.
    """
    id: str
    name: str
    province_name: Optional[str] = None
    department_name: Optional[str] = None
    active: bool
