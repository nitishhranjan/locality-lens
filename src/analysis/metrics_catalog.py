"""
Metrics catalog for Locality Lens.

Defines all available metrics that can be calculated, along with metadata
for LLM-driven metric selection based on user profile.
"""
from typing import Dict, List, Any

# ============================================================================
# METRICS CATALOG
# ============================================================================

METRICS_CATALOG: Dict[str, Dict[str, Any]] = {
    # ========================================================================
    # ESSENTIAL AMENITIES (10 metrics)
    # ========================================================================
    
    "school_count": {
        "name": "School Count",
        "description": "Number of schools within 2km radius",
        "category": "education",
        "keywords": ["school", "education", "learning", "academic", "teaching"],
        "relevance_for": ["family", "student", "parent", "family_with_kids"],
        "calculation_cost": "low",
        "radius_km": 2.0,
        "priority": "high",
        "osmtag": {"amenity": "school"},
        "unit": "count"
    },
    
    "hospital_count": {
        "name": "Hospital & Clinic Count",
        "description": "Number of hospitals, clinics, and medical facilities within 2km",
        "category": "healthcare",
        "keywords": ["hospital", "clinic", "medical", "health", "doctor", "healthcare"],
        "relevance_for": ["family", "senior_citizen", "all"],
        "calculation_cost": "low",
        "radius_km": 2.0,
        "priority": "high",
        "osmtag": {"amenity": ["hospital", "clinic", "doctors", "dentist"]},
        "unit": "count"
    },
    
    "restaurant_count": {
        "name": "Restaurant Count",
        "description": "Number of restaurants, cafes, and food courts within 1km",
        "category": "food_dining",
        "keywords": ["restaurant", "food", "dining", "cafe", "eating", "cuisine"],
        "relevance_for": ["bachelor", "young_professional", "all"],
        "calculation_cost": "low",
        "radius_km": 1.0,
        "priority": "high",
        "osmtag": {"amenity": ["restaurant", "cafe", "fast_food", "food_court"]},
        "unit": "count"
    },
    
    "park_area_km2": {
        "name": "Park Area",
        "description": "Total area of parks and gardens in square kilometers within 2km",
        "category": "green_space",
        "keywords": ["park", "garden", "green", "nature", "outdoor", "recreation"],
        "relevance_for": ["family", "senior_citizen", "all"],
        "calculation_cost": "low",
        "radius_km": 2.0,
        "priority": "high",
        "osmtag": {"leisure": ["park", "garden", "recreation_ground"]},
        "unit": "km²"
    },
    
    "shopping_count": {
        "name": "Shopping Count",
        "description": "Number of shops, markets, and retail stores within 1km",
        "category": "shopping",
        "keywords": ["shop", "shopping", "market", "retail", "store", "mall"],
        "relevance_for": ["family", "all"],
        "calculation_cost": "low",
        "radius_km": 1.0,
        "priority": "medium",
        "osmtag": {"shop": True},
        "unit": "count"
    },
    
    "bank_atm_count": {
        "name": "Bank & ATM Count",
        "description": "Number of banks and ATMs within 1km",
        "category": "financial",
        "keywords": ["bank", "atm", "financial", "money", "cash"],
        "relevance_for": ["working_professional", "all"],
        "calculation_cost": "low",
        "radius_km": 1.0,
        "priority": "medium",
        "osmtag": {"amenity": ["bank", "atm"]},
        "unit": "count"
    },
    
    "pharmacy_count": {
        "name": "Pharmacy Count",
        "description": "Number of pharmacies and drug stores within 1km",
        "category": "healthcare",
        "keywords": ["pharmacy", "drug", "medicine", "medical"],
        "relevance_for": ["family", "senior_citizen", "all"],
        "calculation_cost": "low",
        "radius_km": 1.0,
        "priority": "medium",
        "osmtag": {"amenity": "pharmacy"},
        "unit": "count"
    },
    
    "gym_fitness_count": {
        "name": "Gym & Fitness Count",
        "description": "Number of gyms and fitness centers within 1km",
        "category": "lifestyle",
        "keywords": ["gym", "fitness", "exercise", "workout", "health"],
        "relevance_for": ["bachelor", "young_professional", "working_professional"],
        "calculation_cost": "low",
        "radius_km": 1.0,
        "priority": "medium",
        "osmtag": {"leisure": ["fitness_centre", "gym"]},
        "unit": "count"
    },
    
    "library_count": {
        "name": "Library Count",
        "description": "Number of libraries within 2km",
        "category": "education",
        "keywords": ["library", "books", "reading", "study"],
        "relevance_for": ["student", "family"],
        "calculation_cost": "low",
        "radius_km": 2.0,
        "priority": "low",
        "osmtag": {"amenity": "library"},
        "unit": "count"
    },
    
    "place_of_worship_count": {
        "name": "Places of Worship",
        "description": "Number of temples, mosques, churches within 2km",
        "category": "cultural",
        "keywords": ["temple", "mosque", "church", "worship", "religious"],
        "relevance_for": ["family", "senior_citizen"],
        "calculation_cost": "low",
        "radius_km": 2.0,
        "priority": "low",
        "osmtag": {"amenity": "place_of_worship"},
        "unit": "count"
    },
    
    # ========================================================================
    # TRANSPORTATION & CONNECTIVITY (6 metrics)
    # ========================================================================
    
    "metro_station_count": {
        "name": "Metro Station Count",
        "description": "Number of metro/subway stations within 2km",
        "category": "transportation",
        "keywords": ["metro", "subway", "train", "transit", "public_transport"],
        "relevance_for": ["working_professional", "bachelor", "all"],
        "calculation_cost": "low",
        "radius_km": 2.0,
        "priority": "high",
        "osmtag": {"railway": "station", "station": ["subway", "metro"]},
        "unit": "count"
    },
    
    "bus_stop_count": {
        "name": "Bus Stop Count",
        "description": "Number of bus stops within 500m",
        "category": "transportation",
        "keywords": ["bus", "public_transport", "transit", "commute"],
        "relevance_for": ["student", "working_professional", "all"],
        "calculation_cost": "low",
        "radius_km": 0.5,
        "priority": "high",
        "osmtag": {"highway": "bus_stop"},
        "unit": "count"
    },
    
    "nearest_metro_distance_km": {
        "name": "Nearest Metro Distance",
        "description": "Distance to nearest metro station in kilometers",
        "category": "transportation",
        "keywords": ["metro", "distance", "accessibility", "commute"],
        "relevance_for": ["working_professional", "bachelor"],
        "calculation_cost": "medium",
        "radius_km": 5.0,
        "priority": "high",
        "osmtag": {"railway": "station", "station": ["subway", "metro"]},
        "unit": "km"
    },
    
    "road_density_km_per_km2": {
        "name": "Road Density",
        "description": "Total road length per square kilometer",
        "category": "connectivity",
        "keywords": ["road", "connectivity", "infrastructure", "traffic"],
        "relevance_for": ["working_professional", "all"],
        "calculation_cost": "high",
        "radius_km": 2.0,
        "priority": "medium",
        "osmtag": {"highway": True},
        "unit": "km/km²"
    },
    
    "main_road_count": {
        "name": "Main Road Count",
        "description": "Number of primary and secondary roads",
        "category": "connectivity",
        "keywords": ["road", "highway", "main_road", "connectivity"],
        "relevance_for": ["working_professional", "all"],
        "calculation_cost": "medium",
        "radius_km": 2.0,
        "priority": "low",
        "osmtag": {"highway": ["primary", "secondary"]},
        "unit": "count"
    },
    
    "walkability_score": {
        "name": "Walkability Score",
        "description": "Composite score (0-100) based on POI density, connectivity, and pedestrian infrastructure",
        "category": "composite",
        "keywords": ["walkability", "pedestrian", "walking", "accessibility"],
        "relevance_for": ["bachelor", "young_professional", "senior_citizen"],
        "calculation_cost": "high",
        "radius_km": 1.0,
        "priority": "medium",
        "dependencies": ["poi_density", "road_density_km_per_km2"],
        "unit": "score"
    },
    
    # ========================================================================
    # LIFESTYLE & ENTERTAINMENT (8 metrics)
    # ========================================================================
    
    "nightlife_count": {
        "name": "Nightlife Count",
        "description": "Number of bars, pubs, and nightclubs within 1km",
        "category": "entertainment",
        "keywords": ["bar", "pub", "nightclub", "nightlife", "entertainment"],
        "relevance_for": ["bachelor", "young_professional"],
        "calculation_cost": "low",
        "radius_km": 1.0,
        "priority": "medium",
        "osmtag": {"amenity": ["bar", "pub", "nightclub"]},
        "unit": "count"
    },
    
    "cafe_count": {
        "name": "Cafe Count",
        "description": "Number of cafes (separate from restaurants) within 1km",
        "category": "food_dining",
        "keywords": ["cafe", "coffee", "coffee_shop", "cafe"],
        "relevance_for": ["bachelor", "young_professional", "student"],
        "calculation_cost": "low",
        "radius_km": 1.0,
        "priority": "low",
        "osmtag": {"amenity": "cafe"},
        "unit": "count"
    },
    
    "fast_food_count": {
        "name": "Fast Food Count",
        "description": "Number of fast food joints within 1km",
        "category": "food_dining",
        "keywords": ["fast_food", "quick_food", "convenience"],
        "relevance_for": ["bachelor", "student"],
        "calculation_cost": "low",
        "radius_km": 1.0,
        "priority": "low",
        "osmtag": {"amenity": "fast_food"},
        "unit": "count"
    },
    
    "cinema_count": {
        "name": "Cinema Count",
        "description": "Number of movie theaters and cinemas within 2km",
        "category": "entertainment",
        "keywords": ["cinema", "movie", "theater", "entertainment"],
        "relevance_for": ["bachelor", "young_professional", "family"],
        "calculation_cost": "low",
        "radius_km": 2.0,
        "priority": "low",
        "osmtag": {"amenity": "cinema"},
        "unit": "count"
    },
    
    "playground_count": {
        "name": "Playground Count",
        "description": "Number of playgrounds within 1km",
        "category": "recreation",
        "keywords": ["playground", "kids", "children", "play"],
        "relevance_for": ["family", "family_with_kids"],
        "calculation_cost": "low",
        "radius_km": 1.0,
        "priority": "medium",
        "osmtag": {"leisure": "playground"},
        "unit": "count"
    },
    
    "sports_facility_count": {
        "name": "Sports Facility Count",
        "description": "Number of sports centers and facilities within 2km",
        "category": "recreation",
        "keywords": ["sports", "sports_centre", "recreation", "fitness"],
        "relevance_for": ["bachelor", "young_professional", "family"],
        "calculation_cost": "low",
        "radius_km": 2.0,
        "priority": "low",
        "osmtag": {"leisure": "sports_centre"},
        "unit": "count"
    },
    
    "hotel_count": {
        "name": "Hotel Count",
        "description": "Number of hotels within 2km",
        "category": "tourism",
        "keywords": ["hotel", "accommodation", "tourism"],
        "relevance_for": ["all"],
        "calculation_cost": "low",
        "radius_km": 2.0,
        "priority": "low",
        "osmtag": {"tourism": "hotel"},
        "unit": "count"
    },
    
    "community_centre_count": {
        "name": "Community Centre Count",
        "description": "Number of community centers within 2km",
        "category": "social",
        "keywords": ["community", "social", "gathering"],
        "relevance_for": ["family", "senior_citizen"],
        "calculation_cost": "low",
        "radius_km": 2.0,
        "priority": "low",
        "osmtag": {"amenity": "community_centre"},
        "unit": "count"
    },
    
    # ========================================================================
    # EDUCATION & CHILDCARE (4 metrics)
    # ========================================================================
    
    "university_count": {
        "name": "University Count",
        "description": "Number of universities and colleges within 2km",
        "category": "education",
        "keywords": ["university", "college", "higher_education"],
        "relevance_for": ["student"],
        "calculation_cost": "low",
        "radius_km": 2.0,
        "priority": "high",
        "osmtag": {"amenity": ["university", "college"]},
        "unit": "count"
    },
    
    "kindergarten_count": {
        "name": "Kindergarten Count",
        "description": "Number of kindergartens within 2km",
        "category": "education",
        "keywords": ["kindergarten", "preschool", "early_education"],
        "relevance_for": ["family", "family_with_kids"],
        "calculation_cost": "low",
        "radius_km": 2.0,
        "priority": "medium",
        "osmtag": {"amenity": "kindergarten"},
        "unit": "count"
    },
    
    "childcare_count": {
        "name": "Childcare Count",
        "description": "Number of daycare centers within 2km",
        "category": "childcare",
        "keywords": ["childcare", "daycare", "babysitting"],
        "relevance_for": ["family", "family_with_kids"],
        "calculation_cost": "low",
        "radius_km": 2.0,
        "priority": "medium",
        "osmtag": {"amenity": "childcare"},
        "unit": "count"
    },
    
    "tuition_centre_count": {
        "name": "Tuition Centre Count",
        "description": "Number of coaching and tuition centers within 2km",
        "category": "education",
        "keywords": ["tuition", "coaching", "tutoring"],
        "relevance_for": ["family", "student"],
        "calculation_cost": "low",
        "radius_km": 2.0,
        "priority": "low",
        "osmtag": {"amenity": "tuition"},
        "unit": "count"
    },
    
    # ========================================================================
    # COMPOSITE & ADVANCED METRICS (5 metrics)
    # ========================================================================
    
    "poi_density": {
        "name": "POI Density",
        "description": "Total Points of Interest per square kilometer",
        "category": "composite",
        "keywords": ["density", "poi", "amenities", "vibrancy"],
        "relevance_for": ["all"],
        "calculation_cost": "low",
        "radius_km": 2.0,
        "priority": "high",
        "dependencies": [],
        "unit": "per km²"
    },
    
    "green_space_ratio": {
        "name": "Green Space Ratio",
        "description": "Ratio of park area to total area (0-1)",
        "category": "composite",
        "keywords": ["green", "park", "ratio", "environment"],
        "relevance_for": ["family", "senior_citizen", "all"],
        "calculation_cost": "low",
        "dependencies": ["park_area_km2"],
        "radius_km": 2.0,
        "priority": "medium",
        "unit": "ratio"
    },
    
    "amenity_diversity_score": {
        "name": "Amenity Diversity Score",
        "description": "Shannon diversity index of different amenity types (0-100)",
        "category": "composite",
        "keywords": ["diversity", "variety", "amenities"],
        "relevance_for": ["all"],
        "calculation_cost": "medium",
        "radius_km": 2.0,
        "priority": "low",
        "unit": "score"
    },
    
    "accessibility_score": {
        "name": "Accessibility Score",
        "description": "Composite score based on transportation, walkability, and POI density (0-100)",
        "category": "composite",
        "keywords": ["accessibility", "mobility", "connectivity"],
        "relevance_for": ["senior_citizen", "all"],
        "calculation_cost": "high",
        "dependencies": ["metro_station_count", "bus_stop_count", "poi_density"],
        "radius_km": 2.0,
        "priority": "medium",
        "unit": "score"
    },
    
    "residential_density": {
        "name": "Residential Density",
        "description": "Estimated residential building density",
        "category": "demographics",
        "keywords": ["residential", "housing", "population"],
        "relevance_for": ["all"],
        "calculation_cost": "medium",
        "radius_km": 2.0,
        "priority": "low",
        "osmtag": {"building": "residential"},
        "unit": "per km²"
    }
}

# ============================================================================
# PROFILE-BASED DEFAULT METRICS
# ============================================================================

PROFILE_DEFAULT_METRICS: Dict[str, List[str]] = {
    "Bachelor/Young Professional": [
        "restaurant_count",
        "nightlife_count",
        "metro_station_count",
        "gym_fitness_count",
        "cafe_count",
        "poi_density",
        "walkability_score"
    ],
    
    "Family with Kids": [
        "school_count",
        "park_area_km2",
        "hospital_count",
        "playground_count",
        "kindergarten_count",
        "childcare_count",
        "safety_rating",
        "green_space_ratio"
    ],
    
    "Student": [
        "university_count",
        "library_count",
        "cafe_count",
        "fast_food_count",
        "bus_stop_count",
        "metro_station_count",
        "poi_density"
    ],
    
    "Senior Citizen": [
        "hospital_count",
        "pharmacy_count",
        "park_area_km2",
        "place_of_worship_count",
        "accessibility_score",
        "bus_stop_count",
        "community_centre_count"
    ],
    
    "Working Professional": [
        "metro_station_count",
        "bus_stop_count",
        "restaurant_count",
        "bank_atm_count",
        "gym_fitness_count",
        "poi_density",
        "road_density_km_per_km2"
    ],
    
    "Custom": [
        "school_count",
        "hospital_count",
        "restaurant_count",
        "park_area_km2",
        "metro_station_count",
        "bus_stop_count",
        "poi_density"
    ]
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_all_metrics() -> List[str]:
    """Get list of all available metric keys."""
    return list(METRICS_CATALOG.keys())


def get_metrics_by_category(category: str) -> List[str]:
    """Get metrics filtered by category."""
    return [
        key for key, value in METRICS_CATALOG.items()
        if value.get("category") == category
    ]


def get_metrics_by_cost(cost: str) -> List[str]:
    """Get metrics filtered by calculation cost (low, medium, high)."""
    return [
        key for key, value in METRICS_CATALOG.items()
        if value.get("calculation_cost") == cost
    ]


def get_default_metrics_for_profile(profile: str) -> List[str]:
    """
    Get default metrics for a given profile.
    
    Args:
        profile: User profile type
        
    Returns:
        List of metric keys
    """
    # Normalize profile name
    profile_normalized = profile.strip()
    
    # Direct match
    if profile_normalized in PROFILE_DEFAULT_METRICS:
        return PROFILE_DEFAULT_METRICS[profile_normalized]
    
    # Fuzzy matching for variations
    profile_lower = profile_normalized.lower()
    for key, metrics in PROFILE_DEFAULT_METRICS.items():
        if profile_lower in key.lower() or key.lower() in profile_lower:
            return metrics
    
    # Default fallback
    return PROFILE_DEFAULT_METRICS["Custom"]


def get_metric_info(metric_key: str) -> Dict[str, Any]:
    """
    Get detailed information about a metric.
    
    Args:
        metric_key: Key of the metric
        
    Returns:
        Dictionary with metric information
    """
    return METRICS_CATALOG.get(metric_key, {})


def validate_metrics(metric_keys: List[str]) -> tuple[List[str], List[str]]:
    """
    Validate metric keys and return valid and invalid ones.
    
    Args:
        metric_keys: List of metric keys to validate
        
    Returns:
        Tuple of (valid_metrics, invalid_metrics)
    """
    valid = []
    invalid = []
    
    for key in metric_keys:
        if key in METRICS_CATALOG:
            valid.append(key)
        else:
            invalid.append(key)
    
    return valid, invalid


def get_metrics_for_llm_selection() -> str:
    """
    Format metrics catalog for LLM prompt - MINIMAL VERSION.
    
    Only includes essential information for metric selection.
    Excludes implementation details to prevent hallucination.
    
    Returns:
        Compact string format
    """
    lines = []
    for key, info in METRICS_CATALOG.items():
        name = info.get("name", key)
        description = info.get("description", "")
        # Top 3 keywords only - most relevant for matching
        # keywords = ", ".join(info.get("keywords", [])[:3])
        
        lines.append(
            f"{key}: {name} - {description}"
        )
    return "\n".join(lines)


# ============================================================================
# METRIC DEPENDENCIES
# ============================================================================

METRIC_DEPENDENCIES: Dict[str, List[str]] = {
    "walkability_score": ["poi_density", "road_density_km_per_km2"],
    "green_space_ratio": ["park_area_km2"],
    "accessibility_score": ["metro_station_count", "bus_stop_count", "poi_density"],
    "amenity_diversity_score": []  # Calculated from all POI data
}

def get_required_dependencies(metric_keys: List[str]) -> List[str]:
    """
    Get all dependencies required for given metrics.
    
    Args:
        metric_keys: List of metric keys
        
    Returns:
        List of all required dependency metric keys
    """
    dependencies = set()
    
    for key in metric_keys:
        if key in METRIC_DEPENDENCIES:
            dependencies.update(METRIC_DEPENDENCIES[key])
    
    # Remove metrics that are already in the list
    return [dep for dep in dependencies if dep not in metric_keys]