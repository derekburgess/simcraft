import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

df = pd.read_csv('./data.csv')
center_x, center_y = 600, 600

#Calculate the Euclidean distance from the center for each object
df['distance'] = np.sqrt((df['posx'] - center_x)**2 + (df['posy'] - center_y)**2)

#Categorizing objects
def categorize_object(row):
    if row['type'] == 'BlackHole':
        return 'BlackHole'
    elif row['mass'] < 15 and 8 <= row['size'] <= 15:
        return 'MolecularCloud'
    elif row['mass'] > 15 and row['size'] < 8:
        return 'Star'
    else:
        if row['mass'] < 15:
            return 'MolecularCloud'
        else:
            return 'Star'

df['category'] = df.apply(categorize_object, axis=1)

fig = plt.figure(figsize=(12, 8))
ax = fig.add_subplot(111, projection='3d')

#Assigning colors based on category
color_map = {
    'MolecularCloud': 'gray',
    'Star': 'blue',
    'BlackHole': 'red',
}

df['color'] = df['category'].map(color_map)
ax.scatter(df['mass'], df['distance'], df['observation'], c=df['color'])
ax.set_xlabel('mass')
ax.set_ylabel('Distance from Center')
ax.set_zlabel('Observation Year')
plt.tight_layout()
plt.show()
