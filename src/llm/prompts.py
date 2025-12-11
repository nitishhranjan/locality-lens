"""
Prompt templates for LLM interactions
"""

def get_summary_prompt(statistics: dict, osm_data: dict, address: str = None)-> str:
    """
    Build prompt for locality summary generation.
    """
    # Format statistics
    stats_text = format_statistics(statistics)
    
    # Format OSM data
    osm_text = format_osm_data(osm_data)
    
    # Build prompt
    prompt = f"""You are an expert locality analyst. Generate a concise, informative summary of this location.

Location: {address or "Unknown"}

Statistics:
{stats_text}

POI Data:
{osm_text}

Generate a 2-3 paragraph summary highlighting:
1. Key amenities and facilities
2. Connectivity and transportation
3. Overall livability assessment

Be specific, data-driven, and helpful for someone considering this location.
"""
    return prompt

def format_statistics(statistics: dict)-> str:
    """
    Format statistics for prompt.
    """
    return "\n".join([f"- {metric}: {value}" for metric, value in statistics.items()])

def format_osm_data(osm_data: dict)-> str:
    """
    Format OSM data for prompt.
    """
    return "\n".join([f"- {poi}: {data}" for poi, data in osm_data.items()])