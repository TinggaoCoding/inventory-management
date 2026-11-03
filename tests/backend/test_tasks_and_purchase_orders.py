"""
Tests for task and purchase order API endpoints.
"""
import pytest

import main


@pytest.fixture(autouse=True)
def clear_state():
    """Tasks and purchase orders live in module-level lists; reset them so tests stay independent."""
    main.tasks.clear()
    main.purchase_orders.clear()
    yield
    main.tasks.clear()
    main.purchase_orders.clear()


def make_po(backlog_item_id="1"):
    return {
        "backlog_item_id": backlog_item_id,
        "supplier_name": "Acme Supply",
        "quantity": 350,
        "unit_cost": 4.5,
        "expected_delivery_date": "2025-12-01",
    }


class TestTasksEndpoints:
    """Test suite for task endpoints."""

    def test_task_lifecycle(self, client):
        """Test create, list, toggle and delete of a task."""
        assert client.get("/api/tasks").json() == []

        response = client.post("/api/tasks", json={"title": " Check stock ", "priority": "high", "dueDate": "2025-10-08"})
        assert response.status_code == 201
        task = response.json()
        assert task["title"] == "Check stock"
        assert task["dueDate"] == "2025-10-08"
        assert task["status"] == "pending"
        # Must be a string so App.vue can't confuse it with the numeric mock task ids
        assert isinstance(task["id"], str)

        assert client.get("/api/tasks").json() == [task]
        assert client.patch(f"/api/tasks/{task['id']}").json()["status"] == "completed"
        assert client.patch(f"/api/tasks/{task['id']}").json()["status"] == "pending"

        assert client.delete(f"/api/tasks/{task['id']}").status_code == 200
        assert client.get("/api/tasks").json() == []

    def test_task_ids_unique_after_delete(self, client):
        """Test that deleting a task never lets a new task reuse an existing id."""
        first = client.post("/api/tasks", json={"title": "A", "dueDate": "2025-10-08"}).json()
        second = client.post("/api/tasks", json={"title": "B", "dueDate": "2025-10-08"}).json()
        client.delete(f"/api/tasks/{first['id']}")
        third = client.post("/api/tasks", json={"title": "C", "dueDate": "2025-10-08"}).json()
        assert third["id"] != second["id"]

    @pytest.mark.parametrize("payload", [
        {"title": "", "dueDate": "2025-10-08"},
        {"title": "x", "dueDate": "not-a-date"},
        {"title": "x", "priority": "urgent", "dueDate": "2025-10-08"},
    ])
    def test_create_task_invalid(self, client, payload):
        """Test that invalid task input is rejected."""
        assert client.post("/api/tasks", json=payload).status_code == 422

    def test_create_task_blank_title(self, client):
        """Test that a whitespace-only title is rejected."""
        assert client.post("/api/tasks", json={"title": "   ", "dueDate": "2025-10-08"}).status_code == 400

    def test_nonexistent_task(self, client):
        """Test toggling and deleting a task that doesn't exist."""
        for response in (client.patch("/api/tasks/nope"), client.delete("/api/tasks/nope")):
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()


class TestPurchaseOrderEndpoints:
    """Test suite for purchase order endpoints."""

    def test_create_and_get_purchase_order(self, client):
        """Test creating a PO and reading it back, including via the backlog."""
        response = client.post("/api/purchase-orders", json=make_po())
        assert response.status_code == 201
        po = response.json()
        assert po["backlog_item_id"] == "1"
        assert po["status"] == "Pending"
        assert po["expected_delivery_date"] == "2025-12-01"

        assert client.get("/api/purchase-orders/1").json() == po

        backlog = {b["id"]: b for b in client.get("/api/backlog").json()}
        assert backlog["1"]["purchase_order_id"] == po["id"]
        assert backlog["1"]["has_purchase_order"] is True
        assert backlog["2"]["purchase_order_id"] is None

    def test_duplicate_purchase_order(self, client):
        """Test that a backlog item can only have one PO."""
        client.post("/api/purchase-orders", json=make_po())
        assert client.post("/api/purchase-orders", json=make_po()).status_code == 409

    def test_purchase_order_unknown_backlog_item(self, client):
        """Test creating a PO for a backlog item that doesn't exist."""
        assert client.post("/api/purchase-orders", json=make_po("nope")).status_code == 404

    @pytest.mark.parametrize("field,value", [("quantity", 0), ("unit_cost", -1), ("supplier_name", ""), ("expected_delivery_date", "soon")])
    def test_purchase_order_invalid(self, client, field, value):
        """Test that invalid PO input is rejected."""
        assert client.post("/api/purchase-orders", json={**make_po(), field: value}).status_code == 422

    def test_get_nonexistent_purchase_order(self, client):
        """Test getting a PO for a backlog item that has none."""
        response = client.get("/api/purchase-orders/1")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
