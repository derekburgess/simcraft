import pandas as pd
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

df = pd.read_csv('../example_data.csv')

# Existing categorization function
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

# Prepare 3D plot
fig = plt.figure(figsize=(12, 8))
ax = fig.add_subplot(111, projection='3d')

colors = {
    'MolecularCloud': 'gray',
    'Star': 'blue',
    'BlackHole': 'red'
}

# Plot each category with its position and observation year
for category in df['category'].unique():
    cat_data = df[df['category'] == category]
    ax.scatter(cat_data['posx'], cat_data['posy'], cat_data['observation'], 
               label=category, color=colors[category], marker='o')

# Setting labels and title
ax.set_xlabel('Position X')
ax.set_ylabel('Position Y')
ax.set_zlabel('Observation Year')
ax.set_title('3D Plot of Astronomical Objects')
plt.tight_layout()
plt.show()
