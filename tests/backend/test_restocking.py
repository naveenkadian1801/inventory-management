"""
Tests for restocking API endpoints.
"""
import pytest

from main import restocking_orders, restock_order_counter


class TestRestockingEndpoints:
    """Test suite for restocking-related endpoints."""

    @pytest.fixture(autouse=True)
    def reset_restocking_state(self):
        """Reset in-memory restocking state before each test."""
        restocking_orders.clear()
        restock_order_counter[0] = 0
        yield
        restocking_orders.clear()
        restock_order_counter[0] = 0

    # -- GET /api/restocking/orders (empty state) --

    def test_get_restock_orders_empty(self, client):
        """Test that restocking orders list is empty when no orders placed."""
        response = client.get("/api/restocking/orders")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    # -- GET /api/restocking/recommendations --

    def test_recommendations_default_budget(self, client):
        """Test recommendations with default budget, sorted by demand growth descending."""
        response = client.get("/api/restocking/recommendations")
        assert response.status_code == 200

        data = response.json()
        assert "recommendations" in data
        assert "total_cost" in data
        assert "budget" in data
        assert data["budget"] == 10000

        recs = data["recommendations"]
        assert isinstance(recs, list)
        assert len(recs) > 0

        # Verify structure of each recommendation
        for rec in recs:
            assert "item_sku" in rec
            assert "item_name" in rec
            assert "current_demand" in rec
            assert "forecasted_demand" in rec
            assert "demand_growth" in rec
            assert "unit_cost" in rec
            assert "recommended_qty" in rec
            assert "line_cost" in rec
            assert isinstance(rec["demand_growth"], (int, float))
            assert isinstance(rec["recommended_qty"], (int, float))
            assert isinstance(rec["line_cost"], (int, float))
            assert rec["recommended_qty"] > 0
            assert rec["line_cost"] > 0

        # Verify sorted by demand_growth descending
        growths = [rec["demand_growth"] for rec in recs]
        assert growths == sorted(growths, reverse=True)

    def test_recommendations_budget_constraint(self, client):
        """Test recommendations with a small budget stay within that budget."""
        response = client.get("/api/restocking/recommendations?budget=500")
        assert response.status_code == 200

        data = response.json()
        assert data["budget"] == 500
        assert data["total_cost"] <= 500

        recs = data["recommendations"]
        assert isinstance(recs, list)

        # Verify individual line costs sum to total_cost
        calculated_total = sum(rec["line_cost"] for rec in recs)
        assert abs(calculated_total - data["total_cost"]) < 0.01

    def test_recommendations_total_cost_within_budget(self, client):
        """Test that total_cost never exceeds the requested budget."""
        # Test with several budget values
        for budget in [100, 500, 1000, 5000, 10000, 50000]:
            response = client.get(f"/api/restocking/recommendations?budget={budget}")
            assert response.status_code == 200

            data = response.json()
            assert data["total_cost"] <= data["budget"], (
                f"total_cost {data['total_cost']} exceeds budget {data['budget']}"
            )

    # -- POST /api/restocking/orders --

    def test_place_restock_order(self, client):
        """Test placing a restocking order and verify response structure."""
        order_payload = {
            "items": [
                {"sku": "WDG-001", "name": "Precision Wedge Assembly", "quantity": 10, "unit_price": 18.50},
                {"sku": "FLT-405", "name": "Industrial Flat Washer", "quantity": 5, "unit_price": 12.50}
            ],
            "warehouse": "San Francisco"
        }

        response = client.post("/api/restocking/orders", json=order_payload)
        assert response.status_code == 200

        order = response.json()

        # Verify response structure
        assert "id" in order
        assert "order_number" in order
        assert "status" in order
        assert "warehouse" in order
        assert "total_value" in order
        assert "items" in order
        assert "order_date" in order
        assert "expected_delivery" in order
        assert "customer" in order

        # Verify values
        assert order["order_number"].startswith("RST-2026-")
        assert order["status"] == "Processing"
        assert order["warehouse"] == "San Francisco"
        assert order["customer"] == "Internal Restocking"

        # Verify total_value calculation: (10 * 18.50) + (5 * 12.50) = 247.50
        expected_total = round(10 * 18.50 + 5 * 12.50, 2)
        assert abs(order["total_value"] - expected_total) < 0.01

        # Verify items are present
        assert len(order["items"]) == 2

    # -- GET /api/restocking/orders (after placing orders) --

    def test_get_restock_orders(self, client):
        """Test that placed orders appear in the restocking orders list."""
        order_payload = {
            "items": [
                {"sku": "GSK-203", "name": "Rubber Gasket Seal", "quantity": 20, "unit_price": 8.75}
            ],
            "warehouse": "Tokyo"
        }

        # Place an order first
        post_response = client.post("/api/restocking/orders", json=order_payload)
        assert post_response.status_code == 200
        placed_order = post_response.json()

        # Now fetch all restocking orders
        get_response = client.get("/api/restocking/orders")
        assert get_response.status_code == 200

        orders = get_response.json()
        assert isinstance(orders, list)
        assert len(orders) >= 1

        # Verify the placed order appears in the list
        order_numbers = [o["order_number"] for o in orders]
        assert placed_order["order_number"] in order_numbers
