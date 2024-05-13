import os
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D


sim_data_path = os.getenv("SIMCRAFT_DATA")
sim_data = os.path.join(sim_data_path, 'sim_data.csv')
df = pd.read_csv(sim_data)
unique_types = df['type'].unique()
color_map = {
    'MolecularCloud': 'purple',
    'ProtoStar': 'orange',
    'BlackHole': 'red',
    'NeutronStar': 'blue'
}


def cluster(df):
    center_x, center_y = 600, 600
    df['distance'] = np.sqrt((df['posx'] - center_x)**2 + (df['posy'] - center_y)**2)
    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(111, projection='3d')

    for object_type, color in color_map.items():
        type_df = df[df['type'] == object_type]
        ax.scatter(type_df['mass'], type_df['distance'], type_df['observation'], c=color, alpha=0.5, label=object_type)

    ax.set_xlabel('Mass')
    ax.set_ylabel('Distance from Center')
    ax.set_zlabel('Observation Year')
    ax.set_title('Entity Distance from Center over Time')
    plt.legend()
    plt.tight_layout()
    plt.show()


def heatmap(df):
    aggregated_data = df.groupby('entityid').agg({'posx': 'mean', 'posy': 'mean', 'mass': 'sum', 'flux': 'min', 'type': 'first'}).reset_index()
    blackholes = aggregated_data[aggregated_data['type'] == 'BlackHole']
    neutronstars = aggregated_data[aggregated_data['type'] == 'NeutronStar']
    low_flux_bodies = aggregated_data[(aggregated_data['flux'] < 255) & (aggregated_data['type'] != 'BlackHole') & (aggregated_data['type'] != 'NeutronStar')]
    other_bodies = aggregated_data[(aggregated_data['flux'] >= 255) & (aggregated_data['type'] != 'BlackHole') & (aggregated_data['type'] != 'NeutronStar')]
    plt.figure(figsize=(12, 8))
    plt.scatter(other_bodies['posx'], other_bodies['posy'], c='gray', alpha=0.5, zorder=1, s=other_bodies['mass'], label='Molecular Clouds')
    plt.scatter(low_flux_bodies['posx'], low_flux_bodies['posy'], c='orange', marker='^', alpha=0.5, zorder=2, s=low_flux_bodies['mass'], label='Low Flux Protostars')
    plt.scatter(blackholes['posx'], blackholes['posy'], c='red', marker='x', s=50, zorder=3, label='Black Holes')
    plt.scatter(neutronstars['posx'], neutronstars['posy'], c='blue', marker='o', s=25, zorder=4, label='Neutron Stars')
    plt.title('Event Distribution')
    plt.xlabel('Position X')
    plt.ylabel('Position Y')
    plt.legend()
    plt.show()


def timeseries(df):
    grouped = df.groupby(['observation', 'type']).size().unstack(fill_value=0)
    fig, ax = plt.subplots(figsize=(12, 4))
    for category in grouped.columns:
        ax.plot(grouped.index, grouped[category], label=category, color=color_map[category], marker='o', linestyle='-')
    ax.set_title('Time Series of Astronomical Entities')
    ax.set_xlabel('Observation Year')
    ax.set_ylabel('Number of Entities')
    ax.grid(True)
    plt.legend()
    plt.show()


def main():
    parser = argparse.ArgumentParser(description="Run various analysis against the simulation data")
    parser.add_argument("--cluster", action="store_true", help="View a cluste plot of entity Distance from Center")
    parser.add_argument("--heatmap", action="store_true", help="View a heatmap of Event Distribution")
    parser.add_argument("--time", action="store_true", help="View a time series of Astronomical Entities")

    args = parser.parse_args()

    if args.cluster:
        cluster(df)
    if args.heatmap:
        heatmap(df)
    if args.time:
        timeseries(df)


if __name__ == "__main__":
    main()