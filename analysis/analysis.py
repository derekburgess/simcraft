import os
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D


def cluster(df):
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


def heatmap(df):
    #Aggregate data by body - average positions, sum of mass, and minimum flux
    aggregated_data = df.groupby('body').agg({'posx': 'mean', 'posy': 'mean', 'mass': 'sum', 'flux': 'min', 'type': 'first'}).reset_index()

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


def time3d(df):
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


def timeseries(df):
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


def main():
    parser = argparse.ArgumentParser(description="Run various analysis against the simulation data")
    parser.add_argument("--cluster", action="store_true", help="View a cluste plot of object Distance from Center over Time")
    parser.add_argument("--heatmap", action="store_true", help="View a heatmap of Mass Distribution with Black Holes and Low Flux Bodies Highlighted")
    parser.add_argument("--time", action="store_true", help="View a time series of Unique Astronomical Objects")
    parser.add_argument("--time3d", action="store_true", help="View a 3D scatter plot of Astronomical Objects")

    sim_data_path = os.getenv("SIMCRAFT_DATA")
    sim_data = os.path.join(sim_data_path, 'sim_data.csv')
    df = pd.read_csv(sim_data)

    args = parser.parse_args()

    if args.cluster:
        cluster(df)
    if args.heatmap:
        heatmap(df)
    if args.time3d:
        time3d(df)
    if args.time:
        timeseries(df)


if __name__ == "__main__":
    main()