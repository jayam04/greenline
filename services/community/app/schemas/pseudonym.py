from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator


class RandomPseudonymResponse(BaseModel):
    pseudonym: str


class UpdatePseudonymRequest(BaseModel):
    pseudonym: str

    @field_validator("pseudonym")
    @classmethod
    def validate_pseudonym(cls, v: str) -> str:
        trimmed = v.strip() if v else ""
        if not trimmed:
            raise ValueError("Pseudonym cannot be empty.")
        if len(trimmed) > 255:
            raise ValueError("Pseudonym cannot exceed 255 characters.")
        return trimmed


class UserProfileResponse(BaseModel):
    user_uuid: str
    pseudonym: str
    updated_posts: Optional[int] = 0
    updated_comments: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)
