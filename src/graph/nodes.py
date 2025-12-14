"""
Graph nodes for Locality Lens workflow.

Each node is a function that takes state, performs work, and returns updated state.
"""
import os
import ssl
import json
import warnings
from typing import Dict, Any
from urllib.parse import quote, urlencode

import requests
import urllib3
import urllib3.poolmanager

# ============================================================================
# SSL Configuration: Corporate Proxy/Firewall SSL Inspection
# ============================================================================
# This must be done BEFORE importing requests/osmnx to handle SSL issues
# in corporate proxy environments.

# Disable SSL verification at Python level
ssl._create_default_https_context = ssl._create_unverified_context

# Set environment variables
os.environ['PYTHONHTTPSVERIFY'] = '0'
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Patch urllib3 PoolManager (OSMnx uses this)
_original_poolmanager_init = urllib3.poolmanager.PoolManager.__init__

def _patched_poolmanager_init(self, *args, **kwargs):
    """Force SSL verification off for urllib3."""
    kwargs['cert_reqs'] = ssl.CERT_NONE
    kwargs['ca_certs'] = None
    kwargs['ca_cert_dir'] = None
    return _original_poolmanager_init(self, *args, **kwargs)

urllib3.poolmanager.PoolManager.__init__ = _patched_poolmanager_init

# Patch requests at all levels
_original_get = requests.get
_original_post = requests.post
_original_session_request = requests.Session.request
_original_adapter_send = requests.adapters.HTTPAdapter.send

def _patched_get(*args, **kwargs):
    """Patched requests.get with SSL verification disabled."""
    kwargs.setdefault('verify', False)
    return _original_get(*args, **kwargs)

def _patched_post(*args, **kwargs):
    """Patched requests.post with SSL verification disabled."""
    kwargs.setdefault('verify', False)
    return _original_post(*args, **kwargs)

def _patched_session_request(self, *args, **kwargs):
    """Patched Session.request with SSL verification disabled."""
    kwargs.setdefault('verify', False)
    return _original_session_request(self, *args, **kwargs)

def _patched_adapter_send(self, request, *args, **kwargs):
    """Patched HTTPAdapter.send with SSL verification disabled."""
    kwargs.setdefault('verify', False)
    return _original_adapter_send(self, request, *args, **kwargs)

# Apply patches
requests.get = _patched_get
requests.post = _patched_post
requests.Session.request = _patched_session_request
requests.adapters.HTTPAdapter.send = _patched_adapter_send

# Import geospatial libraries (after SSL patches)
import osmnx as ox
import geopandas as gpd
from shapely.geometry import Point

# Configure OSMnx
warnings.filterwarnings('ignore')
ox.settings.log_console = True
ox.settings.use_cache = True
ox.settings.timeout = 300

from .state import LocalityState

def validate_input(state: LocalityState) -> LocalityState:
    """
    Validate user input.
    
    Checks if input is provided and attempts to parse coordinates if in coordinate format.
    """
    user_input = state.get("user_input", "").strip()
    
    if not user_input:
        state["errors"].append("User input is required")
        state["next_action"] = "error"
        state["processing_steps"].append("validate_input: FAILED - No input provided")
        return state
    
    # Check if input is already coordinates (format: "lat, lon" or "lat,lon")
    if "," in user_input:
        try:
            parts = user_input.replace(" ", "").split(",")
            if len(parts) == 2:
                lat = float(parts[0])
                lon = float(parts[1])
                
                # Validate coordinate ranges
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    state["coordinates"] = (lat, lon)
                    # Don't set next_action - let graph route handle it
                    state["processing_steps"].append(f"validate_input: SUCCESS - Parsed coordinates ({lat}, {lon})")
                    return state
        except ValueError:
            # Not coordinates, treat as address
            pass
    
    # Input is an address, needs geocoding
    # Don't set next_action - let graph route handle it
    state["processing_steps"].append("validate_input: SUCCESS - Address detected, needs geocoding")
    return state


def geocode_location(state: LocalityState) -> LocalityState:
    """
    Geocode address to coordinates using Nominatim (OpenStreetMap).
    
    Converts address string to (latitude, longitude) coordinates.
    Uses direct API calls to handle SSL certificate issues.
    """
    # Skip if coordinates already exist (from validate_input)
    if state.get("coordinates"):
        state["processing_steps"].append("geocode_location: SKIPPED - Coordinates already exist")
        return state
    
    user_input = state.get("user_input", "")
    
    if not user_input:
        state["errors"].append("No input provided for geocoding")
        state["next_action"] = "error"
        return state
    
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            'q': user_input,
            'format': 'json',
            'limit': 1
        }
        headers = {
            'User-Agent': 'locality-lens'  # Required by Nominatim
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10, verify=False)
        
        if response.status_code == 200:
            data = response.json()
            if data:
                location_data = data[0]
                lat = float(location_data['lat'])
                lon = float(location_data['lon'])
                address = location_data.get('display_name', user_input)
                
                state["coordinates"] = (lat, lon)
                state["address"] = address
                state["processing_steps"].append(f"geocode_location: SUCCESS - Geocoded to ({lat}, {lon})")
            else:
                state["errors"].append(f"Could not geocode location: {user_input}")
                state["processing_steps"].append(f"geocode_location: FAILED - No results for '{user_input}'")
        else:
            state["errors"].append(f"Geocoding API returned status {response.status_code}")
            state["processing_steps"].append(f"geocode_location: ERROR - API status {response.status_code}")
    
    except requests.exceptions.SSLError:
        # If SSL still fails, try with urllib3
        try:
            http = urllib3.PoolManager(cert_reqs='CERT_NONE')
            params = urlencode({'q': user_input, 'format': 'json', 'limit': 1})
            url = f"https://nominatim.openstreetmap.org/search?{params}"
            
            response = http.request('GET', url, headers={'User-Agent': 'locality-lens'})
            
            if response.status == 200:
                data = json.loads(response.data.decode('utf-8'))
                if data:
                    location_data = data[0]
                    lat = float(location_data['lat'])
                    lon = float(location_data['lon'])
                    address = location_data.get('display_name', user_input)
                    
                    state["coordinates"] = (lat, lon)
                    state["address"] = address
                    state["processing_steps"].append(f"geocode_location: SUCCESS - Geocoded to ({lat}, {lon}) via urllib3")
                else:
                    state["errors"].append(f"Could not geocode location: {user_input}")
            else:
                state["errors"].append(f"Geocoding failed with status {response.status}")
        except Exception as urllib_error:
            state["errors"].append(f"Geocoding failed: {str(urllib_error)}")
            state["processing_steps"].append(f"geocode_location: ERROR - {str(urllib_error)}")
    
    except Exception as e:
        state["errors"].append(f"Unexpected error during geocoding: {str(e)}")
        state["processing_steps"].append(f"geocode_location: ERROR - {str(e)}")
    
    return state


def fetch_osm_data(state: LocalityState) -> LocalityState:
    """
    Fetch OpenStreetMap POI data around the location.
    
    Uses a single optimized query to fetch all POI categories, then classifies
    and cleans the data for improved accuracy.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with OSM data populated
    """
    coordinates = state.get("coordinates")
    
    if not coordinates:
        state["errors"].append("No coordinates available for OSM data fetching")
        state["next_action"] = "error"
        return state
    
    lat, lon = coordinates
    location_point = (lat, lon)
    radius = 2000  # 2km radius
    
    try:
        # Single optimized query for all POI categories
        all_pois = ox.features_from_point(
            location_point,
            tags={
                # Essential amenities
                'amenity': [
                    'school', 'hospital', 'clinic', 'doctors', 'dentist',
                    'restaurant', 'cafe', 'fast_food', 'food_court',
                    'pharmacy', 'bank', 'atm', 'library', 'place_of_worship',
                    'community_centre', 'kindergarten', 'childcare', 'tuition',
                    'university', 'college', 'cinema'
                ],
                # Leisure & recreation
                'leisure': [
                    'park', 'garden', 'recreation_ground', 'playground',
                    'fitness_centre', 'gym', 'sports_centre'
                ],
                # Entertainment & nightlife
                'amenity': ['bar', 'pub', 'nightclub'],  # Will merge with above
                # Transportation
                'railway': 'station',
                'highway': 'bus_stop',
                # Shopping
                'shop': True,  # All shop types
                # Tourism
                'tourism': ['hotel', 'attraction'],
                # Buildings (for residential density)
                'building': 'residential',
                # Roads (for road density)
                'highway': ['primary', 'secondary', 'tertiary', 'residential', 'cycleway']
            },
            dist=radius
        )
        
        osm_data = {}
        
        # Classify and clean each category
        if not all_pois.empty:
            # Schools
            if 'amenity' in all_pois.columns:
                schools = all_pois[all_pois['amenity'] == 'school'].copy()
                schools = clean_and_deduplicate_pois(schools, "schools")
                osm_data["schools"] = {"count": len(schools), "data": []}
            
                # Hospitals & Clinics
                hospitals = all_pois[all_pois['amenity'].isin(['hospital', 'clinic', 'doctors', 'dentist'])].copy()
                hospitals = clean_and_deduplicate_pois(hospitals, "hospitals")
                osm_data["hospitals"] = {"count": len(hospitals), "data": []}
                
                    # Restaurants (combined)
                restaurants = all_pois[all_pois['amenity'].isin(['restaurant', 'cafe', 'fast_food', 'food_court'])].copy()
                restaurants = clean_and_deduplicate_pois(restaurants, "restaurants")
                osm_data["restaurants"] = {"count": len(restaurants), "data": []}
        
                # Cafes (separate)
                cafes = all_pois[all_pois['amenity'] == 'cafe'].copy()
                cafes = clean_and_deduplicate_pois(cafes, "cafes")
                osm_data["cafes"] = {"count": len(cafes), "data": []}
                
                # Fast food (separate)
                fast_food = all_pois[all_pois['amenity'] == 'fast_food'].copy()
                fast_food = clean_and_deduplicate_pois(fast_food, "fast_food")
                osm_data["fast_food"] = {"count": len(fast_food), "data": []}
                
                # Banks & ATMs
                banks = all_pois[all_pois['amenity'].isin(['bank', 'atm'])].copy()
                banks = clean_and_deduplicate_pois(banks, "banks")
                osm_data["banks"] = {"count": len(banks), "data": []}
                
                # Pharmacies
                pharmacies = all_pois[all_pois['amenity'] == 'pharmacy'].copy()
                pharmacies = clean_and_deduplicate_pois(pharmacies, "pharmacies")
                osm_data["pharmacies"] = {"count": len(pharmacies), "data": []}
                
                # Gyms & Fitness
                gyms = all_pois[all_pois['leisure'].isin(['fitness_centre', 'gym'])].copy()
                gyms = clean_and_deduplicate_pois(gyms, "gyms")
                osm_data["gyms"] = {"count": len(gyms), "data": []}
                
                # Libraries
                libraries = all_pois[all_pois['amenity'] == 'library'].copy()
                libraries = clean_and_deduplicate_pois(libraries, "libraries")
                osm_data["libraries"] = {"count": len(libraries), "data": []}
                
                # Places of worship
                worship = all_pois[all_pois['amenity'] == 'place_of_worship'].copy()
                worship = clean_and_deduplicate_pois(worship, "worship")
                osm_data["worship"] = {"count": len(worship), "data": []}
                
                # Nightlife
                nightlife = all_pois[all_pois['amenity'].isin(['bar', 'pub', 'nightclub'])].copy()
                nightlife = clean_and_deduplicate_pois(nightlife, "nightlife")
                osm_data["nightlife"] = {"count": len(nightlife), "data": []}
                
                # Cinemas
                cinemas = all_pois[all_pois['amenity'] == 'cinema'].copy()
                cinemas = clean_and_deduplicate_pois(cinemas, "cinemas")
                osm_data["cinemas"] = {"count": len(cinemas), "data": []}
                
                # Universities & Colleges
                universities = all_pois[all_pois['amenity'].isin(['university', 'college'])].copy()
                universities = clean_and_deduplicate_pois(universities, "universities")
                osm_data["universities"] = {"count": len(universities), "data": []}
                
                # Kindergartens
                kindergartens = all_pois[all_pois['amenity'] == 'kindergarten'].copy()
                kindergartens = clean_and_deduplicate_pois(kindergartens, "kindergartens")
                osm_data["kindergartens"] = {"count": len(kindergartens), "data": []}
                
                # Childcare
                childcare = all_pois[all_pois['amenity'] == 'childcare'].copy()
                childcare = clean_and_deduplicate_pois(childcare, "childcare")
                osm_data["childcare"] = {"count": len(childcare), "data": []}
                
                # Tuition centres
                tuition = all_pois[all_pois['amenity'] == 'tuition'].copy()
                tuition = clean_and_deduplicate_pois(tuition, "tuition")
                osm_data["tuition"] = {"count": len(tuition), "data": []}
                
                # Community centres
                community = all_pois[all_pois['amenity'] == 'community_centre'].copy()
                community = clean_and_deduplicate_pois(community, "community")
                osm_data["community"] = {"count": len(community), "data": []}
            
            # Leisure categories
            if 'leisure' in all_pois.columns:
                # Parks
                parks = all_pois[all_pois['leisure'].isin(['park', 'garden', 'recreation_ground'])].copy()
                parks = clean_and_deduplicate_pois(parks, "parks")
                estimated_area = len(parks) * 0.15  # Rough estimate
                osm_data["parks"] = {"count": len(parks), "area_km2": round(estimated_area, 2), "data": []}
        
                # Playgrounds
                playgrounds = all_pois[all_pois['leisure'] == 'playground'].copy()
                playgrounds = clean_and_deduplicate_pois(playgrounds, "playgrounds")
                osm_data["playgrounds"] = {"count": len(playgrounds), "data": []}
                
                # Sports facilities
                sports = all_pois[all_pois['leisure'] == 'sports_centre'].copy()
                sports = clean_and_deduplicate_pois(sports, "sports")
                osm_data["sports"] = {"count": len(sports), "data": []}
            
            # Transportation
            if 'railway' in all_pois.columns:
                metro = all_pois[all_pois['railway'] == 'station'].copy()
            if 'station' in all_pois.columns:
                metro = metro[metro['station'].isin(['subway', 'metro'])]
                metro = clean_and_deduplicate_pois(metro, "metro")
            osm_data["metro_stations"] = {"count": len(metro), "data": []}
        
            if 'highway' in all_pois.columns:
                bus_stops = all_pois[all_pois['highway'] == 'bus_stop'].copy()
                bus_stops = clean_and_deduplicate_pois(bus_stops, "bus_stops")
            osm_data["bus_stops"] = {"count": len(bus_stops), "data": []}
        
            # Shopping
            if 'shop' in all_pois.columns:
                shops = all_pois[all_pois['shop'].notna()].copy()
                shops = clean_and_deduplicate_pois(shops, "shops")
                osm_data["shops"] = {"count": len(shops), "data": []}
            
            # Tourism
            if 'tourism' in all_pois.columns:
                hotels = all_pois[all_pois['tourism'] == 'hotel'].copy()
                hotels = clean_and_deduplicate_pois(hotels, "hotels")
                osm_data["hotels"] = {"count": len(hotels), "data": []}
            
            # Buildings (for residential density)
            if 'building' in all_pois.columns:
                residential = all_pois[all_pois['building'] == 'residential'].copy()
                residential = clean_and_deduplicate_pois(residential, "residential")
                osm_data["residential_buildings"] = {"count": len(residential), "data": []}
            
            # Roads (for road density) - need separate query
            # This is expensive, so we'll calculate it separately if needed
        
        state["osm_data"] = osm_data
        state["next_action"] = "select_metrics"  # Changed from calculate_statistics
        state["processing_steps"].append(
            f"fetch_osm_data: SUCCESS - Fetched {len(osm_data)} POI categories"
        )
        
    except Exception as e:
        state["errors"].append(f"Error fetching OSM data: {str(e)}")
        state["next_action"] = "error"
        state["processing_steps"].append(f"fetch_osm_data: ERROR - {str(e)}")
    
    return state


def extract_intent_and_select_metrics(state: LocalityState) -> LocalityState:
    """
    Extract user intent and select relevant metrics.
    
    This can run in parallel with geocoding/OSM fetch since it doesn't need coordinates.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with user intent and selected metrics
    """
    user_profile = state.get("user_profile")
    user_input = state.get("user_input", "")

    # Handle case where no profile is provided
    if not user_profile or not user_profile.strip():
        from src.analysis.metrics_catalog import get_default_metrics_for_profile
        state["user_intent"] = {
            "profile_type": "general",
            "priorities": [],
            "concerns": [],
            "lifestyle": "general"
        }
        state["selected_metrics"] = get_default_metrics_for_profile("Custom")
        state["processing_steps"].append("extract_intent_and_select_metrics: SKIPPED - No profile, used defaults")
        return state

    try:
        from src.llm.intent_extractor import extract_intent_and_select_metrics as llm_extract_and_select

        result = llm_extract_and_select(user_profile, user_input)
        state["user_intent"] = result["user_intent"]
        state["selected_metrics"] = result["selected_metrics"]
        
        # Store reasoning for summary generation
        if "reasoning" in result:
            state["user_intent"]["metric_selection_reasoning"] = result["reasoning"]
        
        state["processing_steps"].append(
            f"extract_intent_and_select_metrics: SUCCESS - Extracted intent, selected {len(result['selected_metrics'])} metrics"
        )
    except Exception as e:
        # Fallback to defaults
        from src.analysis.metrics_catalog import get_default_metrics_for_profile
        
        profile_lower = (user_profile or "").lower()
        if "bachelor" in profile_lower or "young" in profile_lower:
            profile_type = "bachelor"
        elif "family" in profile_lower or "kids" in profile_lower:
            profile_type = "family"
        elif "student" in profile_lower:
            profile_type = "student"
        elif "senior" in profile_lower:
            profile_type = "senior_citizen"
        elif "work" in profile_lower or "professional" in profile_lower:
            profile_type = "working_professional"
        else:
            profile_type = "general"
        
        state["user_intent"] = {
            "profile_type": profile_type,
            "priorities": [],
            "concerns": [],
            "lifestyle": "general"
        }
        state["selected_metrics"] = get_default_metrics_for_profile(profile_type)
        state["warnings"].append(f"Intent/metric selection failed: {str(e)}, used defaults")
        state["processing_steps"].append("extract_intent_and_select_metrics: WARNING - Used defaults (fallback)")
    
    return state


def clean_and_deduplicate_pois(gdf: gpd.GeoDataFrame, category_name: str = "") -> gpd.GeoDataFrame:
    """
    Clean and deduplicate POI GeoDataFrame.
    
    Removes invalid entries and deduplicates by normalized name and location.
    
    Args:
        gdf: GeoDataFrame with POIs
        category_name: Category name for logging (optional)
    
    Returns:
        Cleaned GeoDataFrame
    """
    if gdf.empty:
        return gdf
    
    original_count = len(gdf)
    
    # Remove entries without valid geometry
    if 'geometry' in gdf.columns:
        gdf = gdf[gdf['geometry'].notna()]
        gdf = gdf[~gdf['geometry'].is_empty]
        gdf = gdf[gdf['geometry'].is_valid]
    
    # Deduplicate by normalized name (case-insensitive)
    if 'name' in gdf.columns:
        gdf['_name_normalized'] = (
            gdf['name']
            .fillna('')
            .astype(str)
            .str.lower()
            .str.strip()
            .str.replace(r'\s+', ' ', regex=True)
        )
        gdf = gdf.drop_duplicates(subset=['_name_normalized'], keep='first')
        gdf = gdf.drop(columns=['_name_normalized'], errors='ignore')
    
    # Deduplicate by location (if same name at same location)
    if 'name' in gdf.columns and 'geometry' in gdf.columns and not gdf.empty:
        try:
                gdf['_name_norm'] = gdf['name'].fillna('').astype(str).str.lower().str.strip()
                gdf = gdf.drop_duplicates(subset=['_name_norm', 'geometry'], keep='first')
                gdf = gdf.drop(columns=['_name_norm'], errors='ignore')
        except Exception:
            # If spatial deduplication fails, continue with name-only deduplication
            pass
    
    cleaned_count = len(gdf)
    removed = original_count - cleaned_count
    
    # Note: Processing steps are tracked in the calling function
    # This keeps the cleaning function pure and reusable
    
    return gdf


def calculate_statistics(state: LocalityState) -> LocalityState:
    """
    Calculate statistics from OSM data.
    
    Computes key metrics including POI counts, density, and connectivity indicators.
    
    Args:
        state: Current workflow state with OSM data
        
    Returns:
        Updated state with calculated statistics
    """
    osm_data = state.get("osm_data", {})
    coordinates = state.get("coordinates")
    selected_metrics = state.get("selected_metrics")
    
    if not osm_data:
        state["errors"].append("No OSM data available for statistics calculation")
        state["next_action"] = "error"
        return state
    
    if not coordinates:
        state["errors"].append("No coordinates available for distance calculations")
        state["next_action"] = "error"
        return state
    
    try:
        from src.analysis.metrics_catalog import METRICS_CATALOG, get_required_dependencies

        statistics = {}
        lat, lon = coordinates
        # Get all metrics to calculate (selected + dependencies)
        metrics_to_calculate = selected_metrics.copy() if selected_metrics else []
        if metrics_to_calculate:
            dependencies = get_required_dependencies(metrics_to_calculate)
            metrics_to_calculate.extend([d for d in dependencies if d not in metrics_to_calculate])
        else:
            # If no selection, calculate all basic metrics
            metrics_to_calculate = [
                "school_count", "hospital_count", "restaurant_count",
                "park_area_km2", "metro_station_count", "bus_stop_count",
                "poi_density"
            ]
        
        # ========================================================================
        # CALCULATE ALL METRICS FROM CATALOG
        # ========================================================================
        
        # Basic count metrics (from OSM data)
        category_mapping = {
            "school_count": ("schools", "count"),
            "hospital_count": ("hospitals", "count"),
            "restaurant_count": ("restaurants", "count"),
            "cafe_count": ("cafes", "count"),
            "fast_food_count": ("fast_food", "count"),
            "shopping_count": ("shops", "count"),
            "bank_atm_count": ("banks", "count"),
            "pharmacy_count": ("pharmacies", "count"),
            "gym_fitness_count": ("gyms", "count"),
            "library_count": ("libraries", "count"),
            "place_of_worship_count": ("worship", "count"),
            "nightlife_count": ("nightlife", "count"),
            "cinema_count": ("cinemas", "count"),
            "playground_count": ("playgrounds", "count"),
            "sports_facility_count": ("sports", "count"),
            "hotel_count": ("hotels", "count"),
            "community_centre_count": ("community", "count"),
            "university_count": ("universities", "count"),
            "kindergarten_count": ("kindergartens", "count"),
            "childcare_count": ("childcare", "count"),
            "tuition_centre_count": ("tuition", "count"),
            "metro_station_count": ("metro_stations", "count"),
            "bus_stop_count": ("bus_stops", "count"),
        }

        # Calculate count metrics
        for metric_key in metrics_to_calculate:
            if metric_key in category_mapping:
                category, field = category_mapping[metric_key]
                value = osm_data.get(category, {}).get(field, 0)
                statistics[metric_key] = value
        
        # Park area
        if "park_area_km2" in metrics_to_calculate:
            statistics["park_area_km2"] = osm_data.get("parks", {}).get("area_km2", 0.0)
        
        # Nearest metro distance (if metro stations exist)
        if "nearest_metro_distance_km" in metrics_to_calculate:
            metro_count = statistics.get("metro_station_count", 0)
            if metro_count > 0:
                # Simplified: if metro exists, distance is < 2km (within search radius)
                statistics["nearest_metro_distance_km"] = "< 2km"
        else:
            statistics["nearest_metro_distance_km"] = None
        

        # POI Density
        if "poi_density" in metrics_to_calculate:
            area_km2 = 12.57  # π * (2km)²
            total_pois = sum([
                statistics.get("school_count", 0),
                statistics.get("hospital_count", 0),
                statistics.get("restaurant_count", 0),
                statistics.get("metro_station_count", 0),
                statistics.get("bus_stop_count", 0),
                statistics.get("shopping_count", 0),
            ])
        statistics["poi_density"] = round(total_pois / area_km2, 2) if area_km2 > 0 else 0.0

        # Green space ratio
        if "green_space_ratio" in metrics_to_calculate:
            park_area = statistics.get("park_area_km2", 0.0)
            total_area = 12.57  # π * (2km)²
            statistics["green_space_ratio"] = round(park_area / total_area, 3) if total_area > 0 else 0.0
        
        # Road density (if needed - expensive calculation)
        if "road_density_km_per_km2" in metrics_to_calculate:
            # This requires separate OSM query for roads
            # For now, estimate or skip
            statistics["road_density_km_per_km2"] = None  # Placeholder
            state["warnings"].append("Road density calculation not yet implemented")
        
        # Main road count (if needed)
        if "main_road_count" in metrics_to_calculate:
            # Requires separate query
            statistics["main_road_count"] = None
            state["warnings"].append("Main road count calculation not yet implemented")
        
        # Composite metrics (depend on other metrics)
        if "walkability_score" in metrics_to_calculate:
            # Simplified walkability score (0-100)
            poi_density = statistics.get("poi_density", 0)
            metro_count = statistics.get("metro_station_count", 0)
            bus_count = statistics.get("bus_stop_count", 0)
            
            # Simple scoring
            score = min(100, (poi_density * 2) + (metro_count * 10) + (bus_count * 0.5))
            statistics["walkability_score"] = round(score, 1)
        
        if "accessibility_score" in metrics_to_calculate:
            # Composite accessibility score
            metro_count = statistics.get("metro_station_count", 0)
            bus_count = statistics.get("bus_stop_count", 0)
            poi_density = statistics.get("poi_density", 0)
            
            score = min(100, (metro_count * 15) + (bus_count * 1) + (poi_density * 3))
            statistics["accessibility_score"] = round(score, 1)
        
        if "amenity_diversity_score" in metrics_to_calculate:
            # Shannon diversity index (simplified)
            # Count unique amenity types
            unique_types = sum(1 for k in statistics.keys() if k.endswith("_count") and statistics.get(k, 0) > 0)
            diversity = min(100, unique_types * 10)
            statistics["amenity_diversity_score"] = round(diversity, 1)
        
        if "residential_density" in metrics_to_calculate:
            # Estimate from residential buildings
            residential_count = osm_data.get("residential_buildings", {}).get("count", 0)
            area_km2 = 12.57

        if "residential_density" in metrics_to_calculate:
            # Estimate from residential buildings
            residential_count = osm_data.get("residential_buildings", {}).get("count", 0)
            area_km2 = 12.57
            statistics["residential_density"] = round(residential_count / area_km2, 2) if area_km2 > 0 else 0.0
        
        # Filter to only selected metrics (if selection was made)
        if selected_metrics:
            filtered_statistics = {}
            for metric_key in selected_metrics:
                if metric_key in statistics:
                    filtered_statistics[metric_key] = statistics[metric_key]
            statistics = filtered_statistics
        
        state["statistics"] = statistics
        state["next_action"] = "generate_summary"
        state["processing_steps"].append(
            f"calculate_statistics: SUCCESS - Calculated {len(statistics)} metrics"
        )
    except Exception as e:
        state["errors"].append(f"Error calculating statistics: {str(e)}")
        state["next_action"] = "error"
        state["processing_steps"].append(f"calculate_statistics: ERROR - {str(e)}")
    
    return state


def handle_error(state: LocalityState) -> LocalityState:
    """
    Handle errors gracefully.
    
    Collects all errors and prepares error message for user.
    """
    errors = state.get("errors", [])
    warnings = state.get("warnings", [])
    
    error_message = "Errors encountered:\n" + "\n".join(f"- {error}" for error in errors)
    
    if warnings:
        error_message += "\n\nWarnings:\n" + "\n".join(f"- {warning}" for warning in warnings)
    
    state["summary"] = error_message
    state["next_action"] = "end"
    state["processing_steps"].append("handle_error: Error handling completed")
    
    return state


def generate_summary(state: LocalityState) -> LocalityState:
    """
    Generate a summary of the locality using the LLM with personalized context.
    """
    statistics = state.get("statistics", {})
    osm_data = state.get("osm_data", {})
    address = state.get("address", "")
    user_intent = state.get("user_intent", {})
    selected_metrics = state.get("selected_metrics", [])
    user_profile = state.get("user_profile")

    if not statistics and not osm_data:
        state["errors"].append("No data available for summary generation")
        state["next_action"] = "error"
        return state

    try:
        from src.llm.summary_generator import generate_summary as llm_generate_summary
        
        # Pass all available context for personalized summary
        summary = llm_generate_summary(
            statistics=statistics,
            osm_data=osm_data,
            address=address,
            user_intent=user_intent,
            selected_metrics=selected_metrics,
            user_profile=user_profile
        )
        
        state["summary"] = summary
        state["next_action"] = "end"
        state["processing_steps"].append("generate_summary: SUCCESS - Summary generated")
        return state
    except Exception as e:
        print(f"⚠️ Error generating summary: {e}")
        state["warnings"].append(f"Could not generate summary: {str(e)}")
        # Don't fail - provide basic summary
        state["summary"] = create_fallback_summary(statistics, osm_data, user_intent)
        state["processing_steps"].append(f"generate_summary: WARNING - Used fallback summary")
    
    return state


def create_fallback_summary(statistics: dict, osm_data: dict, user_intent: dict = None) -> str:
    """Create a basic summary if LLM fails."""
    lines = ["Locality Analysis Summary\n"]
    
    # Add user context if available
    if user_intent:
        profile_type = user_intent.get("profile_type", "general")
        lines.append(f"Analysis for: {profile_type.replace('_', ' ').title()}\n")
    
    if statistics:
        lines.append("Key Statistics:")
        for key, value in list(statistics.items())[:8]:
            metric_name = key.replace("_", " ").title()
            lines.append(f"- {metric_name}: {value}")
        lines.append("")
    
    if osm_data:
        lines.append("Nearby Facilities:")
        for category, data in list(osm_data.items())[:8]:
            if isinstance(data, dict):
                count = data.get("count", 0)
                if count > 0:
                    category_name = category.replace("_", " ").title()
                    lines.append(f"- {category_name}: {count}")
    
    return "\n".join(lines)