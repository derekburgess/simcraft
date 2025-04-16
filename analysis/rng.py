import hashlib
import random
import os
import sys
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt

MIN = 10000000000000000000
MAX = 99999999999999999999

def observe_state():
    data_path_var = os.getenv("SIMCRAFT_DATA")
    sim_data_path = os.path.join(data_path_var, 'sim_data.csv')

    sim_data = pd.read_csv(sim_data_path)
    sim_data['observation'] = sim_data['observation'].astype(int)
    sim_data['mass'] = sim_data['mass'].astype(float)
    sim_data['posx'] = sim_data['posx'].astype(float)
    sim_data['posy'] = sim_data['posy'].astype(float)

    observation_years = sorted(sim_data['observation'].unique())
    selected_year = random.choice(observation_years)
    year_df = sim_data[sim_data['observation'] == selected_year]

    total_mass = year_df['mass'].sum()
    total_entities = len(year_df)
    avg_pos_x = year_df['posx'].mean()
    avg_pos_y = year_df['posy'].mean()
    
    state = {
        'observation_year': selected_year,
        'total_entities': total_entities,
        'total_mass': total_mass,
        'avg_pos_x': avg_pos_x,
        'avg_pos_y': avg_pos_y,
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    return state

def rng(min_val, max_val, generations=1):
    results = []
    range_size = max_val - min_val + 1
    os_random_bytes = 32

    for i in range(generations):
        state = observe_state()

        seed_components = [
            str(state['total_entities']),
            str(state['total_mass']),
            str(state['avg_pos_x']),
            str(state['avg_pos_y']),
            state['timestamp']
        ]
        
        state_seed = "".join(seed_components)
        state_hash = hashlib.sha256(state_seed.encode()).digest()
        os_random = os.urandom(os_random_bytes)
        combined_input = state_hash + os_random
        combined_hash = hashlib.sha256(combined_input).digest()
        raw_int = int.from_bytes(combined_hash, 'big')
        random_number = min_val + (raw_int % range_size)
                
        result = {
            "random_number": random_number,
            "generation_time": state['timestamp'],
            "universe_state": {
                "observation_year": state['observation_year'],
                "total_entities": state['total_entities'],
                "total_mass": state['total_mass']
            },
            "range": {
                "min": min_val,
                "max": max_val
            }
        }
        
        print(f"{random_number}")

        if generations == 1:
             return result

        results.append({
            'random_number': result['random_number'],
            'generation_time': result['generation_time'],
            'observation_year': result['universe_state']['observation_year'],
            'total_entities': result['universe_state']['total_entities'],
            'total_mass': result['universe_state']['total_mass']
        })
             
    return pd.DataFrame(results)

def randomness(df):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    ax1.hist(df['random_number'], bins=50, alpha=0.7, color='blue')
    ax1.set_title('Distribution')
    ax1.set_xlabel('Number')
    ax1.set_ylabel('Frequency')
    ax1.grid(True, alpha=0.3)
    
    ax2.plot(df.index, df['random_number'], 'o-', alpha=0.7, color='blue')
    ax2.set_title('Randomness')
    ax2.set_xlabel('Generation')
    ax2.set_ylabel('Number')
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()
    plt.close()

def main():
    num_generations = 1
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        num_generations = int(sys.argv[1])

    if num_generations > 1:
        df = rng(MIN, MAX, num_generations)
        randomness(df)
    else:
        result = rng(MIN, MAX)
        print(f"\nObservation Year: {result['universe_state']['observation_year']}")
        print(f"Total Entities: {result['universe_state']['total_entities']}")
        print(f"Total Mass: {result['universe_state']['total_mass']}")

if __name__ == "__main__":
    main()