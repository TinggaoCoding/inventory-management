"""
Tests for restock order API endpoints.
"""
import pytest

import main


@pytest.fixture(autouse=True)
def clear_restock_orders():
    """Restock orders live in a module-level list; reset it so tests stay independent."""
    main.restock_orders.clear()
    yield
    main.restock_orders.clear()


class TestRestockEndpoints:
    """Test suite for restock-related endpoints."""

    def test_demand_forecasts_have_cost_and_lead_time(self, client):
        """Test that every forecast carries the fields restocking needs."""
        data = client.get("/api/demand").json()
        assert len(data) > 0
        for forecast in data:
            assert isinstance(forecast["unit_cost"], (int, float))
            assert forecast["unit_cost"] > 0
            assert isinstance(forecast["lead_time_days"], int)
            assert forecast["lead_time_days"] > 0

    def test_create_restock_order_calculation(self, client):
        """Test that total and lead time come from server data, using the slowest item."""
        forecasts = {f["item_sku"]: f for f in client.get("/api/demand").json()}
        lines = [{"sku": "WDG-001", "quantity": 10}, {"sku": "MTR-304", "quantity": 2}]

        response = client.post("/api/restock-orders", json={"items": lines})
        assert response.status_code == 201

        order = response.json()
        expected_total = sum(l["quantity"] * forecasts[l["sku"]]["unit_cost"] for l in lines)
        assert abs(order["total_cost"] - expected_total) < 0.01
        assert order["lead_time_days"] == max(forecasts[l["sku"]]["lead_time_days"] for l in lines)
        assert order["status"] == "Submitted"
        assert order["order_number"] == "RST-0001"
        assert "T" in order["expected_delivery"]

    def test_create_restock_order_ignores_client_price(self, client):
        """Test that an extra unit_cost field from the client cannot change the price."""
        server_cost = next(f["unit_cost"] for f in client.get("/api/demand").json() if f["item_sku"] == "PSU-501")
        response = client.post(
            "/api/restock-orders",
            json={"items": [{"sku": "PSU-501", "quantity": 1, "unit_cost": 0.01}]},
        )
        assert response.status_code == 201
        assert response.json()["items"][0]["unit_cost"] == server_cost

    def test_create_restock_order_duplicate_sku(self, client):
        """Test that the same SKU twice in one order is rejected."""
        lines = [{"sku": "WDG-001", "quantity": 1}, {"sku": "WDG-001", "quantity": 2}]
        response = client.post("/api/restock-orders", json={"items": lines})
        assert response.status_code == 400
        assert client.get("/api/restock-orders").json() == []

    def test_create_restock_order_unknown_sku(self, client):
        """Test that an unknown SKU is rejected and nothing is stored."""
        response = client.post("/api/restock-orders", json={"items": [{"sku": "NOPE-999", "quantity": 1}]})
        assert response.status_code == 400
        assert "NOPE-999" in response.json()["detail"]
        assert client.get("/api/restock-orders").json() == []

    @pytest.mark.parametrize("payload", [
        {"items": []},
        {"items": [{"sku": "WDG-001", "quantity": 0}]},
        {"items": [{"sku": "WDG-001", "quantity": -5}]},
        {"items": [{"sku": "WDG-001", "quantity": 10**30}]},
    ])
    def test_create_restock_order_invalid_input(self, client, payload):
        """Test that empty orders and non-positive quantities fail validation."""
        response = client.post("/api/restock-orders", json=payload)
        assert response.status_code == 422

    def test_get_restock_orders_newest_first(self, client):
        """Test that submitted orders are listed newest first."""
        client.post("/api/restock-orders", json={"items": [{"sku": "WDG-001", "quantity": 1}]})
        client.post("/api/restock-orders", json={"items": [{"sku": "BRG-102", "quantity": 1}]})

        response = client.get("/api/restock-orders")
        assert response.status_code == 200
        numbers = [o["order_number"] for o in response.json()]
        assert numbers == ["RST-0002", "RST-0001"]
