import csv
import hashlib
import random
import os
import sys
from datetime import datetime

def generate_hash_from_random_year(hash_algorithm='sha256'):
    sim_data_path = os.getenv("SIMCRAFT_DATA")
    if not sim_data_path:
        return "Error: SIMCRAFT_DATA environment variable not set"
    
    sim_data = os.path.join(sim_data_path, 'sim_data.csv')
    if not os.path.exists(sim_data):
        return f"Error: Simulation data file not found at {sim_data}"
    
    try:
        with open(sim_data, 'r') as file:
            reader = csv.DictReader(file)
            all_rows = list(reader)
        
        if not all_rows:
            return "Error: No data found in simulation file"
        
        observation_years = set(row['observation'] for row in all_rows)
        selected_year = random.choice(list(observation_years))
        year_rows = [row for row in all_rows if row['observation'] == selected_year]
        year_rows.sort(key=lambda x: (x['entityid'], x['type'], x['mass']))
        
        structured_data = []
        for row in year_rows:
            processed_row = {}
            for key, value in row.items():
                try:
                    if key in ['posx', 'posy', 'mass', 'size']:
                        processed_row[key] = float(value)
                    elif key in ['rowid', 'entityid', 'observation']:
                        processed_row[key] = int(value)
                    else:
                        processed_row[key] = value
                except ValueError:
                    processed_row[key] = value
            structured_data.append(processed_row)
        
        combined_data = str(structured_data)
        
        hash_algos = {
            'sha256': hashlib.sha256,
            'sha512': hashlib.sha512,
            'sha3_256': hashlib.sha3_256,
            'blake2b': hashlib.blake2b
        }
        
        if hash_algorithm not in hash_algos:
            return f"Error: Unsupported hash algorithm {hash_algorithm}"
        
        hash_func = hash_algos[hash_algorithm]
        hash_obj = hash_func(combined_data.encode())
        secure_hash = hash_obj.hexdigest()
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows_used = len(year_rows)
        
        result = {
            "timestamp": timestamp,
            "observation_year": selected_year,
            "rows_used": rows_used,
            "hash_algorithm": hash_algorithm,
            "hash": secure_hash
        }
        
        return result
    
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    hash_algorithm = sys.argv[1] if len(sys.argv) > 1 else 'sha256'
    result = generate_hash_from_random_year(hash_algorithm)
    
    if isinstance(result, dict):
        print(f"Generated hash from simulation data:")
        print(f"Timestamp: {result['timestamp']}")
        print(f"Observation year: {result['observation_year']}")
        print(f"Rows used: {result['rows_used']}")
        print(f"Algorithm: {result['hash_algorithm']}")
        print(f"Hash: {result['hash']}")
    else:
        print(result)