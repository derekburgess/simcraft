import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

file_path = './data/sim_data.csv'
data = pd.read_csv(file_path)

#Aggregate data by body - average positions, sum of mass, and minimum flux
aggregated_data = data.groupby('body').agg({'posx': 'mean', 'posy': 'mean', 'mass': 'sum', 'flux': 'min', 'type': 'first'}).reset_index()

#Separate BlackHoles, bodies with flux below 255, and other bodies
blackholes = aggregated_data[aggregated_data['type'] == 'BlackHole']
low_flux_bodies = aggregated_data[(aggregated_data['flux'] < 255) & (aggregated_data['type'] != 'BlackHole')]
other_bodies = aggregated_data[(aggregated_data['flux'] >= 255) & (aggregated_data['type'] != 'BlackHole')]

#Generate a scatter plot
plt.figure(figsize=(12, 8))
plt.scatter(other_bodies['posx'], other_bodies['posy'], c='gray', alpha=0.5, s=other_bodies['mass'], label='Other Bodies')
plt.scatter(low_flux_bodies['posx'], low_flux_bodies['posy'], c='blue', alpha=0.5, s=low_flux_bodies['mass'], label='Low Flux Bodies')
plt.scatter(blackholes['posx'], blackholes['posy'], c='red', marker='x', s=50, label='BlackHoles')
plt.title('Mass Distribution with Black Holes and Low Flux Bodies Highlighted')
plt.xlabel('posx')
plt.ylabel('posy')
plt.colorbar(label='Mass')
plt.show()
