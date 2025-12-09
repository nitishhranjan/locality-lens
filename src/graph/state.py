"""
State schema for Locality Lens LangGraph workflow.
"""
from typing import TypedDict, Optional, List, Dict, Any


class LocalityState(TypedDict):
    """
    State schema for the Locality Lens workflow.
    
    This TypedDict defines all the data that flows through the graph.
    Each node reads from and writes to this state.
    """
    # Input fields
    user_input: str  # Location input (address or coordinates)
    user_profile: Optional[str]  # User profile type (bachelor, family, etc.)
    
    # Geocoding fields
    coordinates: Optional[tuple[float, float]]  # (latitude, longitude)
    address: Optional[str]  # Resolved address from geocoding
    
    # Data fields
    osm_data: Dict[str, Any]  # OpenStreetMap POI data
    aqi_data: Optional[Dict[str, Any]]  # Air Quality Index data
    
    # Analysis fields
    selected_metrics: List[str]  # Metrics selected by LLM (future)
    statistics: Dict[str, Any]  # Calculated statistics/metrics
    user_intent: Dict[str, Any]  # Extracted user intent (future)
    
    # Output fields
    summary: Optional[str]  # LLM-generated summary (future)
    recommendations: List[str]  # Actionable recommendations (future)
    visualization_data: Optional[Dict[str, Any]]  # Map data (future)
    
    # Control fields
    errors: List[str]  # List of errors encountered
    warnings: List[str]  # List of warnings
    next_action: str  # Next action to take (for routing)
    processing_steps: List[str]  # Audit trail of processing steps