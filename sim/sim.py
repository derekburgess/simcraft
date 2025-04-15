import os
import csv
import pygame
import math
import random
import matplotlib.pyplot as plt
import matplotlib.backends.backend_agg as agg


RING_RADIUS = 600
RING_ATTRACTOR_COUNT = 200
RING_ROTATION_SPEED = 0.2
RING_GRAVITY_CONSTANT = 2
RING_COLOR = (0, 0, 120)
RING_OPACITY = 0

MOLECULAR_CLOUD_COUNT = 15000
MOLECULAR_CLOUD_START_SIZE = 20
MOLECULAR_CLOUD_MIN_SIZE = 2
MOLECULAR_CLOUD_GROWTH_RATE = 1
MOLECULAR_CLOUD_START_MASS = 1
MOLECULAR_CLOUD_GRAVITY_CONSTANT = 0.01
MOLECULAR_CLOUD_MAX_MASS = 22
MOLECULAR_CLOUD_START_COLORS = [
    (50, 0, 0),    # Hydrogen - Red (H-alpha) - 75%
    (50, 50, 0),   # Helium - Yellow (D3) - 23%
    (0, 50, 0),    # Oxygen - Green (OI) - 1%
    (0, 0, 50),    # Carbon - Blue (C2) - 0.5%
    (60, 165, 0),  # Neon - Orange (NeI) - 0.1%
    (25, 0, 50)    # Nitrogen - Violet (NII) - 0.1%
]
MOLECULAR_CLOUD_END_COLOR = (225, 255, 255)
DEFAULT_STATE_CHANCE = 1
PROTOSTAR_THRESHOLD = 18

BLACK_HOLE_THRESHOLD = 20
BLACK_HOLE_CHANCE = 0.3
BLACK_HOLE_RADIUS = 8
BLACK_HOLE_MAX_MASS = 40
BLACK_HOLE_GRAVITY_CONSTANT = 0.1
BLACK_HOLE_DECAY_RATE = 0.08
BLACK_HOLE_DECAY_THRESHOLD = 2
BLACK_HOLE_COLOR = (0,0,0)
BLACK_HOLE_BORDER_COLOR = (200, 0, 0)
BLACK_HOLE_MERGE_COLOR = (0, 0, 160, 200)
DISK_COLOR = (255, 100, 100)
DISK_SIZE = 1
DISK_ROTATION = 10.0

NEUTRON_STAR_CHANCE = 0.2
NEUTRON_STAR_RADIUS = 1
NEUTRON_STAR_GRAVITY_CONSTANT = 0.02
NEUTRON_STAR_DECAY_RATE = 0.08
NEUTRON_STAR_DECAY_THRESHOLD = 0.8
NEUTRON_STAR_COLOR = (0, 120, 255)
NEUTRON_STAR_PULSE_RATE = 0.5
NEUTRON_STAR_PULSE_STRENGTH = 2
NEUTRON_STAR_PULSE_COLOR = (0, 0, 160, 40)
NEUTRON_STAR_PULSE_WIDTH = 2
NEUTRON_STAR_RIPPLE_SPEED = 50
NEUTRON_STAR_RIPPLE_EFFECT_WIDTH = 6

BACKGROUND_COLOR = (0, 0, 10)
SNAPSHOT_SPEED = 100
LABEL_COLOR = (255, 255, 255)
BORDER_COLOR = (150, 150, 150)
BOX_BG_COLOR = (0, 0, 10)
SUB_WINDOW_RECT = pygame.Rect(20, 20, 180, 450)
CLOSE_BUTTON_RECT = pygame.Rect(180, 20, 20, 20)

SCREEN_WIDTH = 1536
SCREEN_HEIGHT = 960


pygame.init()
pygame.display.set_caption("simcraft")
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
font = pygame.font.SysFont('Monospace', 14)
sim_data_path = os.getenv("SIMCRAFT_DATA")
sim_data = os.path.join(sim_data_path, 'sim_data.csv')


entity_id_counter = 0
def generate_unique_id():
    global entity_id_counter
    entity_id_counter += 1
    return entity_id_counter


class ATTRACTOR_RING:
    def __init__(self, center, radius, num_points, angle):
        self.center = center
        self.radius = radius
        self.num_points = num_points
        self.angle = angle
        self.points = self.set_ring_points()
    
    def set_ring_points(self):
        points = []
        for i in range(self.num_points):
            theta = self.angle + (2 * math.pi / self.num_points) * i
            x = self.center[0] + self.radius * math.cos(theta)
            y = self.center[1] + self.radius * math.sin(theta)
            points.append((x, y))
        return points

    def draw_ring(self, screen, color, opacity):
        for point in self.points:
            surface = pygame.Surface((4, 4), pygame.SRCALPHA)
            rgba_color = color + (opacity,)
            pygame.draw.circle(surface, rgba_color, (5, 5), 5)
            screen.blit(surface, (point[0] - 5, point[1] - 5))

    def apply_gravity(self, list_of_molecular_clouds, list_of_black_holes=None, list_of_neutron_stars=None):
        for molecular_cloud in list_of_molecular_clouds:
            for point in self.points:
                dx = point[0] - molecular_cloud.x
                dy = point[1] - molecular_cloud.y
                distance = max(math.hypot(dx, dy), 1)
                force = RING_GRAVITY_CONSTANT * molecular_cloud.mass / (distance**2)
                if distance > molecular_cloud.size / 2:
                    molecular_cloud.x += (dx / distance) * force
                    molecular_cloud.y += (dy / distance) * force
        
        if list_of_black_holes:
            for black_hole in list_of_black_holes:
                for point in self.points:
                    dx = point[0] - black_hole.x
                    dy = point[1] - black_hole.y
                    distance = max(math.hypot(dx, dy), 1)
                    force = (RING_GRAVITY_CONSTANT * black_hole.mass / (distance**2)) * 0.5
                    black_hole.x += (dx / distance) * force
                    black_hole.y += (dy / distance) * force
        
        if list_of_neutron_stars:
            for neutron_star in list_of_neutron_stars:
                for point in self.points:
                    dx = point[0] - neutron_star.x
                    dy = point[1] - neutron_star.y
                    distance = max(math.hypot(dx, dy), 1)
                    force = (RING_GRAVITY_CONSTANT * neutron_star.mass / (distance**2)) * 0.7
                    neutron_star.x += (dx / distance) * force
                    neutron_star.y += (dy / distance) * force


def interpolate_color(start_color, end_color, factor):
    r = start_color[0] + factor * (end_color[0] - start_color[0])
    g = start_color[1] + factor * (end_color[1] - start_color[1])
    b = start_color[2] + factor * (end_color[2] - start_color[2])
    return int(r), int(g), int(b)


def interpolate_multi_color(colors, factor):
    if factor <= 0:
        return colors[0]
    if factor >= 1:
        return colors[-1]
    
    num_segments = len(colors) - 1
    segment_size = 1.0 / num_segments
    segment_index = min(int(factor / segment_size), num_segments - 1)
    segment_factor = (factor - segment_index * segment_size) / segment_size
    start_color = colors[segment_index]
    end_color = colors[segment_index + 1]
    
    return interpolate_color(start_color, end_color, segment_factor)


list_of_molecular_clouds = []
ELEMENTAL_ABUNDANCE = [
    (0, 0.75),     # Hydrogen range: 0-75%
    (0.75, 0.98),  # Helium range: 75-98%
    (0.98, 0.99),  # Oxygen range: 98-99%
    (0.99, 0.995), # Carbon range: 99-99.5%
    (0.995, 0.996),# Neon range: 99.5-99.6%
    (0.996, 1.0)   # Nitrogen range: 99.6-100%
]

class MOLECULAR_CLOUD:
    def __init__(self, x, y, size, mass):
        self.selected = False
        self.id = generate_unique_id()
        self.x = x
        self.y = y
        self.size = size
        self.mass = mass
        self.opacity = 255
        self.gravity_sources = []
        
        # Select color based on elemental abundance
        rand = random.random()
        for i, (start, end) in enumerate(ELEMENTAL_ABUNDANCE):
            if start <= rand < end:
                self.start_color = MOLECULAR_CLOUD_START_COLORS[i]
                break

    def draw_molecular_cloud(self, screen):
        if self.selected:
            highlight_color = (255, 165, 0)
            pygame.draw.rect(screen, highlight_color, (self.x, self.y, self.size, self.size))
        else:
            if self.size <= 4:
                self.color = MOLECULAR_CLOUD_END_COLOR
            else:
                factor = 1.0 - (self.size - 4) / (MOLECULAR_CLOUD_START_SIZE - 4)
                self.color = interpolate_color(self.start_color, MOLECULAR_CLOUD_END_COLOR, factor)
            pygame.draw.rect(screen, self.color, (self.x, self.y, self.size, self.size))

    def update_molecular_cloud(self):
        self.size = max(MOLECULAR_CLOUD_MIN_SIZE, MOLECULAR_CLOUD_START_SIZE - int((self.mass - MOLECULAR_CLOUD_START_MASS) * MOLECULAR_CLOUD_GROWTH_RATE))
        self.mass = min(self.mass, MOLECULAR_CLOUD_MAX_MASS)
        if self.size < 4:
            self.opacity = random.randint(0, 255)

    def check_collisions_with_molecular_clouds(self, other):
        return (self.x < other.x + other.size and
                self.x + self.size > other.x and
                self.y < other.y + other.size and
                self.y + self.size > other.y)
    
    def update_gravity_of_molecular_clouds(self):
        for source in self.gravity_sources:
            dx = source.x - self.x
            dy = source.y - self.y
            distance = max(math.hypot(dx, dy), 1)
            force = MOLECULAR_CLOUD_GRAVITY_CONSTANT * (self.mass * source.mass) / (distance**2)   
            self.x += (dx / distance) * force
            self.y += (dy / distance) * force

    def molecular_cloud_clicked(self, click_x, click_y):
        return (self.x <= click_x <= self.x + self.size and
                self.y <= click_y <= self.y + self.size)


list_of_black_holes = []
list_of_black_hole_pulses = []

class BLACK_HOLE:
    def __init__(self, x, y, mass):
        self.id = generate_unique_id()
        self.selected = False
        self.x = x
        self.y = y
        self.mass = min(mass, BLACK_HOLE_MAX_MASS)
        self.border_radius = int(self.mass // BLACK_HOLE_RADIUS)
        self.gravity_sources = []
        self.tracer_angle = random.uniform(0, 2 * math.pi)

    def draw_black_hole(self, screen):
        radius = int(self.mass // BLACK_HOLE_RADIUS)
        self.border_radius = radius
        if self.selected:
            highlight_color = (255, 165, 0)
            pygame.draw.circle(screen, highlight_color, (int(self.x), int(self.y)), radius)
        else:
            pygame.draw.circle(screen, BLACK_HOLE_BORDER_COLOR, (int(self.x), int(self.y)), radius)
            pygame.draw.circle(screen, BLACK_HOLE_COLOR, (int(self.x), int(self.y)), radius - 2)
        
        tracer_x = self.x + self.border_radius * math.cos(self.tracer_angle)
        tracer_y = self.y + self.border_radius * math.sin(self.tracer_angle)
        pygame.draw.circle(screen, DISK_COLOR, (int(tracer_x), int(tracer_y)), DISK_SIZE)

    def black_hole_clicked(self, click_x, click_y):
        distance = math.hypot(click_x - self.x, click_y - self.y)
        return distance <= self.border_radius

    def attract_entities_to_black_holes(self, list_of_molecular_clouds, list_of_neutron_stars):
        list_of_entities_to_remove = []
        
        for black_hole in list_of_black_holes:
            if black_hole is not self:
                dx = self.x - black_hole.x
                dy = self.y - black_hole.y
                distance = max(math.hypot(dx, dy), 1)
                
                if self.mass > black_hole.mass and distance < self.border_radius:
                    list_of_entities_to_remove.append(black_hole)
                    self.mass += black_hole.mass
                    self.mass = min(self.mass, BLACK_HOLE_MAX_MASS)
                    list_of_black_hole_pulses.append([self.x, self.y, 0, black_hole.mass])
                elif distance > 0:
                    force = BLACK_HOLE_GRAVITY_CONSTANT * (self.mass * black_hole.mass) / (distance**2)
                    black_hole.x += (dx / distance) * force
                    black_hole.y += (dy / distance) * force
                    black_hole.gravity_sources.append(self)
        
        for entity in list_of_molecular_clouds + list_of_neutron_stars:
            dx = self.x - entity.x
            dy = self.y - entity.y
            distance = max(math.hypot(dx, dy), 1)
            
            if isinstance(entity, NEUTRON_STAR) and distance < self.border_radius:
                list_of_entities_to_remove.append(entity)
                self.mass += entity.mass
                self.mass = min(self.mass, BLACK_HOLE_MAX_MASS)
            elif isinstance(entity, MOLECULAR_CLOUD) and distance < self.border_radius:
                list_of_entities_to_remove.append(entity)
                self.mass += entity.mass
                self.mass = min(self.mass, BLACK_HOLE_MAX_MASS)
            else:
                force = BLACK_HOLE_GRAVITY_CONSTANT * (self.mass * entity.mass) / (distance**2)
                entity.x += (dx / distance) * force
                entity.y += (dy / distance) * force
                entity.gravity_sources.append(self)
        
        for entity in list_of_entities_to_remove:
            if entity in list_of_molecular_clouds:
                list_of_molecular_clouds.remove(entity)
            elif entity in list_of_neutron_stars:
                list_of_neutron_stars.remove(entity)
            elif entity in list_of_black_holes:
                list_of_black_holes.remove(entity)

    def update_gravity_of_black_holes(self, list_of_molecular_clouds, list_of_neutron_stars):
        for entity in list_of_molecular_clouds + list_of_neutron_stars + list_of_black_holes:
            if entity is not self:
                dx = entity.x - self.x
                dy = entity.y - self.y
                distance = max(math.hypot(dx, dy), 1)
                force = MOLECULAR_CLOUD_GRAVITY_CONSTANT * (self.mass * entity.mass) / (distance**2)
                self.x += (dx / distance) * force
                self.y += (dy / distance) * force

    def black_hole_decay(self):
        self.mass -= BLACK_HOLE_DECAY_RATE
        if self.mass < BLACK_HOLE_DECAY_THRESHOLD:
            if self in list_of_black_holes:
                list_of_black_holes.remove(self)


list_of_neutron_stars = []
class NEUTRON_STAR:
    def __init__(self, x, y, mass):
        self.id = generate_unique_id()
        self.selected = False
        self.x = x
        self.y = y
        self.mass = mass
        self.radius = NEUTRON_STAR_RADIUS
        self.pulse_rate = NEUTRON_STAR_PULSE_RATE
        self.pulse_strength = NEUTRON_STAR_PULSE_STRENGTH
        self.time_since_last_pulse = 0
        self.gravity_sources = []
        self.active_pulses = []
        self.pulse_color_state = 0  # 0: normal color, 1: white during pulse
        self.pulse_color_duration = 0.1  # Duration of white color in seconds

    def draw_neotron_star(self, screen):
        if self.selected:
            highlight_color = (255, 165, 0)
            pygame.draw.circle(screen, highlight_color, (int(self.x), int(self.y)), self.radius)
        else:
            current_color = (255, 255, 255) if self.pulse_color_state == 1 else NEUTRON_STAR_COLOR
            pygame.draw.circle(screen, current_color, (int(self.x), int(self.y)), self.radius)
        
        for pulse in self.active_pulses:
            pulse_radius, _ = pulse
            center_x, center_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
            distance_from_center = math.hypot(self.x - center_x, self.y - center_y)
            
            if distance_from_center + pulse_radius <= RING_RADIUS:
                pulse_surface = pygame.Surface((pulse_radius*2, pulse_radius*2), pygame.SRCALPHA)
                pygame.draw.circle(pulse_surface, NEUTRON_STAR_PULSE_COLOR, (pulse_radius, pulse_radius), pulse_radius, NEUTRON_STAR_PULSE_WIDTH)
                screen.blit(pulse_surface, (self.x - pulse_radius, self.y - pulse_radius))

    def neutron_star_clicked(self, click_x, click_y):
        distance = math.hypot(click_x - self.x, click_y - self.y)
        return distance <= self.radius

    def pulse_gravity_from_neutron_star(self, list_of_molecular_clouds, delta_time):
        self.time_since_last_pulse += delta_time
        
        if self.pulse_color_state == 1:
            self.pulse_color_duration -= delta_time
            if self.pulse_color_duration <= 0:
                self.pulse_color_state = 0
                self.pulse_color_duration = 0.1
        
        pulses_to_remove = []
        for i, pulse in enumerate(self.active_pulses):
            radius, time_alive = pulse
            new_radius = radius + (NEUTRON_STAR_RIPPLE_SPEED * delta_time)
            new_time = time_alive + delta_time
            
            self.active_pulses[i] = [new_radius, new_time]
            
            for molecular_cloud in list_of_molecular_clouds:
                dx = molecular_cloud.x - self.x
                dy = molecular_cloud.y - self.y
                distance = math.hypot(dx, dy)
                
                ripple_dist = abs(distance - radius)
                if ripple_dist < NEUTRON_STAR_RIPPLE_EFFECT_WIDTH:
                    effect_factor = 1.0 - (ripple_dist / NEUTRON_STAR_RIPPLE_EFFECT_WIDTH)
                    force = self.pulse_strength * effect_factor / ((ripple_dist + 1) ** 1.5)
                    
                    if distance > 0:
                        molecular_cloud.x += (dx / distance) * force * delta_time
                        molecular_cloud.y += (dy / distance) * force * delta_time
            
            for black_hole in list_of_black_holes:
                dx = black_hole.x - self.x
                dy = black_hole.y - self.y
                distance = math.hypot(dx, dy)
                
                ripple_dist = abs(distance - radius)
                if ripple_dist < NEUTRON_STAR_RIPPLE_EFFECT_WIDTH:
                    effect_factor = (1.0 - (ripple_dist / NEUTRON_STAR_RIPPLE_EFFECT_WIDTH)) * 0.3
                    force = self.pulse_strength * effect_factor / ((ripple_dist + 1) ** 2)
                    
                    if distance > 0:
                        black_hole.x += (dx / distance) * force * delta_time * 0.2
                        black_hole.y += (dy / distance) * force * delta_time * 0.2
            
            if new_radius > RING_RADIUS:
                pulses_to_remove.append(i)
        
        for i in sorted(pulses_to_remove, reverse=True):
            if i < len(self.active_pulses):
                self.active_pulses.pop(i)
        
        if self.time_since_last_pulse >= self.pulse_rate:
            self.active_pulses.append([0, 0])
            self.time_since_last_pulse = 0
            self.pulse_color_state = 1  # Set to white during pulse
            self.pulse_color_duration = 0.1  # Reset duration

    def update_position_of_entities_from_pulse(self, list_of_molecular_clouds, delta_time):
        for molecular_cloud in list_of_molecular_clouds:
            if molecular_cloud is not self:
                dx = molecular_cloud.x - self.x
                dy = molecular_cloud.y - self.y
                distance = max(math.hypot(dx, dy), 1)
                
                force = NEUTRON_STAR_GRAVITY_CONSTANT * (self.mass * molecular_cloud.mass) / (distance**2)
                
                molecular_cloud.x += (dx / distance) * force * delta_time
                molecular_cloud.y += (dy / distance) * force * delta_time
                
                self.x -= (dx / distance) * force * delta_time
                self.y -= (dy / distance) * force * delta_time
        
        for black_hole in list_of_black_holes:
            dx = black_hole.x - self.x
            dy = black_hole.y - self.y
            distance = max(math.hypot(dx, dy), 1)
            
            force = NEUTRON_STAR_GRAVITY_CONSTANT * (self.mass * black_hole.mass) / (distance**2)
            
            self.x += (dx / distance) * force * delta_time * 1.5
            self.y += (dy / distance) * force * delta_time * 1.5
            
            black_hole.x -= (dx / distance) * force * delta_time * 0.3
            black_hole.y -= (dy / distance) * force * delta_time * 0.3
    
    def decay_neutron_star(self):
        self.mass -= NEUTRON_STAR_DECAY_RATE
        if self.mass < NEUTRON_STAR_DECAY_THRESHOLD:
            if self in list_of_neutron_stars:
                list_of_neutron_stars.remove(self)


def handle_collisions(list_of_molecular_clouds):
    for i, molecular_cloud in enumerate(list_of_molecular_clouds):
        for other in list_of_molecular_clouds[i+1:]:
            if molecular_cloud.check_collisions_with_molecular_clouds(other):
                merged_mass = molecular_cloud.mass + other.mass
                list_of_molecular_clouds.remove(other)
                molecular_cloud.mass = min(merged_mass, MOLECULAR_CLOUD_MAX_MASS)
                molecular_cloud.update_molecular_cloud()
                break


def update_entities(list_of_molecular_clouds):
    global list_of_black_holes, list_of_neutron_stars
    handle_collisions(list_of_molecular_clouds)
    list_of_molecular_clouds_to_remove = []
    for molecular_cloud in list_of_molecular_clouds:
        molecular_cloud.update_molecular_cloud()
        if molecular_cloud.mass > BLACK_HOLE_THRESHOLD:
            if random.random() < BLACK_HOLE_CHANCE:
                if random.random() < NEUTRON_STAR_CHANCE:
                    list_of_neutron_stars.append(NEUTRON_STAR(molecular_cloud.x, molecular_cloud.y, molecular_cloud.mass))
                else:
                    list_of_black_holes.append(BLACK_HOLE(molecular_cloud.x, molecular_cloud.y, molecular_cloud.mass))
                list_of_molecular_clouds_to_remove.append(molecular_cloud)
            elif random.random() < DEFAULT_STATE_CHANCE:
                molecular_cloud.mass = MOLECULAR_CLOUD_START_MASS
                molecular_cloud.size = MOLECULAR_CLOUD_START_SIZE
    for molecular_cloud in list_of_molecular_clouds_to_remove:
        list_of_molecular_clouds.remove(molecular_cloud)


global_index_counter = 1
def dump_to_csv(list_of_molecular_clouds, list_of_black_holes, list_of_neutron_stars, current_year, filename=sim_data):
    global global_index_counter
    file_exists = os.path.isfile(filename)
    with open(filename, mode='a' if file_exists else 'w', newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(['rowid', 'entityid', 'type', 'posx', 'posy', 'mass', 'size', 'flux', 'observation'])
        row_id = global_index_counter
        for molecular_cloud in list_of_molecular_clouds:
            flux = molecular_cloud.opacity if hasattr(molecular_cloud, 'opacity') else 'N/A'
            if PROTOSTAR_THRESHOLD <= molecular_cloud.mass <= BLACK_HOLE_THRESHOLD:
                entity_type = 'ProtoStar'
            else:
                entity_type = 'MolecularCloud'
            writer.writerow([row_id, molecular_cloud.id, entity_type, molecular_cloud.x, molecular_cloud.y, molecular_cloud.mass, molecular_cloud.size, flux, current_year])
            row_id += 1
        for black_hole in list_of_black_holes:
            writer.writerow([row_id, black_hole.id, 'BlackHole', black_hole.x, black_hole.y, black_hole.mass, black_hole.border_radius, 0, current_year])
            row_id += 1
        for neutron_star in list_of_neutron_stars:
            writer.writerow([row_id, neutron_star.id, 'NeutronStar', neutron_star.x, neutron_star.y, neutron_star.mass, neutron_star.radius, 0, current_year])
            row_id += 1
        global_index_counter = row_id


def draw_static_key(screen):
    #Data Snapshot Key
    snapshot_pos = (30, SCREEN_HEIGHT - 110)
    screen.blit(font.render('[SPACEBAR] DATA SNAPSHOT', True, LABEL_COLOR), (snapshot_pos[0], snapshot_pos[1]))  
    snapshot_pos = (30, SCREEN_HEIGHT - 80)
    screen.blit(font.render('[Q] EXIT', True, LABEL_COLOR), (snapshot_pos[0], snapshot_pos[1]))


def load_csv_data(file_path):
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return {} 
    with open(file_path, 'r') as file:
        try:
            reader = csv.DictReader(file)
            data = {}
            for row in reader:
                entityid = row['entityid']
                if entityid not in data:
                    data[entityid] = []
                row_data = {
                    'observation': row.get('observation', '0'),
                    'mass': row.get('mass', '0'),
                    'size': row.get('size', '0'),
                    'flux': row.get('flux', 'N/A'),
                    'posx': row.get('posx', '0'),
                    'posy': row.get('posy', '0'),
                    'rowid': row.get('rowid', 'N/A'),
                    'entityid': entityid,
                    'type': row.get('type', 'N/A')
                }
                data[entityid].append(row_data)
            return data
        except (IOError, csv.Error) as e:
            print(f"Error reading or parsing CSV: {e}")
            return {}


def plot_graph(x_values, data):
    fig, ax = plt.subplots(figsize=(2, 1), dpi=80)
    fig.patch.set_alpha(0.0)
    ax.patch.set_alpha(0.0)
    colors = ['white', 'gray', 'purple']
    linestyles = [':', ':', '-']
    plot_successful = False
    for i, (key, y_values) in enumerate(data.items()):
        if len(x_values) == len(y_values) and len(x_values) > 0:
            try:
                numeric_x = [float(x) for x in x_values]
                numeric_y = [float(y) if y != 'N/A' else 0 for y in y_values]
                ax.plot(numeric_x, numeric_y, label=key.upper(), color=colors[i % len(colors)], linestyle=linestyles[i % len(linestyles)])
                plot_successful = True
            except ValueError as e:
                print(f"Warning: Could not plot {key}, invalid data: {e}")
        else:
             print(f"Warning: Skipping plot for {key} due to mismatched lengths or empty data (x: {len(x_values)}, y: {len(y_values)}).")

    ax.set_xticklabels([])
    ax.set_yticklabels([])
    plt.tight_layout()
    canvas = agg.FigureCanvasAgg(fig)
    canvas.draw()
    plt.close(fig)
    return canvas, plot_successful


def display_molecular_cloud_data(screen, selected_entity, rect, font, csv_data):
    if selected_entity is None:
        return

    # Common data for all entities
    live_data_texts = [
        "LIVE DATA:",
        f"ID: {selected_entity.id}",
        f"POSX: {round(selected_entity.x, 5)}",
        f"POSY: {round(selected_entity.y, 5)}",
        f"MASS: {round(selected_entity.mass, 5)}"
    ]

    # Add size/radius information based on entity type
    if isinstance(selected_entity, MOLECULAR_CLOUD):
        live_data_texts.append(f"SIZE: {round(selected_entity.size, 5)}")
        live_data_texts.append(f"FLUX: {selected_entity.opacity if hasattr(selected_entity, 'opacity') else 'N/A'}")
    elif isinstance(selected_entity, BLACK_HOLE):
        live_data_texts.append(f"RADIUS: {round(selected_entity.border_radius, 5)}")
        live_data_texts.append("FLUX: N/A")
    elif isinstance(selected_entity, NEUTRON_STAR):
        live_data_texts.append(f"RADIUS: {round(selected_entity.radius, 5)}")
        live_data_texts.append("FLUX: N/A")

    y_offset = 5
    for text in live_data_texts:
        text_surface = font.render(text, True, LABEL_COLOR)
        screen.blit(text_surface, (rect.x + 10, rect.y + y_offset))
        y_offset += 20

    y_offset = 160
    header_surface = font.render("OBSERVATIONAL DATA:", True, LABEL_COLOR)
    screen.blit(header_surface, (rect.x + 10, rect.y + y_offset))
    y_offset += 20

    entity_csv_data = csv_data.get(str(selected_entity.id))
    graph_plotted = False
    if entity_csv_data:
        most_recent_observation = entity_csv_data[-1]
        display_keys = ['rowid', 'entityid', 'type', 'posx', 'posy', 'mass', 'size', 'flux', 'observation']
        for key in display_keys:
            value = most_recent_observation.get(key, 'N/A')
            try:
                if key in ['posx', 'posy', 'mass']:
                    value = round(float(value), 5)
                elif key == 'size':
                    if isinstance(selected_entity, MOLECULAR_CLOUD):
                        value = round(float(value), 5)
                    elif isinstance(selected_entity, BLACK_HOLE):
                        value = round(float(value), 5)  # Using size as border_radius
                    elif isinstance(selected_entity, NEUTRON_STAR):
                        value = round(float(value), 5)  # Using size as radius
                elif key == 'observation':
                    value = int(float(value))
            except (ValueError, TypeError):
                value = 'N/A'

            csv_text = f"{key.upper()}: {value}"
            text_surface = font.render(csv_text, True, LABEL_COLOR)
            screen.blit(text_surface, (rect.x + 10, rect.y + y_offset))
            y_offset += 20

        observations = [row['observation'] for row in entity_csv_data if 'observation' in row]
        plot_data = {}
        for key in ['mass', 'size', 'flux']:
            plot_data[key] = [row[key] for row in entity_csv_data if key in row]

        min_len = len(observations)
        for key in plot_data:
            min_len = min(min_len, len(plot_data[key]))

        valid_observations = observations[:min_len]
        valid_plot_data = {k: v[:min_len] for k, v in plot_data.items()}

        if valid_observations and all(valid_plot_data.values()):
            canvas, plot_successful = plot_graph(valid_observations, valid_plot_data)
            if plot_successful:
                width, height = canvas.get_width_height()
                pygame_surface = pygame.image.fromstring(canvas.tostring_argb(), (width, height), 'ARGB')
                plot_y_pos = rect.y + y_offset
                screen.blit(pygame_surface, (rect.x + 10, plot_y_pos))
                graph_plotted = True

    if not entity_csv_data:
        no_data_text = "No observational data found."
        text_surface = font.render(no_data_text, True, LABEL_COLOR)
        screen.blit(text_surface, (rect.x + 10, rect.y + y_offset))
        y_offset += 20
    elif not graph_plotted:
        plot_fail_text = "Could not generate plot."
        text_surface = font.render(plot_fail_text, True, LABEL_COLOR)
        screen.blit(text_surface, (rect.x + 10, rect.y + y_offset + 10))


def handle_input(list_of_molecular_clouds, selected_entity, sub_window_active):
    running = True
    new_selected_entity = selected_entity
    new_sub_window_active = sub_window_active

    for event in pygame.event.get():
        if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_q):
            running = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
            pass

        if event.type == pygame.MOUSEBUTTONDOWN:
            click_x, click_y = event.pos
            clicked_on_entity = False
            if new_sub_window_active:
                if CLOSE_BUTTON_RECT.collidepoint(click_x, click_y):
                    if new_selected_entity:
                        new_selected_entity.selected = False
                    new_selected_entity = None
                    new_sub_window_active = False
                elif not SUB_WINDOW_RECT.collidepoint(click_x, click_y):
                    for molecular_cloud in list_of_molecular_clouds:
                        if molecular_cloud.molecular_cloud_clicked(click_x, click_y):
                            if new_selected_entity:
                                new_selected_entity.selected = False
                            new_selected_entity = molecular_cloud
                            new_selected_entity.selected = True
                            new_sub_window_active = True
                            clicked_on_entity = True
                            break
                    
                    if not clicked_on_entity:
                        for black_hole in list_of_black_holes:
                            if black_hole.black_hole_clicked(click_x, click_y):
                                if new_selected_entity:
                                    new_selected_entity.selected = False
                                new_selected_entity = black_hole
                                new_selected_entity.selected = True
                                new_sub_window_active = True
                                clicked_on_entity = True
                                break
                    
                    if not clicked_on_entity:
                        for neutron_star in list_of_neutron_stars:
                            if neutron_star.neutron_star_clicked(click_x, click_y):
                                if new_selected_entity:
                                    new_selected_entity.selected = False
                                new_selected_entity = neutron_star
                                new_selected_entity.selected = True
                                new_sub_window_active = True
                                clicked_on_entity = True
                                break
                    
                    if not clicked_on_entity:
                        if new_selected_entity:
                            new_selected_entity.selected = False
                        new_selected_entity = None
                        new_sub_window_active = False
            else:
                for molecular_cloud in list_of_molecular_clouds:
                    if molecular_cloud.molecular_cloud_clicked(click_x, click_y):
                        if new_selected_entity:
                            new_selected_entity.selected = False
                        new_selected_entity = molecular_cloud
                        new_selected_entity.selected = True
                        new_sub_window_active = True
                        clicked_on_entity = True
                        break
                
                if not clicked_on_entity:
                    for black_hole in list_of_black_holes:
                        if black_hole.black_hole_clicked(click_x, click_y):
                            if new_selected_entity:
                                new_selected_entity.selected = False
                            new_selected_entity = black_hole
                            new_selected_entity.selected = True
                            new_sub_window_active = True
                            clicked_on_entity = True
                            break
                
                if not clicked_on_entity:
                    for neutron_star in list_of_neutron_stars:
                        if neutron_star.neutron_star_clicked(click_x, click_y):
                            if new_selected_entity:
                                new_selected_entity.selected = False
                            new_selected_entity = neutron_star
                            new_selected_entity.selected = True
                            new_sub_window_active = True
                            clicked_on_entity = True
                            break
                
                if not clicked_on_entity and new_selected_entity:
                    new_selected_entity.selected = False
                    new_selected_entity = None
                    new_sub_window_active = False

    if new_selected_entity:
        for mc in list_of_molecular_clouds:
            if mc is not new_selected_entity:
                mc.selected = False
        for bh in list_of_black_holes:
            if bh is not new_selected_entity:
                bh.selected = False
        for ns in list_of_neutron_stars:
            if ns is not new_selected_entity:
                ns.selected = False

    return running, new_selected_entity, new_sub_window_active


def update_simulation_state(list_of_molecular_clouds, list_of_black_holes, list_of_neutron_stars, ring, delta_time, current_year):
    update_entities(list_of_molecular_clouds)

    ring.apply_gravity(list_of_molecular_clouds, list_of_black_holes, list_of_neutron_stars)

    for molecular_cloud in list_of_molecular_clouds:
         molecular_cloud.gravity_sources = []

    for black_hole in list_of_black_holes:
        black_hole.tracer_angle += DISK_ROTATION * delta_time

    pulses_to_remove = []
    for i, pulse in enumerate(list_of_black_hole_pulses):
        x, y, radius, consumed_mass = pulse
        new_radius = radius + (NEUTRON_STAR_RIPPLE_SPEED * delta_time * 1.5)
        list_of_black_hole_pulses[i] = [x, y, new_radius, consumed_mass]
        
        for molecular_cloud in list_of_molecular_clouds:
            dx = molecular_cloud.x - x
            dy = molecular_cloud.y - y
            distance = math.hypot(dx, dy)
            
            ripple_dist = abs(distance - radius)
            if ripple_dist < NEUTRON_STAR_RIPPLE_EFFECT_WIDTH * 2:
                effect_factor = 1.0 - (ripple_dist / (NEUTRON_STAR_RIPPLE_EFFECT_WIDTH * 2))
                force = NEUTRON_STAR_PULSE_STRENGTH * 5 * effect_factor * (consumed_mass / 10) / ((ripple_dist + 1) ** 1.5)
                
                if distance > 0:
                    molecular_cloud.x += (dx / distance) * force * delta_time
                    molecular_cloud.y += (dy / distance) * force * delta_time
        
        for black_hole in list_of_black_holes:
            dx = black_hole.x - x
            dy = black_hole.y - y
            distance = math.hypot(dx, dy)
            
            ripple_dist = abs(distance - radius)
            if ripple_dist < NEUTRON_STAR_RIPPLE_EFFECT_WIDTH * 3:
                effect_factor = 1.0 - (ripple_dist / (NEUTRON_STAR_RIPPLE_EFFECT_WIDTH * 3))
                force = NEUTRON_STAR_PULSE_STRENGTH * 2 * effect_factor * (consumed_mass / 10) / ((ripple_dist + 1) ** 2)
                
                if distance > 0:
                    black_hole.x += (dx / distance) * force * delta_time * 0.5
                    black_hole.y += (dy / distance) * force * delta_time * 0.5

        for neutron_star in list_of_neutron_stars:
            dx = neutron_star.x - x
            dy = neutron_star.y - y
            distance = math.hypot(dx, dy)
            
            ripple_dist = abs(distance - radius)
            if ripple_dist < NEUTRON_STAR_RIPPLE_EFFECT_WIDTH * 2:
                effect_factor = 1.0 - (ripple_dist / (NEUTRON_STAR_RIPPLE_EFFECT_WIDTH * 2))
                force = NEUTRON_STAR_PULSE_STRENGTH * 3 * effect_factor * (consumed_mass / 10) / ((ripple_dist + 1) ** 1.8)
                
                if distance > 0:
                    neutron_star.x += (dx / distance) * force * delta_time * 1.5
                    neutron_star.y += (dy / distance) * force * delta_time * 1.5
        
        if new_radius > RING_RADIUS:
            pulses_to_remove.append(i)
    
    for i in sorted(pulses_to_remove, reverse=True):
        if i < len(list_of_black_hole_pulses):
            list_of_black_hole_pulses.pop(i)

    decay_blackholes = []
    for black_hole in list_of_black_holes:
         for entity in list_of_molecular_clouds + list_of_neutron_stars + list_of_black_holes:
             if entity is not black_hole: 
                 entity.gravity_sources = []
         black_hole.attract_entities_to_black_holes(list_of_molecular_clouds, list_of_neutron_stars)
         black_hole.update_gravity_of_black_holes(list_of_molecular_clouds, list_of_neutron_stars)
         black_hole.black_hole_decay()
         if black_hole.mass <= BLACK_HOLE_DECAY_THRESHOLD:
              decay_blackholes.append(black_hole)
    for decayed_black_hole in decay_blackholes:
        if decayed_black_hole in list_of_black_holes:
            list_of_black_holes.remove(decayed_black_hole)

    decay_neutronstars = []
    for neutron_star in list_of_neutron_stars:
        neutron_star.update_position_of_entities_from_pulse(list_of_molecular_clouds, delta_time)
        neutron_star.pulse_gravity_from_neutron_star(list_of_molecular_clouds, delta_time)
        neutron_star.decay_neutron_star()
        if neutron_star.mass <= NEUTRON_STAR_DECAY_THRESHOLD:
            decay_neutronstars.append(neutron_star)
    for decay_neutronstar in decay_neutronstars:
        if decay_neutronstar in list_of_neutron_stars:
            list_of_neutron_stars.remove(decay_neutronstar)

    if current_year == 20:
        dump_to_csv(list_of_molecular_clouds, list_of_black_holes, list_of_neutron_stars, current_year)
    if current_year % SNAPSHOT_SPEED == 0:
        dump_to_csv(list_of_molecular_clouds, list_of_black_holes, list_of_neutron_stars, current_year)


def draw_simulation(screen, ring, list_of_molecular_clouds, list_of_black_holes, list_of_neutron_stars):
    ring.draw_ring(screen, RING_COLOR, RING_OPACITY)

    for molecular_cloud in list_of_molecular_clouds:
        molecular_cloud.draw_molecular_cloud(screen)

    for pulse in list_of_black_hole_pulses[:]:
        x, y, pulse_radius, consumed_mass = pulse
        if pulse_radius > 0:
            center_x, center_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
            distance_from_center = math.hypot(x - center_x, y - center_y)
            
            if distance_from_center + pulse_radius <= RING_RADIUS:
                pulse_width = max(2, int(consumed_mass / 20))
                pulse_surface = pygame.Surface((pulse_radius*2, pulse_radius*2), pygame.SRCALPHA)
                pygame.draw.circle(pulse_surface, BLACK_HOLE_MERGE_COLOR, (pulse_radius, pulse_radius), pulse_radius, pulse_width)
                screen.blit(pulse_surface, (x - pulse_radius, y - pulse_radius))

    for black_hole in list_of_black_holes:
        black_hole.draw_black_hole(screen)

    for neutron_star in list_of_neutron_stars:
        neutron_star.draw_neotron_star(screen)


def draw_ui(screen, font, current_year, selected_entity, sub_window_active):
    draw_static_key(screen)

    year_text = font.render(f"TIME(YEARS): {current_year}M", True, LABEL_COLOR)
    screen.blit(year_text, (30, SCREEN_HEIGHT - 40 ))

    if sub_window_active:
        csv_data = load_csv_data(sim_data)

        pygame.draw.rect(screen, BORDER_COLOR, SUB_WINDOW_RECT, 1)
        inner_rect = SUB_WINDOW_RECT.inflate(-2 * 1, -2 * 1)
        pygame.draw.rect(screen, BOX_BG_COLOR, inner_rect)
        pygame.draw.rect(screen, BORDER_COLOR, CLOSE_BUTTON_RECT)

        if selected_entity:
            display_molecular_cloud_data(screen, selected_entity, SUB_WINDOW_RECT, font, csv_data)
        else:
             no_selection_text = font.render("No entity selected", True, LABEL_COLOR)
             screen.blit(no_selection_text, (SUB_WINDOW_RECT.x + 10, SUB_WINDOW_RECT.y + 10))


def run_simulation():
    try:
        running = True
        global font
        pygame.font.init()
        angle = 0
        current_year = 0
        last_frame_time = pygame.time.get_ticks()
        selected_entity = None
        sub_window_active = False

        ring = ATTRACTOR_RING((SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2), RING_RADIUS, RING_ATTRACTOR_COUNT, 0)

        while running:
            current_time = pygame.time.get_ticks()
            delta_time = (current_time - last_frame_time) / 1000.0
            last_frame_time = current_time

            running, selected_entity, sub_window_active = handle_input(
                list_of_molecular_clouds, selected_entity, sub_window_active
            )
            if not running:
                break

            angle += RING_ROTATION_SPEED * delta_time * 60
            ring.angle = angle
            ring.points = ring.set_ring_points()

            update_simulation_state(
                list_of_molecular_clouds, list_of_black_holes, list_of_neutron_stars,
                ring, delta_time, current_year
            )

            screen.fill(BACKGROUND_COLOR)

            draw_simulation(
                screen, ring, list_of_molecular_clouds, list_of_black_holes, list_of_neutron_stars
            )

            draw_ui(
                screen, font, current_year, selected_entity, sub_window_active
            )

            current_year += 1

            pygame.display.flip()

        print("Exited simulation")
    except Exception as e:
        import traceback
        print(f"Error occurred in simulation loop: {e}")
        traceback.print_exc()
    finally:
        pygame.quit()


def main():
    if os.path.isfile(sim_data):
        os.remove(sim_data)
        print(f"Checking and clearing sim_data")
    
    print("Populating space with molecular clouds")
    for _ in range(MOLECULAR_CLOUD_COUNT):
        radius = random.uniform(0, RING_RADIUS)
        angle = random.uniform(0, 2 * math.pi)
        x = SCREEN_WIDTH // 2 + radius * math.cos(angle)
        y = SCREEN_HEIGHT // 2 + radius * math.sin(angle)
        molecular_cloud = MOLECULAR_CLOUD(x, y, MOLECULAR_CLOUD_START_SIZE, MOLECULAR_CLOUD_START_MASS)
        list_of_molecular_clouds.append(molecular_cloud)

    print("Starting simulation")
    run_simulation()

if __name__ == "__main__":
    main()