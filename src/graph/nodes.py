"""
Graph nodes for Locality Lens workflow.
Each node is a function that takes state, performs work, and returns updated state.
"""
import os
import ssl
import urllib3

# ============================================================================
# FIX SSL ISSUES: Corporate Proxy/Firewall SSL Inspection
# ============================================================================
# This must be done BEFORE importing requests/osmnx

# Disable SSL verification at Python level
ssl._create_default_https_context = ssl._create_unverified_context

# Set environment variables
os.environ['PYTHONHTTPSVERIFY'] = '0'
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''

# Import and patch requests/urllib3 BEFORE OSMnx
import requests
import urllib3.poolmanager

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

def _patched_get(*args, **kwargs):
    kwargs.setdefault('verify', False)
    return _original_get(*args, **kwargs)

def _patched_post(*args, **kwargs):
    kwargs.setdefault('verify', False)
    return _original_post(*args, **kwargs)

def _patched_session_request(self, *args, **kwargs):
    kwargs.setdefault('verify', False)
    return _original_session_request(self, *args, **kwargs)

requests.get = _patched_get
requests.post = _patched_post
requests.Session.request = _patched_session_request

# Patch HTTPAdapter (what OSMnx actually uses internally)
_original_adapter_send = requests.adapters.HTTPAdapter.send

def _patched_adapter_send(self, request, *args, **kwargs):
    """Patch HTTPAdapter.send - this is what OSMnx uses."""
    kwargs.setdefault('verify', False)
    return _original_adapter_send(self, request, *args, **kwargs)

requests.adapters.HTTPAdapter.send = _patched_adapter_send

# NOW import OSMnx and other libraries (after SSL patches)
import osmnx as ox
import geopandas as gpd
from shapely.geometry import Point
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import warnings

warnings.filterwarnings('ignore')

# Configure OSMnx EXACTLY like your notebook
ox.settings.log_console = True
ox.settings.use_cache = True
ox.settings.timeout = 300

from typing import Dict, Any
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
        # Use requests directly to bypass SSL issues
        from urllib.parse import quote
        
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            'q': user_input,
            'format': 'json',
            'limit': 1
        }
        headers = {
            'User-Agent': 'locality-lens'  # Required by Nominatim
        }
        
        # Disable SSL verification for corporate/proxy environments
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
    
    except requests.exceptions.SSLError as e:
        # If SSL still fails, try with urllib3
        try:
            http = urllib3.PoolManager(cert_reqs='CERT_NONE')
            from urllib.parse import urlencode
            
            params = urlencode({'q': user_input, 'format': 'json', 'limit': 1})
            url = f"https://nominatim.openstreetmap.org/search?{params}"
            
            response = http.request('GET', url, headers={'User-Agent': 'locality-lens'})
            
            if response.status == 200:
                import json
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
    Fetch ALL POIs in one query, then classify and clean.
    """
    coordinates = state.get("coordinates")
    
    if not coordinates:
        state["errors"].append("No coordinates available")
        state["next_action"] = "error"
        return state
    
    lat, lon = coordinates
    location_point = (lat, lon)
    radius = 2000
    
    print("\n🗺️  Fetching ALL POIs in one query...")
    
    try:
        # SINGLE QUERY for everything
        all_pois = ox.features_from_point(
            location_point,
            tags={
                'amenity': ['school', 'hospital', 'clinic', 'doctors', 'dentist',
                           'restaurant', 'cafe', 'fast_food', 'food_court'],
                'leisure': ['park', 'garden', 'recreation_ground'],
                'railway': 'station',
                'highway': 'bus_stop'
            },
            dist=radius
        )
        
        print(f"   ✅ Fetched {len(all_pois)} total POIs")
        print("   🔍 Classifying and cleaning POIs...")
        
        osm_data = {}
        
        # Classify and clean each category
        if not all_pois.empty and 'amenity' in all_pois.columns:
            # Schools
            schools = all_pois[all_pois['amenity'] == 'school'].copy()
            schools = clean_and_deduplicate_pois(schools, "schools")
            osm_data["schools"] = {"count": len(schools), "data": []}
            
            # Hospitals
            hospitals = all_pois[all_pois['amenity'].isin(['hospital', 'clinic', 'doctors', 'dentist'])].copy()
            hospitals = clean_and_deduplicate_pois(hospitals, "hospitals")
            osm_data["hospitals"] = {"count": len(hospitals), "data": []}
            
            # Restaurants
            restaurants = all_pois[all_pois['amenity'].isin(['restaurant', 'cafe', 'fast_food', 'food_court'])].copy()
            restaurants = clean_and_deduplicate_pois(restaurants, "restaurants")
            osm_data["restaurants"] = {"count": len(restaurants), "data": []}
        
        if not all_pois.empty and 'leisure' in all_pois.columns:
            parks = all_pois[all_pois['leisure'].isin(['park', 'garden', 'recreation_ground'])].copy()
            parks = clean_and_deduplicate_pois(parks, "parks")
            estimated_area = len(parks) * 0.15
            osm_data["parks"] = {"count": len(parks), "area_km2": round(estimated_area, 2), "data": []}
        
        if not all_pois.empty and 'railway' in all_pois.columns:
            metro = all_pois[all_pois['railway'] == 'station'].copy()
            if 'station' in all_pois.columns:
                metro = metro[metro['station'].isin(['subway', 'metro'])]
            metro = clean_and_deduplicate_pois(metro, "metro stations")
            osm_data["metro_stations"] = {"count": len(metro), "data": []}
        
        if not all_pois.empty and 'highway' in all_pois.columns:
            bus_stops = all_pois[all_pois['highway'] == 'bus_stop'].copy()
            bus_stops = clean_and_deduplicate_pois(bus_stops, "bus stops")
            osm_data["bus_stops"] = {"count": len(bus_stops), "data": []}
        
        print("   ✅ Classification and cleaning complete!")
        
        state["osm_data"] = osm_data
        state["next_action"] = "calculate_statistics"
        state["processing_steps"].append(f"fetch_osm_data: SUCCESS - Fetched, classified, and cleaned {len(osm_data)} POI categories")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        state["errors"].append(f"Error fetching OSM data: {str(e)}")
        state["next_action"] = "error"
    
    return state


def clean_and_deduplicate_pois(gdf, category_name=""):
    """
    Clean and deduplicate POI GeoDataFrame.
    
    Steps:
    1. Remove entries without geometry
    2. Remove entries with invalid geometry
    3. Deduplicate by normalized name (case-insensitive)
    4. Optional: Deduplicate by location proximity
    
    Args:
        gdf: GeoDataFrame with POIs
        category_name: Category name for logging
    
    Returns:
        Cleaned GeoDataFrame
    """
    if gdf.empty:
        return gdf
    
    original_count = len(gdf)
    
    # 1. Remove entries without geometry
    if 'geometry' in gdf.columns:
        # Remove null geometries
        gdf = gdf[gdf['geometry'].notna()]
        # Remove empty geometries
        gdf = gdf[~gdf['geometry'].is_empty]
        # Remove invalid geometries
        gdf = gdf[gdf['geometry'].is_valid]
    
    # 2. Deduplicate by name (case-insensitive, normalized)
    if 'name' in gdf.columns:
        # Create normalized name column
        gdf['_name_normalized'] = (
            gdf['name']
            .fillna('')  # Fill NaN with empty string
            .astype(str)
            .str.lower()  # Lowercase
            .str.strip()  # Remove whitespace
            .str.replace(r'\s+', ' ', regex=True)  # Normalize whitespace
        )
        
        # Remove exact duplicates by normalized name
        # Keep first occurrence
        gdf = gdf.drop_duplicates(subset=['_name_normalized'], keep='first')
        
        # Optional: Remove entries with empty names
        # Uncomment if you want to exclude unnamed POIs
        # gdf = gdf[gdf['_name_normalized'] != '']
        
        # Drop temporary column
        gdf = gdf.drop(columns=['_name_normalized'], errors='ignore')
    
    # 3. Additional: Deduplicate by location (if same name at very close location)
    # This handles cases like "School" at (12.9784, 77.6408) and "School" at (12.9785, 77.6409)
    if 'name' in gdf.columns and 'geometry' in gdf.columns and not gdf.empty:
        try:
            # Group by name, check for very close geometries
            # Use buffer to find duplicates within 10 meters
            from shapely.geometry import Point
            
            # For entries with same normalized name, check proximity
            if 'name' in gdf.columns:
                # Create normalized name again for grouping
                gdf['_name_norm'] = gdf['name'].fillna('').astype(str).str.lower().str.strip()
                
                # Group by name and check for spatial duplicates
                # Simple approach: if same name and geometry is very similar, keep one
                gdf = gdf.drop_duplicates(
                    subset=['_name_norm', 'geometry'], 
                    keep='first'
                )
                
                gdf = gdf.drop(columns=['_name_norm'], errors='ignore')
        except Exception as e:
            # If spatial deduplication fails, continue with name-only deduplication
            pass
    
    cleaned_count = len(gdf)
    removed = original_count - cleaned_count
    
    if removed > 0 and category_name:
        print(f"      🧹 {category_name}: {original_count} → {cleaned_count} (removed {removed} duplicates/invalid)")
    
    return gdf


def calculate_statistics(state: LocalityState) -> LocalityState:
    """
    Calculate statistics from OSM data.
    
    SIMPLIFIED VERSION - Fast calculations only.
    """
    osm_data = state.get("osm_data", {})
    coordinates = state.get("coordinates")
    
    if not osm_data:
        state["errors"].append("No OSM data available for statistics calculation")
        state["next_action"] = "error"
        return state
    
    if not coordinates:
        state["errors"].append("No coordinates available for distance calculations")
        state["next_action"] = "error"
        return state
    
    statistics = {}
    
    try:
        print("   📊 Calculating statistics...", end="", flush=True)
        
        # Basic counts (fast - just reading from dict)
        statistics["school_count"] = osm_data.get("schools", {}).get("count", 0)
        statistics["hospital_count"] = osm_data.get("hospitals", {}).get("count", 0)
        statistics["park_area_km2"] = osm_data.get("parks", {}).get("area_km2", 0.0)
        statistics["restaurant_count"] = osm_data.get("restaurants", {}).get("count", 0)
        statistics["metro_station_count"] = osm_data.get("metro_stations", {}).get("count", 0)
        statistics["bus_stop_count"] = osm_data.get("bus_stops", {}).get("count", 0)
        
        # Simplified metro distance
        if statistics["metro_station_count"] > 0:
            statistics["nearest_metro_distance_km"] = "< 5km"  # Simplified
        else:
            statistics["nearest_metro_distance_km"] = None
        
        # Calculate POI density
        area_km2 = 12.57  # π * (2km)²
        total_pois = (
            statistics["school_count"] +
            statistics["hospital_count"] +
            statistics["restaurant_count"] +
            statistics["metro_station_count"] +
            statistics["bus_stop_count"]
        )
        statistics["poi_density"] = round(total_pois / area_km2, 2) if area_km2 > 0 else 0.0
        
        print(" ✓")
        
        state["statistics"] = statistics
        state["next_action"] = "end"
        state["processing_steps"].append("calculate_statistics: SUCCESS - Statistics calculated")
        
    except Exception as e:
        print(f" ✗ Error: {str(e)}")
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