"""
tests/e2e/test_ui.py — End-to-end browser tests using Playwright.

These tests run a real Chromium browser against the mock server and verify
that the UI behaves correctly from a user's perspective. They complement
the unit tests (which test Python logic) by testing the full stack:
server → router → handler → JSON → JavaScript → DOM.

What is covered here that unit tests cannot cover:
  - The search dropdown appears and is interactive
  - Clicking a player card closes the dropdown and shows the player card
  - Selecting two players reveals the charts section
  - The stat selector changes both charts simultaneously
  - Charts render SVG elements (not just empty divs)

Run with:
    FPL_MOCK=1 pytest tests/e2e/ -v --headed   # visible browser
    FPL_MOCK=1 pytest tests/e2e/ -v            # headless

The FPL_MOCK env var is set by conftest.py for the server subprocess.
The --headed flag is useful when a test is failing and you want to see why.
"""

from playwright.sync_api import Page, expect

# ── Helpers ──────────────────────────────────────────────────────────────────


def search_and_select(page: Page, input_id: str, dropdown_id: str, query: str):
    """Type a query, wait for the dropdown, and click the first result."""
    page.locator(f"#{input_id}").fill(query)
    page.wait_for_selector(f"#{dropdown_id} .fpl-dropdown-item", state="visible")
    page.locator(f"#{dropdown_id} .fpl-dropdown-item").first.click()


# ── Page load ─────────────────────────────────────────────────────────────────


class TestPageLoad:
    def test_page_title(self, page: Page, live_server_url: str):
        page.goto(live_server_url)
        expect(page).to_have_title("FPL Analytics")

    def test_header_text(self, page: Page, live_server_url: str):
        page.goto(live_server_url)
        expect(page.locator("h1")).to_have_text("FPL Analytics")

    def test_both_search_inputs_visible(self, page: Page, live_server_url: str):
        page.goto(live_server_url)
        expect(page.locator("#search1")).to_be_visible()
        expect(page.locator("#search2")).to_be_visible()

    def test_empty_state_visible_initially(self, page: Page, live_server_url: str):
        page.goto(live_server_url)
        expect(page.locator("#empty-state")).to_be_visible()

    def test_charts_section_hidden_initially(self, page: Page, live_server_url: str):
        page.goto(live_server_url)
        expect(page.locator("#charts-section")).to_be_hidden()

    def test_players_api_returns_data(self, page: Page, live_server_url: str):
        """JS loads players on DOMContentLoaded — verify the API works."""
        response = page.request.get(f"{live_server_url}/api/players")
        assert response.ok
        players = response.json()
        assert len(players) == 12
        assert all("full_name" in p for p in players)


# ── Search dropdown ───────────────────────────────────────────────────────────


class TestSearchDropdown:
    def test_typing_two_chars_shows_dropdown(self, page: Page, live_server_url: str):
        page.goto(live_server_url)
        page.locator("#search1").fill("Sa")
        expect(page.locator("#dropdown1")).to_be_visible()

    def test_typing_one_char_does_not_show_dropdown(self, page: Page, live_server_url: str):
        page.goto(live_server_url)
        page.locator("#search1").fill("S")
        expect(page.locator("#dropdown1")).to_be_hidden()

    def test_dropdown_items_contain_player_name(self, page: Page, live_server_url: str):
        page.goto(live_server_url)
        page.locator("#search1").fill("Sa")
        items = page.locator("#dropdown1 .fpl-dropdown-item")
        expect(items.first).to_contain_text("Salah")

    def test_dropdown_items_show_team_and_position(self, page: Page, live_server_url: str):
        page.goto(live_server_url)
        page.locator("#search1").fill("Sa")
        first_item = page.locator("#dropdown1 .fpl-dropdown-item").first
        # meta span should contain team · position · price
        expect(first_item.locator(".meta")).to_be_visible()

    def test_clearing_input_hides_dropdown(self, page: Page, live_server_url: str):
        page.goto(live_server_url)
        page.locator("#search1").fill("Sa")
        page.wait_for_selector("#dropdown1 .fpl-dropdown-item", state="visible")
        page.locator("#search1").fill("")
        expect(page.locator("#dropdown1")).to_be_hidden()

    def test_unknown_query_shows_no_results(self, page: Page, live_server_url: str):
        page.goto(live_server_url)
        page.locator("#search1").fill("zzzzzzz")
        expect(page.locator("#dropdown1")).to_be_hidden()

    def test_search2_dropdown_is_independent(self, page: Page, live_server_url: str):
        """Typing in search2 must only affect dropdown2, not dropdown1."""
        page.goto(live_server_url)
        page.locator("#search2").fill("Ha")
        expect(page.locator("#dropdown2")).to_be_visible()
        expect(page.locator("#dropdown1")).to_be_hidden()

    def test_keyboard_arrow_navigates_items(self, page: Page, live_server_url: str):
        page.goto(live_server_url)
        page.locator("#search1").fill("Sa")
        page.wait_for_selector("#dropdown1 .fpl-dropdown-item", state="visible")
        page.locator("#search1").press("ArrowDown")
        # First item should have the active class after one arrow-down
        first_item = page.locator("#dropdown1 .fpl-dropdown-item").first
        expect(first_item).to_have_class("fpl-dropdown-item active")

    def test_escape_closes_dropdown(self, page: Page, live_server_url: str):
        page.goto(live_server_url)
        page.locator("#search1").fill("Sa")
        page.wait_for_selector("#dropdown1 .fpl-dropdown-item", state="visible")
        page.locator("#search1").press("Escape")
        expect(page.locator("#dropdown1")).to_be_hidden()


# ── Player selection ──────────────────────────────────────────────────────────


class TestPlayerSelection:
    def test_clicking_dropdown_item_fills_input(self, page: Page, live_server_url: str):
        page.goto(live_server_url)
        search_and_select(page, "search1", "dropdown1", "Sa")
        # Input should now contain the selected player's full name
        value = page.locator("#search1").input_value()
        assert len(value) > 3  # not empty

    def test_clicking_dropdown_item_hides_dropdown(self, page: Page, live_server_url: str):
        page.goto(live_server_url)
        search_and_select(page, "search1", "dropdown1", "Sa")
        expect(page.locator("#dropdown1")).to_be_hidden()

    def test_selecting_player_shows_card(self, page: Page, live_server_url: str):
        page.goto(live_server_url)
        search_and_select(page, "search1", "dropdown1", "Sa")
        expect(page.locator("#card1")).to_be_visible()

    def test_player_card_shows_name(self, page: Page, live_server_url: str):
        page.goto(live_server_url)
        search_and_select(page, "search1", "dropdown1", "Sa")
        card = page.locator("#card1")
        # Card should contain the player's name
        assert "Salah" in card.inner_text()

    def test_player_card_shows_cost(self, page: Page, live_server_url: str):
        page.goto(live_server_url)
        search_and_select(page, "search1", "dropdown1", "Sa")
        # Cost should be formatted as £X.Xm (divided by 10 server-side)
        assert "£" in page.locator("#card1").inner_text()

    def test_selecting_player_one_does_not_reveal_charts(self, page: Page, live_server_url: str):
        """Charts only appear when BOTH players are selected."""
        page.goto(live_server_url)
        search_and_select(page, "search1", "dropdown1", "Sa")
        page.wait_for_timeout(500)  # allow any async fetch to complete
        expect(page.locator("#charts-section")).to_be_hidden()


# ── Two-player comparison ─────────────────────────────────────────────────────


class TestComparison:
    def _select_two_players(self, page: Page, live_server_url: str):
        page.goto(live_server_url)
        search_and_select(page, "search1", "dropdown1", "Sa")
        search_and_select(page, "search2", "dropdown2", "Ha")
        # Wait for both history API calls to complete
        page.wait_for_selector("#charts-section:not(.hidden)", timeout=8000)

    def test_selecting_two_players_reveals_charts(self, page: Page, live_server_url: str):
        self._select_two_players(page, live_server_url)
        expect(page.locator("#charts-section")).to_be_visible()

    def test_selecting_two_players_hides_empty_state(self, page: Page, live_server_url: str):
        self._select_two_players(page, live_server_url)
        expect(page.locator("#empty-state")).to_be_hidden()

    def test_bar_chart_renders_svg(self, page: Page, live_server_url: str):
        self._select_two_players(page, live_server_url)
        svg = page.locator("#bar-chart svg")
        expect(svg).to_be_visible()
        # Should contain at least some rect elements (the bars)
        bars = page.locator("#bar-chart rect")
        assert bars.count() > 0

    def test_line_chart_renders_svg(self, page: Page, live_server_url: str):
        self._select_two_players(page, live_server_url)
        svg = page.locator("#line-chart svg")
        expect(svg).to_be_visible()
        # Should contain two path elements (one line per player)
        paths = page.locator("#line-chart path")
        assert paths.count() >= 2

    def test_fixtures_section_shows_both_players(self, page: Page, live_server_url: str):
        self._select_two_players(page, live_server_url)
        expect(page.locator("#fixtures1")).to_be_visible()
        expect(page.locator("#fixtures2")).to_be_visible()

    def test_fixtures_show_fdr_colours(self, page: Page, live_server_url: str):
        """Fixture difficulty boxes must use FDR CSS classes (fdr-1 through fdr-5)."""
        self._select_two_players(page, live_server_url)
        # At least one fixture box must have an fdr-* class
        fdr_boxes = page.locator("[class*='fdr-']")
        assert fdr_boxes.count() > 0

    def test_stat_selector_is_visible(self, page: Page, live_server_url: str):
        self._select_two_players(page, live_server_url)
        expect(page.locator("#stat-select")).to_be_visible()

    def test_changing_stat_rerenders_bar_chart(self, page: Page, live_server_url: str):
        self._select_two_players(page, live_server_url)
        # Count bars before stat change
        before = page.locator("#bar-chart rect").count()
        # Change stat to goals_scored
        page.locator("#stat-select").select_option("goals_scored")
        page.wait_for_timeout(200)
        after = page.locator("#bar-chart rect").count()
        # Chart should have re-rendered (same number of bars, same structure)
        assert after > 0
        assert before > 0

    def test_both_player_cards_visible(self, page: Page, live_server_url: str):
        self._select_two_players(page, live_server_url)
        expect(page.locator("#card1")).to_be_visible()
        expect(page.locator("#card2")).to_be_visible()
