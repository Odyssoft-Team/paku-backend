"""Tests for Geo module API endpoints.

Minimal tests for GET /geo/districts and GET /geo/districts/{id}.
Uses mocks to avoid DB dependencies.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.modules.geo.domain.schemas import DistrictOut
from app.main import app


client = TestClient(app)


class TestListDistricts:
    """Tests for GET /geo/districts endpoint."""

    @pytest.mark.asyncio
    async def test_list_districts_returns_200(self):
        """Test that listing districts returns 200 and expected structure."""
        # Mock the GeoService
        mock_districts = [
            {
                "id": "150101",
                "name": "Lima",
                "province_name": "Lima",
                "department_name": "Lima",
                "active": True,
            },
            {
                "id": "150102",
                "name": "Barranco",
                "province_name": "Lima",
                "department_name": "Lima",
                "active": True,
            },
        ]
        
        with patch(
            "app.modules.geo.infra.repository.PostgresDistrictRepository.list_districts",
            new_callable=AsyncMock,
            return_value=mock_districts,
        ):
            response = client.get("/geo/districts")
            
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 2
            # Verify structure
            for item in data:
                assert "id" in item
                assert "name" in item
                assert "province_name" in item
                assert "department_name" in item
                assert "active" in item

    @pytest.mark.asyncio
    async def test_list_districts_with_active_filter(self):
        """Test filtering districts by active status."""
        mock_districts = [
            {
                "id": "150101",
                "name": "Lima",
                "province_name": "Lima",
                "department_name": "Lima",
                "active": True,
            },
        ]
        
        with patch(
            "app.modules.geo.infra.repository.PostgresDistrictRepository.list_districts",
            new_callable=AsyncMock,
            return_value=mock_districts,
        ) as mock_list:
            response = client.get("/geo/districts?active=true")
            
            assert response.status_code == 200
            mock_list.assert_awaited_once_with(active_only=True)


class TestGetDistrict:
    """Tests for GET /geo/districts/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_district_valid_id_returns_200(self):
        """Test getting a district with valid ID returns 200."""
        mock_district = {
            "id": "150101",
            "name": "Lima",
            "province_name": "Lima",
            "department_name": "Lima",
            "active": True,
        }
        
        with patch(
            "app.modules.geo.infra.repository.PostgresDistrictRepository.get_district",
            new_callable=AsyncMock,
            return_value=mock_district,
        ):
            response = client.get("/geo/districts/150101")
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "150101"
            assert data["name"] == "Lima"
            assert data["active"] is True

    @pytest.mark.asyncio
    async def test_get_district_invalid_id_returns_404(self):
        """Test getting a district with invalid ID returns 404."""
        with patch(
            "app.modules.geo.infra.repository.PostgresDistrictRepository.get_district",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = client.get("/geo/districts/invalid-id")
            
            assert response.status_code == 404
            assert "District not found" in response.json()["detail"]
