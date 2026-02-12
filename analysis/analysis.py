import os
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D


sim_data_path = os.getenv("SIMCRAFT_DATA")
sim_data = os.path.join(sim_data_path, 'sim_data.csv')
df = pd.read_csv(sim_data)
color_map = {
    'MolecularCloud': 'purple',
    'ProtoStar': 'orange',
    'BlackHole': 'red',
    'NeutronStar': 'blue'
}


def cluster(df):
    center_x, center_y = 600, 600
    df['distance'] = np.sqrt((df['posx'] - center_x)**2 + (df['posy'] - center_y)**2)
    figure = plt.figure(figsize=(8, 8))
    axis = figure.add_subplot(111, projection='3d')

    for object_type, color in color_map.items():
        type_df = df[df['type'] == object_type]
        axis.scatter(type_df['mass'], type_df['distance'], type_df['observation'], c=color, alpha=0.5, label=object_type)

    axis.set_xlabel('Mass')
    axis.set_ylabel('Distance from Center', fontsize=10)
    axis.set_zlabel('Observation Year', fontsize=10)
    plt.legend()
    plt.tight_layout()
    plt.show()


def timeseries(df):
    grouped = df.groupby(['observation', 'type']).size().unstack(fill_value=0)
    fig, ax = plt.subplots(figsize=(12, 4))

    for category in grouped.columns:
        ax.plot(grouped.index, grouped[category], label=category, color=color_map[category], marker='o', linestyle='-')

    ax.set_xlabel('Observation Year', fontsize=10)
    ax.set_ylabel('Number of Entities', fontsize=10)
    ax.grid(True, linestyle='--', color='#BCBCBC', alpha=0.5, zorder=0)
    plt.legend()
    plt.tight_layout()
    plt.show()


def heatmap(df):
    aggregated_data = df.groupby('entityid').agg({'posx': 'mean', 'posy': 'mean', 'mass': 'sum', 'flux': 'min', 'type': 'first'}).reset_index()
    blackholes = aggregated_data[aggregated_data['type'] == 'BlackHole']
    neutronstars = aggregated_data[aggregated_data['type'] == 'NeutronStar']
    variable_flux_entities = aggregated_data[(aggregated_data['flux'] < 255) & (aggregated_data['type'] != 'BlackHole') & (aggregated_data['type'] != 'NeutronStar')]
    static_entities = aggregated_data[(aggregated_data['flux'] >= 255) & (aggregated_data['type'] != 'BlackHole') & (aggregated_data['type'] != 'NeutronStar')]

    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(111)
    ax.set_facecolor('#021F6C')

    plt.scatter(static_entities['posx'], static_entities['posy'], c='#00B86A', s=static_entities['mass'], alpha=0.7, zorder=1, label='Molecular Clouds')
    plt.scatter(variable_flux_entities['posx'], variable_flux_entities['posy'], c='orange', marker='^', s=50, alpha=0.8, zorder=2, label='Variable Flux Entities')
    plt.scatter(blackholes['posx'], blackholes['posy'], c='red', marker='o', s=blackholes['mass'], alpha=0.8, zorder=5, label='Black Holes')
    plt.scatter(neutronstars['posx'], neutronstars['posy'], c='yellow', marker='d', s=25, alpha=0.8, zorder=4, label='Neutron Stars')
    plt.grid(True, linestyle='--', color='#ffffff', alpha=0.5, zorder=0)
    plt.legend()
    legend_labels = plt.legend()
    for handle in legend_labels.legend_handles:
        handle._sizes = [30]
    plt.tight_layout()
    plt.show()


def main():
    parser = argparse.ArgumentParser(description="Run various analysis against the simulation data")
    parser.add_argument("--cluster", action="store_true", help="View a cluster plot of entity distance from center.")
    parser.add_argument("--time", action="store_true", help="View a time series of Astronomical Entities")
    parser.add_argument("--heatmap", action="store_true", help="View a heatmap of Event Distribution")

    args = parser.parse_args()

    if args.cluster:
        cluster(df)
    if args.time:
        timeseries(df)
    if args.heatmap:
        heatmap(df)
    

if __name__ == "__main__":
    main()