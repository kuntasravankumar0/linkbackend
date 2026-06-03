"""
Full API test suite — covers all 10 frontend-facing endpoints.
Run: py -m pytest tests/ -v
"""
import pytest

ADMIN_HEADERS = {"X-Admin-Key": "SRAVAN@123"}


# ── Helper ─────────────────────────────────────────────────────────────────────

def make_project(client, name="Test Project", access_type="FREE"):
    return client.post("/api/templates", json={
        "projectName":    name,
        "subCategory":    "Python / FastAPI",
        "accessType":     access_type,
        "details":        "A test project description",
        "subdetails":     "Technical details here",
        "guide":          "Step 1: install. Step 2: run.",
        "source":         "GitHub",
        "link":           "https://github.com/example",
        "image":          "https://example.com/img.png",
        "implementation": "print('hello world')",
    })


# ── System ─────────────────────────────────────────────────────────────────────

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert "health" in data
    assert "api" in data
    # /docs is disabled in production (DEBUG=False)
    assert "docs" not in data


# ── Create ─────────────────────────────────────────────────────────────────────

def test_create_project_success(client):
    r = make_project(client, "My Project")
    assert r.status_code == 201
    data = r.json()
    assert data["projectName"] == "My Project"
    assert data["approvalStatus"] == "PENDING"
    assert data["accessType"] == "FREE"
    assert "id" in data
    assert "uniqueId" in data
    assert len(data["uniqueId"]) == 36  # UUID format


def test_create_project_missing_name(client):
    r = client.post("/api/templates", json={"accessType": "FREE"})
    assert r.status_code == 422
    body = r.json()
    assert "message" in body
    assert "errors" in body


def test_create_project_empty_name(client):
    r = client.post("/api/templates", json={"projectName": "   "})
    assert r.status_code == 422


def test_create_project_paid(client):
    r = make_project(client, "Paid Project", "PAID")
    assert r.status_code == 201
    assert r.json()["accessType"] == "PAID"


# ── Read ───────────────────────────────────────────────────────────────────────

def test_get_all_returns_content_wrapper(client):
    make_project(client, "List Test")
    r = client.get("/api/templates")
    assert r.status_code == 200
    body = r.json()
    assert "content" in body
    assert isinstance(body["content"], list)
    assert len(body["content"]) >= 1


def test_get_by_id_success(client):
    created = make_project(client, "Detail Test").json()
    r = client.get(f"/api/templates/{created['id']}")
    assert r.status_code == 200
    data = r.json()
    assert data["projectName"] == "Detail Test"
    assert data["id"] == created["id"]


def test_get_by_id_not_found(client):
    r = client.get("/api/templates/999999")
    assert r.status_code == 404
    assert "message" in r.json()


# ── Update ─────────────────────────────────────────────────────────────────────

def test_update_project(client):
    created = make_project(client, "Old Name").json()
    r = client.put(f"/api/templates/{created['id']}", json={
        "projectName": "New Name",
        "details": "Updated details",
    }, headers=ADMIN_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["projectName"] == "New Name"
    assert data["details"] == "Updated details"


def test_update_nonexistent(client):
    r = client.put("/api/templates/999999", json={"projectName": "X"}, headers=ADMIN_HEADERS)
    assert r.status_code == 404


def test_update_requires_admin(client):
    created = make_project(client, "No Public Update").json()
    r = client.put(f"/api/templates/{created['id']}", json={"projectName": "Blocked"})
    assert r.status_code == 401


# ── Approve / Reject ───────────────────────────────────────────────────────────

def test_approve_project(client):
    created = make_project(client, "Approve Me").json()
    r = client.put(f"/api/templates/{created['id']}/approve", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    assert r.json()["approvalStatus"] == "APPROVED"


def test_reject_project(client):
    created = make_project(client, "Reject Me").json()
    r = client.put(f"/api/templates/{created['id']}/reject", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    assert r.json()["approvalStatus"] == "REJECTED"


def test_approve_requires_admin(client):
    created = make_project(client, "No Public Approve").json()
    r = client.put(f"/api/templates/{created['id']}/approve")
    assert r.status_code == 401


# ── Filter ─────────────────────────────────────────────────────────────────────

def test_filter_by_status_approved(client):
    created = make_project(client, "Approved One").json()
    client.put(f"/api/templates/{created['id']}/approve", headers=ADMIN_HEADERS)

    r = client.get("/api/templates/filter", params={"status": "APPROVED"})
    assert r.status_code == 200
    content = r.json()["content"]
    assert len(content) >= 1
    assert all(p["approvalStatus"] == "APPROVED" for p in content)


def test_filter_by_access_type_free(client):
    make_project(client, "Free One", "FREE")
    r = client.get("/api/templates/filter", params={"accessType": "FREE"})
    assert r.status_code == 200
    content = r.json()["content"]
    assert all(p["accessType"] == "FREE" for p in content)


def test_filter_by_access_type_paid(client):
    make_project(client, "Paid One", "PAID")
    r = client.get("/api/templates/filter", params={"accessType": "PAID"})
    assert r.status_code == 200
    content = r.json()["content"]
    assert all(p["accessType"] == "PAID" for p in content)


def test_filter_no_params_returns_all(client):
    r = client.get("/api/templates/filter")
    assert r.status_code == 200
    assert "content" in r.json()


# ── Search ─────────────────────────────────────────────────────────────────────

def test_search_by_name(client):
    make_project(client, "UniqueXYZ123")
    r = client.get("/api/templates/search", params={"projectName": "UniqueXYZ123"})
    assert r.status_code == 200
    content = r.json()["content"]
    assert any("UniqueXYZ123" in p["projectName"] for p in content)


def test_search_partial_match(client):
    make_project(client, "PartialMatchProject")
    r = client.get("/api/templates/search", params={"projectName": "PartialMatch"})
    assert r.status_code == 200
    content = r.json()["content"]
    assert any("PartialMatch" in p["projectName"] for p in content)


def test_search_empty_returns_all(client):
    r = client.get("/api/templates/search", params={"projectName": ""})
    assert r.status_code == 200
    assert "content" in r.json()


def test_search_no_results(client):
    r = client.get("/api/templates/search", params={"projectName": "ZZZNOMATCH999"})
    assert r.status_code == 200
    assert r.json()["content"] == []


# ── Delete ─────────────────────────────────────────────────────────────────────

def test_soft_delete(client):
    created = make_project(client, "Delete Me").json()
    r = client.delete(f"/api/templates/{created['id']}", headers=ADMIN_HEADERS)
    assert r.status_code == 204

    # Should be gone from all queries
    r2 = client.get(f"/api/templates/{created['id']}")
    assert r2.status_code == 404


def test_delete_nonexistent(client):
    r = client.delete("/api/templates/999999", headers=ADMIN_HEADERS)
    assert r.status_code == 404


def test_delete_requires_admin(client):
    created = make_project(client, "No Public Delete").json()
    r = client.delete(f"/api/templates/{created['id']}")
    assert r.status_code == 401


# ── Response shape validation ──────────────────────────────────────────────────

def test_response_has_all_frontend_fields(client):
    """Verify every field the frontend reads is present in the response."""
    created = make_project(client, "Field Check").json()
    r = client.get(f"/api/templates/{created['id']}")
    data = r.json()

    required_fields = [
        "id", "uniqueId", "projectName", "subCategory",
        "accessType", "details", "subdetails", "guide",
        "source", "link", "image", "implementation", "approvalStatus"
    ]
    for field in required_fields:
        assert field in data, f"Missing field: {field}"
