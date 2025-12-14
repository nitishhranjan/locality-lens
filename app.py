"""
Streamlit application for Locality Lens.
AI-powered locality analysis using LangGraph and OpenStreetMap.

Restructured for optimal user experience with clear information hierarchy.
"""
import streamlit as st
import time
import math
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
# UI Components - Restructured for Better UX
# ============================================================================

def render_input_form():
    """Render a clean, focused input form."""
    # Hero section
    st.markdown("""
    <div style='text-align: center; padding: 20px 0;'>
        <h1 style='margin-bottom: 10px;'>🏘️ Locality Lens</h1>
        <p style='color: #666; font-size: 1.1em;'>AI-Powered Location Analysis</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Input form in a container for better focus
    with st.container():
        col1, col2 = st.columns([2, 1])
        
        with col1:
            location_input = st.text_input(
                "📍 Enter Location",
                value=DEFAULT_LOCATION,
                help="Enter an address (e.g., 'Indiranagar, Bangalore') or coordinates (e.g., '12.9784, 77.6408')",
                placeholder="Indiranagar, Bangalore or 12.9784, 77.6408",
                label_visibility="visible"
            )
        
        with col2:
            profile_type = st.selectbox(
                "👤 Your Profile",
                options=["", "Bachelor/Young Professional", "Family with Kids", "Student", 
                        "Senior Citizen", "Working Professional", "Custom"],
                help="Select your profile for personalized insights",
                label_visibility="visible"
            )
        
        # Custom profile input (shown when "Custom" is selected)
        custom_profile = None
        if profile_type == "Custom":
            custom_profile = st.text_area(
                "Describe Your Needs",
                placeholder="e.g., I'm a fitness enthusiast who loves parks and gyms, need good connectivity",
                help="Describe your lifestyle, priorities, and concerns",
                height=80
            )
            user_profile = custom_profile if custom_profile else None
        else:
            user_profile = profile_type if profile_type else None
        
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
            "weight": 0.03,
            "status": "pending"
        },
        "intent": {
            "name": "Extracting Intent & Selecting Metrics",
            "icon": "🎯",
            "weight": 0.12,
            "status": "pending"
        },
        "geocode": {
            "name": "Geocoding Location",
            "icon": "🌍",
            "weight": 0.08,
            "status": "pending"
        },
        "fetch": {
            "name": "Fetching Location Data",
            "icon": "🗺️",
            "weight": 0.55,
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
            "weight": 0.12,
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
                        elif node_name == "extract_intent_and_select_metrics" or "intent" in step_text or "extract" in step_text:
                            current_step = "intent"
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


def display_summary_with_typing_effect(placeholder, full_text: str, speed: float = 0.03):
    """
    Display summary with a typing effect (word by word).
    
    Args:
        placeholder: Streamlit placeholder to update
        full_text: Complete summary text
        speed: Delay between words in seconds
    """
    words = full_text.split()
    displayed_text = ""
    
    for i, word in enumerate(words):
        displayed_text += word + " "
        
        # Update placeholder with current text
        placeholder.markdown(f"""
        <div style='background: #f8f9fa; padding: 20px; border-radius: 8px; 
                    border-left: 4px solid #667eea; margin-bottom: 30px;'>
            <p style='font-size: 1.1em; line-height: 1.8; color: #333;'>
            {displayed_text}<span style='opacity: 0.5;'>|</span>
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Small delay for typing effect
        time.sleep(speed)
    
    # Final render without cursor
    placeholder.markdown(f"""
    <div style='background: #f8f9fa; padding: 20px; border-radius: 8px; 
                border-left: 4px solid #667eea; margin-bottom: 30px;'>
        <p style='font-size: 1.1em; line-height: 1.8; color: #333;'>
        {full_text}
        </p>
    </div>
    """, unsafe_allow_html=True)


def create_location_map(result: LocalityState) -> folium.Map:
    """
    Create an interactive Folium map showing the location, search radius, and POIs.
    
    Adds markers for key POIs from OSM data.
    """
    if not result.get("coordinates"):
        return None
    
    lat, lon = result["coordinates"]
    osm_data = result.get("osm_data", {})
    
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
        tooltip="Analysis Location",
        icon=folium.Icon(
            color="red",
            icon="home",
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
    
    # ========================================================================
    # ADD POI MARKERS FROM OSM DATA
    # ========================================================================
    
    # POI category icons and colors
    poi_config = {
        "schools": {"icon": "graduation-cap", "color": "blue", "emoji": "🏫"},
        "hospitals": {"icon": "hospital", "color": "red", "emoji": "🏥"},
        "restaurants": {"icon": "cutlery", "color": "orange", "emoji": "🍽️"},
        "cafes": {"icon": "coffee", "color": "brown", "emoji": "☕"},
        "metro_stations": {"icon": "train", "color": "purple", "emoji": "🚇"},
        "bus_stops": {"icon": "bus", "color": "green", "emoji": "🚌"},
        "parks": {"icon": "tree", "color": "green", "emoji": "🌳"},
        "gyms": {"icon": "dumbbell", "color": "darkred", "emoji": "💪"},
        "pharmacies": {"icon": "medkit", "color": "lightred", "emoji": "💊"},
        "banks": {"icon": "university", "color": "darkgreen", "emoji": "🏦"},
        "libraries": {"icon": "book", "color": "darkblue", "emoji": "📚"},
        "shops": {"icon": "shopping-cart", "color": "pink", "emoji": "🛍️"},
    }
    
    # Sample POIs from each category (limit to avoid overcrowding)
    max_pois_per_category = 10
    poi_count = 0
    max_total_pois = 50  # Limit total POIs to keep map readable
    
    for category, data in osm_data.items():
        if poi_count >= max_total_pois:
            break
            
        if not isinstance(data, dict):
            continue
            
        count = data.get("count", 0)
        if count == 0:
            continue
        
        # Get POI config
        config = poi_config.get(category, {"icon": "info", "color": "gray", "emoji": "📍"})
        
        # Get POI data points if available
        poi_list = data.get("data", [])
        
        # If we have actual POI coordinates, use them
        if poi_list and isinstance(poi_list, list) and len(poi_list) > 0:
            # Sample up to max_pois_per_category
            sample_pois = poi_list[:max_pois_per_category]
            
            for poi in sample_pois:
                if poi_count >= max_total_pois:
                    break
                    
                if isinstance(poi, dict):
                    # Try to get coordinates from POI
                    geometry = poi.get("geometry")
                    if geometry:
                        # Handle different geometry formats
                        if isinstance(geometry, dict):
                            coords = geometry.get("coordinates")
                            if coords and len(coords) >= 2:
                                poi_lat, poi_lon = coords[1], coords[0]  # GeoJSON format
                                
                                name = poi.get("name", category.replace("_", " ").title())
                                
                                folium.Marker(
                                    [poi_lat, poi_lon],
                                    popup=f"{config['emoji']} {name}",
                                    tooltip=category.replace("_", " ").title(),
                                    icon=folium.Icon(
                                        color=config["color"],
                                        icon=config["icon"],
                                        prefix="fa"
                                    )
                                ).add_to(m)
                                
                                poi_count += 1
        else:
            # If no specific coordinates, create representative markers around the center
            # This is a fallback - distribute markers in a circle
            category_count = min(count, max_pois_per_category)
            
            for i in range(category_count):
                if poi_count >= max_total_pois:
                    break
                
                # Distribute in a circle around center (within 1km radius)
                angle = (2 * math.pi * i) / category_count
                distance = 500 + (i % 3) * 200  # Vary distance slightly
                poi_lat = lat + (distance / 111000) * math.cos(angle)
                poi_lon = lon + (distance / 111000) * math.sin(angle) / math.cos(math.radians(lat))
                
                folium.Marker(
                    [poi_lat, poi_lon],
                    popup=f"{config['emoji']} {category.replace('_', ' ').title()} ({count} total)",
                    tooltip=category.replace("_", " ").title(),
                    icon=folium.Icon(
                        color=config["color"],
                        icon=config["icon"],
                        prefix="fa"
                    )
                ).add_to(m)
                
                poi_count += 1
    
    return m


def display_results(result: LocalityState):
    """
    Display results with optimal UX:
    1. Hero: Summary + Key Insights (most important first)
    2. Quick Stats: Top metrics at a glance
    3. Tabs: Organized details (Map, Statistics, Details)
    """
    
    if not result:
        st.error("Failed to generate analysis. Please try again.")
        return
    
    # Check for errors
    if result.get("errors"):
        st.error("## ❌ Errors Encountered")
        for error in result["errors"]:
            st.error(f"- {error}")
        
        with st.expander("🔍 Debug Information", expanded=False):
            st.write("Processing Steps:")
            for step in result.get("processing_steps", []):
                st.code(step)
        return
    
    # Show warnings if any
    if result.get("warnings"):
        for warning in result["warnings"]:
            st.warning(f"⚠️ {warning}")
    
    # ============================================================================
    # HERO SECTION: Summary + Key Insights (Most Important First)
    # ============================================================================
    st.markdown("---")
    
    # AI-Generated Summary (Hero) with Live Typing Effect
    if result.get("summary"):
        st.markdown("""
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 30px; border-radius: 10px; color: white; margin-bottom: 20px;'>
            <h2 style='color: white; margin-bottom: 15px;'>🤖 AI Analysis Summary</h2>
        </div>
        """, unsafe_allow_html=True)
        
        # Create placeholder for streaming summary
        summary_placeholder = st.empty()
        
        # Stream summary word by word for typing effect
        summary_text = result["summary"]
        display_summary_with_typing_effect(summary_placeholder, summary_text)
    
    # ============================================================================
    # QUICK STATS: Top Metrics at a Glance
    # ============================================================================
    if result.get("statistics"):
        stats = result["statistics"]
        
        st.subheader("📊 Quick Stats")
        
        # Get top metrics based on user profile or default important ones
        top_metrics = get_top_metrics(stats, result.get("selected_metrics", []))
        
        # Display in a grid
        num_cols = min(4, len(top_metrics))
        cols = st.columns(num_cols)
        
        for idx, (metric, value) in enumerate(top_metrics.items()):
            with cols[idx % num_cols]:
                metric_name = format_metric_name(metric)
                icon = get_metric_icon(metric)
                st.metric(f"{icon} {metric_name}", format_metric_value(value))
    
    st.markdown("---")
    
    # ============================================================================
    # TABS: Organized Details (Progressive Disclosure)
    # ============================================================================
    tab1, tab2, tab3, tab4 = st.tabs(["🗺️ Map & Location", "📊 Detailed Statistics", "🎯 Personalization", "🔍 Technical Details"])
    
    # Tab 1: Map & Location
    with tab1:
        display_map_and_location(result)
    
    # Tab 2: Detailed Statistics
    with tab2:
        display_detailed_statistics(result)
    
    # Tab 3: Personalization
    with tab3:
        display_personalization_info(result)
    
    # Tab 4: Technical Details
    with tab4:
        display_technical_details(result)


def get_top_metrics(statistics: dict, selected_metrics: list, max_count: int = 8) -> dict:
    """Get top metrics to display in quick stats."""
    # Priority order for metrics
    priority_metrics = [
        "school_count", "hospital_count", "metro_station_count",
        "restaurant_count", "park_area_km2", "poi_density",
        "walkability_score", "accessibility_score", "bus_stop_count",
        "gym_fitness_count", "shopping_count"
    ]
    
    # If metrics were selected, prioritize those
    if selected_metrics:
        # Get selected metrics that exist in statistics
        top = {k: statistics[k] for k in selected_metrics[:max_count] if k in statistics}
        if len(top) < max_count:
            # Fill with priority metrics
            for metric in priority_metrics:
                if metric in statistics and metric not in top:
                    top[metric] = statistics[metric]
                    if len(top) >= max_count:
                        break
        return top
    
    # Otherwise use priority order
    top = {}
    for metric in priority_metrics:
        if metric in statistics:
            top[metric] = statistics[metric]
            if len(top) >= max_count:
                break
    
    return top


def format_metric_name(metric: str) -> str:
    """Format metric name for display."""
    return metric.replace("_", " ").title()


def format_metric_value(value) -> str:
    """Format metric value for display."""
    if value is None:
        return "N/A"
    elif isinstance(value, (int, float)):
        if isinstance(value, float) and value < 1:
            return f"{value:.2f}"
        elif isinstance(value, float):
            return f"{value:.1f}"
        else:
            return str(value)
    else:
        return str(value)


def get_metric_icon(metric: str) -> str:
    """Get icon for metric."""
    icon_map = {
        "school": "🏫", "hospital": "🏥", "metro": "🚇", "restaurant": "🍽️",
        "park": "🌳", "gym": "💪", "bus": "🚌", "shopping": "🛍️",
        "walkability": "🚶", "accessibility": "♿", "poi": "📍"
    }
    
    metric_lower = metric.lower()
    for key, icon in icon_map.items():
        if key in metric_lower:
            return icon
    return "📊"


def display_map_and_location(result: LocalityState):
    """Display map and location information."""
    # Location Info
    col1, col2 = st.columns(2)
    
    with col1:
        if result.get("coordinates"):
            lat, lon = result["coordinates"]
            st.metric("📍 Coordinates", f"{lat:.4f}, {lon:.4f}")
        else:
            st.metric("📍 Coordinates", "N/A")
    
    with col2:
        if result.get("address"):
            st.metric("🏠 Address", result["address"])
        else:
            st.metric("🏠 Address", "N/A")
    
    st.markdown("---")
    
    # Map - Full Width
    if result.get("coordinates"):
        st.subheader("🗺️ Interactive Map")
        location_map = create_location_map(result)
        
        if location_map:
            # Full width map
            map_data = st_folium(
                location_map,
                width=None,  # Full width
                height=600,  # Increased height
                returned_objects=["last_object_clicked"]
            )
            
            with st.expander("ℹ️ Map Guide", expanded=False):
                st.markdown("""
                **Map Features:**
                - 🔴 **Red marker**: Analysis location (center)
                - 🔵 **Blue circle**: 1km search radius (primary analysis area)
                - ⚪ **Gray circle**: 2km extended radius (reference)
                - 🏫 **Colored markers**: Nearby POIs (schools, hospitals, restaurants, etc.)
                
                **POI Categories:**
                - 🏫 Schools (Blue) | 🏥 Hospitals (Red) | 🍽️ Restaurants (Orange)
                - 🚇 Metro (Purple) | 🚌 Bus Stops (Green) | 🌳 Parks (Green)
                - 💪 Gyms (Dark Red) | 💊 Pharmacies (Light Red) | 🏦 Banks (Dark Green)
                
                **Interactions:**
                - Click markers for details
                - Zoom in/out with mouse wheel
                - Drag to pan around
                """)


def display_detailed_statistics(result: LocalityState):
    """Display detailed statistics organized by category."""
    if not result.get("statistics"):
        st.info("No statistics available.")
        return
    
    stats = result["statistics"]
    selected_metrics = result.get("selected_metrics", [])
    
    if selected_metrics:
        st.info(f"📌 Showing {len(stats)} metrics selected based on your profile")
    
    # Organize by category
    categories = {
        "🎓 Education & Childcare": ["school", "university", "kindergarten", "childcare", "tuition"],
        "🏥 Healthcare": ["hospital", "clinic", "pharmacy", "health"],
        "🍽️ Food & Dining": ["restaurant", "cafe", "fast_food", "food"],
        "🚇 Transportation": ["metro", "bus", "road", "accessibility", "walkability"],
        "🌳 Recreation & Green Spaces": ["park", "gym", "sports", "playground", "green", "leisure"],
        "🛍️ Shopping & Services": ["shop", "bank", "atm", "shopping"],
        "📍 Other Metrics": []
    }
    
    categorized = {cat: [] for cat in categories}
    
    # Categorize metrics
    for metric, value in stats.items():
        categorized_flag = False
        for category, keywords in categories.items():
            if category == "📍 Other Metrics":
                continue
            if any(keyword in metric.lower() for keyword in keywords):
                categorized[category].append((metric, value))
                categorized_flag = True
                break
        if not categorized_flag:
            categorized["📍 Other Metrics"].append((metric, value))
    
    # Display by category
    for category, items in categorized.items():
        if items:
            st.subheader(category)
            cols = st.columns(min(4, len(items)))
            for idx, (metric, value) in enumerate(items):
                with cols[idx % len(cols)]:
                    metric_name = format_metric_name(metric)
                    icon = get_metric_icon(metric)
                    st.metric(f"{icon} {metric_name}", format_metric_value(value))
            st.markdown("")


def display_personalization_info(result: LocalityState):
    """Display personalization information."""
    # User Intent
    if result.get("user_intent"):
        intent = result["user_intent"]
        
        st.subheader("👤 Your Profile")
        
        col1, col2 = st.columns(2)
        
        with col1:
            profile_type = intent.get("profile_type", "general")
            st.metric("Profile Type", profile_type.replace("_", " ").title())
        
        with col2:
            priorities = intent.get("priorities", [])
            if priorities:
                st.write("**Top Priorities:**")
                for priority in priorities:
                    st.caption(f"• {priority.title()}")
        
        if intent.get("concerns"):
            st.write("**Main Concerns:**")
            for concern in intent.get("concerns", []):
                st.caption(f"• {concern.title()}")
        
        if intent.get("lifestyle"):
            with st.expander("💭 Lifestyle Preferences", expanded=True):
                st.write(intent["lifestyle"])
    
    # Selected Metrics
    if result.get("selected_metrics"):
        st.subheader("📊 Selected Metrics")
        
        selected_metrics = result["selected_metrics"]
        reasoning = result.get("user_intent", {}).get("metric_selection_reasoning", "")
        
        if reasoning:
            st.info(f"**Why these metrics?** {reasoning}")
        
        # Display in grid
        num_cols = 3
        cols = st.columns(num_cols)
        
        for idx, metric in enumerate(selected_metrics):
            with cols[idx % num_cols]:
                metric_display = format_metric_name(metric)
                st.caption(f"✓ {metric_display}")


def display_technical_details(result: LocalityState):
    """Display technical details for debugging."""
    st.subheader("🔍 Processing Information")
    
    # Processing Steps
    if result.get("processing_steps"):
        with st.expander("📋 Processing Steps", expanded=False):
            for step in result["processing_steps"]:
                st.caption(f"• {step}")
    
    # OSM Data
    if result.get("osm_data"):
        with st.expander("🗺️ Raw OSM Data", expanded=False):
            for category, data in result["osm_data"].items():
                if isinstance(data, dict) and "count" in data:
                    count = data["count"]
                    category_name = category.replace("_", " ").title()
                    st.write(f"**{category_name}**: {count} found")
    
    # State Info
    with st.expander("⚙️ State Information", expanded=False):
        st.json({
            "coordinates": result.get("coordinates"),
            "selected_metrics_count": len(result.get("selected_metrics", [])),
            "statistics_count": len(result.get("statistics", {})),
            "has_summary": result.get("summary") is not None,
            "has_intent": bool(result.get("user_intent"))
        })

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
                display_results(result)
    
    # Sidebar with info
    with st.sidebar:
        st.header("ℹ️ About")
        st.markdown("""
        **Locality Lens** provides:
        - 🎯 Personalized analysis
        - 📊 Key statistics
        - 🤖 AI-generated insights
        - 🗺️ Interactive maps
        """)
        
        st.markdown("---")
        st.subheader("💡 Tips")
        st.markdown("""
        - Enter an **address** or **coordinates**
        - Select your **profile** for personalized insights
        - Use **Custom** to describe specific needs
        - Analysis takes 3-5 seconds
        """)
        
        st.markdown("---")
        st.subheader("✨ Features")
        st.markdown("""
        - 🎯 LLM-driven metric selection
        - ⚡ Parallel execution
        - 📊 Personalized statistics
        - 💭 Intent extraction
        """)
        
        st.markdown("---")
        st.caption("Built with LangGraph, OSMnx, and Groq LLM")

if __name__ == "__main__":
    main()
