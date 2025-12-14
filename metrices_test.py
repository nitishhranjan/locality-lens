# Quick test
import sys
sys.path.insert(0, '.')
from src.analysis.metrics_catalog import (
    get_all_metrics,
    get_default_metrics_for_profile,
    get_metrics_for_llm_selection
)

print(f"Total metrics: {len(get_all_metrics())}")
print(f"Family metrics: {get_default_metrics_for_profile('Family with Kids')}")
print("\nFirst 3 metrics for LLM:")
print(get_metrics_for_llm_selection().split('\n')[:3])