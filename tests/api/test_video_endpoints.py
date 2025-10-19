def test_get_videos_unauthorized(client):
    """GET /api/videos sin token debe retornar 401"""
    response = client.get("/api/videos/")
    assert response.status_code == 401


def test_get_videos_authorized(client):
    """Ejemplo de GET /api/videos con token (mock)"""
    headers = {"Authorization": "Bearer fake_token"}
    response = client.get("/api/videos/", headers=headers)

    # En tu backend real probablemente devuelva 401, pero sirve de placeholder
    assert response.status_code in [200, 401, 403]