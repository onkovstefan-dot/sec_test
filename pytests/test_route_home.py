from __future__ import annotations

from app import create_app


def test_home_page_renders_html():
    app = create_app()
    client = app.test_client()

    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.content_type.startswith("text/html")

    html = resp.get_data(as_text=True)
    # Basic marker that should stay stable for the frontend.
    assert "<!doctype html" in html.lower() or "<html" in html.lower()
