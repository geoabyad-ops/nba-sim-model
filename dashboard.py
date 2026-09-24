import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import subprocess
from datetime import datetime
from nba_api.stats.endpoints import scoreboardv3
from nba_api.stats.endpoints import leaguedashteamstats

# --- Logo Database ---
logo_map = {
    "Hawks": "atl", "Celtics": "bos", "Nets": "bkn", "Hornets": "cha",
    "Bulls": "chi", "Cavaliers": "cle", "Mavericks": "dal", "Nuggets": "den",
    "Pistons": "det", "Warriors": "gsw", "Rockets": "hou", "Pacers": "ind",
    "Clippers": "lac", "Lakers": "lal", "Grizzlies": "mem", "Heat": "mia",
    "Bucks": "mil", "Timberwolves": "min", "Pelicans": "nop", "Knicks": "nyk",
    "Thunder": "okc", "Magic": "orl", "76ers": "phi", "Suns": "phx",
    "Trail Blazers": "por", "Kings": "sac", "Spurs": "sas", "Raptors": "tor",
    "Jazz": "uta", "Wizards": "was"
}

def get_logo_url(team_name):
    abbr = logo_map.get(team_name, "nba")
    return f"https://a.espncdn.com/i/teamlogos/nba/500/{abbr}.png"

# --- 1. Page Layout ---
st.set_page_config(page_title="NBA Sim Model", layout="wide", page_icon="🏀")
st.title("🏀 NBA Control Center")

# --- Sidebar Controls ---
with st.sidebar:
    st.header("⚙️ System Controls")
    st.write("Sync your app with your latest Google Sheets and CSV uploads.")
    
    if st.button("🔄 Sync Cloud Data", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.success("✅ App memory wiped and ready for new data!")

# --- 2. Math Engine ---
def calc_win_prob(net_diff, pace):
    exponent = -(net_diff * np.sqrt(pace / 100.0)) / 11.5
    return 1.0 / (1.0 + 10.0 ** exponent)

def run_living_monte_carlo(teams, df_schedule, n_simulations):
    team_names = list(teams.keys())
    sim_wins = {team: np.zeros(n_simulations, dtype=int) for team in team_names}
    current_wins_tracker = {team: 0 for team in team_names}
    
    played_games = df_schedule.dropna(subset=['Home_Score', 'Away_Score'])
    for index, game in played_games.iterrows():
        if game['Home_Score'] > game['Away_Score']:
            sim_wins[game['Home']] += 1
            current_wins_tracker[game['Home']] += 1
        elif game['Away_Score'] > game['Home_Score']:
            sim_wins[game['Away']] += 1
            current_wins_tracker[game['Away']] += 1

    future_games = df_schedule[df_schedule['Home_Score'].isna() | df_schedule['Away_Score'].isna()]
    game_probs, game_pairs = [], []
    
    for index, g in future_games.iterrows():
        h_team, a_team = g["Home"], g["Away"]
        avg_pace = (teams[h_team]["pace"] + teams[a_team]["pace"]) / 2.0
        
        diff = teams[h_team]["active_net_rtg"] - teams[a_team]["active_net_rtg"] + 2.1
        if g["Home_B2B"] == True: diff -= 2.2
        if g["Away_B2B"] == True: diff += 2.2
            
        game_probs.append(calc_win_prob(diff, avg_pace))
        game_pairs.append((h_team, a_team))
        
    if len(game_probs) > 0:
        probs = np.array(game_probs)
        random_draws = np.random.uniform(0.0, 1.0, size=(len(probs), n_simulations))
        home_wins_matrix = random_draws < probs[:, np.newaxis]
        
        for idx, (h_team, a_team) in enumerate(game_pairs):
            sim_wins[h_team] += home_wins_matrix[idx]
            sim_wins[a_team] += (~home_wins_matrix[idx])
            
    results = []
    for team in team_names:
        wins = sim_wins[team]
        results.append({
            "Team": team,
            "Current Wins": current_wins_tracker[team],
            "Projected Wins": np.round(np.mean(wins), 1),
            "10th Pct Floor": int(np.percentile(wins, 10)),
            "90th Pct Ceiling": int(np.percentile(wins, 90)),
        })
        
    return pd.DataFrame(results).sort_values(by="Projected Wins", ascending=False)

# --- 3. Load Databases ---
# ttl=3600 tells the app to hold the data for 1 hour before asking the NBA for an update
@st.cache_data(ttl=3600)
def load_team_data():
    try:
        # 1. Fetch Net Ratings from your CSV instead of the blocked API
        df_nba = pd.read_csv("team_data.csv")
        
        # 2. Fetch your manual Media Ranks live from Google Sheets
        sheet_id = "1MMo_FgfBQdBykFUGjY0ovFxnZPfulx1hX3tGGO06LIQ"
        sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        df_media = pd.read_csv(sheet_url)
        
        teams = {}
        for index, row in df_nba.iterrows():
            team = row['Team']
            
            # Match the CSV data with your Google Sheet
            sheet_row = df_media[df_media['Team'] == team]
            rank = float(sheet_row['media_rank'].values[0]) if not sheet_row.empty else 15.5
            
            net, pace = float(row['net_rtg']), float(row['pace'])
            media_modifier = (15.5 - rank) * 0.20 
            
            teams[team] = {"net_rtg": net, "pace": pace, "media_rank": rank, "active_net_rtg": (net * 0.80) + media_modifier}
            
        return teams
    except Exception as e:
        st.error(f"Team Data Crash: {e}")
        return None

@st.cache_data
def load_schedule():
    try:
        return pd.read_csv("schedule.csv")
    except Exception as e:
        st.error(f"Schedule Crash: {e}")
        return None

@st.cache_data
def load_schedule():
    try:
        return pd.read_csv("schedule.csv")
    except:
        return None

# Actually run the functions to load the data
teams_data = load_team_data()
df_schedule = load_schedule()

# Stop the app if the data fails to load
if not teams_data or df_schedule is None:
    st.error("Error: Could not fetch data from the NBA or Google Sheets.")
    st.stop()

# Create the alphabetical list of teams for the dropdowns
team_list = sorted(list(teams_data.keys()))

# --- 4. Build the UI Tabs ---
tab1, tab2, tab3, tab4 = st.tabs(["Single Game", "Daily Slate", "Season Simulator", "Data Manager"])

# TAB 1: SINGLE GAME
with tab1:
    st.header("Custom Matchup")
    col1, col2 = st.columns(2)
    with col1:
        home_team = st.selectbox("Home Team", team_list, index=team_list.index("Knicks") if "Knicks" in team_list else 0)
        home_b2b = st.checkbox(f"Is {home_team} on a Back-to-Back?", key="h_b2b")
    with col2:
        away_team = st.selectbox("Away Team", team_list, index=team_list.index("Celtics") if "Celtics" in team_list else 1)
        away_b2b = st.checkbox(f"Is {away_team} on a Back-to-Back?", key="a_b2b")
        
    if st.button("Generate Prediction", type="primary"):
        h_stats, a_stats = teams_data[home_team], teams_data[away_team]
        avg_pace = (h_stats["pace"] + a_stats["pace"]) / 2.0
        
        diff = h_stats["active_net_rtg"] - a_stats["active_net_rtg"] + 2.1
        if home_b2b: diff -= 2.2
        if away_b2b: diff += 2.2
        
        win_prob = calc_win_prob(diff, avg_pace)
        spread = diff * (avg_pace / 100.0)
        
        st.divider()
        if win_prob > 0.5:
            st.success(f"**FAVORITE:** {home_team} by {abs(spread):.1f} points")
            st.metric(f"{home_team} Win Probability", f"{win_prob*100:.1f}%")
        else:
            st.success(f"**FAVORITE:** {away_team} by {abs(spread):.1f} points")
            st.metric(f"{away_team} Win Probability", f"{(1-win_prob)*100:.1f}%")

# TAB 2: DAILY SLATE
with tab2:
    st.header("Daily Slate")
    user_date = st.date_input("Select Date", datetime.now())
    if st.button("Fetch Matchups"):
        with st.spinner("Connecting to NBA database..."):
            try:
                board = scoreboardv3.ScoreboardV3(game_date=user_date.strftime('%Y-%m-%d'))
                games = board.get_dict()['scoreboard']['games']
                if not games:
                    st.warning(f"No games found for {user_date.strftime('%b %d, %Y')}.")
                else:
                    for game in games:
                        away_name, home_name = game['awayTeam']['teamName'], game['homeTeam']['teamName']
                        away = "Trail Blazers" if "Blazers" in away_name else away_name.split(" ")[-1]
                        home = "Trail Blazers" if "Blazers" in home_name else home_name.split(" ")[-1]
                        
                        if home in teams_data and away in teams_data:
                            h_stats, a_stats = teams_data[home], teams_data[away]
                            avg_pace = (h_stats["pace"] + a_stats["pace"]) / 2.0
                            diff = h_stats["active_net_rtg"] - a_stats["active_net_rtg"] + 2.1
                            win_prob = calc_win_prob(diff, avg_pace)
                            spread = diff * (avg_pace / 100.0)
                            
                            fav, prob = (home, win_prob) if win_prob > 0.5 else (away, 1-win_prob)
                            st.info(f"**{away} @ {home}**  |  {fav} by {abs(spread):.1f} pts ({prob*100:.1f}%)")
            except Exception as e:
                st.error(f"Failed to fetch data: {e}")

# TAB 3: SEASON SIMULATOR
with tab3:
    st.header("Season Simulator")
    st.write("Run the full 30-team simulation engine using your live schedule and ratings database.")
    
    sim_count = st.slider("Simulations to run", min_value=1000, max_value=20000, value=10000, step=1000)
    
    if st.button("Run Simulation", type="primary", key="sim_btn"):
        with st.spinner(f"Running {sim_count} universes. This takes a few seconds..."):
            results_df = run_living_monte_carlo(teams_data, df_schedule, n_simulations=sim_count)
            
            # Make the index start at 1 instead of 0 for clean rankings
            results_df.index = np.arange(1, len(results_df) + 1)
            
            # Save the results to Streamlit's memory so it survives the download refresh
            st.session_state['saved_standings'] = results_df
            st.success("Simulation Complete!")
            
    # If there are saved standings in memory, display the table and the download button
    if 'saved_standings' in st.session_state:
        display_df = st.session_state['saved_standings'].copy()
        
        if "Logo" not in display_df.columns:
            display_df.insert(0, "Logo", display_df["Team"].apply(get_logo_url))
        
        st.dataframe(
            display_df, 
            use_container_width=True,
            column_config={
                "Logo": st.column_config.ImageColumn("Logo", width="small"),
                "Projected Wins": st.column_config.NumberColumn(format="%.1f")
            }
        )
        
        csv_data = st.session_state['saved_standings'].to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Standings as CSV",
            data=csv_data,
            file_name="2026_projected_standings.csv",
            mime="text/csv",
        )

# TAB 4: DATA MANAGER
with tab4:
    st.header("Database Manager")
    st.write("Your app now automatically pulls live Net Ratings from the NBA. To edit Media Ranks, use your Google Sheet.")
    
    # Paste the exact URL from your browser when you have the Google Sheet open
    st.link_button("📝 Edit Rankings in Google Sheets", "https://docs.google.com/spreadsheets/d/1MMo_FgfBQdBykFUGjY0ovFxnZPfulx1hX3tGGO06LIQ/edit?gid=0#gid=0")
    
    if st.button("🔄 Sync with Cloud Database"):
        st.cache_data.clear()
        st.rerun()
        
    st.divider()
    st.subheader("📊 Visual Data Explorer")
    
    chart_df = pd.DataFrame([{
        "Team": t, "net_rtg": stats["net_rtg"], "pace": stats["pace"]
    } for t, stats in teams_data.items()])
    
    sort_order = st.radio(
        "Sort Charts By:",
        options=["Worst to Best", "Best to Worst", "Alphabetical (By Team)"],
        horizontal=True
    )
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.markdown("**Base Net Rating**")
        if sort_order == "Worst to Best":
            net_df = chart_df.sort_values("net_rtg", ascending=True)
        elif sort_order == "Best to Worst":
            net_df = chart_df.sort_values("net_rtg", ascending=False)
        else:
            net_df = chart_df.sort_values("Team", ascending=True)
            
        chart1 = alt.Chart(net_df).mark_bar().encode(
            x=alt.X('Team', sort=None), y='net_rtg'
        ).properties(height=400)
        st.altair_chart(chart1, use_container_width=True)
        
    with col_chart2:
        st.markdown("**Game Pace (Possessions)**")
        if sort_order == "Worst to Best":
            pace_df = chart_df.sort_values("pace", ascending=True)
        elif sort_order == "Best to Worst":
            pace_df = chart_df.sort_values("pace", ascending=False)
        else:
            pace_df = chart_df.sort_values("Team", ascending=True)
            
        chart2 = alt.Chart(pace_df).mark_bar().encode(
            x=alt.X('Team', sort=None), y=alt.Y('pace', scale=alt.Scale(zero=False)) 
        ).properties(height=400)
        st.altair_chart(chart2, use_container_width=True)