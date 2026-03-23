from datetime import datetime


class MessageFormatter:

    def format_daily_ticket(self, ticket: dict) -> str:
        date = ticket["date"]
        picks = ticket["picks"]
        total_odds = ticket["total_odds"]

        lines = [
            "🏆 *SPORTSORAL CLE — DAILY 10-ODDS TICKET*",
            f"📅 {date}",
            "━━━━━━━━━━━━━━━━━━━━━━━\n",
        ]

        for i, pick in enumerate(picks, 1):
            confidence = pick.get("confidence", 0)
            conf_bar = self._confidence_bar(confidence)
            kickoff = self._format_time(pick.get("kickoff", ""))
            source_tag = "🔵 AUTO" if pick.get("source") == "auto" else "🟡 MANUAL"

            lines.append(f"*{i}.* ⚽ {pick['home']} vs {pick['away']}")
            lines.append(f"   🏟 {pick.get('league', 'Unknown League')}")
            lines.append(f"   ⏰ {kickoff}  {source_tag}")
            lines.append(f"   📌 Pick: *{pick['pick']}*")
            lines.append(f"   💰 Odds: *{pick.get('odds', 'N/A')}*")
            lines.append(f"   🎯 Confidence: {conf_bar} {confidence}%")
            lines.append(f"   💡 _{pick.get('reason', '')}_\n")

        lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"📊 *Total Picks:* {len(picks)}")
        lines.append(f"💥 *Combined Odds: {total_odds}x*")
        lines.append("\n⚠️ _Bet responsibly. Predictions are for informational purposes only._")
        lines.append("🔍 *Tap below to deep-analyze any match*")

        return "\n".join(lines)

    def format_deep_analysis(self, data: dict) -> str:
        fixture = data["fixture"]
        home = data["home"]
        away = data["away"]
        analysis = data["analysis"]
        pred = analysis["predictions"]
        home_form = analysis["home_form_rating"]
        away_form = analysis["away_form_rating"]
        h2h = analysis["h2h_summary"]
        goals = analysis["goals_analysis"]
        injuries = analysis["injury_report"]
        best_picks = analysis["best_picks"]

        league = fixture.get("league", {})
        kickoff = self._format_time(fixture["fixture"].get("date", ""))
        venue = fixture["fixture"].get("venue", {}).get("name", "Unknown")

        lines = [
            f"🔍 *DEEP MATCH ANALYSIS*",
            f"━━━━━━━━━━━━━━━━━━━━━━━",
            f"⚽ *{home['name']} vs {away['name']}*",
            f"🏆 {league.get('name', 'N/A')} — {league.get('country', 'N/A')}",
            f"🏟 {venue}",
            f"⏰ Kickoff: *{kickoff}*\n",

            # Win probability
            "📊 *WIN PROBABILITY*",
            f"🏠 {home['name']}: *{pred.get('home_pct', 'N/A')}*",
            f"🤝 Draw: *{pred.get('draw_pct', 'N/A')}*",
            f"✈️ {away['name']}: *{pred.get('away_pct', 'N/A')}*",
            f"🧠 API Advice: _{pred.get('advice', 'N/A')}_\n",

            # Form
            "📈 *RECENT FORM (last 5/6 games)*",
            f"🏠 {home['name']}: `{home_form.get('form_string', 'N/A')}` | Rating: *{home_form.get('rating', 'N/A')}/10*",
            f"   W:{home_form['wins']} D:{home_form['draws']} L:{home_form['losses']} | GF:{home_form['goals_scored']} GA:{home_form['goals_conceded']}",
            f"✈️ {away['name']}: `{away_form.get('form_string', 'N/A')}` | Rating: *{away_form.get('rating', 'N/A')}/10*",
            f"   W:{away_form['wins']} D:{away_form['draws']} L:{away_form['losses']} | GF:{away_form['goals_scored']} GA:{away_form['goals_conceded']}\n",

            # H2H
            "🔄 *HEAD-TO-HEAD (last 10 meetings)*",
            f"🏠 {home['name']} wins: *{h2h['home_wins']}*",
            f"🤝 Draws: *{h2h['draws']}*",
            f"✈️ {away['name']} wins: *{h2h['away_wins']}*",
            f"📊 Total analyzed: {h2h['total']} games\n",

            # Goals
            "⚽ *GOALS ANALYSIS*",
            f"📊 Avg goals/game (H2H): *{goals['avg_goals_h2h']}*",
            f"🎯 Over 2.5 in H2H: *{goals['over25_h2h']}*",
            f"🔥 BTTS in H2H: *{goals['btts_h2h']}*",
            f"✅ Over 2.5 Likely: {'*YES* 🟢' if goals['over25_likely'] else '*NO* 🔴'}",
            f"✅ BTTS Likely: {'*YES* 🟢' if goals['btts_likely'] else '*NO* 🔴'}\n",

            # Expected goals
            "📐 *EXPECTED GOALS (API)*",
            f"🏠 {home['name']}: *{pred.get('goals_home', 'N/A')}* xG",
            f"✈️ {away['name']}: *{pred.get('goals_away', 'N/A')}* xG\n",

            # Injuries
            "🏥 *INJURY REPORT*",
        ]

        home_inj = injuries.get("home", [])
        away_inj = injuries.get("away", [])
        if home_inj:
            lines.append(f"🏠 {home['name']} injuries:")
            for inj in home_inj:
                lines.append(f"   ❌ {inj}")
        else:
            lines.append(f"🏠 {home['name']}: ✅ No major injuries reported")
        if away_inj:
            lines.append(f"✈️ {away['name']} injuries:")
            for inj in away_inj:
                lines.append(f"   ❌ {inj}")
        else:
            lines.append(f"✈️ {away['name']}: ✅ No major injuries reported")

        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("🎯 *BEST PICKS FOR THIS MATCH*")
        for bp in best_picks:
            conf = bp.get("confidence", 0)
            bar = self._confidence_bar(conf)
            lines.append(f"\n✅ *{bp['pick']}*")
            lines.append(f"   💰 Odds estimate: {bp['odds_est']}")
            lines.append(f"   🎯 Confidence: {bar} {conf}%")

        lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("⚠️ _Analysis for informational use only. Bet responsibly._")

        return "\n".join(lines)

    def format_fixtures(self, fixtures: list) -> str:
        lines = [
            "📋 *TODAY'S UPCOMING FIXTURES*",
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        ]

        for f in fixtures:
            home = f["teams"]["home"]["name"]
            away = f["teams"]["away"]["name"]
            league = f["league"]["name"]
            country = f["league"]["country"]
            kickoff = self._format_time(f["fixture"].get("date", ""))
            lines.append(f"⚽ *{home} vs {away}*")
            lines.append(f"🏆 {league} ({country})")
            lines.append(f"⏰ {kickoff}\n")

        lines.append(f"_Showing {len(fixtures)} fixtures — tap to analyze_")
        return "\n".join(lines)

    def _confidence_bar(self, confidence: int) -> str:
        filled = int(confidence / 10)
        empty = 10 - filled
        return "🟩" * filled + "⬜" * empty

    def _format_time(self, iso_str: str) -> str:
        try:
            dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            return dt.strftime("%H:%M UTC, %d %b")
        except:
            return iso_str or "TBC"
