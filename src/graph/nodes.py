"""
Graph nodes for Locality Lens workflow.
Each node is a function that takes state, performs work, and returns updated state.
"""
from typing import Dict, Any
import osmnx as ox
import geopandas as gpd
from shapely.geometry import Point
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

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
                    state["next_action"] = "skip_geocode"
                    state["processing_steps"].append(f"validate_input: SUCCESS - Parsed coordinates ({lat}, {lon})")
                    return state
        except ValueError:
            # Not coordinates, treat as address
            pass
    
    # Input is an address, needs geocoding
    state["next_action"] = "geocode"
    state["processing_steps"].append("validate_input: SUCCESS - Address detected, needs geocoding")
    return state


def geocode_location(state: LocalityState) -> LocalityState:
    """
    Geocode address to coordinates using Nominatim (OpenStreetMap).
    
    Converts address string to (latitude, longitude) coordinates.
    Uses direct API calls to handle SSL certificate issues.
    """
    # Skip if coordinates already exist
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
                state["next_action"] = "fetch_osm"
                state["processing_steps"].append(f"geocode_location: SUCCESS - Geocoded to ({lat}, {lon})")
            else:
                state["errors"].append(f"Could not geocode location: {user_input}")
                state["next_action"] = "error"
                state["processing_steps"].append(f"geocode_location: FAILED - No results for '{user_input}'")
        else:
            state["errors"].append(f"Geocoding API returned status {response.status_code}")
            state["next_action"] = "error"
            state["processing_steps"].append(f"geocode_location: ERROR - API status {response.status_code}")
    
    except requests.exceptions.SSLError as e:
        # If SSL still fails, try with urllib3
        try:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
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
                    state["next_action"] = "fetch_osm"
                    state["processing_steps"].append(f"geocode_location: SUCCESS - Geocoded to ({lat}, {lon}) via urllib3")
                else:
                    state["errors"].append(f"Could not geocode location: {user_input}")
                    state["next_action"] = "error"
            else:
                state["errors"].append(f"Geocoding failed with status {response.status}")
                state["next_action"] = "error"
        except Exception as urllib_error:
            state["errors"].append(f"Geocoding failed: {str(urllib_error)}")
            state["next_action"] = "error"
            state["processing_steps"].append(f"geocode_location: ERROR - {str(urllib_error)}")
    
    except Exception as e:
        state["errors"].append(f"Unexpected error during geocoding: {str(e)}")
        state["next_action"] = "error"
        state["processing_steps"].append(f"geocode_location: ERROR - {str(e)}")
    
    return state


def fetch_osm_data(state: LocalityState) -> LocalityState:
    """
    Fetch OpenStreetMap POI data around the location.
    
    Fetches schools, hospitals, parks, restaurants, metro stations, and bus stops.
    """
    coordinates = state.get("coordinates")
    
    if not coordinates:
        state["errors"].append("No coordinates available for OSM data fetching")
        state["next_action"] = "error"
        return state
    
    lat, lon = coordinates
    location_point = (lat, lon)
    radius = 2000  # 2km radius
    
    osm_data = {}
    
    try:
        # Fetch schools (within 2km)
        try:
            schools = ox.features_from_point(
                location_point,
                tags={'amenity': 'school'},
                dist=radius
            )
            osm_data["schools"] = {
                "count": len(schools),
                "data": schools.to_dict('records') if not schools.empty else []
            }
        except Exception as e:
            state["warnings"].append(f"Could not fetch schools: {str(e)}")
            osm_data["schools"] = {"count": 0, "data": []}
        
        # Fetch hospitals and clinics (within 2km)
        try:
            hospitals = ox.features_from_point(
                location_point,
                tags={'amenity': ['hospital', 'clinic']},
                dist=radius
            )
            osm_data["hospitals"] = {
                "count": len(hospitals),
                "data": hospitals.to_dict('records') if not hospitals.empty else []
            }
        except Exception as e:
            state["warnings"].append(f"Could not fetch hospitals: {str(e)}")
            osm_data["hospitals"] = {"count": 0, "data": []}
        
        # Fetch parks (within 2km)
        try:
            parks = ox.features_from_point(
                location_point,
                tags={'leisure': ['park', 'garden']},
                dist=radius
            )
            # Calculate total park area
            if not parks.empty and 'geometry' in parks.columns:
                parks_gdf = gpd.GeoDataFrame(parks, geometry='geometry')
                parks_gdf.set_crs(epsg=4326, inplace=True)
                parks_gdf.to_crs(epsg=3857, inplace=True)  # Convert to metric projection
                total_area_km2 = parks_gdf.geometry.area.sum() / 1_000_000  # Convert to km²
            else:
                total_area_km2 = 0.0
            
            osm_data["parks"] = {
                "count": len(parks),
                "area_km2": round(total_area_km2, 2),
                "data": parks.to_dict('records') if not parks.empty else []
            }
        except Exception as e:
            state["warnings"].append(f"Could not fetch parks: {str(e)}")
            osm_data["parks"] = {"count": 0, "area_km2": 0.0, "data": []}
        
        # Fetch restaurants (within 1km)
        try:
            restaurants = ox.features_from_point(
                location_point,
                tags={'amenity': ['restaurant', 'cafe', 'fast_food']},
                dist=1000  # 1km
            )
            osm_data["restaurants"] = {
                "count": len(restaurants),
                "data": restaurants.to_dict('records') if not restaurants.empty else []
            }
        except Exception as e:
            state["warnings"].append(f"Could not fetch restaurants: {str(e)}")
            osm_data["restaurants"] = {"count": 0, "data": []}
        
        # Fetch metro stations (within 5km - search wider)
        try:
            metro_stations = ox.features_from_point(
                location_point,
                tags={'railway': 'station', 'station': ['subway', 'metro']},
                dist=5000
            )
            osm_data["metro_stations"] = {
                "count": len(metro_stations),
                "data": metro_stations.to_dict('records') if not metro_stations.empty else []
            }
        except Exception as e:
            state["warnings"].append(f"Could not fetch metro stations: {str(e)}")
            osm_data["metro_stations"] = {"count": 0, "data": []}
        
        # Fetch bus stops (within 500m)
        try:
            bus_stops = ox.features_from_point(
                location_point,
                tags={'highway': 'bus_stop'},
                dist=500
            )
            osm_data["bus_stops"] = {
                "count": len(bus_stops),
                "data": bus_stops.to_dict('records') if not bus_stops.empty else []
            }
        except Exception as e:
            state["warnings"].append(f"Could not fetch bus stops: {str(e)}")
            osm_data["bus_stops"] = {"count": 0, "data": []}
        
        state["osm_data"] = osm_data
        state["next_action"] = "calculate_statistics"
        state["processing_steps"].append(f"fetch_osm_data: SUCCESS - Fetched {len(osm_data)} POI categories")
        
    except Exception as e:
        state["errors"].append(f"Error fetching OSM data: {str(e)}")
        state["next_action"] = "error"
        state["processing_steps"].append(f"fetch_osm_data: ERROR - {str(e)}")
    
    return state


def calculate_statistics(state: LocalityState) -> LocalityState:
    """
    Calculate statistics from OSM data.
    
    Computes metrics like counts, distances, and densities.
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
    
    lat, lon = coordinates
    location_point = Point(lon, lat)  # Note: Shapely uses (lon, lat)
    
    statistics = {}
    
    try:
        # Basic counts
        statistics["school_count"] = osm_data.get("schools", {}).get("count", 0)
        statistics["hospital_count"] = osm_data.get("hospitals", {}).get("count", 0)
        statistics["park_area_km2"] = osm_data.get("parks", {}).get("area_km2", 0.0)
        statistics["restaurant_count"] = osm_data.get("restaurants", {}).get("count", 0)
        statistics["metro_station_count"] = osm_data.get("metro_stations", {}).get("count", 0)
        statistics["bus_stop_count"] = osm_data.get("bus_stops", {}).get("count", 0)
        
        # Calculate nearest metro distance
        metro_data = osm_data.get("metro_stations", {}).get("data", [])
        if metro_data:
            try:
                # Convert metro stations to GeoDataFrame
                metro_gdf = gpd.GeoDataFrame(metro_data)
                if 'geometry' in metro_gdf.columns:
                    metro_gdf.set_crs(epsg=4326, inplace=True)
                    metro_gdf.to_crs(epsg=3857, inplace=True)
                    location_point_3857 = gpd.GeoSeries([location_point], crs=4326).to_crs(epsg=3857)[0]
                    
                    distances = metro_gdf.geometry.distance(location_point_3857)
                    nearest_distance_m = distances.min()
                    nearest_distance_km = round(nearest_distance_m / 1000, 2)
                    statistics["nearest_metro_distance_km"] = nearest_distance_km
                else:
                    statistics["nearest_metro_distance_km"] = None
            except Exception as e:
                state["warnings"].append(f"Could not calculate metro distance: {str(e)}")
                statistics["nearest_metro_distance_km"] = None
        else:
            statistics["nearest_metro_distance_km"] = None
        
        # Calculate POI density (POIs per km²)
        # Use 2km radius area = π * (2km)² ≈ 12.57 km²
        area_km2 = 12.57
        total_pois = (
            statistics["school_count"] +
            statistics["hospital_count"] +
            statistics["restaurant_count"] +
            statistics["metro_station_count"] +
            statistics["bus_stop_count"]
        )
        statistics["poi_density"] = round(total_pois / area_km2, 2) if area_km2 > 0 else 0.0
        
        state["statistics"] = statistics
        state["next_action"] = "end"
        state["processing_steps"].append("calculate_statistics: SUCCESS - Statistics calculated")
        
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