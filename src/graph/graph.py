"""
LangGraph workflow construction for Locality Lens.
"""
from langgraph.graph import StateGraph, END

from .state import LocalityState
from .nodes import (
    validate_input,
    geocode_location,
    extract_intent_and_select_metrics,
    fetch_osm_data,
    calculate_statistics,
    handle_error,
    generate_summary,
)


def create_graph() -> StateGraph:
    """
    Create and configure the Locality Lens workflow graph.
    
    Returns:
        Compiled StateGraph ready for execution
    """
    # Create graph with state schema
    graph = StateGraph(LocalityState)
    
    # Add nodes
    graph.add_node("validate_input", validate_input)
    graph.add_node("extract_intent_and_select_metrics", extract_intent_and_select_metrics)
    graph.add_node("geocode_location", geocode_location)
    graph.add_node("fetch_osm_data", fetch_osm_data)
    graph.add_node("calculate_statistics", calculate_statistics)
    graph.add_node("generate_summary", generate_summary)
    graph.add_node("handle_error", handle_error)
    
    # Set entry point
    graph.set_entry_point("validate_input")
    
    # ========================================================================
    # ROUTING AFTER VALIDATION
    # ========================================================================
    def route_after_validate(state: LocalityState) -> str:
        """Route based on validation result."""
        if state.get("errors"):
            return "error"
        # Always start parallel execution after validation
        return "parallel_start"
    
    graph.add_conditional_edges(
        "validate_input",
        route_after_validate,
        {
            "error": "handle_error",
            "parallel_start": "extract_intent_and_select_metrics"
        }
    )

    # ========================================================================
    # PARALLEL EXECUTION: Intent extraction + Geocoding/OSM fetch
    # ========================================================================
    # After intent extraction, route to geocoding or OSM fetch
    def route_after_intent(state: LocalityState) -> str:
        """Route after intent extraction - check if coordinates exist."""
        if state.get("errors"):
            return "error"
        if state.get("coordinates"):
            # Coordinates exist - go directly to OSM fetch
            return "fetch_osm"
        # Need geocoding
        return "geocode"
    
    graph.add_conditional_edges(
        "extract_intent_and_select_metrics",
        route_after_intent,
        {
            "error": "handle_error",
            "fetch_osm": "fetch_osm_data",  # Parallel path 1: OSM fetch
            "geocode": "geocode_location"    # Parallel path 2: Geocoding
        }
    )
    
    
    # ========================================================================
    # AFTER GEOCODING: Fetch OSM data
    # ========================================================================
    def route_after_geocode(state: LocalityState) -> str:
        """Route after geocoding."""
        if state.get("errors"):
            return "error"
        if state.get("coordinates"):
            return "fetch_osm"
        return "error"
    
    graph.add_conditional_edges(
        "geocode_location",
        route_after_geocode,
        {
            "error": "handle_error",
            "fetch_osm": "fetch_osm_data"
        }
    )
    
    # ========================================================================
    # AFTER OSM FETCH: Calculate statistics (needs both OSM data + selected_metrics)
    # ========================================================================
    def route_after_fetch(state: LocalityState) -> str:
        """Route after OSM fetch - ensure both OSM data and selected_metrics exist."""
        if state.get("errors"):
            return "error"
        
        # Check if both required data is available
        osm_data = state.get("osm_data", {})
        selected_metrics = state.get("selected_metrics", [])
        
        if not osm_data:
            return "error"
        
        # If no metrics selected yet, wait or use defaults
        if not selected_metrics:
            # Intent extraction might still be running - this shouldn't happen
            # but handle gracefully
            from src.analysis.metrics_catalog import get_default_metrics_for_profile
            state["selected_metrics"] = get_default_metrics_for_profile("general")
        
        return "calculate"
    
    graph.add_conditional_edges(
        "fetch_osm_data",
        route_after_fetch,
        {
            "error": "handle_error",
            "calculate": "calculate_statistics"
        }
    )
    
    # ========================================================================
    # AFTER CALCULATION: Generate summary
    # ========================================================================
    def route_after_calculate(state: LocalityState) -> str:
        """Route after statistics calculation"""
        if state.get("errors"):
            return "error"
        return "generate_summary"
    
    graph.add_conditional_edges(
        "calculate_statistics",
        route_after_calculate,
        {
            "error": "handle_error",
            "generate_summary": "generate_summary"
        }       
    )
    graph.add_edge("generate_summary", END)
    graph.add_edge("handle_error", END)

    return graph

def compile_graph() -> StateGraph:
    """
    Compile the graph for execution.
    
    Returns:
        Compiled graph ready to use
    """
    graph = create_graph()
    return graph.compile()