import pandas as pd
import numpy as np

# 1. Load Baseline Team Data from your new CSV
df_team_data = pd.read_csv("team_data.csv")
teams_data = {}

for index, row in df_team_data.iterrows():
    teams_data[row['Team']] = {
        "net_rtg": float(row['net_rtg']),
        "pace": float(row['pace']),
        "media_rank": float(row['media_rank'])
    }

# 2. Blend the Media Rank with your Baseline Data
for team, stats in teams_data.items():
    rank = stats["media_rank"]
    
    # Calculate how far a team is from average (Rank 15.5 is dead center).
    media_modifier = (15.5 - rank) * 0.20 
    
    # Combine them: 80% weight on your baseline, 20% weight on the media's opinion
    stats["active_net_rtg"] = (stats["net_rtg"] * 0.80) + (media_modifier * 0.20)

HCA = 2.1  # Home Court Advantage

def calc_win_prob(net_diff, pace):
    """Logistic win probability adjusted for game pace."""
    exponent = -(net_diff * np.sqrt(pace / 100.0)) / 11.5
    return 1.0 / (1.0 + 10.0 ** exponent)

# 3. Load Living Schedule
def load_living_schedule(filepath):
    return pd.read_csv(filepath)

# 4. Living Monte Carlo Engine
def run_living_monte_carlo(teams, df_schedule, n_simulations=10000):
    team_names = list(teams.keys())
    
    # Array to hold the final win counts across all 10,000 universes
    sim_wins = {team: np.zeros(n_simulations, dtype=int) for team in team_names}
    
    # Track current actual wins for the output display
    current_wins_tracker = {team: 0 for team in team_names}
    
    # --- BUCKET 1: THE PAST (Lock in real wins) ---
    played_games = df_schedule.dropna(subset=['Home_Score', 'Away_Score'])
    
    for index, game in played_games.iterrows():
        if game['Home_Score'] > game['Away_Score']:
            sim_wins[game['Home']] += 1
            current_wins_tracker[game['Home']] += 1
        elif game['Away_Score'] > game['Home_Score']:
            sim_wins[game['Away']] += 1
            current_wins_tracker[game['Away']] += 1

    # --- BUCKET 2: THE FUTURE (Simulate remaining games) ---
    future_games = df_schedule[df_schedule['Home_Score'].isna() | df_schedule['Away_Score'].isna()]
    
    game_probs = []
    game_pairs = []
    
    for index, g in future_games.iterrows():
        h_team, a_team = g["Home"], g["Away"]
        avg_pace = (teams[h_team]["pace"] + teams[a_team]["pace"]) / 2.0
        
        # Using the new blended active_net_rtg instead of basic net_rtg
        diff = teams[h_team]["active_net_rtg"] - teams[a_team]["active_net_rtg"] + HCA
        if g["Home_B2B"] == True: diff -= 2.2
        if g["Away_B2B"] == True: diff += 2.2
            
        game_probs.append(calc_win_prob(diff, avg_pace))
        game_pairs.append((h_team, a_team))
        
    if len(game_probs) > 0:
        probs = np.array(game_probs)
        num_games = len(probs)
        random_draws = np.random.uniform(0.0, 1.0, size=(num_games, n_simulations))
        home_wins_matrix = random_draws < probs[:, np.newaxis]
        
        for idx, (h_team, a_team) in enumerate(game_pairs):
            sim_wins[h_team] += home_wins_matrix[idx]
            sim_wins[a_team] += (~home_wins_matrix[idx])
            
    # --- SUMMARY OUTPUT ---
    results = []
    for team in team_names:
        wins = sim_wins[team]
        results.append({
            "Team": team,
            "Current Wins": current_wins_tracker[team],
            "Mean Final Wins": np.round(np.mean(wins), 1),
            "10th Pct": int(np.percentile(wins, 10)),
            "90th Pct": int(np.percentile(wins, 90)),
        })
        
    return pd.DataFrame(results).sort_values(by="Mean Final Wins", ascending=False)

if __name__ == "__main__":
    print("Loading living schedule and running 10,000 simulations...")
    df_sched = load_living_schedule("schedule.csv")
    df_results = run_living_monte_carlo(teams_data, df_sched, n_simulations=10000)
    
    print("\n--- LIVE SIMULATION RESULTS ---")
    print(df_results.to_string(index=False))