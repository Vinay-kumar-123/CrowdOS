from pydantic import BaseModel


class BaseSchema(BaseModel):
    """
    Base Pydantic schema for request and response validation.
    """
    class Config:
        from_attributes = True
