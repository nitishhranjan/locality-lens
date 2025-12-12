"""
Streamlit application for Locality Lens.
AI-powered locality analysis using LangGraph and OpenStreetMap.
"""
import streamlit as st
import time
from pathlib import Path
import sys


# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Map visualization imports
import folium
from streamlit_folium import st_folium

from config.config import APP_NAME, DEFAULT_LOCATION
from src.graph.graph import compile_graph
from src.graph.state import LocalityState

# ============================================================================
# Cached Resources
# ============================================================================

@st.cache_resource
def get_graph():
    """Initialize and cache the LangGraph workflow."""
    try:
        return compile_graph()
    except Exception as e:
        st.error(f"Failed to initialize graph: {e}")
        return None

# ============================================================================
# UI Components
# ============================================================================

def render_input_form():
    """Render the input form for location and profile."""
    st.header("📍 Location Analysis")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        location_input = st.text_input(
            "Enter Location",
            value=DEFAULT_LOCATION,
            help="Enter an address (e.g., 'Indiranagar, Bangalore') or coordinates (e.g., '12.9784, 77.6408')",
            placeholder="Indiranagar, Bangalore or 12.9784, 77.6408",
            label_visibility="visible"
        )
    
    with col2:
        user_profile = st.selectbox(
            "Your Profile (Optional)",
            options=["", "Bachelor/Young Professional", "Family with Kids", "Student", 
                    "Senior Citizen", "Working Professional", "Custom"],
            help="Select your profile for personalized insights",
            label_visibility="visible"
        )
    
    submit_button = st.button("🔍 Analyze Location", type="primary", use_container_width=True)
    
    return location_input, user_profile, submit_button

def create_initial_state(location_input: str, user_profile: str = None) -> LocalityState:
    """Create initial state for the graph."""
    return {
        "user_input": location_input.strip(),
        "user_profile": user_profile if user_profile else None,
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

def run_analysis(graph, initial_state: LocalityState):
    """Run the graph workflow with real-time progress updates."""
    
    # Create collapsible progress section (expanded during execution)
    progress_expander = st.expander("📊 Analysis Progress", expanded=True)
    
    with progress_expander:
        # Progress bar and status
        status_placeholder = st.empty()
        progress_bar = st.progress(0)
        progress_text = st.empty()
        
        # Steps checklist (real-time updates)
        steps_placeholder = st.empty()
    
    start_time = time.time()
    
    # Step definitions with weights for progress calculation
    step_definitions = {
        "validate": {
            "name": "Validating Input",
            "icon": "🔍",
            "weight": 0.05,
            "status": "pending"
        },
        "geocode": {
            "name": "Geocoding Location",
            "icon": "🌍",
            "weight": 0.10,
            "status": "pending"
        },
        "fetch": {
            "name": "Fetching Location Data",
            "icon": "🗺️",
            "weight": 0.60,  # Longest step
            "status": "pending"
        },
        "calculate": {
            "name": "Calculating Statistics",
            "icon": "📊",
            "weight": 0.10,
            "status": "pending"
        },
        "summarize": {
            "name": "Generating AI Summary",
            "icon": "🤖",
            "weight": 0.15,
            "status": "pending"
        }
    }
    
    last_node = None
    final_state = None
    
    def update_ui():
        """Update UI elements with current step status."""
        # Calculate progress
        total_weight = sum(
            step_info["weight"] 
            for step_info in step_definitions.values() 
            if step_info["status"] == "completed"
        )
        
        # Update progress bar
        progress_bar.progress(min(total_weight, 0.95))
        progress_text.text(f"**{int(total_weight * 100)}% Complete**")
        
        # Build steps display
        steps_display = []
        for step_key, step_info in step_definitions.items():
            status = step_info["status"]
            icon = step_info["icon"]
            name = step_info["name"]
            
            if status == "completed":
                steps_display.append(f"✅ **{icon} {name}**")
            elif status == "running":
                steps_display.append(f"⏳ **{icon} {name}** *(in progress...)*")
            else:
                steps_display.append(f"⏸️ {icon} {name}")
        
        # Update steps display
        with steps_placeholder.container():
            for step_line in steps_display:
                st.markdown(step_line)
    
    try:
        # Initial render
        status_placeholder.info("🔄 **Initializing analysis...**")
        update_ui()
        
        # Stream execution - use "updates" mode to get node names
        for event in graph.stream(initial_state, stream_mode="updates"):
            # Event structure: {node_name: state_dict}
            for node_name, state in event.items():
                if isinstance(state, dict):
                    steps = state.get("processing_steps", [])
                    if steps:
                        step_text = steps[-1].lower()
                        elapsed = time.time() - start_time
                        
                        # Determine which step is running/completed based on node name
                        current_step = None
                        
                        if node_name == "validate_input" or "validate" in step_text:
                            current_step = "validate"
                        elif node_name == "geocode_location" or "geocode" in step_text:
                            current_step = "geocode"
                        elif node_name == "fetch_osm_data" or "fetch_osm" in step_text:
                            current_step = "fetch"
                        elif node_name == "calculate_statistics" or "calculate" in step_text:
                            current_step = "calculate"
                        elif node_name == "generate_summary" or "generate_summary" in step_text or "summary" in step_text:
                            current_step = "summarize"
                        
                        # Update step status when node changes
                        if current_step and current_step != last_node:
                            # Mark previous step as completed
                            if last_node:
                                step_definitions[last_node]["status"] = "completed"
                            
                            # Mark current step as running
                            if step_definitions[current_step]["status"] == "pending":
                                step_definitions[current_step]["status"] = "running"
                            
                            last_node = current_step
                            
                            # Update status message
                            step_info = step_definitions[current_step]
                            status_placeholder.info(
                                f"**{step_info['icon']} {step_info['name']}...**\n"
                                f"*Elapsed: {elapsed:.1f}s*"
                            )
                            
                            # Update UI immediately
                            update_ui()
                            
                            # Force Streamlit to update by adding a small delay
                            time.sleep(0.1)
                        
                        # Store final state
                        final_state = state
        
        # Mark final step as completed
        if last_node:
            step_definitions[last_node]["status"] = "completed"
        
        # Mark all remaining steps as completed
        for step_key in step_definitions:
            if step_definitions[step_key]["status"] == "pending":
                step_definitions[step_key]["status"] = "completed"
        
        # Final updates
        elapsed = time.time() - start_time
        progress_bar.progress(1.0)
        progress_text.text("**100% Complete** ✅")
        
        # Final status
        status_placeholder.success(
            f"**✅ Analysis completed successfully!**\n"
            f"*Total time: {elapsed:.1f} seconds*"
        )
        
        # Final render of all completed steps
        update_ui()
        
        # Return final state (use the state from stream, not invoke)
        if final_state:
            return final_state
        else:
            # Fallback: get result if stream didn't provide final state
            return graph.invoke(initial_state)
        
    except Exception as e:
        progress_bar.progress(1.0)
        progress_text.text("**Error** ❌")
        status_placeholder.error(f"**❌ Error occurred:** {str(e)}")
        
        import traceback
        with st.expander("🔍 Error Details", expanded=False):
            st.code(traceback.format_exc())
        return None


def create_location_map(result: LocalityState) -> folium.Map:
    """
    Create an interactive Folium map showing the location and search radius.
    
    Args:
        result: The final state with coordinates and data
        
    Returns:
        Folium map object
    """
    if not result.get("coordinates"):
        return None
    
    lat, lon = result["coordinates"]
    
    # Create map centered on location
    m = folium.Map(
        location=[lat, lon],
        zoom_start=14,
        tiles='OpenStreetMap'
    )
    
    # Add center marker (the analyzed location)
    folium.Marker(
        [lat, lon],
        popup=f"📍 Analysis Location\n{result.get('address', 'Unknown')}",
        tooltip="Click for details",
        icon=folium.Icon(
            color="red",
            icon="info-sign",
            prefix="fa"
        )
    ).add_to(m)
    
    # Add search radius circle (1000m = 1km)
    folium.Circle(
        location=[lat, lon],
        radius=1000,  # 1km radius
        popup="Search Radius: 1km",
        color="blue",
        fill=True,
        fillColor="blue",
        fillOpacity=0.1,
        weight=2
    ).add_to(m)
    
    # Add a larger radius circle (2km) for reference
    folium.Circle(
        location=[lat, lon],
        radius=2000,  # 2km radius
        popup="Extended Radius: 2km",
        color="gray",
        fill=False,
        weight=1,
        dashArray="5, 5"
    ).add_to(m)
    
    return m


def display_results(result: LocalityState):
    """Display the analysis results."""
    
    if not result:
        st.error("Failed to generate analysis. Please try again.")
        return
    
    # Check for errors
    if result.get("errors"):
        st.error("## ❌ Errors Encountered")
        for error in result["errors"]:
            st.error(f"- {error}")
        
        # Show processing steps for debugging
        with st.expander("🔍 Debug Information", expanded=False):
            st.write("Processing Steps:")
            for step in result.get("processing_steps", []):
                st.code(step)
        return
    
    # Show warnings if any
    if result.get("warnings"):
        with st.expander("⚠️ Warnings", expanded=False):
            for warning in result["warnings"]:
                st.warning(warning)
    
    # Location Information
    st.header("📍 Location Information")
    col1, col2 = st.columns(2)
    
    with col1:
        if result.get("coordinates"):
            lat, lon = result["coordinates"]
            st.metric("Coordinates", f"{lat}, {lon}")
        else:
            st.metric("Coordinates", "N/A")
    
    with col2:
        if result.get("address"):
            st.metric("Address", result["address"])
        else:
            st.metric("Address", "N/A")
    
    st.divider()

    # ============================================================================
    # MAP VISUALIZATION - ADD THIS SECTION
    # ============================================================================
    if result.get("coordinates"):
        st.header("🗺️ Location Map")
        
        # Create map
        location_map = create_location_map(result)
        
        if location_map:
            # Display map in Streamlit
            map_data = st_folium(
                location_map,
                width=700,
                height=500,
                returned_objects=["last_object_clicked"]
            )
            
            # Optional: Show map interaction info
            with st.expander("ℹ️ Map Information", expanded=False):
                st.markdown("""
                **Map Features:**
                - 🔴 **Red marker**: Analysis location
                - 🔵 **Blue circle**: 1km search radius (primary analysis area)
                - ⚪ **Gray circle**: 2km extended radius (reference)
                
                **Interactions:**
                - Click markers for details
                - Zoom in/out with mouse wheel
                - Drag to pan around
                """)
        else:
            st.warning("Unable to create map - coordinates missing")
    
    st.divider()
    
    # AI-Generated Summary
    if result.get("summary"):
        st.header("🤖 AI-Generated Summary")
        st.markdown(result["summary"])
        st.divider()
    
    # Key Statistics
    if result.get("statistics"):
        st.header("📊 Key Statistics")
        
        stats = result["statistics"]
        
        # Essential Amenities
        st.subheader("Essential Amenities")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("🏫 Schools", stats.get("school_count", 0))
            st.metric("🏥 Hospitals", stats.get("hospital_count", 0))
        
        with col2:
            st.metric("🍽️ Restaurants", stats.get("restaurant_count", 0))
            st.metric("🌳 Parks Area", f"{stats.get('park_area_km2', 0)} km²")
        
        with col3:
            st.metric("🚇 Metro Stations", stats.get("metro_station_count", 0))
            st.metric("🚌 Bus Stops", stats.get("bus_stop_count", 0))
        
        # Connectivity & Density
        st.subheader("Connectivity & Density")
        col1, col2 = st.columns(2)
        
        with col1:
            if stats.get("nearest_metro_distance_km"):
                st.metric("🚇 Nearest Metro", stats["nearest_metro_distance_km"])
            else:
                st.metric("🚇 Nearest Metro", "Not available")
        
        with col2:
            st.metric("📍 POI Density", f"{stats.get('poi_density', 0)} per km²")
        
        st.divider()
    
    # Detailed OSM Data (Collapsible)
    if result.get("osm_data"):
        with st.expander("🗺️ Detailed POI Data", expanded=False):
            for category, data in result["osm_data"].items():
                if isinstance(data, dict) and "count" in data:
                    count = data["count"]
                    category_name = category.replace("_", " ").title()
                    st.write(f"**{category_name}**: {count} found")
    
    # Processing Steps (Collapsible, for debugging)
    with st.expander("🔍 Processing Steps", expanded=False):
        for step in result.get("processing_steps", []):
            st.caption(f"• {step}")

# ============================================================================
# Main Application
# ============================================================================

def main():
    """Main Streamlit application."""
    st.set_page_config(
        page_title=APP_NAME,
        page_icon="🏘️",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # Header
    st.title(f"🏘️ {APP_NAME}")
    st.markdown("**AI-powered locality analysis using OpenStreetMap data and LLM integration**")
    st.markdown("---")
    
    # Initialize graph (cached)
    graph = get_graph()
    
    if graph is None:
        st.error("Failed to initialize the analysis system. Please check your configuration.")
        st.stop()
    
    # Render input form
    location_input, user_profile, submit_button = render_input_form()
    
    # Process on submit
    if submit_button:
        if not location_input or not location_input.strip():
            st.warning("⚠️ Please enter a location")
        else:
            # Create initial state
            initial_state = create_initial_state(location_input, user_profile)
            
            # Run analysis
            result = run_analysis(graph, initial_state)
            
            # Display results
            if result:
                st.divider()
                display_results(result)

    # Sidebar with info
    with st.sidebar:
        st.header("ℹ️ About")
        st.markdown("""
        **Locality Lens** analyzes any location and provides:
        - 📍 Location insights
        - 📊 Key statistics
        - 🤖 AI-generated summaries
        - 🗺️ POI data analysis
        """)
        
        st.markdown("---")
        st.subheader("💡 Tips")
        st.markdown("""
        - Enter an **address** (e.g., "Indiranagar, Bangalore")
        - Or enter **coordinates** (e.g., "12.9784, 77.6408")
        - Select your profile for personalized insights
        - Analysis takes 5-10 seconds
        """)
        
        st.markdown("---")
        st.caption("Built with LangGraph, OSMnx, and Groq LLM")

if __name__ == "__main__":
    main()