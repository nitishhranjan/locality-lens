"""
Testing script for Locality Lens application.
Tests various scenarios to ensure robustness.
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.graph.graph import compile_graph
from src.graph.state import LocalityState

def create_test_state(location: str, profile: str = None) -> LocalityState:
    """Create test state for a location."""
    return {
        "user_input": location,
        "user_profile": profile,
        "coordinates": None,
        "address": None,
        "osm_data": {},
        "aqi_data": None,
        "selected_metrics": [],
        "statistics": {},
        "user_intent": {},
        "summary": None,
        "recommendations": [],
        "visualization_data": None,
        "errors": [],
        "warnings": [],
        "next_action": "",
        "processing_steps": []
    }

def test_location(graph, location: str, profile: str = None):
    """Test a single location."""
    print(f"\n{'='*60}")
    print(f"Testing: {location}")
    if profile:
        print(f"Profile: {profile}")
    print(f"{'='*60}")
    
    initial_state = create_test_state(location, profile)
    
    try:
        result = graph.invoke(initial_state)
        
        # Check for errors
        if result.get("errors"):
            print(f"❌ Errors: {result['errors']}")
            return False
        
        # Check for warnings
        if result.get("warnings"):
            print(f"⚠️  Warnings: {result['warnings']}")
        
        # Check results
        if result.get("coordinates"):
            lat, lon = result["coordinates"]
            print(f"✅ Coordinates: {lat}, {lon}")
        else:
            print("⚠️  No coordinates found")
        
        if result.get("address"):
            print(f"✅ Address: {result['address']}")
        
        if result.get("statistics"):
            stats = result["statistics"]
            print(f"✅ Statistics calculated: {len(stats)} metrics")
            # Show a few key stats
            for key in ["school_count", "hospital_count", "restaurant_count"]:
                if key in stats:
                    print(f"   - {key}: {stats[key]}")
        
        if result.get("summary"):
            summary_len = len(result["summary"])
            print(f"✅ Summary generated: {summary_len} characters")
        else:
            print("⚠️  No summary generated")
        
        print("✅ Test PASSED")
        return True
        
    except Exception as e:
        print(f"❌ Test FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("🧪 Locality Lens - Testing Suite")
    print("="*60)
    
    # Compile graph
    try:
        graph = compile_graph()
        print("✅ Graph compiled successfully\n")
    except Exception as e:
        print(f"❌ Failed to compile graph: {e}")
        return
    
    # Test cases
    test_cases = [
        # Valid locations
        ("Indiranagar, Bangalore", None),
        ("12.9784, 77.6408", None),  # Coordinates
        ("Connaught Place, Delhi", None),
        ("Mumbai, Maharashtra", None),
        
        # With profiles
        ("Indiranagar, Bangalore", "Bachelor/Young Professional"),
        ("Indiranagar, Bangalore", "Family with Kids"),
        ("Indiranagar, Bangalore", "Student"),
        
        # Edge cases
        ("", None),  # Empty input
        ("asdfghjkl", None),  # Invalid location
    ]
    
    results = []
    for location, profile in test_cases:
        success = test_location(graph, location, profile)
        results.append((location, profile, success))
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 Test Summary")
    print(f"{'='*60}")
    
    passed = sum(1 for _, _, success in results if success)
    total = len(results)
    
    print(f"Total tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Success rate: {passed/total*100:.1f}%")
    
    # Show failures
    failures = [(loc, prof) for loc, prof, success in results if not success]
    if failures:
        print(f"\n❌ Failed tests:")
        for loc, prof in failures:
            print(f"   - {loc} ({prof or 'No profile'})")
    
    print(f"\n{'='*60}")

if __name__ == "__main__":
    main()

