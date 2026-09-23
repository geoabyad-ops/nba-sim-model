import pandas as pd
import numpy as np

def calc_win_prob(net_diff, pace):
    exponent = -(net_diff * np.sqrt(pace / 100.0)) / 11.5
    return 1.0 / (1.0 + 10.0 ** exponent)

# 1. Load your existing living data
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

# Recalculate your custom blended ratings
for team, stats in teams_data.items():
    media_modifier = (15.5 - stats["media_rank"]) * 0.20 
    stats["active_net_rtg"] = (stats["net_rtg"] * 0.80) + (media_modifier * 0.20)

print("\n--- NBA SINGLE GAME PREDICTOR ---")
home_team = input("Enter Home Team (e.g., Knicks): ")
away_team = input("Enter Away Team (e.g., Celtics): ")

if home_team not in teams_data or away_team not in teams_data:
    print("\nError: Team not found. Check your spelling (use mascot name only, capitalized).")
else:
    home_b2b = input(f"Is {home_team} on a Back-to-Back? (y/n): ").lower() == 'y'
    away_b2b = input(f"Is {away_team} on a Back-to-Back? (y/n): ").lower() == 'y'

    # 2. Run the math
    HCA = 2.1
    h_stats = teams_data[home_team]
    a_stats = teams_data[away_team]
    
    # Calculate the expected speed of the game
    avg_pace = (h_stats["pace"] + a_stats["pace"]) / 2.0

    # Calculate the rating differential
    diff = h_stats["active_net_rtg"] - a_stats["active_net_rtg"] + HCA
    if home_b2b: diff -= 2.2
    if away_b2b: diff += 2.2

    # 3. Generate the outputs
    win_prob = calc_win_prob(diff, avg_pace)
    
    # Convert Per-100 rating diff to an actual game Point Spread
    point_spread = diff * (avg_pace / 100.0)

    print("\n--- PREDICTION OUTPUT ---")
    if win_prob > 0.5:
        print(f"FAVORITE: {home_team} (Win Probability: {win_prob*100:.1f}%)")
        print(f"PROJECTED SPREAD: {home_team} by {abs(point_spread):.1f} points")
    else:
        print(f"FAVORITE: {away_team} (Win Probability: {(1-win_prob)*100:.1f}%)")
        print(f"PROJECTED SPREAD: {away_team} by {abs(point_spread):.1f} points")
    print(f"EXPECTED GAME PACE: {avg_pace:.1f} possessions")
    print("-------------------------\n")