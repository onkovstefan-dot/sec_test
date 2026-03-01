from __future__ import annotations

import re

import pytest

playwright = pytest.importorskip("playwright")
from playwright.sync_api import Page, expect  # type: ignore


def test_check_cik_cards_expand_and_navigate(page: Page, seeded_live_server):
    page.goto(f"{seeded_live_server.base_url}/check-cik", wait_until="domcontentloaded")

    # At least one card should be present.
    cards = page.locator("details.cik-card")
    expect(cards).to_have_count(2)

    first = cards.nth(0)

    # Expand the first card.
    first.locator("summary").click()
    expect(first).to_have_attribute("open", "")

    # Button exists and navigates to daily values.
    open_btn = first.get_by_role("link", name="Open daily values")
    expect(open_btn).to_be_visible()

    open_btn.click()
    expect(page).to_have_url(re.compile(r".*/daily-values(\?.*)?$"))

    # Daily values page should render a table.
    expect(page.locator("table")).to_be_visible()


def test_check_cik_load_more_button_hidden_when_no_more(page: Page, seeded_live_server):
    page.goto(f"{seeded_live_server.base_url}/check-cik", wait_until="domcontentloaded")

    # With only 2 seeded entities, the button should not exist.
    expect(page.locator("#load-more")).to_have_count(0)
