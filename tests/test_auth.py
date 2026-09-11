import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register(client: AsyncClient):
    resp = await client.post("/api/auth/register", json={
        "phone": "+8613800000003",
        "username": "charlie",
        "display_name": "Charlie",
        "password": "password123",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["username"] == "charlie"


@pytest.mark.asyncio
async def test_register_duplicate_phone(client: AsyncClient):
    await client.post("/api/auth/register", json={
        "phone": "+8613800000003",
        "username": "charlie",
        "display_name": "Charlie",
        "password": "password123",
    })
    resp = await client.post("/api/auth/register", json={
        "phone": "+8613800000003",
        "username": "charlie2",
        "display_name": "Charlie2",
        "password": "password123",
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_register_duplicate_username(client: AsyncClient):
    await client.post("/api/auth/register", json={
        "phone": "+8613800000003",
        "username": "charlie",
        "display_name": "Charlie",
        "password": "password123",
    })
    resp = await client.post("/api/auth/register", json={
        "phone": "+8613800000004",
        "username": "charlie",
        "display_name": "Charlie2",
        "password": "password123",
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_login(client: AsyncClient, test_user):
    resp = await client.post("/api/auth/login", json={
        "phone": test_user.phone,
        "password": "password123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["username"] == test_user.username


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, test_user):
    resp = await client.post("/api/auth/login", json={
        "phone": test_user.phone,
        "password": "wrongpassword",
    })
    assert resp.status_code == 401
