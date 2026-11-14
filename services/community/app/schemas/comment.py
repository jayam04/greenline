from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator


class CommentCreate(BaseModel):
    content: str
    parent_comment_id: Optional[int] = None
    author_pseudonym: Optional[str] = None

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Comment content cannot be empty or contain only whitespace.")
        if len(v) > 5000:
            raise ValueError("Comment content exceeds maximum length of 5,000 characters.")
        return v


class CommentResponse(BaseModel):
    id: int
    comment_id: int
    post_id: int
    parent_comment_id: Optional[int] = None
    author_sub: str
    author_pseudonym: Optional[str] = None
    content: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
