"""
Prompt templates for LLM interactions with advanced prompt engineering.
"""
from typing import Dict, Any, List, Optional


def get_summary_prompt(
    statistics: dict,
    osm_data: dict,
    address: str = None,
    user_intent: dict = None,
    selected_metrics: List[str] = None,
    user_profile: str = None
) -> str:
    """
    Build an optimized, personalized prompt for locality summary generation.
    
    Uses advanced prompt engineering techniques:
    - Role-based prompting (expert analyst)
    - Context-rich formatting
    - Personalized based on user intent
    - Structured output guidance
    - Clear instructions with examples
    
    Args:
        statistics: Calculated statistics/metrics
        osm_data: OSM POI data
        address: Location address
        user_intent: Extracted user intent (profile_type, priorities, concerns, lifestyle)
        selected_metrics: List of selected metric keys
        user_profile: Original user profile string
        
    Returns:
        Optimized prompt string
    """
    # ========================================================================
    # FORMAT CONTEXT DATA
    # ========================================================================
    
    # Format statistics with better structure
    stats_text = format_statistics_structured(statistics, selected_metrics)
    
    # Format OSM data with counts
    osm_text = format_osm_data_structured(osm_data)
    
    # Format user intent
    intent_text = format_user_intent(user_intent) if user_intent else None
    
    # Format selected metrics info
    metrics_info = format_selected_metrics(selected_metrics, user_intent) if selected_metrics else None
    
    # ========================================================================
    # BUILD OPTIMIZED PROMPT
    # ========================================================================
    
    prompt = f"""You are an expert urban planner and locality analyst with 20+ years of experience evaluating neighborhoods for livability, accessibility, and quality of life. Your task is to generate a comprehensive, personalized analysis of a location.

# LOCATION CONTEXT
Location: {address or "Unknown location"}
{'- User Profile: ' + user_profile if user_profile else ''}

{intent_text if intent_text else ''}

{metrics_info if metrics_info else ''}

# DATA ANALYSIS

## Key Statistics (Selected Metrics)
{stats_text}

## Nearby Facilities & Amenities
{osm_text}

# YOUR TASK

Generate a personalized, data-driven summary (2-3 paragraphs, ~200-300 words) that:

1. **Opening Context** (1-2 sentences):
   - Briefly introduce the location
   - Reference the user's profile/priorities if available
   - Set the analytical tone

2. **Core Analysis** (main paragraph):
   - Highlight the MOST RELEVANT metrics based on user priorities
   - Compare values to typical urban standards (e.g., "good connectivity" if metro < 1km, "excellent" if >3 restaurants)
   - Address user concerns if mentioned
   - Use specific numbers from the statistics
   - Mention key amenities from OSM data

3. **Livability Assessment** (1-2 sentences):
   - Overall assessment tailored to user profile
   - Strengths and potential considerations
   - Actionable insight (e.g., "Great for families" or "Ideal for young professionals")

# WRITING GUIDELINES

- **Be specific**: Use exact numbers (e.g., "5 schools within 2km" not "several schools")
- **Be comparative**: Reference what's typical (e.g., "above average connectivity")
- **Be personalized**: Focus on metrics relevant to user's profile and priorities
- **Be balanced**: Mention both strengths and any limitations
- **Be actionable**: Help the user make an informed decision
- **Use natural language**: Avoid jargon, write conversationally
- **Be concise**: Every sentence should add value

# OUTPUT FORMAT

Write ONLY the summary text. No headers, no bullet points, no markdown formatting. Just flowing, well-structured paragraphs.

Begin your analysis:"""

    return prompt


def format_statistics_structured(statistics: dict, selected_metrics: List[str] = None) -> str:
    """
    Format statistics in a structured, readable way.
    Groups by category and highlights selected metrics.
    """
    if not statistics:
        return "No statistics available."
    
    # Categorize metrics
    categories = {
        "Education & Childcare": ["school", "university", "kindergarten", "childcare", "tuition"],
        "Healthcare": ["hospital", "clinic", "pharmacy", "health"],
        "Food & Dining": ["restaurant", "cafe", "fast_food", "food"],
        "Transportation": ["metro", "bus", "road", "accessibility", "walkability"],
        "Recreation": ["park", "gym", "sports", "playground", "green", "leisure"],
        "Shopping & Services": ["shop", "bank", "atm", "shopping"],
        "Other": []
    }
    
    lines = []
    categorized = {cat: [] for cat in categories}
    uncategorized = []
    
    # Categorize all statistics
    for metric, value in statistics.items():
        categorized_flag = False
        for category, keywords in categories.items():
            if category == "Other":
                continue
            if any(keyword in metric.lower() for keyword in keywords):
                categorized[category].append((metric, value))
                categorized_flag = True
                break
        if not categorized_flag:
            uncategorized.append((metric, value))
    
    categorized["Other"] = uncategorized
    
    # Format by category
    for category, items in categorized.items():
        if items:
            lines.append(f"\n### {category}")
            for metric, value in items:
                # Format metric name
                metric_name = metric.replace("_", " ").title()
                
                # Format value
                if value is None:
                    value_str = "Not available"
                elif isinstance(value, (int, float)):
                    if "area" in metric or "density" in metric or "ratio" in metric:
                        value_str = f"{value:.2f}"
                    else:
                        value_str = str(value)
                else:
                    value_str = str(value)
                
                # Highlight if selected
                marker = "⭐" if selected_metrics and metric in selected_metrics else "  "
                lines.append(f"{marker} {metric_name}: {value_str}")
    
    return "\n".join(lines) if lines else "No statistics available."


def format_osm_data_structured(osm_data: dict) -> str:
    """
    Format OSM data in a structured way, showing counts and key info.
    """
    if not osm_data:
        return "No POI data available."
    
    lines = []
    
    # Group by type
    essential = ["schools", "hospitals", "restaurants", "metro_stations", "bus_stops"]
    amenities = ["cafes", "gyms", "parks", "libraries", "pharmacies", "banks"]
    other = []
    
    for category, data in osm_data.items():
        if isinstance(data, dict):
            count = data.get("count", 0)
            if count > 0:
                category_name = category.replace("_", " ").title()
                if category in essential:
                    lines.append(f"• {category_name}: {count} found")
                elif category in amenities:
                    other.append(f"• {category_name}: {count} found")
                else:
                    other.append(f"• {category_name}: {count} found")
    
    if other:
        lines.extend(other)
    
    return "\n".join(lines) if lines else "No POI data available."


def format_user_intent(user_intent: dict) -> str:
    """
    Format user intent for prompt context.
    """
    if not user_intent:
        return ""
    
    lines = ["# USER PROFILE & PRIORITIES"]
    
    profile_type = user_intent.get("profile_type", "general")
    priorities = user_intent.get("priorities", [])
    concerns = user_intent.get("concerns", [])
    lifestyle = user_intent.get("lifestyle", "")
    
    lines.append(f"Profile Type: {profile_type.replace('_', ' ').title()}")
    
    if priorities:
        lines.append(f"Top Priorities: {', '.join([p.title() for p in priorities])}")
    
    if concerns:
        lines.append(f"Main Concerns: {', '.join([c.title() for c in concerns])}")
    
    if lifestyle and lifestyle != "general":
        lines.append(f"Lifestyle: {lifestyle}")
    
    return "\n".join(lines)


def format_selected_metrics(selected_metrics: List[str], user_intent: dict = None) -> str:
    """
    Format information about selected metrics.
    """
    if not selected_metrics:
        return ""
    
    lines = ["# METRIC SELECTION"]
    lines.append(f"Selected {len(selected_metrics)} relevant metrics based on user profile.")
    
    # Get reasoning if available
    reasoning = user_intent.get("metric_selection_reasoning", "") if user_intent else ""
    if reasoning:
        lines.append(f"Reasoning: {reasoning}")
    
    # List selected metrics (brief)
    metric_names = [m.replace("_", " ").title() for m in selected_metrics[:5]]
    if len(selected_metrics) > 5:
        metric_names.append(f"... and {len(selected_metrics) - 5} more")
    lines.append(f"Metrics: {', '.join(metric_names)}")
    
    return "\n".join(lines)


def format_statistics(statistics: dict) -> str:
    """
    Simple format for backward compatibility.
    """
    return "\n".join([f"- {metric}: {value}" for metric, value in statistics.items()])


def format_osm_data(osm_data: dict) -> str:
    """
    Simple format for backward compatibility.
    """
    return "\n".join([f"- {poi}: {data}" for poi, data in osm_data.items()])