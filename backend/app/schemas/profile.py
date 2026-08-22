from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ProfileTypeLiteral = Literal["JEE", "GATE", "Semester Study", "Custom Learning"]


class ProfileBase(BaseModel):
    name: str = Field(..., description="The user's display name for this profile", min_length=1)
    profile_type: ProfileTypeLiteral = Field(..., description="The specific type of learning profile")


class ProfileCreate(ProfileBase):
    """Payload for creating a learning profile."""


class ProfileUpdate(BaseModel):
    name: str | None = Field(None, min_length=1)
    profile_type: ProfileTypeLiteral | None = None


class ProfileResponse(ProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
