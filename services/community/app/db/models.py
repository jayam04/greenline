from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

try:
    from .database import Base
except (ImportError, ValueError):
    from app.db.database import Base


class CommunityPost(Base):
    __tablename__ = "community_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False, index=True)
    author_pseudonym = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    media_attachments = Column(Text, nullable=True)
    comments_count = Column(Integer, default=0, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    comments = relationship(
        "CommunityComment",
        back_populates="post",
        cascade="all, delete-orphan",
        order_by="[CommunityComment.created_at.asc(), CommunityComment.id.asc()]",
        passive_deletes=True
    )

    @property
    def post_id(self) -> int:
        return self.id

    @property
    def author_sub(self) -> str:
        return self.user_id


class CommunityComment(Base):
    __tablename__ = "community_comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(
        Integer,
        ForeignKey("community_posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    parent_comment_id = Column(
        Integer,
        ForeignKey("community_comments.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    user_id = Column(String(255), nullable=False, index=True)
    author_pseudonym = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    post = relationship("CommunityPost", back_populates="comments")
    parent = relationship("CommunityComment", remote_side=[id], back_populates="replies")
    replies = relationship(
        "CommunityComment",
        back_populates="parent",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    @property
    def comment_id(self) -> int:
        return self.id

    @property
    def author_sub(self) -> str:
        return self.user_id
