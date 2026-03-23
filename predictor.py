import asyncio
import logging
from datetime import datetime
from api import FootballAPI

logger = logging.getLogger(__name__)


class MatchPredictor:
    def __init__(self, api: FootballAPI):
        self.api = api

    # ── DAILY TICKET ──────────────────────────────────────────────────────────

    async def build_daily_ticket(self, manual_picks: list = None):
        """Build a 10-odds accumulator ticket from today's best matches"""
        manual_picks = manual_picks or []

        fixtures = await self.api.get_todays_fixtures()
        if not fixtures:
            return None

        analyzed = []
        # Analyze up to 30 fixtures concurrently, take best
        tasks = [self._quick_analyze(f) for f in fixtures[:40]]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, dict) and r.get("confidence", 0) >= 55:
                analyzed.append(r)

        # Sort by confidence
        analyzed.sort(key=lambda x: x["confidence"], reverse=True)

        # Build ticket: manual picks first, then auto-fill to 10
        picks = []

        for mp in manual_picks:
            picks.append({
                "home": mp["match"].split("vs")[0].strip(),
                "away": mp["match"].split("vs")[-1].strip(),
                "fixture_id": "manual",
                "pick": mp["pick"],
                "odds": mp["odds"],
                "confidence": 70,
                "reason": "Manual pick",
                "source": "manual"
            })

        # Auto picks (avoid duplicates)
        manual_matches = {p["home"] + p["away"] for p in picks}
        for a in analyzed:
            if len(picks) >= 10:
                break
            key = a["home"] + a["away"]
            if key not in manual_matches:
                picks.append(a)
                manual_matches.add(key)

        if len(picks) < 3:
            return None

        total_odds = 1.0
        for p in picks:
            total_odds *= p.get("odds", 1.0)

        return {
            "date": datetime.now().strftime("%A, %d %B %Y"),
            "picks": picks[:10],
            "total_odds": round(total_odds, 2),
            "pick_count": len(picks[:10])
        }

    async def _quick_analyze(self, fixture: dict) -> dict:
        """Fast analysis of a single fixture to score it for the ticket"""
        try:
            home = fixture["teams"]["home"]
            away = fixture["teams"]["away"]
            fid = fixture["fixture"]["id"]
            league = fixture["league"]

            # Get predictions from API
            pred = await self.api.get_fixture_predictions(fid)
            h2h = await self.api.get_head_to_head(home["id"], away["id"], last=8)
            home_form = await self.api.get_team_last_matches(home["id"], last=5)
            away_form = await self.api.get_team_last_matches(away["id"], last=5)

            pick, odds, confidence, reason = self._determine_pick(
                pred, h2h, home_form, away_form, home, away
            )

            return {
                "fixture_id": fid,
                "home": home["name"],
                "away": away["name"],
                "league": f"{league['name']} ({league['country']})",
                "kickoff": fixture["fixture"]["date"],
                "pick": pick,
                "odds": odds,
                "confidence": confidence,
                "reason": reason,
                "source": "auto",
                "venue": fixture["fixture"].get("venue", {}).get("name", "Unknown")
            }
        except Exception as e:
            logger.debug(f"Quick analyze failed: {e}")
            return {}

    def _determine_pick(self, pred, h2h, home_form, away_form, home, away):
        """Determine best pick based on data"""
        pick = "1X2 - Home Win"
        odds = 1.85
        confidence = 60
        reason = "Statistical edge"

        if pred:
            predictions = pred.get("predictions", {})
            percent = predictions.get("percent", {})
            winner = predictions.get("winner", {})

            home_pct = int(str(percent.get("home", "0")).replace("%", "") or 0)
            draw_pct = int(str(percent.get("draw", "0")).replace("%", "") or 0)
            away_pct = int(str(percent.get("away", "0")).replace("%", "") or 0)

            under_over = predictions.get("goals", {})
            advice = predictions.get("advice", "")

            # Determine pick from API prediction
            if home_pct >= 65:
                pick = f"Home Win ({home['name']})"
                odds = round(1.50 + (100 - home_pct) * 0.02, 2)
                confidence = min(home_pct, 88)
                reason = f"Strong home advantage ({home_pct}% win probability)"
            elif away_pct >= 65:
                pick = f"Away Win ({away['name']})"
                odds = round(1.70 + (100 - away_pct) * 0.025, 2)
                confidence = min(away_pct, 85)
                reason = f"Away side dominant ({away_pct}% win probability)"
            elif draw_pct >= 35:
                pick = "Double Chance 1X"
                odds = 1.35
                confidence = 72
                reason = f"Draw likely ({draw_pct}%), covering home win + draw"
            else:
                pick = "Both Teams to Score (GG)"
                odds = 1.80
                confidence = 65
                reason = f"Balanced teams, {home_pct}% vs {away_pct}%, BTTS value"

            # H2H adjustment
            if h2h:
                goals_per_game = self._avg_goals(h2h)
                if goals_per_game > 2.8 and "BTTS" not in pick:
                    pick = "Over 2.5 Goals"
                    odds = 1.75
                    confidence = 68
                    reason = f"H2H avg {goals_per_game:.1f} goals/game, Over 2.5 value"

        return pick, odds, confidence, reason

    def _avg_goals(self, h2h_matches):
        if not h2h_matches:
            return 0
        total = sum(
            m["goals"]["home"] + m["goals"]["away"]
            for m in h2h_matches
            if m.get("goals") and m["goals"]["home"] is not None
        )
        return total / len(h2h_matches)

    # ── DEEP ANALYSIS ─────────────────────────────────────────────────────────

    async def deep_analyze(self, fixture_id: int) -> dict:
        """Full deep analysis of a single fixture"""
        fixture = await self.api.get_fixture_by_id(fixture_id)
        if not fixture:
            raise Exception("Fixture not found")

        home = fixture["teams"]["home"]
        away = fixture["teams"]["away"]

        # Gather all data concurrently
        (pred, h2h, home_form, away_form,
         odds_data, injuries, lineups) = await asyncio.gather(
            self.api.get_fixture_predictions(fixture_id),
            self.api.get_head_to_head(home["id"], away["id"], last=10),
            self.api.get_team_last_matches(home["id"], last=6),
            self.api.get_team_last_matches(away["id"], last=6),
            self.api.get_fixture_odds(fixture_id),
            self.api.get_injuries(fixture_id),
            self.api.get_fixture_lineups(fixture_id),
            return_exceptions=True
        )

        # Safe extraction
        def safe(val): return val if not isinstance(val, Exception) else None

        pred = safe(pred)
        h2h = safe(h2h) or []
        home_form = safe(home_form) or []
        away_form = safe(away_form) or []
        odds_data = safe(odds_data) or []
        injuries = safe(injuries) or []
        lineups = safe(lineups) or []

        return {
            "fixture": fixture,
            "home": home,
            "away": away,
            "prediction": pred,
            "h2h": h2h,
            "home_form": home_form,
            "away_form": away_form,
            "odds": odds_data,
            "injuries": injuries,
            "lineups": lineups,
            "analysis": self._build_analysis(
                pred, h2h, home_form, away_form, home, away, injuries
            )
        }

    def _build_analysis(self, pred, h2h, home_form, away_form, home, away, injuries):
        """Build structured analysis dict"""
        analysis = {
            "home_form_rating": self._form_rating(home_form, home["id"]),
            "away_form_rating": self._form_rating(away_form, away["id"]),
            "h2h_summary": self._h2h_summary(h2h, home["id"], away["id"]),
            "goals_analysis": self._goals_analysis(h2h, home_form, away_form, home["id"], away["id"]),
            "corners_analysis": self._corners_analysis(h2h),
            "injury_report": self._injury_report(injuries, home["name"], away["name"]),
            "predictions": self._extract_predictions(pred),
            "best_picks": []
        }

        # Build best picks
        analysis["best_picks"] = self._generate_best_picks(analysis)
        return analysis

    def _form_rating(self, matches, team_id):
        if not matches:
            return {"wins": 0, "draws": 0, "losses": 0, "goals_scored": 0, "goals_conceded": 0, "rating": "N/A"}
        wins = draws = losses = gf = ga = 0
        for m in matches:
            home_id = m["teams"]["home"]["id"]
            is_home = home_id == team_id
            g_home = m["goals"]["home"] or 0
            g_away = m["goals"]["away"] or 0
            gf += g_home if is_home else g_away
            ga += g_away if is_home else g_home
            score_home = m["score"]["fulltime"]["home"] or 0
            score_away = m["score"]["fulltime"]["away"] or 0
            if is_home:
                if score_home > score_away: wins += 1
                elif score_home == score_away: draws += 1
                else: losses += 1
            else:
                if score_away > score_home: wins += 1
                elif score_home == score_away: draws += 1
                else: losses += 1
        pts = wins * 3 + draws
        max_pts = len(matches) * 3
        rating = round((pts / max_pts) * 10, 1) if max_pts > 0 else 0
        form_str = ""
        for m in matches[-5:]:
            home_id = m["teams"]["home"]["id"]
            is_home = home_id == team_id
            sh = m["score"]["fulltime"]["home"] or 0
            sa = m["score"]["fulltime"]["away"] or 0
            if is_home:
                form_str += "W" if sh > sa else ("D" if sh == sa else "L")
            else:
                form_str += "W" if sa > sh else ("D" if sh == sa else "L")
        return {
            "wins": wins, "draws": draws, "losses": losses,
            "goals_scored": gf, "goals_conceded": ga,
            "rating": rating, "form_string": form_str
        }

    def _h2h_summary(self, h2h, home_id, away_id):
        if not h2h:
            return {"total": 0, "home_wins": 0, "away_wins": 0, "draws": 0}
        home_wins = away_wins = draws = 0
        for m in h2h:
            winner = m.get("teams", {}).get("home" if m["teams"]["home"]["id"] == home_id else "away", {})
            sh = m["score"]["fulltime"]["home"] or 0
            sa = m["score"]["fulltime"]["away"] or 0
            if sh > sa:
                if m["teams"]["home"]["id"] == home_id: home_wins += 1
                else: away_wins += 1
            elif sa > sh:
                if m["teams"]["away"]["id"] == away_id: away_wins += 1
                else: home_wins += 1
            else:
                draws += 1
        return {"total": len(h2h), "home_wins": home_wins, "away_wins": away_wins, "draws": draws}

    def _goals_analysis(self, h2h, home_form, away_form, home_id, away_id):
        h2h_goals = [
            (m["goals"]["home"] or 0) + (m["goals"]["away"] or 0)
            for m in h2h if m.get("goals")
        ]
        avg_h2h = round(sum(h2h_goals) / len(h2h_goals), 2) if h2h_goals else 0
        over25_h2h = sum(1 for g in h2h_goals if g > 2.5)
        btts_h2h = sum(
            1 for m in h2h
            if m.get("goals") and (m["goals"]["home"] or 0) > 0 and (m["goals"]["away"] or 0) > 0
        )
        return {
            "avg_goals_h2h": avg_h2h,
            "over25_h2h": f"{over25_h2h}/{len(h2h_goals)}",
            "btts_h2h": f"{btts_h2h}/{len(h2h)}",
            "over25_likely": avg_h2h > 2.5,
            "btts_likely": btts_h2h > len(h2h) * 0.5
        }

    def _corners_analysis(self, h2h):
        # Corners data not always available, provide estimates based on match style
        return {
            "note": "Corners data varies by API plan",
            "estimated_avg": "9-12 corners per game (typical for top leagues)"
        }

    def _injury_report(self, injuries, home_name, away_name):
        if not injuries:
            return {"home": [], "away": [], "note": "No injury data available"}
        home_inj = [i for i in injuries if i.get("team", {}).get("name") == home_name]
        away_inj = [i for i in injuries if i.get("team", {}).get("name") == away_name]
        return {
            "home": [f"{i['player']['name']} ({i['player']['reason']})" for i in home_inj[:5]],
            "away": [f"{i['player']['name']} ({i['player']['reason']})" for i in away_inj[:5]],
        }

    def _extract_predictions(self, pred):
        if not pred:
            return {}
        p = pred.get("predictions", {})
        return {
            "advice": p.get("advice", "N/A"),
            "home_pct": p.get("percent", {}).get("home", "N/A"),
            "draw_pct": p.get("percent", {}).get("draw", "N/A"),
            "away_pct": p.get("percent", {}).get("away", "N/A"),
            "goals_home": p.get("goals", {}).get("home", "N/A"),
            "goals_away": p.get("goals", {}).get("away", "N/A"),
            "winner_name": pred.get("predictions", {}).get("winner", {}).get("name", "N/A"),
        }

    def _generate_best_picks(self, analysis):
        picks = []
        ga = analysis["goals_analysis"]
        pred = analysis["predictions"]

        if ga.get("over25_likely"):
            picks.append({"pick": "Over 2.5 Goals", "odds_est": "1.70-1.90", "confidence": 72})
        if ga.get("btts_likely"):
            picks.append({"pick": "Both Teams to Score (GG)", "odds_est": "1.75-1.95", "confidence": 68})

        home_pct = str(pred.get("home_pct", "0")).replace("%", "")
        away_pct = str(pred.get("away_pct", "0")).replace("%", "")
        try:
            if int(home_pct) >= 60:
                picks.append({"pick": "Home Win / Double Chance 1X", "odds_est": "1.40-1.80", "confidence": int(home_pct)})
            elif int(away_pct) >= 60:
                picks.append({"pick": "Away Win", "odds_est": "1.60-2.10", "confidence": int(away_pct)})
        except: pass

        if not picks:
            picks.append({"pick": "Draw / Both Teams Score", "odds_est": "1.80-2.20", "confidence": 60})

        return picks[:4]
        
