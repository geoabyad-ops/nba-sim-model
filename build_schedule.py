import pandas as pd
import numpy as np

teams = [
    "Celtics", "Thunder", "Knicks", "Heat", "Nuggets", "Spurs", "Mavericks", "76ers",
    "Timberwolves", "Bucks", "Pacers", "Cavaliers", "Pelicans", "Suns", "Magic", "Lakers",
    "Kings", "Warriors", "Rockets", "Clippers", "Grizzlies", "Hawks", "Bulls", "Jazz",
    "Nets", "Raptors", "Trail Blazers", "Hornets", "Pistons", "Wizards"
]

all_games = []
n = len(teams)

print("Generating a mathematically perfect 1,230 game schedule...")

# Each team hosts exactly 41 games
for i in range(41):
    for home_idx, home_team in enumerate(teams):
        # Mathematical offset so a team never plays itself
        offset = (i % (n - 1)) + 1
        away_team = teams[(home_idx + offset) % n]
        
        # NBA teams play back-to-backs roughly 16% of the time
        home_b2b = np.random.rand() < 0.16
        away_b2b = np.random.rand() < 0.18
        
        all_games.append({
            "Home": home_team,
            "Away": away_team,
            "Home_Score": "",
            "Away_Score": "",
            "Home_B2B": home_b2b,
            "Away_B2B": away_b2b
        })

# Save to your database
df = pd.DataFrame(all_games)
df.to_csv("schedule.csv", index=False)
print(f"Success! {len(df)} games written directly to schedule.csv.")