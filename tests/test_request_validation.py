"""
`max_comments` is checked the same way on every route that starts a run.

Until 26 Sep 2026 only /sweep/start checked it. /analyse and /analyse/start ran
`int(body["max_comments"])` unguarded, so a non-number was a 500 (a server
fault reported for a bad request) and a large number was passed to YouTube.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

import app as app_module

VIDEO = "https://youtu.be/dQw4w9WgXcQ"
ROUTES = {
    "/analyse": {"video_url": VIDEO, "brand_name": "B"},
    "/analyse/start": {"video_url": VIDEO, "brand_name": "B", "product_name": "Never Saved"},
    "/sweep/start": {"subject": "Acme", "video_ids": ["dQw4w9WgXcQ"]},
}


@pytest.fixture()
def client():
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


@pytest.mark.parametrize("route", sorted(ROUTES))
@pytest.mark.parametrize("value,reason", [
    ("lots", "whole number"), (None, "whole number"), ([], "whole number"),
    (0, "between 1 and 500"), (-5, "between 1 and 500"), (501, "between 1 and 500"),
    (10 ** 9, "between 1 and 500"),
])
def test_a_bad_max_comments_is_a_400_on_every_route(client, route, value, reason):
    with patch("app.fetch_comments") as fetch, patch("app._claim_worker") as claim:
        response = client.post(route, json=dict(ROUTES[route], max_comments=value))
    assert response.status_code == 400
    assert reason in response.get_json()["error"]
    fetch.assert_not_called()
    claim.assert_not_called()


@pytest.mark.parametrize("value", [1, 100, 500, "250"])
def test_the_helper_accepts_the_range_it_names(value):
    assert app_module._max_comments({"max_comments": value}) == (int(value), None)


def test_absent_means_the_default_of_100():
    assert app_module._max_comments({}) == (100, None)
