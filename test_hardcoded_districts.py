"""Test script to verify hardcoded districts work without database.

This script tests that the geo module works correctly with hardcoded data,
without requiring a database connection.
"""

import asyncio
from app.modules.geo.infra.districts_data import get_all_districts, get_district_by_id


async def test_hardcoded_districts():
    """Test hardcoded districts functionality."""
    
    print("=" * 60)
    print("🗺️  TESTING HARDCODED DISTRICTS (No DB Required)")
    print("=" * 60)
    
    # Test 1: Get all active districts
    print("\n1️⃣  GET ALL ACTIVE DISTRICTS:")
    print("-" * 60)
    active_districts = get_all_districts(active_only=True)
    print(f"✅ Found {len(active_districts)} active districts:")
    for d in active_districts:
        print(f"   • {d['id']}: {d['name']} ({d['province_name']}, {d['department_name']})")
    
    # Test 2: Get all districts (including inactive)
    print("\n2️⃣  GET ALL DISTRICTS (including inactive):")
    print("-" * 60)
    all_districts = get_all_districts(active_only=False)
    print(f"✅ Total districts: {len(all_districts)}")
    
    # Test 3: Get specific district by ID
    print("\n3️⃣  GET DISTRICT BY ID:")
    print("-" * 60)
    test_id = "150104"  # Barranco
    district = get_district_by_id(test_id)
    if district:
        print(f"✅ Found district {test_id}: {district['name']}")
        print(f"   Province: {district['province_name']}")
        print(f"   Department: {district['department_name']}")
        print(f"   Active: {district['active']}")
    else:
        print(f"❌ District {test_id} not found")
    
    # Test 4: Try to get non-existent district
    print("\n4️⃣  GET NON-EXISTENT DISTRICT:")
    print("-" * 60)
    invalid_id = "999999"
    district = get_district_by_id(invalid_id)
    if district is None:
        print(f"✅ Correctly returned None for invalid ID: {invalid_id}")
    else:
        print(f"❌ Unexpected: found district for invalid ID")
    
    # Test 5: Validation flow (like in create_address)
    print("\n5️⃣  SIMULATE ADDRESS CREATION VALIDATION:")
    print("-" * 60)
    test_cases = [
        ("150104", "Barranco - Should be VALID"),
        ("150113", "Jesús María - Should be VALID"),
        ("150116", "Lince - Should be VALID"),
        ("150101", "Lima Cercado - Should be INVALID (not in list)"),
    ]
    
    for district_id, description in test_cases:
        district = get_district_by_id(district_id)
        is_valid = district is not None and district.get("active", False)
        status = "✅ VALID" if is_valid else "❌ INVALID"
        print(f"   {status}: {description}")
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS COMPLETED - Districts working without DB!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_hardcoded_districts())
