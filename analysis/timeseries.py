import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv('./data/sim_data.csv')

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

#Ensuring we track only unique objects, we'll drop duplicates based on the 'body' column
#df_unique = df.drop_duplicates(subset='body')

#Grouping by Observation year and Category for unique objects
#grouped = df_unique.groupby(['observation', 'category']).size().unstack(fill_value=0)
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
ax.set_title('Time Series of Unique Astronomical Objects')
ax.set_xlabel('Observation Year')
ax.set_ylabel('Number of Unique Objects')
ax.grid(True)
ax.legend(title='Category')
plt.show()
