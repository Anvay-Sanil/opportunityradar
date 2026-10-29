import pytest
from httpx import AsyncClient

class TestProfile:
    @pytest.mark.asyncio
    async def test_create_profile(self, client: AsyncClient, auth_headers):
        resp = await client.put("/api/profile", json={
            "college": "MUJ",
            "year": "3rd Year",
            "branch": "Computer Science",
            "degree": "B.Tech",
            "skills": ["Python", "React", "TypeScript"],
            "preferred_domains": ["Software Development"],
            "preferred_locations": ["Bangalore", "Remote"],
            "work_mode": "remote",
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["college"] == "MUJ"
        assert "Python" in data["skills"]

    @pytest.mark.asyncio
    async def test_get_profile(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/profile", headers=auth_headers)
        assert resp.status_code in (200, 404)

    @pytest.mark.asyncio
    async def test_profile_requires_auth(self, client: AsyncClient):
        resp = await client.put("/api/profile", json={"college": "MUJ"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_incomplete_profile_returns_validation_error(self, client, auth_headers):
        response = await client.put("/api/profile", json={"year": "Graduate"}, headers=auth_headers)
        assert response.status_code == 422
        response = await client.put("/api/profile", json={"year": "Graduate", "branch": "Computer Science"}, headers=auth_headers)
        assert response.status_code == 200
        response = await client.put("/api/profile", json={"bio": "Updated"}, headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["branch"] == "Computer Science"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("changes", [{"year": "Graduated"}, {"year": None}, {"branch": None}, {"skills": None}, {"branch": "x" * 201}, {"work_mode": "invalid"}])
    async def test_invalid_profile_cannot_corrupt_saved_data(self, client, auth_headers, changes):
        valid = {"year": "Graduate", "branch": "Computer Science", "skills": ["Python"]}
        assert (await client.put("/api/profile", json=valid, headers=auth_headers)).status_code == 200
        response = await client.put("/api/profile", json=changes, headers=auth_headers)
        assert response.status_code == 422
        saved = (await client.get("/api/profile", headers=auth_headers)).json()
        assert saved["year"] == "Graduate" and saved["skills"] == ["Python"]
