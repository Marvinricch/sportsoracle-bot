import aiohttp
import asyncio
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

BASE_URL = "https://api.football-data.org/v4"

# football-data.org free tier competition IDs
FREE_COMPETITIONS = {
    "PL":  {"name": "Premier League",     "country": "England"},
    "PD":  {"name": "La Liga",            "country": "Spain"},
    "SA":  {"name": "Serie A",            "country": "Italy"},
    "BL1": {"name": "Bundesliga",         "country": "Germany"},
    "FL1": {"name": "Ligue 1",            "country": "France"},
    "DED": {"name": "Eredivisie",         "country": "Netherlands"},
    "PPL": {"name": "Primeira Liga",      "country": "Portugal"},
    "CL":  {"name": "Champions League",   "country": "Europe"},
    "EL":  {"name": "Europa League",      "country": "Europe"},
    "EC":  {"name": "Euro Championship",  "country": "Europe"},
    "WC":  {"name": "FIFA World Cup",     "country": "World"},
    "BSA": {"name": "Brasileirao",        "country": "Brazil"},
}


class FootballAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "X-Auth-Token": api_key,
            "Content-Type": "application/json"
        }

    async def _get(self, endpoint: str, params: dict = None):
        url = f"{BASE_URL}/{endpoint}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers, params=params or {}) as resp:
                if resp.status == 429:
                    raise Exception("Rate limit hit. Free plan allows 10 requests/minute.")
                if resp.status == 403:
                    raise Exception("API key invalid or permission denied.")
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"API error {resp.status}: {text}")
                return await resp.json()

    # ── FIXTURES ──────────────────────────────────────────────────────────────

    async def get_todays_fixtures(self):
        """Get all today's matches across all free competitions"""
        today = datetime.now().strftime("%Y-%m-%d")
        all_fixtures = []

        tasks = [
            self._get_competition_matches(code, today, today)
            for code in FREE_COMPETITIONS
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for code, result in zip(FREE_COMPETITIONS.keys(), results):
            if isinstance(result, Exception):
                logger.debug(f"Skipping {code}: {result}")
                continue
            matches = result.get("matches", [])
            comp_info = FREE_COMPETITIONS[code]
            for m in matches:
                if m.get("status") in ("SCHEDULED", "TIMED"):
                    all_fixtures.append(self._normalize_match(m, comp_info))

        return all_fixtures

    async def _get_competition_matches(self, competition_code: str, date_from: str, date_to: str):
        return await self._get(
            f"competitions/{competition_code}/matches",
            {"dateFrom": date_from, "dateTo": date_to}
        )

    async def get_fixture_by_id(self, fixture_id: int):
        data = await self._get(f"matches/{fixture_id}")
        if not data:
            return None
        comp_code = data.get("competition", {}).get("code", "")
        comp_info = FREE_COMPETITIONS.get(comp_code, {
            "name": data.get("competition", {}).get("name", "Unknown"),
            "country": data.get("area", {}).get("name", "Unknown")
        })
        return self._normalize_match(data, comp_info)

    async def search_fixture(self, query: str):
        """Search upcoming fixtures by team names"""
        parts = [p.strip() for p in query.lower().split("vs")]
        if len(parts) != 2:
            return None
        home_name, away_name = parts[0].strip(), parts[1].strip()

        today = datetime.now().strftime("%Y-%m-%d")
        end = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

        tasks = [
            self._get_competition_matches(code, today, end)
            for code in FREE_COMPETITIONS
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for code, result in zip(FREE_COMPETITIONS.keys(), results):
            if isinstance(result, Exception):
                continue
            for m in result.get("matches", []):
                home = m["homeTeam"]["name"].lower()
                away = m["awayTeam"]["name"].lower()
                if (home_name in home and away_name in away) or \
                   (away_name in home and home_name in away):
                    return self._normalize_match(m, FREE_COMPETITIONS[code])
        return None

    async def get_fixtures_by_date(self, date: str):
        return await self.get_todays_fixtures()

    # ── TEAM MATCHES (for form) ────────────────────────────────────────────────

    async def get_team_last_matches(self, team_id: int, last: int = 5):
        try:
            data = await self._get(f"teams/{team_id}/matches", {
                "status": "FINISHED",
                "limit": last
            })
            matches = data.get("matches", [])
            return [self._normalize_match(m, {"name": "Unknown", "country": "Unknown"}) for m in matches[-last:]]
        except Exception as e:
            logger.debug(f"Form fetch failed for team {team_id}: {e}")
            return []

    # ── HEAD TO HEAD ──────────────────────────────────────────────────────────

    async def get_head_to_head(self, team1_id: int, team2_id: int, last: int = 10):
        try:
            data = await self._get(f"teams/{team1_id}/matches", {
                "status": "FINISHED",
                "limit": 30
            })
            all_matches = data.get("matches", [])
            h2h = [
                m for m in all_matches
                if m.get("homeTeam", {}).get("id") == team2_id
                or m.get("awayTeam", {}).get("id") == team2_id
            ]
            return [self._normalize_match(m, {}) for m in h2h[:last]]
        except Exception as e:
            logger.debug(f"H2H fetch failed: {e}")
            return []

    # ── STANDINGS ─────────────────────────────────────────────────────────────

    async def get_standings(self, competition_code: str = "PL", season: int = None):
        try:
            params = {}
            if season:
                params["season"] = season
            return await self._get(f"competitions/{competition_code}/standings", params)
        except Exception as e:
            logger.debug(f"Standings fetch failed: {e}")
            return None

    # ── NOT AVAILABLE ON FREE PLAN ────────────────────────────────────────────

    async def get_fixture_predictions(self, fixture_id: int):
        return None  # Generated from stats instead

    async def get_fixture_odds(self, fixture_id: int):
        return []

    async def get_injuries(self, fixture_id: int):
        return []

    async def get_fixture_lineups(self, fixture_id: int):
        return []

    async def get_fixture_statistics(self, fixture_id: int):
        return []

    async def get_team_statistics(self, team_id: int, league_id: int = None, season: int = None):
        return {}

    # ── NORMALIZER ────────────────────────────────────────────────────────────

    def _normalize_match(self, m: dict, comp_info: dict) -> dict:
        """Normalize football-data.org format to internal format"""
        home_team = m.get("homeTeam", {})
        away_team = m.get("awayTeam", {})
        score = m.get("score", {})
        ft = score.get("fullTime", {})
        comp = m.get("competition", {})

        return {
            "fixture": {
                "id": m.get("id"),
                "date": m.get("utcDate", ""),
                "status": m.get("status", ""),
                "venue": {"name": "N/A"}
            },
            "league": {
                "id": comp.get("id"),
                "name": comp_info.get("name") or comp.get("name", "Unknown"),
                "country": comp_info.get("country") or m.get("area", {}).get("name", "Unknown"),
                "code": comp.get("code", "")
            },
            "teams": {
                "home": {
                    "id": home_team.get("id"),
                    "name": home_team.get("name", "Unknown"),
                    "shortName": home_team.get("shortName", "")
                },
                "away": {
                    "id": away_team.get("id"),
                    "name": away_team.get("name", "Unknown"),
                    "shortName": away_team.get("shortName", "")
                }
            },
            "goals": {
                "home": ft.get("home"),
                "away": ft.get("away")
            },
            "score": {
                "fulltime": {
                    "home": ft.get("home"),
                    "away": ft.get("away")
                }
            }
        }
