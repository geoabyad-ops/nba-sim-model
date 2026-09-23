import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import subprocess
from datetime import datetime
from nba_api.stats.endpoints import scoreboardv3

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
    st.write("Fetch yesterday's scores and today's live Net Ratings from the NBA servers.")
    
    if st.button("🔄 Update Live Data", type="primary", use_container_width=True):
        with st.spinner("Downloading from NBA.com..."):
            try:
                # Run both of your background scripts
                ratings_run = subprocess.run(["python", "update_ratings.py"], capture_output=True, text=True)
                # Note: We run auto_updater.py here assuming you have it in the same folder for the schedule scores
                scores_run = subprocess.run(["python", "auto_updater.py"], capture_output=True, text=True)
                
                if ratings_run.returncode == 0:
                    # Clear the cache so Streamlit is forced to read the new CSV files
                    st.cache_data.clear()
                    st.success("✅ Database successfully updated!")
                else:
                    st.error("⚠️ Error pulling data.")
                    st.code(ratings_run.stderr)
            except Exception as e:
                st.error(f"System error: {e}")

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
@st.cache_data
def load_team_data():
    try:
        df = pd.read_csv("team_data.csv")
        teams = {}
        for _, row in df.iterrows():
            team = row['Team']
            net, pace, rank = float(row['net_rtg']), float(row['pace']), float(row['media_rank'])
            media_modifier = (15.5 - rank) * 0.20 
            teams[team] = {"net_rtg": net, "pace": pace, "media_rank": rank, "active_net_rtg": (net * 0.80) + media_modifier}
        return teams
    except:
        return None

@st.cache_data
def load_schedule():
    try:
        return pd.read_csv("schedule.csv")
    except:
        return None

teams_data = load_team_data()
df_schedule = load_schedule()

if not teams_data or df_schedule is None:
    st.error("Error: Could not find team_data.csv or schedule.csv.")
    st.stop()

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
        # We make a copy for the display so we can inject logos without messing up the CSV download
        display_df = st.session_state['saved_standings'].copy()
        
        # 1. Add the Logo column
        if "Logo" not in display_df.columns:
            display_df.insert(0, "Logo", display_df["Team"].apply(get_logo_url))
        
        # 2. Display with ImageColumn configuration
        st.dataframe(
            display_df, 
            use_container_width=True,
            column_config={
                "Logo": st.column_config.ImageColumn("Logo", width="small"),
                "Projected Wins": st.column_config.NumberColumn(format="%.1f")
            }
        )
        
        # Convert the raw dataframe (no logos) to a CSV format in the background
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
    st.write("Edit team ratings, pace, and media rankings directly. Click Save to update the model globally.")
    
    try:
        df_edit = pd.read_csv("team_data.csv")
        
        # 1. Automatically sort the table from best to worst Net Rating by default
        df_edit = df_edit.sort_values("net_rtg", ascending=False)
        
        # 2. Add logos for the UI
        df_edit.insert(0, "Logo", df_edit["Team"].apply(get_logo_url))
        
        # 3. Rearrange the columns left-to-right so they look cleaner
        df_edit = df_edit[["Logo", "Team", "net_rtg", "pace", "media_rank"]]
        
        # Add a quick tip to the UI so you remember the headers are clickable
        st.info("💡 Tip: Click any column header (like 'pace' or 'media_rank') to instantly sort the table!")
        
        edited_df = st.data_editor(
            df_edit, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "Logo": st.column_config.ImageColumn("Logo", width="small")
            }
        )
        
        if st.button("💾 Save Changes to Database", type="primary"):
            # Drop the Logo column before saving back to the CSV
            clean_df = edited_df.drop(columns=["Logo"])
            clean_df.to_csv("team_data.csv", index=False)
            st.cache_data.clear()
            st.success("Database updated successfully!")
            
        st.divider()
        st.subheader("📊 Visual Data Explorer")
        
        sort_order = st.radio(
            "Sort Charts By:",
            options=["Worst to Best", "Best to Worst", "Alphabetical (By Team)"],
            horizontal=True
        )
        
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            st.markdown("**Base Net Rating**")
            if sort_order == "Worst to Best":
                net_df = edited_df.sort_values("net_rtg", ascending=True)
            elif sort_order == "Best to Worst":
                net_df = edited_df.sort_values("net_rtg", ascending=False)
            else:
                net_df = edited_df.sort_values("Team", ascending=True)
            
            # alt.X(sort=None) forces the chart to respect our Pandas order
            chart1 = alt.Chart(net_df).mark_bar().encode(
                x=alt.X('Team', sort=None),
                y='net_rtg'
            ).properties(height=400)
            st.altair_chart(chart1, use_container_width=True)
            
        with col_chart2:
            st.markdown("**Game Pace (Possessions)**")
            if sort_order == "Worst to Best":
                pace_df = edited_df.sort_values("pace", ascending=True)
            elif sort_order == "Best to Worst":
                pace_df = edited_df.sort_values("pace", ascending=False)
            else:
                pace_df = edited_df.sort_values("Team", ascending=True)
            
            # scale=alt.Scale(zero=False) zooms the chart in so the small differences in pace are visible
            chart2 = alt.Chart(pace_df).mark_bar().encode(
                x=alt.X('Team', sort=None),
                y=alt.Y('pace', scale=alt.Scale(zero=False)) 
            ).properties(height=400)
            st.altair_chart(chart2, use_container_width=True)
            
    except FileNotFoundError:
        st.error("Error: team_data.csv not found.")