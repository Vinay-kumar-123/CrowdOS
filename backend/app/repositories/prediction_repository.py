"""
Prediction Repository — Sprint 10.
"""
from typing import Optional, List
from app.models.prediction import PredictionDBModel
from app.repositories.base import BaseRepository


class PredictionRepository(BaseRepository[PredictionDBModel]):
    """
    Repository for persisting and retrieving predictive crowd risk snapshots in MongoDB.
    """

    def __init__(self, collection):
        super().__init__(collection, PredictionDBModel)

    async def get_by_prediction_id(self, prediction_id: str) -> Optional[PredictionDBModel]:
        """Fetch prediction snapshot by prediction_id."""
        return await self.find_one({"prediction_id": prediction_id})

    async def save_prediction(self, prediction: PredictionDBModel) -> Optional[PredictionDBModel]:
        """Persist prediction evaluation outcome."""
        return await self.create(prediction)

    async def list_predictions(
        self,
        venue_id: str,
        session_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[PredictionDBModel]:
        """Fetch historical prediction snapshots for venue and optional session."""
        query = {"venue_id": venue_id}
        if session_id:
            query["session_id"] = session_id

        return await self.find_many(query, sort=[("timestamp", -1)], limit=limit)
