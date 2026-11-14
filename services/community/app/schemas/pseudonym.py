from pydantic import BaseModel


class RandomPseudonymResponse(BaseModel):
    pseudonym: str
