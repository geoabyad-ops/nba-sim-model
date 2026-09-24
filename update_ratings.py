import pandas as pd
from nba_api.stats.endpoints import leaguedashteamstats

print("Downloading live NBA stats...")
try:
    stats = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense='Advanced', season='2025-26')
    df_nba = stats.get_data_frames()[0]
    
    teams = []
    for index, row in df_nba.iterrows():
        full_name = row['TEAM_NAME']
        team = "Trail Blazers" if full_name == "Portland Trail Blazers" else full_name.split(" ")[-1]
        teams.append({
            "Team": team, 
            "net_rtg": float(row['NET_RATING']), 
            "pace": float(row['PACE'])
        })
        
    df = pd.DataFrame(teams)
    df.to_csv("team_data.csv", index=False)
    print("Success! team_data.csv has been updated.")
except Exception as e:
    print(f"Error fetching data: {e}")