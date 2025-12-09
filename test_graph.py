"""
Test script for Day 1 & 2 - Basic graph functionality.
"""
from src.graph.graph import compile_graph
from src.graph.state import LocalityState
import time

def test_graph():
    """Test the basic graph with sample input."""
    
    # Compile graph
    print("Compiling graph...")
    app = compile_graph()
    print("Graph compiled successfully!\n")
    
    # Test case 1: Coordinate input (FASTER - skip geocoding)
    print("=" * 60)
    print("Test 1: Coordinate Input (12.9784, 77.6408) - Indiranagar, Bangalore")
    print("=" * 60)
    print("This will skip geocoding and go straight to OSM data fetching...")
    print("OSM data fetching may take 30-60 seconds, please wait...\n")
    
    initial_state: LocalityState = {
        "user_input": "12.9784, 77.6408",  # Use coordinates directly
        "user_profile": None,
        "coordinates": None,
        "address": None,
        "osm_data": {},
        "aqi_data": None,
        "selected_metrics": [],
        "statistics": {},
        "user_intent": {},
        "summary": None,
        "recommendations": [],
        "visualization_data": None,
        "errors": [],
        "warnings": [],
        "next_action": "",
        "processing_steps": []
    }
    
    start_time = time.time()
    
    # Use streaming to see progress
    print("Starting workflow...")
    print("-" * 60)
    
    try:
        # Stream to see progress - FIXED: Handle event structure correctly
        for event in app.stream(initial_state, stream_mode="values"):
            # Event is a dict with node names as keys
            if isinstance(event, dict):
                # Get the state from the last node that executed
                node_name = list(event.keys())[0] if event else None
                state = event.get(node_name) if node_name else None
                
                # Check if state is actually a dict (not a string)
                if isinstance(state, dict):
                    steps = state.get("processing_steps", [])
                    if steps:
                        print(f"✓ {steps[-1]}")  # Print last step
                    elif node_name:
                        print(f"✓ Executing: {node_name}")
                elif node_name:
                    print(f"✓ Executing: {node_name}")
        
        # Get final result
        print("\nGetting final result...")
        result = app.invoke(initial_state)
        
        elapsed = time.time() - start_time
        print("-" * 60)
        print(f"\nWorkflow completed in {elapsed:.2f} seconds\n")
        
        print("Processing Steps:")
        for step in result.get("processing_steps", []):
            print(f"  - {step}")
        
        print("\nErrors:", result.get("errors", []))
        print("Warnings:", result.get("warnings", []))
        
        if result.get("coordinates"):
            print(f"\nCoordinates: {result['coordinates']}")
            print(f"Address: {result.get('address', 'N/A')}")
        
        if result.get("statistics"):
            print("\nStatistics:")
            for key, value in result["statistics"].items():
                print(f"  {key}: {value}")
        
        if result.get("osm_data"):
            print("\nOSM Data Summary:")
            for key, value in result["osm_data"].items():
                if isinstance(value, dict) and "count" in value:
                    print(f"  {key}: {value['count']} found")
    
    except KeyboardInterrupt:
        print("\n\nWorkflow interrupted by user")
    except Exception as e:
        print(f"\n\nError during workflow: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_graph()