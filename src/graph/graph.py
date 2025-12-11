"""
LangGraph workflow construction for Locality Lens.
"""
from langgraph.graph import StateGraph, END

from .state import LocalityState
from .nodes import (
    validate_input,
    geocode_location,
    fetch_osm_data,
    calculate_statistics,
    handle_error,
    generate_summary
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
    graph.add_node("geocode_location", geocode_location)
    graph.add_node("fetch_osm_data", fetch_osm_data)
    graph.add_node("calculate_statistics", calculate_statistics)
    graph.add_node("generate_summary", generate_summary)
    graph.add_node("handle_error", handle_error)
    
    # Set entry point
    graph.set_entry_point("validate_input")
    
    # Conditional routing after validation
    def route_after_validate(state: LocalityState) -> str:
        """Route based on validation result."""
        if state.get("errors"):
            return "error"
        # Check if coordinates already exist (from validate_input)
        if state.get("coordinates"):
            return "skip_geocode"  # Skip geocoding, go straight to fetch
        return "geocode"  # Need to geocode
    
    graph.add_conditional_edges(
        "validate_input",
        route_after_validate,
        {
            "error": "handle_error",
            "skip_geocode": "fetch_osm_data",  # Skip geocoding
            "geocode": "geocode_location"
        }
    )
    
    # Conditional routing after geocoding
    def route_after_geocode(state: LocalityState) -> str:
        """Route based on geocoding result."""
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
    
    # After fetching OSM data
    def route_after_fetch(state: LocalityState) -> str:
        """Route based on fetch result."""
        if state.get("errors"):
            return "error"
        return "calculate"
    
    graph.add_conditional_edges(
        "fetch_osm_data",
        route_after_fetch,
        {
            "error": "handle_error",
            "calculate": "calculate_statistics"
        }
    )
    
    # # After calculating statistics
    # graph.add_edge("calculate_statistics", END)
    # graph.add_edge("handle_error", END)
    

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