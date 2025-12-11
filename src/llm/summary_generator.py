"""
LLM integration for generating locality summaries.
"""
from langchain_groq import ChatGroq
from config.config import GROQ_API_KEY
from .prompts import get_summary_prompt

def get_llm():
    """Get LLM instance."""
    return ChatGroq(
        api_key=GROQ_API_KEY,
        model_name="llama-3.1-8b-instant",
        temperature=0.6,
        max_tokens=1024
    )

def generate_summary(statistics: dict, osm_data: dict, address: str = None)-> str:
    """
    Generate a summary of the locality.
    """
    prompt = get_summary_prompt(statistics, osm_data, address)
    llm = get_llm()
    response = llm.invoke(prompt)
    return response.content