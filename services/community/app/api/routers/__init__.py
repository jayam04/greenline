from .posts import router as posts_router
from .comments import router as comments_router
from .pseudonyms import router as pseudonyms_router

__all__ = ["posts_router", "comments_router", "pseudonyms_router"]
