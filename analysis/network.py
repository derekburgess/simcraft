import matplotlib.pyplot as plt
import pandas as pd
import networkx as nx

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
        return None

df['category'] = df.apply(categorize_object, axis=1)

#Filtering objects by categories
molecular_clouds = df[df['category'] == 'MolecularCloud']
stars = df[df['category'] == 'Star']
black_holes = df[df['category'] == 'BlackHole']

#Color map based on categories
color_map = {
    'MolecularCloud': 'purple',
    'Star': 'red',
    'BlackHole': 'black'
}
G = nx.DiGraph()

#Add connections: Molecular Clouds -> Stars
for _, cloud in molecular_clouds.iterrows():
    nearest_star = stars.loc[((stars['posx'] - cloud['posx'])**2 + (stars['posy'] - cloud['posy'])**2).idxmin()]
    G.add_edge(cloud.name, nearest_star.name)

#Check if there are Black Holes before adding connections: Stars -> Black Holes
if not black_holes.empty:
    for _, star in stars.iterrows():
        nearest_black_hole = black_holes.loc[((black_holes['posx'] - star['posx'])**2 + (black_holes['posy'] - star['posy'])**2).idxmin()]
        G.add_edge(star.name, nearest_black_hole.name)

#Assign colors to nodes based on their category
node_colors = [color_map[df.loc[node, 'category']] for node in G.nodes()]

plt.figure(figsize=(12, 8))
pos = nx.spring_layout(G)
nx.draw(G, pos, node_color=node_colors, with_labels=False, edge_color='gray', node_size=50, arrows=True)
plt.title('Hierarchical Network Graph: Molecular Clouds → Stars → Black Holes')
plt.show()
