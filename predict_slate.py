import pandas as pd
import numpy as np
from datetime import datetime
from nba_api.stats.endpoints import scoreboardv3

def calc_win_prob(net_diff, pace):
    exponent = -(net_diff * np.sqrt(pace / 100.0)) / 11.5
    return 1.0 / (1.0 + 10.0 ** exponent)

# 1. Load your living team data
try:
    df_team_data = pd.read_csv("team_data.csv")
except FileNotFoundError:
    print("Error: team_data.csv not found. Run update_ratings.py first!")
    exit()

teams_data = {}
for index, row in df_team_data.iterrows():
    teams_data[row['Team']] = {
        "net_rtg": float(row['net_rtg']),
        "pace": float(row['pace']),
        "media_rank": float(row['media_rank'])
    }

# Blend the ratings
for team, stats in teams_data.items():
    media_modifier = (15.5 - stats["media_rank"]) * 0.20 
    stats["active_net_rtg"] = (stats["net_rtg"] * 0.80) + (media_modifier * 0.20)

# 2. Get the Date
print("\n--- NBA DAILY SLATE PREDICTOR ---")
user_date = input("Enter a date (YYYY-MM-DD) to test, or press Enter for today: ")
if user_date.strip() == "":
    user_date = datetime.now().strftime('%Y-%m-%d')

print(f"\nFetching matchups for {user_date}...")
try:
    board = scoreboardv3.ScoreboardV3(game_date=user_date)
    # V3 uses a cleaner dictionary structure instead of the old Pandas rows
    games = board.get_dict()['scoreboard']['games']
except Exception as e:
    print(f"Error fetching data from NBA.com: {e}")
    exit()

if not games:
    print(f"No games found on {user_date}. Try a date during the regular season!")
    exit()
    
print(f"\n--- PREDICTIONS FOR {user_date} ---\n")

for game in games:
    # Extract the team names from the new V3 dictionary format
    away_name = game['awayTeam']['teamName']
    home_name = game['homeTeam']['teamName']
    
    # Clean names to match your CSV database
    away = "Trail Blazers" if "Blazers" in away_name else away_name.split(" ")[-1]
    home = "Trail Blazers" if "Blazers" in home_name else home_name.split(" ")[-1]
    
    if home not in teams_data or away not in teams_data:
        continue
        
    # 3. Run the math engine
    h_stats = teams_data[home]
    a_stats = teams_data[away]
    
    avg_pace = (h_stats["pace"] + a_stats["pace"]) / 2.0
    HCA = 2.1 # Home Court Advantage
    
    diff = h_stats["active_net_rtg"] - a_stats["active_net_rtg"] + HCA
    win_prob = calc_win_prob(diff, avg_pace)
    point_spread = diff * (avg_pace / 100.0)
    
    # 4. Print the Scouting Report
    matchup = f"{away} @ {home}"
    if win_prob > 0.5:
        print(f"{matchup:<25} ->  FAVORITE: {home:<12} by {abs(point_spread):.1f} pts  ({win_prob*100:.1f}% Win Prob)")
    else:
        print(f"{matchup:<25} ->  FAVORITE: {away:<12} by {abs(point_spread):.1f} pts  ({(1-win_prob)*100:.1f}% Win Prob)")
        
print("\n-----------------------------------")