import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_send_friend_request(client: AsyncClient, auth_headers, test_user2):
    resp = await client.post(
        "/api/friends/requests",
        json={"username": test_user2.username},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_send_friend_request_self(client: AsyncClient, auth_headers, test_user):
    resp = await client.post(
        "/api/friends/requests",
        json={"username": test_user.username},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_accept_friend_request(client: AsyncClient, auth_headers, auth_headers2, test_user, test_user2):
    resp = await client.post(
        "/api/friends/requests",
        json={"username": test_user2.username},
        headers=auth_headers,
    )
    friend_id = resp.json()["id"]

    resp = await client.post(
        f"/api/friends/requests/{friend_id}/accept",
        headers=auth_headers2,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"


@pytest.mark.asyncio
async def test_list_friends(client: AsyncClient, auth_headers, auth_headers2, test_user, test_user2):
    resp = await client.post(
        "/api/friends/requests",
        json={"username": test_user2.username},
        headers=auth_headers,
    )
    friend_id = resp.json()["id"]
    await client.post(f"/api/friends/requests/{friend_id}/accept", headers=auth_headers2)

    resp = await client.get("/api/friends", headers=auth_headers)
    assert resp.status_code == 200
    friends = resp.json()
    assert len(friends) == 1
    assert friends[0]["username"] == test_user2.username


@pytest.mark.asyncio
async def test_list_pending_requests(client: AsyncClient, auth_headers, auth_headers2, test_user2):
    await client.post(
        "/api/friends/requests",
        json={"username": test_user2.username},
        headers=auth_headers,
    )
    resp = await client.get("/api/friends/requests", headers=auth_headers2)
    assert resp.status_code == 200
    requests = resp.json()
    assert len(requests) == 1
