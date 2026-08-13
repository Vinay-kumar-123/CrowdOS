from typing import Generic, TypeVar, Optional, List
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class BaseRepository(Generic[T]):
    """
    Abstract Generic Repository pattern for data access layer decoupling.
    """
    def __init__(self, collection):
        self.collection = collection

    async def get_by_id(self, id: str) -> Optional[T]:
        raise NotImplementedError

    async def list_all(self, limit: int = 100) -> List[T]:
        raise NotImplementedError
