import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv('../data.csv')

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

#Grouping by Observation year and Category
grouped = df.groupby(['observation', 'category']).size().unstack(fill_value=0)

#Define colors for categories
colors = {
    'MolecularCloud': 'gray',
    'Star': 'blue',
    'BlackHole': 'red'
}

#Time Series Plotting
fig, ax = plt.subplots(figsize=(12, 4))
for category in grouped.columns:
    ax.plot(grouped.index, grouped[category], label=category, color=colors[category], marker='o', linestyle='-')
ax.set_title('Time Series of Astronomical Objects')
ax.set_xlabel('Observation Year')
ax.set_ylabel('Number of Objects')
ax.grid(True)
ax.legend(title='Category')
plt.show()
