"""
Integration tests for User Authentication and Organization tenancy.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_signup_and_login_flow(client: AsyncClient):
    # 1. Signup
    signup_data = {
        "email": "testceo@enterprise.com",
        "password": "StrongPassword123!",
        "full_name": "Enterprise CEO",
    }
    res = await client.post("/api/v1/auth/signup", json=signup_data)
    assert res.status_code == 201
    payload = res.json()
    assert "user" in payload
    assert payload["user"]["email"] == "testceo@enterprise.com"
    assert "tokens" in payload
    access_token = payload["tokens"]["access_token"]
    assert access_token is not None

    # 2. Login
    login_data = {
        "email": "testceo@enterprise.com",
        "password": "StrongPassword123!",
    }
    res_login = await client.post("/api/v1/auth/login", json=login_data)
    assert res_login.status_code == 200
    login_payload = res_login.json()
    assert "tokens" in login_payload

    # 3. Access protected profile
    headers = {"Authorization": f"Bearer {access_token}"}
    res_me = await client.get("/api/v1/users/me", headers=headers)
    assert res_me.status_code == 200
    assert res_me.json()["full_name"] == "Enterprise CEO"


@pytest.mark.asyncio
async def test_invalid_login_credentials(client: AsyncClient):
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@user.com", "password": "WrongPassword"},
    )
    assert res.status_code == 401
    assert res.json()["error"] is True
