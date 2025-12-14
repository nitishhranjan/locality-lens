"""
LLM-based intent extraction
"""
import json
import re
from typing import Dict, Any
from langchain_groq import ChatGroq
from config.config import GROQ_API_KEY
from src.analysis.metrics_catalog import (
    get_metrics_for_llm_selection,
    validate_metrics,
    get_default_metrics_for_profile
)

def get_llm():
    """Get LLM instance."""
    return ChatGroq(
        api_key=GROQ_API_KEY,
        model_name="llama-3.1-8b-instant",
        temperature=0.6,
        max_tokens=1024
    )

def extract_intent_and_select_metrics(user_profile: str, user_input: str = "") -> Dict[str, Any]:
    """
    Extract user intent AND select relevant metrics in ONE LLM call.
    
    This is more efficient than two separate calls and allows the LLM
    to consider both tasks together for better coherence.
    
    Args:
        user_profile: User profile (categorical or free text)
        user_input: Additional context
        
    Returns:
        Dictionary with:
        - user_intent: {profile_type, priorities, concerns, lifestyle}
        - selected_metrics: List of metric keys
        - reasoning: Why these metrics were selected
    """
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not configured")
    
    # Get metrics catalog (simplified format)
    metrics_catalog = get_metrics_for_llm_selection()
    
    # Build comprehensive prompt
    prompt = f"""You are a location analysis expert. Analyze the user profile and:
    1. Extract their intent (profile type, priorities, concerns, lifestyle)
    2. Select 5-8 most relevant metrics from the catalog

    USER PROFILE: {user_profile}
    ADDITIONAL CONTEXT: {user_input if user_input else "None"}

    AVAILABLE METRICS (select 5-8 most relevant):
    {metrics_catalog}

    TASK:
    Based on the user profile, extract their intent and select the most relevant metrics.

    IMPORTANT:
    - Return ONLY valid JSON, no markdown, no explanations
    - Select exactly 5-8 metrics (not more, not less)
    - Use metric keys EXACTLY as shown (e.g., "school_count", not "schools")

    REQUIRED JSON FORMAT:
    {{
        "user_intent": {{
            "profile_type": "bachelor",
            "priorities": ["restaurants", "nightlife", "connectivity"],
            "concerns": ["safety", "noise"],
            "lifestyle": "Active, social, urban lifestyle"
        }},
        "selected_metrics": ["restaurant_count", "nightlife_count", "metro_station_count", "gym_fitness_count", "cafe_count", "poi_density", "walkability_score"],
        "reasoning": "Selected metrics based on user priorities for restaurants, nightlife, and connectivity"
    }}

    Return valid JSON only:
    """
    try:
        llm = get_llm()
        response = llm.invoke(prompt)
        
        # Robust JSON parsing
        content = response.content.strip()

        # Remove markdown code blocks
        content = re.sub(r'^```json\s*', '', content, flags=re.MULTILINE)
        content = re.sub(r'^```\s*', '', content, flags=re.MULTILINE)
        content = re.sub(r'```\s*$', '', content, flags=re.MULTILINE)
        content = content.strip()

        # Extract JSON if wrapped in text
        json_match = re.search(r'\{[^{}]*"user_intent"[^{}]*\}', content, re.DOTALL)
        if json_match:
            # Try to get full JSON
            json_match = re.search(r'\{.*"user_intent".*"selected_metrics".*\}', content, re.DOTALL)
            if json_match:
                content = json_match.group(0)
        
        # Parse JSON
        result = json.loads(content)

        # Validate structure
        if "user_intent" not in result:
            raise ValueError("No user_intent in response")
        if "selected_metrics" not in result:
            raise ValueError("No selected_metrics in response")
        
        user_intent = result["user_intent"]
        selected_metrics = result["selected_metrics"]
        
        # Validate and set defaults for intent
        user_intent.setdefault("profile_type", "general")
        user_intent.setdefault("priorities", [])
        user_intent.setdefault("concerns", [])
        user_intent.setdefault("lifestyle", "general")
        
# Ensure arrays are lists
        if not isinstance(user_intent["priorities"], list):
            user_intent["priorities"] = []
        if not isinstance(user_intent["concerns"], list):
            user_intent["concerns"] = []
        
        # Validate metric keys
        valid_metrics, invalid_metrics = validate_metrics(selected_metrics)
        
        if invalid_metrics:
            selected_metrics = valid_metrics
        
        # Ensure 5-8 metrics
        if len(selected_metrics) < 5:
            profile_type = user_intent.get("profile_type", "general")
            defaults = get_default_metrics_for_profile(profile_type)
            for metric in defaults:
                if metric not in selected_metrics and len(selected_metrics) < 8:
                    selected_metrics.append(metric)
        elif len(selected_metrics) > 8:
            selected_metrics = selected_metrics[:8]
        
        return {
            "user_intent": user_intent,
            "selected_metrics": selected_metrics,
            "reasoning": result.get("reasoning", "Selected based on user profile")
        }

    except (json.JSONDecodeError, ValueError, KeyError) as e:
        # Fallback: use defaults
        profile_lower = user_profile.lower()
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
        
        defaults = get_default_metrics_for_profile(profile_type)
        
        return {
            "user_intent": {
                "profile_type": profile_type,
                "priorities": [],
                "concerns": [],
                "lifestyle": "general"
            },
            "selected_metrics": defaults,
            "reasoning": f"Used defaults (Error: {str(e)})"
        }
    
    except Exception as e:
        # Final fallback
        defaults = get_default_metrics_for_profile("Custom")
        return {
            "user_intent": {
                "profile_type": "general",
                "priorities": [],
                "concerns": [],
                "lifestyle": "general"
            },
            "selected_metrics": defaults,
            "reasoning": f"Used defaults (Error: {str(e)})"
        }


