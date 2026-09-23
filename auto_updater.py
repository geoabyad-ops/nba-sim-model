import pandas as pd
import datetime
from nba_api.stats.endpoints import scoreboardv2

print("Opening your schedule...")
df = pd.read_csv('schedule.csv')

# 1. Figure out yesterday's date
yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
date_string = yesterday.strftime('%Y-%m-%d')
print(f"Asking NBA.com for scores on {date_string}...")

# 2. Fetch data directly from the NBA
try:
    board = scoreboardv2.ScoreboardV2(game_date=date_string)
    teams_data = board.line_score.get_data_frame()

    if teams_data.empty:
        print("No games were played yesterday!")
    else:
        # 3. Match the NBA data to your CSV
        games = teams_data.groupby('GAME_ID')
        for game_id, game_info in games:
            team1_name = game_info.iloc[0]['TEAM_NAME']  # e.g., "Knicks"
            team1_pts = game_info.iloc[0]['PTS']
            
            team2_name = game_info.iloc[1]['TEAM_NAME']  # e.g., "Celtics"
            team2_pts = game_info.iloc[1]['PTS']
            
            # Check for Team 1 at Home, Team 2 Away
            mask1 = (df['Home'] == team1_name) & (df['Away'] == team2_name)
            if mask1.any():
                df.loc[mask1, 'Home_Score'] = team1_pts
                df.loc[mask1, 'Away_Score'] = team2_pts
                print(f"Updated: {team1_name} {team1_pts} vs {team2_name} {team2_pts}")
                
            # Check for Team 2 at Home, Team 1 Away
            mask2 = (df['Home'] == team2_name) & (df['Away'] == team1_name)
            if mask2.any():
                df.loc[mask2, 'Home_Score'] = team2_pts
                df.loc[mask2, 'Away_Score'] = team1_pts
                print(f"Updated: {team2_name} {team2_pts} vs {team1_name} {team1_pts}")

    # 4. Save the new scores back to the CSV
    df.to_csv('schedule.csv', index=False)
    print("Schedule successfully updated with the latest scores!")

except Exception as e:
    print(f"Could not connect to NBA.com. Error: {e}")