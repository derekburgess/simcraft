import csv
import hashlib
import random
import os
import sys
from datetime import datetime

def collect_state(sim_data_path=None):
    sim_data_path = os.getenv("SIMCRAFT_DATA")
    sim_data = os.path.join(sim_data_path, 'sim_data.csv')

    with open(sim_data, 'r') as file:
        reader = csv.DictReader(file)
        all_rows = list(reader)
    
    observation_years = sorted(set(int(row['observation']) for row in all_rows))
    selected_year = random.choice(observation_years)
    year_rows = [row for row in all_rows if int(row['observation']) == selected_year]
    
    total_mass = sum(float(row['mass']) for row in year_rows)
    total_entities = len(year_rows)
    avg_pos_x = sum(float(row['posx']) for row in year_rows) / total_entities
    avg_pos_y = sum(float(row['posy']) for row in year_rows) / total_entities
    
    state = {
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'observation_year': selected_year,
        'total_mass': total_mass,
        'total_entities': total_entities,
        'avg_pos_x': avg_pos_x,
        'avg_pos_y': avg_pos_y,
        'raw_state': year_rows
    }
    
    return state

def rng(min_value=0, max_value=100):
    state = collect_state()
    
    seed_components = [
        str(state['total_mass']),
        str(state['total_entities']),
        str(state['avg_pos_x']),
        str(state['avg_pos_y']),
        state['timestamp']
    ]
    
    seed_string = "".join(seed_components)
    seed_hash = hashlib.sha256(seed_string.encode()).hexdigest()
    
    random.seed(int(seed_hash[:8], 16))
    
    random_number = random.randint(min_value, max_value)
    
    result = {
        "random_number": random_number,
        "generation_time": state['timestamp'],
        "universe_state": {
            "observation_year": state['observation_year'],
            "total_entities": state['total_entities'],
            "total_mass": state['total_mass']
        },
        "range": {
            "min": min_value,
            "max": max_value
        }
    }
    
    return result

if __name__ == "__main__":
    min_val = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    max_val = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    
    result = rng(min_val, max_val)
    
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        print(f"Range: {result['range']['min']} to {result['range']['max']}")
        print(f"Number: {result['random_number']}")

        print(f"\nObservation Year: {result['universe_state']['observation_year']}")
        print(f"Total Entities: {result['universe_state']['total_entities']}")
        print(f"Total Mass: {result['universe_state']['total_mass']}")