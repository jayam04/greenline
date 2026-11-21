import json
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, field_validator


class MediaAttachment(BaseModel):
    url: str
    type: str = "image"
    name: Optional[str] = None
    size: Optional[int] = None


class PostCreate(BaseModel):
    content: str
    media_attachments: Optional[List[MediaAttachment]] = None
    author_pseudonym: Optional[str] = None

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Post content cannot be empty or contain only whitespace.")
        if len(v) > 10000:
            raise ValueError("Post content exceeds maximum length of 10,000 characters.")
        return v


class PostResponse(BaseModel):
    id: int
    post_id: int
    author_sub: str
    author_uuid: Optional[str] = None
    user_uuid: Optional[str] = None
    author_pseudonym: Optional[str] = None
    content: str
    media_attachments: Optional[List[MediaAttachment]] = None
    comments_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("media_attachments", mode="before")
    @classmethod
    def parse_media_attachments(cls, v):
        if isinstance(v, str):
            try:
                data = json.loads(v)
                return data if isinstance(data, list) else None
            except Exception:
                return None
        return v


class PostListResponse(BaseModel):
    items: List[PostResponse]
    total_count: int
    limit: int
    offset: int
