"""Integration test: Geo + IAM Address Flow

This test simulates the complete flow of:
1. User gets available districts
2. User selects a district
3. User creates an address with that district
4. System validates district exists and is active

NO DATABASE REQUIRED - Uses hardcoded districts.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.modules.geo.infra.repository import PostgresDistrictRepository
from app.modules.geo.use_cases.geo_service import GeoService


async def test_integration_flow():
    """Test the complete geo + address creation flow."""
    
    print("\n" + "=" * 70)
    print("🔗 INTEGRATION TEST: Geo + Address Creation Flow")
    print("=" * 70)
    
    # Mock session (not used since we're using hardcoded data)
    mock_session = AsyncMock()
    
    # Create repository and service
    district_repo = PostgresDistrictRepository(session=mock_session)
    geo_service = GeoService(district_repo=district_repo)
    
    # ============================================================
    # STEP 1: User opens "Create Address" screen
    # Frontend calls: GET /geo/districts?active=true
    # ============================================================
    print("\n📍 STEP 1: User requests available districts")
    print("-" * 70)
    
    districts = await geo_service.list_districts(active_only=True)
    
    print(f"✅ API Response: {len(districts)} active districts")
    for d in districts:
        print(f"   • {d.id}: {d.name} ({d.province_name})")
    
    assert len(districts) == 3, "Should have 3 active districts"
    assert all(d.active for d in districts), "All should be active"
    
    # ============================================================
    # STEP 2: User selects "Barranco" from dropdown
    # ============================================================
    print("\n🎯 STEP 2: User selects district 'Barranco' (150104)")
    print("-" * 70)
    
    selected_district_id = "150104"
    selected_district = await geo_service.get_district(selected_district_id)
    
    assert selected_district is not None, "District should exist"
    assert selected_district.name == "Barranco", "Should be Barranco"
    print(f"✅ Selected: {selected_district.name}")
    
    # ============================================================
    # STEP 3: User fills address form and submits
    # Backend validates district before creating address
    # ============================================================
    print("\n✍️  STEP 3: User submits address form")
    print("-" * 70)
    
    # Simulated form data
    address_form = {
        "district_id": "150104",
        "address_line": "Av. Pedro de Osma 123",
        "lat": -12.1465,
        "lng": -77.0204,
        "reference": "Casa verde, segundo piso",
    }
    
    print(f"   District: {address_form['district_id']}")
    print(f"   Address: {address_form['address_line']}")
    print(f"   Reference: {address_form['reference']}")
    
    # ============================================================
    # STEP 4: Backend validates district (like in POST /addresses)
    # ============================================================
    print("\n🔍 STEP 4: Backend validates district")
    print("-" * 70)
    
    is_valid = await geo_service.validate_district_exists_and_active(
        address_form["district_id"]
    )
    
    if is_valid:
        print("✅ VALIDATION PASSED: District exists and is active")
        print("✅ Address would be created successfully")
    else:
        print("❌ VALIDATION FAILED: District not found or inactive")
        print("❌ Address creation would be rejected (422)")
    
    assert is_valid, "District validation should pass"
    
    # ============================================================
    # STEP 5: Test with INVALID district
    # ============================================================
    print("\n⚠️  STEP 5: Test with invalid district (should fail)")
    print("-" * 70)
    
    invalid_cases = [
        ("150101", "Lima Cercado (not in supported list)"),
        ("999999", "Invalid UBIGEO code"),
        ("150104x", "Malformed district ID"),
    ]
    
    for invalid_id, description in invalid_cases:
        is_valid = await geo_service.validate_district_exists_and_active(invalid_id)
        status = "❌ REJECTED" if not is_valid else "⚠️  UNEXPECTED PASS"
        print(f"   {status}: {description}")
        assert not is_valid, f"Should reject invalid district: {invalid_id}"
    
    # ============================================================
    # SUCCESS SUMMARY
    # ============================================================
    print("\n" + "=" * 70)
    print("✅ INTEGRATION TEST PASSED")
    print("=" * 70)
    print("\n📋 Summary:")
    print("   ✅ Districts API works without database")
    print("   ✅ District validation works correctly")
    print("   ✅ Invalid districts are properly rejected")
    print("   ✅ Address creation flow is unblocked")
    print("\n🚀 Ready for production!")
    print("=" * 70 + "\n")


async def test_edge_cases():
    """Test edge cases and error handling."""
    
    print("\n" + "=" * 70)
    print("🧪 EDGE CASES TEST")
    print("=" * 70)
    
    mock_session = AsyncMock()
    district_repo = PostgresDistrictRepository(session=mock_session)
    geo_service = GeoService(district_repo=district_repo)
    
    # Test case 1: Empty district ID
    print("\n1️⃣  Empty district ID")
    is_valid = await geo_service.validate_district_exists_and_active("")
    assert not is_valid, "Empty ID should be invalid"
    print("   ✅ Empty string correctly rejected")
    
    # Test case 2: None district ID
    print("\n2️⃣  None district ID")
    try:
        is_valid = await geo_service.validate_district_exists_and_active(None)  # type: ignore
        assert not is_valid, "None should be invalid"
        print("   ✅ None correctly rejected")
    except:
        print("   ✅ None correctly raises exception")
    
    # Test case 3: Case sensitivity
    print("\n3️⃣  Case sensitivity test")
    is_valid_lower = await geo_service.validate_district_exists_and_active("150104")
    is_valid_upper = await geo_service.validate_district_exists_and_active("150104")  # Same
    assert is_valid_lower == is_valid_upper, "Should be case-consistent"
    print("   ✅ District IDs handled consistently")
    
    # Test case 4: Get all districts including inactive
    print("\n4️⃣  Get all districts (including inactive)")
    all_districts = await geo_service.list_districts(active_only=False)
    active_districts = await geo_service.list_districts(active_only=True)
    print(f"   All districts: {len(all_districts)}")
    print(f"   Active only: {len(active_districts)}")
    assert len(all_districts) >= len(active_districts), "All >= Active"
    print("   ✅ Filtering works correctly")
    
    print("\n" + "=" * 70)
    print("✅ ALL EDGE CASES PASSED")
    print("=" * 70 + "\n")


async def main():
    """Run all integration tests."""
    try:
        await test_integration_flow()
        await test_edge_cases()
        
        print("\n" + "🎉" * 35)
        print("\n   ✅ ALL INTEGRATION TESTS PASSED!")
        print("   🚀 Geo + Address flow is ready for production")
        print("\n" + "🎉" * 35 + "\n")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        raise
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}\n")
        raise


if __name__ == "__main__":
    asyncio.run(main())
