"""State schema for the Locality Lens graph."""
from __future__ import annotations

import operator
from typing import Annotated, Any, Optional, TypedDict


class LocalityState(TypedDict, total=False):
    """Data flowing through the graph. Each node reads and writes a slice.

    `errors` and `warnings` carry `operator.add` reducers because intent
    extraction and geocoding run as concurrent branches: without a reducer,
    two parallel nodes writing the same key raise InvalidUpdateError.
    """

    # Input
    user_input: str
    user_profile: Optional[str]

    # Resolved location
    coordinates: Optional[tuple[float, float]]
    address: Optional[str]

    # Data
    pois: list[dict[str, Any]]
    counts: dict[str, int]
    park_area_km2: float
    raw_feature_count: int

    # Analysis
    user_intent: dict[str, Any]
    selected_metrics: list[str]
    statistics: dict[str, Any]

    # Output
    summary: Optional[str]

    # Control
    errors: Annotated[list[str], operator.add]
    warnings: Annotated[list[str], operator.add]

    # Set once the failure has been reported to the client. Both branches can
    # reach handle_error, and the client should see one error, not two.
    reported: Annotated[bool, operator.or_]
