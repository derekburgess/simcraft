import os
import csv
import pygame
import math
import random
import matplotlib.pyplot as plt
import matplotlib.backends.backend_agg as agg


RING_RADIUS = 400
RING_ATTRACTOR_COUNT = 40
RING_ROTATION_SPEED = 0.01
RING_GRAVITY_CONSTANT = 1
RING_COLOR = (0, 0, 255)
RING_OPACITY = 0

MOLECULAR_CLOUD_COUNT = 4000
MOLECULAR_CLOUD_START_SIZE = 18
MOLECULAR_CLOUD_MIN_SIZE = 4
MOLECULAR_CLOUD_GROWTH_RATE = 0.8
MOLECULAR_CLOUD_START_MASS = 1
MOLECULAR_CLOUD_GRAVITY_CONSTANT = 0.02
MOLECULAR_CLOUD_MAX_MASS = 40
DEFAULT_STATE_CHANCE = 1
MOLECULAR_CLOUD_START_COLOR = (60, 0, 60)
MOLECULAR_CLOUD_END_COLOR = (225, 200, 255)

BLACK_HOLE_THRESHOLD = 35
BLACK_HOLE_CHANCE = 0.2
BLACK_HOLE_RADIUS = 16
BLACK_HOLE_GRAVITY_CONSTANT = 0.001
BLACK_HOLE_DECAY_RATE = 0.50
BLACK_HOLE_DECAY_THRESHOLD = 5
BLACK_HOLE_COLOR = (0,0,0)
BLACK_HOLE_BORDER_COLOR = (200, 0, 0)

NEUTRON_STAR_CHANCE = 0.2
NEUTRON_STAR_RADIUS = 2
NEUTRON_STAR_GRAVITY_CONSTANT = 0.01
NEUTRON_STAR_PULSE_STRENGTH = 400
NEUTRON_STAR_EFFECT_RADIUS = 800
NEUTRON_STAR_DECAY_RATE = 0.08
NEUTRON_STAR_DECAY_THRESHOLD = 0.8
NEUTRON_STAR_PULSE_RATE = 4
NEUTRON_STAR_COLOR = (0, 0, 200)

BACKGROUND_COLOR = (0, 0, 20)
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
            surface = pygame.Surface((10, 10), pygame.SRCALPHA)
            rgba_color = color + (opacity,)
            pygame.draw.circle(surface, rgba_color, (5, 5), 5)
            screen.blit(surface, (point[0] - 5, point[1] - 5))

    def apply_gravity(self, list_of_molecular_clouds):
        for molecular_cloud in list_of_molecular_clouds:
            for point in self.points:
                dx = point[0] - molecular_cloud.x
                dy = point[1] - molecular_cloud.y
                distance = max(math.hypot(dx, dy), 1)
                force = RING_GRAVITY_CONSTANT * molecular_cloud.mass / (distance**2)
                if distance > molecular_cloud.size / 2:
                    molecular_cloud.x += (dx / distance) * force
                    molecular_cloud.y += (dy / distance) * force


def interpolate_color(start_color, end_color, factor):
    r = start_color[0] + factor * (end_color[0] - start_color[0])
    g = start_color[1] + factor * (end_color[1] - start_color[1])
    b = start_color[2] + factor * (end_color[2] - start_color[2])
    return int(r), int(g), int(b)


list_of_molecular_clouds = []
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

    def draw_molecular_cloud(self, screen):
        if self.selected:
            highlight_color = (255, 165, 0)
            pygame.draw.rect(screen, highlight_color, (self.x, self.y, self.size, self.size))
        else:
            factor = self.mass / MOLECULAR_CLOUD_MAX_MASS
            self.color = interpolate_color(MOLECULAR_CLOUD_START_COLOR, MOLECULAR_CLOUD_END_COLOR, factor)
            pygame.draw.rect(screen, self.color, (self.x, self.y, self.size, self.size))

    def update_molecular_cloud(self):
        self.size = max(MOLECULAR_CLOUD_MIN_SIZE, MOLECULAR_CLOUD_START_SIZE - int((self.mass - MOLECULAR_CLOUD_START_MASS) * MOLECULAR_CLOUD_GROWTH_RATE))
        self.mass = min(self.mass, MOLECULAR_CLOUD_MAX_MASS)
        if self.size < 6:
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
class BLACK_HOLE:
    def __init__(self, x, y, mass):
        self.id = generate_unique_id()
        self.x = x
        self.y = y
        self.mass = mass
        self.border_radius = int(mass // BLACK_HOLE_RADIUS)
        self.gravity_sources = []

    def draw_black_hole(self, screen):
        radius = int(self.mass // BLACK_HOLE_RADIUS)
        pygame.draw.circle(screen, BLACK_HOLE_BORDER_COLOR, (int(self.x), int(self.y)), radius)
        pygame.draw.circle(screen, BLACK_HOLE_COLOR, (int(self.x), int(self.y)), radius - 2)

    def attract_entities_to_black_holes(self, list_of_molecular_clouds, list_of_neutron_stars):
        list_of_entities_to_remove = []
        for entity in list_of_molecular_clouds + list_of_neutron_stars:
            dx = self.x - entity.x
            dy = self.y - entity.y
            distance = max(math.hypot(dx, dy), 1)
            
            if isinstance(entity, BLACK_HOLE) and entity.mass < self.mass:
                list_of_entities_to_remove.append(entity)
            elif isinstance(entity, NEUTRON_STAR) and distance < self.border_radius:
                list_of_entities_to_remove.append(entity)
                self.mass += entity.mass
            elif isinstance(entity, MOLECULAR_CLOUD) and distance < self.border_radius:
                list_of_entities_to_remove.append(entity)
                self.mass += entity.mass
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
        self.x = x
        self.y = y
        self.mass = mass
        self.radius = NEUTRON_STAR_RADIUS
        self.pulse_rate = NEUTRON_STAR_PULSE_RATE
        self.pulse_strength = NEUTRON_STAR_PULSE_STRENGTH
        self.time_since_last_pulse = 0
        self.gravity_sources = []

    def draw_neotron_star(self, screen):
        pygame.draw.circle(screen, NEUTRON_STAR_COLOR, (self.x, self.y), self.radius)

    def pulse_gravity_from_neutron_star(self, list_of_molecular_clouds, delta_time):
        self.time_since_last_pulse += delta_time
        if self.time_since_last_pulse >= self.pulse_rate:
            for molecular_cloud in list_of_molecular_clouds:
                dx = molecular_cloud.x - self.x
                dy = molecular_cloud.y - self.y
                distance = max(math.hypot(dx, dy), 1)
                
                if distance < NEUTRON_STAR_EFFECT_RADIUS:
                    force = self.pulse_strength / (distance ** 2)
                    molecular_cloud.x += (dx / distance) * force
                    molecular_cloud.y += (dy / distance) * force
                    
            self.time_since_last_pulse = 0

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
            if 20 <= molecular_cloud.mass <= BLACK_HOLE_THRESHOLD:
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
    snapshot_pos = (26, SCREEN_HEIGHT - 110)
    screen.blit(font.render('[Q] EXIT', True, LABEL_COLOR), (snapshot_pos[0], snapshot_pos[1]))
    snapshot_pos = (26, SCREEN_HEIGHT - 80)
    screen.blit(font.render('[SPACEBAR] DATA SNAPSHOT', True, LABEL_COLOR), (snapshot_pos[0], snapshot_pos[1])) 


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
        

        # Handle user input
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_q):
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                    dump_to_csv(list_of_molecular_clouds, list_of_black_holes, list_of_neutron_stars, current_year)

                if event.type == pygame.MOUSEBUTTONDOWN:
                    click_x, click_y = event.pos
                    if sub_window_active:
                        if CLOSE_BUTTON_RECT.collidepoint(click_x, click_y):
                            if selected_entity:
                                selected_entity.selected = False
                                selected_entity = None
                            sub_window_active = False
                        elif not SUB_WINDOW_RECT.collidepoint(click_x, click_y):
                            for molecular_cloud in list_of_molecular_clouds:
                                molecular_cloud.selected = False
                                if molecular_cloud.molecular_cloud_clicked(click_x, click_y):
                                    selected_entity = molecular_cloud
                                    molecular_cloud.selected = True
                                    sub_window_active = True
                    else:
                        for molecular_cloud in list_of_molecular_clouds:
                            molecular_cloud.selected = False
                            if molecular_cloud.molecular_cloud_clicked(click_x, click_y):
                                selected_entity = molecular_cloud
                                molecular_cloud.selected = True
                                sub_window_active = True
            

            # Set up the screen and draw the key and timer
            current_time = pygame.time.get_ticks()
            delta_time = (current_time - last_frame_time) / 1000
            last_frame_time = current_time
            screen.fill(BACKGROUND_COLOR)

            draw_static_key(screen)
            if current_year == 20:
                dump_to_csv(list_of_molecular_clouds, list_of_black_holes, list_of_neutron_stars, current_year)

            if current_year % SNAPSHOT_SPEED == 0:
                dump_to_csv(list_of_molecular_clouds, list_of_black_holes, list_of_neutron_stars, current_year)

            current_year += 1
            year_text = font.render(f"TIME(YEARS): {current_year}M", True, LABEL_COLOR)
            screen.blit(year_text, (30, SCREEN_HEIGHT - 40 ))
            

            # Update and draw Attractor Ring
            ring = ATTRACTOR_RING((SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2), RING_RADIUS, RING_ATTRACTOR_COUNT, 0)
            ring.points = ring.set_ring_points()
            angle += RING_ROTATION_SPEED
            ring.angle = angle
            ring.points = ring.set_ring_points()
            ring.draw_ring(screen, RING_COLOR, RING_OPACITY)
            update_entities(list_of_molecular_clouds)
            ring.apply_gravity(list_of_molecular_clouds)


            # Update and draw Molecular Clouds
            for molecular_cloud in list_of_molecular_clouds:
                molecular_cloud.update_gravity_of_molecular_clouds()
            for molecular_cloud in list_of_molecular_clouds:
                molecular_cloud.draw_molecular_cloud(screen)


            # Update and draw Black Holes
            decay_blackholes = []
            for black_hole in list_of_black_holes:
                black_hole.attract_entities_to_black_holes(list_of_molecular_clouds, list_of_neutron_stars)
                black_hole.update_gravity_of_black_holes(list_of_molecular_clouds, list_of_neutron_stars)
                black_hole.black_hole_decay()
                black_hole.draw_black_hole(screen)
                if black_hole.mass <= BLACK_HOLE_DECAY_THRESHOLD:
                    decay_blackholes.append(black_hole)
            for decayed_black_hole in decay_blackholes.copy():
                if decayed_black_hole in list_of_black_holes:
                    list_of_black_holes.remove(decayed_black_hole)
                decay_blackholes.remove(decayed_black_hole)


            # Update and draw Neutron Stars
            decay_neutronstars = []
            for neutron_star in list_of_neutron_stars:
                neutron_star.update_position_of_entities_from_pulse(list_of_molecular_clouds, delta_time)
                neutron_star.pulse_gravity_from_neutron_star(list_of_molecular_clouds, delta_time)
                neutron_star.decay_neutron_star()
                neutron_star.draw_neotron_star(screen)
                if neutron_star.mass <= BLACK_HOLE_DECAY_THRESHOLD:
                    decay_neutronstars.append(neutron_star)
            for decay_neutronstar in decay_neutronstars.copy():
                if decay_neutronstar in list_of_neutron_stars:
                    list_of_neutron_stars.remove(decay_neutronstar)
                decay_neutronstars.remove(decay_neutronstar)



            # Everything Below is for the window-in-window data readout.

            def load_csv_data(file_path):
                with open(file_path, 'r') as file:
                    reader = csv.DictReader(file)
                    data = {}
                    for row in reader:
                        entityid = row['entityid']
                        if entityid not in data:
                            data[entityid] = []
                        data[entityid].append(row)
                    return data
            csv_data = load_csv_data(sim_data)

            def plot_graph(x_values, data, title):
                fig, ax = plt.subplots(figsize=(2, 1), dpi=80)
                fig.patch.set_alpha(0.0)
                ax.patch.set_alpha(0.0)
                colors = ['white', 'gray', 'purple']
                linestyles = [':', ':', '-']
                for i, (key, y_values) in enumerate(data.items()):
                    ax.plot(x_values, y_values, label=key.upper(), color=colors[i % len(colors)], linestyle=linestyles[i % len(linestyles)])
                ax.set_xticklabels([])
                ax.set_yticklabels([])
                plt.tight_layout()
                canvas = agg.FigureCanvasAgg(fig)
                canvas.draw()
                plt.close(fig)
                return canvas

            def display_molecular_cloud_data(screen, selected_entity, rect, font, csv_data):
                if selected_entity is None:
                    return
                
                live_data_texts = [
                    "LIVE DATA:",
                    f"ID: {selected_entity.id}",
                    f"POSX: {round(selected_entity.x, 5)}",
                    f"POSY: {round(selected_entity.y, 5)}",
                    f"MASS: {selected_entity.mass}",
                    f"SIZE: {selected_entity.size}",
                    f"FLUX: {selected_entity.opacity}"
                ]

                y_offset = 5
                for text in live_data_texts:
                    text_surface = font.render(text, True, LABEL_COLOR)
                    screen.blit(text_surface, (rect.x + 10, rect.y + y_offset))
                    y_offset += 20

                y_offset = 160
                molecular_cloud_csv_data = csv_data.get(str(selected_entity.id))
                if molecular_cloud_csv_data:
                    csv_header_text = "OBSERVATIONAL DATA:"
                    header_surface = font.render(csv_header_text, True, LABEL_COLOR)
                    screen.blit(header_surface, (rect.x + 10, rect.y + y_offset))
                    y_offset += 20

                    most_recent_observation = molecular_cloud_csv_data[-1]
                    for key, value in most_recent_observation.items():
                        if key == 'posx' or key == 'posy':
                            value = round(float(value), 5)

                        csv_text = f"{key.upper()}: {value}"
                        text_surface = font.render(csv_text, True, LABEL_COLOR)
                        screen.blit(text_surface, (rect.x + 10, rect.y + y_offset))
                        y_offset += 20

                    x_values = [float(row['observation']) for row in molecular_cloud_csv_data]
                    data = {key: [float(row[key]) for row in molecular_cloud_csv_data] for key in ['mass', 'size', 'flux']}
                    min_length = min(len(x_values), min(len(v) for v in data.values()))
                    x_values = x_values[:min_length]
                    data = {k: v[:min_length] for k, v in data.items()}
                    canvas = plot_graph(x_values, data, "OBSERVATIONAL DATA")
                    width, height = canvas.get_width_height()
                    pygame_surface = pygame.image.fromstring(canvas.tostring_argb(), (width, height), 'ARGB')
                    screen.blit(pygame_surface, (rect.x + 10, rect.y + y_offset))

            if sub_window_active:
                pygame.draw.rect(screen, BORDER_COLOR, SUB_WINDOW_RECT, 1)
                inner_rect = SUB_WINDOW_RECT.inflate(-2 * 1, -2 * 1)
                pygame.draw.rect(screen, BOX_BG_COLOR, inner_rect)
                pygame.draw.rect(screen, BORDER_COLOR, CLOSE_BUTTON_RECT)
                if selected_entity:
                    display_molecular_cloud_data(screen, selected_entity, SUB_WINDOW_RECT, font, csv_data)

            # END of window-in-window data readout.


            pygame.display.flip()
        print("Exited simulation")
    except Exception as e:
        print(f"Error occurred: {e}")
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