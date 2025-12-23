"""
LLM integration for generating locality summaries.
"""
from langchain_openai import ChatOpenAI
from config.config import OPENAI_API_KEY
from .prompts import get_summary_prompt

def get_llm():
    """Get LLM instance."""
    return ChatOpenAI(
        api_key=OPENAI_API_KEY,
        model_name="gpt-4o",
        temperature=0.6,
        max_tokens=1024
    )

def generate_summary(
    statistics: dict,
    osm_data: dict,
    address: str = None,
    user_intent: dict = None,
    selected_metrics: list = None,
    user_profile: str = None
) -> str:
    """
    Generate a summary of the locality with personalized context.
    
    Args:
        statistics: Calculated statistics/metrics
        osm_data: OSM POI data
        address: Location address
        user_intent: Extracted user intent (profile_type, priorities, concerns, lifestyle)
        selected_metrics: List of selected metric keys
        user_profile: Original user profile string
        
    Returns:
        Generated summary text
    """
    prompt = get_summary_prompt(
        statistics=statistics,
        osm_data=osm_data,
        address=address,
        user_intent=user_intent,
        selected_metrics=selected_metrics,
        user_profile=user_profile
    )
    llm = get_llm()
    response = llm.invoke(prompt)
    return response.content