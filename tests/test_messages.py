import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_send_message(client: AsyncClient, auth_headers, test_user2):
    resp = await client.post(
        "/api/messages",
        json={"receiver_username": test_user2.username, "content": "Hello Bob!"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["content"] == "Hello Bob!"
    assert data["is_read"] is False


@pytest.mark.asyncio
async def test_send_message_to_self(client: AsyncClient, auth_headers, test_user):
    resp = await client.post(
        "/api/messages",
        json={"receiver_username": test_user.username, "content": "Hello me!"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_get_chat_history(client: AsyncClient, auth_headers, auth_headers2, test_user, test_user2):
    await client.post(
        "/api/messages",
        json={"receiver_username": test_user2.username, "content": "Hi Bob"},
        headers=auth_headers,
    )
    await client.post(
        "/api/messages",
        json={"receiver_username": test_user.username, "content": "Hi Alice"},
        headers=auth_headers2,
    )

    resp = await client.get(
        f"/api/messages/{test_user2.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    messages = resp.json()
    assert len(messages) == 2


@pytest.mark.asyncio
async def test_mark_read(client: AsyncClient, auth_headers, auth_headers2, test_user, test_user2):
    await client.post(
        "/api/messages",
        json={"receiver_username": test_user2.username, "content": "Hi Bob"},
        headers=auth_headers,
    )

    resp = await client.post(
        f"/api/messages/read/{test_user.id}",
        headers=auth_headers2,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["message_ids"]) == 1
