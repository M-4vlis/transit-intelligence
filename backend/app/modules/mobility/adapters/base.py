from abc import ABC, abstractmethod

from app.modules.mobility.models import TransitBatch


class TransitSourceError(RuntimeError):
    """Base error for failures while reading an external transit source."""


class TransitSourceUnavailable(TransitSourceError):
    """The source could not be reached or returned an unavailable response."""


class TransitSourceSchemaError(TransitSourceError):
    """The source responded, but its payload no longer matches the expected contract."""


class TransitRealtimeAdapter(ABC):
    @abstractmethod
    async def fetch_vehicle_positions(self) -> TransitBatch:
        """Fetch and normalize the latest vehicle positions from one source."""
        raise NotImplementedError
