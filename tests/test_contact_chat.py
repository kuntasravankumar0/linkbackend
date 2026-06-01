"""
Tests for Contact and Chat endpoints.
Run: py -m pytest tests/ -v
"""
import pytest

ADMIN_HEADERS = {"X-Admin-Key": "SRAVAN@123"}


# ─────────────────────────────────────────────────────────────────────────────
# CONTACT TESTS
# ─────────────────────────────────────────────────────────────────────────────

def test_contact_submit_success(client):
    r = client.post("/api/contact", json={
        "name":    "Test User",
        "email":   "test@example.com",
        "message": "Hello, this is a test message.",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["name"]    == "Test User"
    assert data["email"]   == "test@example.com"
    assert data["is_read"] == False


def test_contact_submit_with_all_fields(client):
    r = client.post("/api/contact", json={
        "name":    "Full User",
        "email":   "full@example.com",
        "phone":   "+91 98765 43210",
        "subject": "General Inquiry",
        "message": "Full message with all fields.",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["phone"]   == "+91 98765 43210"
    assert data["subject"] == "General Inquiry"


def test_contact_submit_missing_name(client):
    r = client.post("/api/contact", json={
        "email":   "test@example.com",
        "message": "No name provided.",
    })
    assert r.status_code == 422


def test_contact_submit_missing_message(client):
    r = client.post("/api/contact", json={
        "name":  "Test",
        "email": "test@example.com",
    })
    assert r.status_code == 422


def test_contact_submit_invalid_email(client):
    r = client.post("/api/contact", json={
        "name":    "Test",
        "email":   "not-an-email",
        "message": "Test message.",
    })
    assert r.status_code == 422


def test_contact_admin_list(client):
    # Submit a message first
    client.post("/api/contact", json={
        "name": "Admin List Test", "email": "adminlist@example.com",
        "message": "Test for admin list.",
    })
    r = client.get("/api/contact", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert "content" in body
    assert "total"   in body
    assert "unread"  in body
    assert isinstance(body["content"], list)
    assert body["total"] >= 1


def test_contact_admin_list_no_key(client):
    r = client.get("/api/contact")
    assert r.status_code == 401


def test_contact_admin_list_wrong_key(client):
    r = client.get("/api/contact", headers={"X-Admin-Key": "wrongkey"})
    assert r.status_code == 403


def test_contact_mark_read(client):
    created = client.post("/api/contact", json={
        "name": "Mark Read", "email": "markread@example.com",
        "message": "Mark me as read.",
    }).json()
    assert created["is_read"] == False

    r = client.put(f"/api/contact/{created['id']}/read", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    assert r.json()["is_read"] == True


def test_contact_mark_unread(client):
    created = client.post("/api/contact", json={
        "name": "Mark Unread", "email": "markunread@example.com",
        "message": "Mark me as unread.",
    }).json()
    # First mark read
    client.put(f"/api/contact/{created['id']}/read", headers=ADMIN_HEADERS)
    # Then unread
    r = client.put(f"/api/contact/{created['id']}/unread", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    assert r.json()["is_read"] == False


def test_contact_delete(client):
    created = client.post("/api/contact", json={
        "name": "Delete Me", "email": "deleteme@example.com",
        "message": "Delete this message.",
    }).json()

    r = client.delete(f"/api/contact/{created['id']}", headers=ADMIN_HEADERS)
    assert r.status_code == 204


def test_contact_delete_no_key(client):
    created = client.post("/api/contact", json={
        "name": "No Key Delete", "email": "nokey@example.com",
        "message": "Should not be deleted.",
    }).json()
    r = client.delete(f"/api/contact/{created['id']}")
    assert r.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# CHAT TESTS
# ─────────────────────────────────────────────────────────────────────────────

def test_chat_send_message(client):
    r = client.post("/api/chat/send", json={
        "email":   "chatuser@example.com",
        "name":    "Chat User",
        "message": "Hello from chat!",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["email"]   == "chatuser@example.com"
    assert data["sender"]  == "user"
    assert data["message"] == "Hello from chat!"
    assert data["is_read"] == False


def test_chat_send_without_name(client):
    r = client.post("/api/chat/send", json={
        "email":   "noname@example.com",
        "message": "Message without name.",
    })
    assert r.status_code == 201
    assert r.json()["sender"] == "user"


def test_chat_send_invalid_email(client):
    r = client.post("/api/chat/send", json={
        "email":   "not-valid",
        "message": "Bad email.",
    })
    assert r.status_code == 422


def test_chat_send_empty_message(client):
    r = client.post("/api/chat/send", json={
        "email":   "test@example.com",
        "message": "   ",
    })
    assert r.status_code == 422


def test_chat_get_user_thread(client):
    email = "threaduser@example.com"
    client.post("/api/chat/send", json={"email": email, "name": "Thread User", "message": "Msg 1"})
    client.post("/api/chat/send", json={"email": email, "message": "Msg 2"})

    r = client.get("/api/chat/history", params={"email": email})
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == email
    assert "messages" in data
    assert len(data["messages"]) == 2
    # Oldest first
    assert data["messages"][0]["message"] == "Msg 1"
    assert data["messages"][1]["message"] == "Msg 2"


def test_chat_get_empty_thread(client):
    r = client.get("/api/chat/history", params={"email": "nobody@example.com"})
    assert r.status_code == 200
    assert r.json()["messages"] == []


def test_chat_admin_list_threads(client):
    client.post("/api/chat/send", json={
        "email": "adminview@example.com", "name": "Admin View", "message": "Test thread"
    })
    r = client.get("/api/chat/admin/threads", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert "threads"      in body
    assert "total_unread" in body
    assert isinstance(body["threads"], list)


def test_chat_admin_list_no_key(client):
    r = client.get("/api/chat/admin/threads")
    assert r.status_code == 401


def test_chat_admin_get_thread(client):
    email = "adminthread@example.com"
    client.post("/api/chat/send", json={"email": email, "name": "Admin Thread", "message": "Read me"})

    r = client.get("/api/chat/admin/thread", params={"email": email}, headers=ADMIN_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == email
    assert len(data["messages"]) >= 1
    # After admin views, message should be marked read
    assert data["messages"][0]["is_read"] == True


def test_chat_admin_reply(client):
    email = "replytest@example.com"
    client.post("/api/chat/send", json={"email": email, "message": "User message"})

    r = client.post("/api/chat/admin/reply",
                    json={"email": email, "message": "Admin reply here"},
                    headers=ADMIN_HEADERS)
    assert r.status_code == 201
    data = r.json()
    assert data["sender"]  == "admin"
    assert data["message"] == "Admin reply here"
    assert data["email"]   == email


def test_chat_admin_reply_no_key(client):
    r = client.post("/api/chat/admin/reply",
                    json={"email": "test@example.com", "message": "Unauthorized reply"})
    assert r.status_code == 401


def test_chat_thread_shows_both_sides(client):
    email = "bothsides@example.com"
    client.post("/api/chat/send", json={"email": email, "name": "Both Sides", "message": "User says hi"})
    client.post("/api/chat/admin/reply",
                json={"email": email, "message": "Admin says hello"},
                headers=ADMIN_HEADERS)

    r = client.get("/api/chat/history", params={"email": email})
    messages = r.json()["messages"]
    assert len(messages) == 2
    senders = [m["sender"] for m in messages]
    assert "user"  in senders
    assert "admin" in senders


def test_chat_delete_thread(client):
    email = "deletechat@example.com"
    client.post("/api/chat/send", json={"email": email, "message": "Delete this thread"})

    r = client.delete("/api/chat/admin/thread",
                      params={"email": email},
                      headers=ADMIN_HEADERS)
    assert r.status_code == 204

    # Thread should be empty after delete
    r2 = client.get("/api/chat/history", params={"email": email})
    assert r2.json()["messages"] == []


def test_chat_delete_no_key(client):
    r = client.delete("/api/chat/admin/thread", params={"email": "test@example.com"})
    assert r.status_code == 401


def test_chat_email_case_insensitive(client):
    """Same email in different cases should be the same thread."""
    client.post("/api/chat/send", json={"email": "CaseTest@Example.COM", "message": "Upper case"})
    client.post("/api/chat/send", json={"email": "casetest@example.com", "message": "Lower case"})

    r = client.get("/api/chat/history", params={"email": "casetest@example.com"})
    assert len(r.json()["messages"]) == 2
