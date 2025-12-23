"""
OSM data fetching and processing utilities.
"""
import os
import ssl
import warnings
import numpy as np
import geopandas as gpd
import pandas as pd
from scipy.spatial import cKDTree
import osmnx as ox

# SSL Configuration (for corporate proxies)
ssl._create_default_https_context = ssl._create_unverified_context
os.environ['PYTHONHTTPSVERIFY'] = '0'
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

warnings.filterwarnings('ignore')
ox.settings.log_console = False
ox.settings.use_cache = True
ox.settings.timeout = 300


def determine_poi_type(row):
    """
    Determine POI type from OSM tags.
    
    Returns just the value (e.g., "restaurant", "park", "school").
    Uses priority order: amenity > leisure > shop > highway > railway > tourism
    
    Args:
        row: DataFrame row with OSM tags
        
    Returns:
        POI type value or np.nan
    """
    tag_priority = ["amenity", "leisure", "shop", "highway", "railway", "tourism"]
    
    for tag_key in tag_priority:
        value = row.get(tag_key)
        if pd.notna(value) and value != '':
            return value  # Return just the value, not "tag_key_value"
    
    return np.nan


def deduplicate_pois(gdf, distance_m=200):
    """
    Fast deduplication: same name + poi_type within distance_m.
    
    Uses spatial indexing (KDTree) for O(n log n) performance.
    KEEPS FIRST occurrence, drops subsequent duplicates.
    
    Args:
        gdf: GeoDataFrame with 'name' and 'poi_type' columns
        distance_m: Maximum distance in meters for duplicates
        
    Returns:
        Cleaned GeoDataFrame with duplicates removed
    """
    if gdf.empty:
        return gdf
    
    # Validate geometries first
    gdf = gdf[
        gdf.geometry.notna() & 
        gdf.geometry.is_valid &
        ~gdf.geometry.is_empty
    ].copy().reset_index(drop=True)
    
    # Create poi_type if not exists
    if 'poi_type' not in gdf.columns:
        gdf['poi_type'] = gdf.apply(determine_poi_type, axis=1)
    
    # Drop features with missing name (as per notebook approach)
    # Keep only features with names for deduplication
    gdf = gdf.dropna(subset=['name']).reset_index(drop=True)
    
    if gdf.empty:
        return gdf
    
    # Create deduplication key: name + poi_type
    gdf['name_poi_key'] = (
        gdf['name'].astype(str) + '_' + 
        gdf['poi_type'].astype(str)
    )
    
    # Get centroid coordinates for distance calculation
    centroids = gdf.geometry.centroid
    gdf['centroid_x'] = centroids.x
    gdf['centroid_y'] = centroids.y
    
    to_drop = set()
    
    # Group by name_poi_key - only check duplicates within same group
    for name_poi, group in gdf.groupby('name_poi_key'):
        if len(group) == 1:
            continue  # No duplicates possible
        
        # Extract coordinates for this group
        coords = np.column_stack([group['centroid_x'].values, group['centroid_y'].values])
        
        # Scale to meters for accurate distance calculation
        # This accounts for latitude (longitude degrees vary by latitude)
        avg_lat = coords[:, 1].mean()  # y is latitude
        lat_scale = 111000  # meters per degree latitude
        lon_scale = 111000 * np.cos(np.radians(avg_lat))  # meters per degree longitude
        
        coords_scaled = coords.copy()
        coords_scaled[:, 0] *= lon_scale  # x is longitude
        coords_scaled[:, 1] *= lat_scale  # y is latitude
        
        # Build spatial index
        tree = cKDTree(coords_scaled)
        
        # Find all pairs within distance_m (in meters)
        pairs = tree.query_pairs(distance_m, output_type='ndarray')
        
        if len(pairs) > 0:
            # IMPORTANT: pairs[:, 0] = first occurrence (KEEP)
            #            pairs[:, 1] = subsequent occurrence (DROP)
            # This ensures we keep one value per duplicate group
            indices_to_drop = group.iloc[pairs[:, 1]].index.tolist()
            to_drop.update(indices_to_drop)
    
    # Drop duplicates and clean up helper columns
    result = gdf.drop(index=list(to_drop)).drop(
        columns=['name_poi_key', 'centroid_x', 'centroid_y']
    ).reset_index(drop=True)
    
    return result


def fetch_osm_features(location_point, radius_m=2000):
    """
    Fetch OSM features with comprehensive tags.
    
    Args:
        location_point: (lat, lon) tuple
        radius_m: Search radius in meters
        
    Returns:
        GeoDataFrame with all features and 'poi_type' column
    """
    tags = {
        # Fetch all amenities (catch regional variations)
        'amenity': True,
        
        # Fetch all leisure (catch variations)
        'leisure': True,
        
        # Fetch all shops
        'shop': True,
        
        # Fetch specific transportation (standardized)
        'highway': ['bus_stop'],
        'railway': ['station', 'subway', 'subway_entrance', 'platform', 'light_rail', 'tram'],
        
        # Fetch specific tourism
        'tourism': ['hotel', 'hostel', 'guest_house', 'artwork', 'attraction'],
    }
    
    all_features = ox.features_from_point(
        center_point=location_point,
        dist=radius_m,
        tags=tags
    )
    
    # Create poi_type column
    all_features['poi_type'] = all_features.apply(determine_poi_type, axis=1)
    
    return all_features