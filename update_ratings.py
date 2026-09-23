import pandas as pd
from nba_api.stats.endpoints import leaguedashteamstats

print("Connecting to the NBA API for live Net Ratings...")

# We ask for 'Advanced' stats to get Net Rating and Pace
stats = leaguedashteamstats.LeagueDashTeamStats(
    measure_type_detailed_defense='Advanced',
    season='2025-26' 
)
df_api = stats.get_data_frames()[0]

teams_data = []

for index, row in df_api.iterrows():
    full_name = row['TEAM_NAME']
    
    # The API gives us "Boston Celtics", but our schedule uses "Celtics". This cuts off the city.
    if full_name == "Portland Trail Blazers":
        short_name = "Trail Blazers"
    else:
        short_name = full_name.split(" ")[-1]
        
    teams_data.append({
        "Team": short_name,
        "net_rtg": row['NET_RATING'],
        "pace": row['PACE'],
        "media_rank": 15.5 # A default average rank to start
    })

# Save to a new CSV file
df_teams = pd.DataFrame(teams_data)
df_teams.to_csv("team_data.csv", index=False)
print("Success! Live ratings saved to team_data.csv.")

print("Fetching your media rankings from Google Sheets...")

# Paste your Sheet ID here inside the quotes
sheet_id = "1RZ7D4ZnnsVdOFn5yEFsbzvLLBcjF8uf5w3uscZbTu3E"

# This URL automatically forces Google Sheets to export as a CSV that Pandas can read
sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"

try:
    df_media = pd.read_csv(sheet_url)
    
    # Merge the media ranks from Google Sheets into your NBA API stats
    # This matches them up by the "Team" column
    df_teams = pd.merge(df_teams.drop(columns=['media_rank']), df_media, on='Team', how='left')
    
    # Save the combined data back to your local CSV
    df_teams.to_csv("team_data.csv", index=False)
    print("Success! Live NBA ratings and Media Rankings combined and saved.")
    
except Exception as e:
    print(f"Failed to fetch Google Sheet. Make sure the link is set to 'Anyone with the link'. Error: {e}")

try:
    df_media = pd.read_csv(sheet_url)
    
    # Merge the media ranks from Google Sheets into your NBA API stats
    df_teams = pd.merge(df_teams.drop(columns=['media_rank']), df_media, on='Team', how='left')
    
    # --- NEW SAFETY NET LINE ---
    # Fill any missing matches with an average rank so the math doesn't crash
    df_teams['media_rank'] = df_teams['media_rank'].fillna(15.5)
    
    # Save the combined data back to your local CSV
    df_teams.to_csv("team_data.csv", index=False)
    print("Success! Live NBA ratings and Media Rankings combined and saved.")
    
except Exception as e:
    print(f"Failed to fetch Google Sheet. Error: {e}")