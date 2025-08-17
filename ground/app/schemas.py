"""Pydantic data models for raw telemetry and processed state."""

from pydantic import BaseModel


class Telemetry(BaseModel):
    """Placeholder telemetry schema."""
    # TODO: define fields for sensor data
    pass


class State(BaseModel):
    """Placeholder processed state schema."""
    # TODO: define fields for computed state parameters
    pass
