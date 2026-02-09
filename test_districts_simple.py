"""Quick test of hardcoded districts data (no dependencies).

This test verifies that districts_data.py works correctly
without requiring any external dependencies.
"""

import sys
import os

# Fix encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.modules.geo.infra.districts_data import (
    DISTRICTS_DATA,
    get_all_districts,
    get_district_by_id,
)


def test_districts_data():
    """Test hardcoded districts functionality."""
    
    print("\n" + "=" * 70)
    print("🧪 QUICK TEST: Hardcoded Districts Data")
    print("=" * 70)
    
    # Test 1: Raw data structure
    print("\n1️⃣  Test raw DISTRICTS_DATA:")
    print("-" * 70)
    assert len(DISTRICTS_DATA) > 0, "Should have at least 1 district"
    print(f"✅ Total districts in data: {len(DISTRICTS_DATA)}")
    
    for district in DISTRICTS_DATA:
        assert "id" in district, "District must have 'id'"
        assert "name" in district, "District must have 'name'"
        assert "active" in district, "District must have 'active'"
        print(f"   • {district['id']}: {district['name']} (active={district['active']})")
    
    # Test 2: Get all active districts
    print("\n2️⃣  Test get_all_districts(active_only=True):")
    print("-" * 70)
    active = get_all_districts(active_only=True)
    print(f"✅ Active districts: {len(active)}")
    assert all(d["active"] for d in active), "All should be active"
    
    # Test 3: Get all districts (including inactive)
    print("\n3️⃣  Test get_all_districts(active_only=False):")
    print("-" * 70)
    all_districts = get_all_districts(active_only=False)
    print(f"✅ Total districts: {len(all_districts)}")
    assert len(all_districts) >= len(active), "Total >= Active"
    
    # Test 4: Get district by ID (valid)
    print("\n4️⃣  Test get_district_by_id (valid ID):")
    print("-" * 70)
    test_id = "150104"  # Barranco
    district = get_district_by_id(test_id)
    assert district is not None, f"Should find district {test_id}"
    assert district["id"] == test_id, "Should return correct district"
    print(f"✅ Found: {district['name']} ({test_id})")
    
    # Test 5: Get district by ID (invalid)
    print("\n5️⃣  Test get_district_by_id (invalid ID):")
    print("-" * 70)
    invalid_id = "999999"
    district = get_district_by_id(invalid_id)
    assert district is None, "Should return None for invalid ID"
    print(f"✅ Correctly returned None for {invalid_id}")
    
    # Test 6: Validate district exists and is active (simulation)
    print("\n6️⃣  Test validation logic (simulate API behavior):")
    print("-" * 70)
    
    def validate_district(district_id: str) -> bool:
        """Simulate GeoService.validate_district_exists_and_active"""
        district = get_district_by_id(district_id)
        if district is None:
            return False
        return district.get("active", False) is True
    
    test_cases = [
        ("150104", True, "Barranco (valid)"),
        ("150113", True, "Jesús María (valid)"),
        ("150116", True, "Lince (valid)"),
        ("150122", True, "Miraflores (valid)"),
        ("999999", False, "Invalid UBIGEO"),
        ("", False, "Empty string"),
    ]
    
    for district_id, expected, description in test_cases:
        result = validate_district(district_id)
        status = "✅ PASS" if result == expected else "❌ FAIL"
        print(f"   {status}: {description} -> {result}")
        assert result == expected, f"Validation failed for {description}"
    
    # Success summary
    print("\n" + "=" * 70)
    print("✅ ALL TESTS PASSED!")
    print("=" * 70)
    print("\n📋 Summary:")
    print(f"   • Total districts in data: {len(DISTRICTS_DATA)}")
    print(f"   • Active districts: {len(active)}")
    print(f"   • Data structure: ✅ Valid")
    print(f"   • Lookup functions: ✅ Working")
    print(f"   • Validation logic: ✅ Correct")
    print("\n🚀 Hardcoded districts are ready to use!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    try:
        test_districts_data()
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
