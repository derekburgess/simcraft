import datetime
import pygame
import numpy as np

window_size = 720
time_scale = 1
cell_size = 360
num_units = 50
max_initial_mass = 1
gravity_mass_threshold = 3
unit_radius = 1
min_color_value = 20
max_color_value = 235
tick_spacing = 1
attractor_mass = 250
attractor_size = 5
attractor_color = (0, 150, 0)
ring_radius = window_size // 2
black_hole_mass_threshold = 10
max_black_hole_size = 50

pygame.init()
screen = pygame.display.set_mode((window_size, window_size))
pygame.display.set_caption("Universal Clock")

def draw_background():
    screen.fill((0, 0, 0))
    grid_color = (10, 10, 10)
    for x in range(0, window_size, cell_size):
        pygame.draw.line(screen, grid_color, (x, 0), (x, window_size), 1)
    for y in range(0, window_size, cell_size):
        pygame.draw.line(screen, grid_color, (0, y), (window_size, y), 1)

def draw_ring():
    now = datetime.datetime.now()
    minute_angle = now.minute * 6
    second_fraction = now.second / 60.0 
    radian_angle = np.radians(minute_angle + second_fraction * 6 - 90)
    x = window_size // 2 + ring_radius * np.cos(radian_angle)
    y = window_size // 2 + ring_radius * np.sin(radian_angle)
    pygame.draw.circle(screen, attractor_color, (int(x), int(y)), attractor_size)

def draw_clock_face():
    center = (window_size // 2, window_size // 2)
    pygame.draw.circle(screen, (0, 0, 0), center, ring_radius, 1)

def draw_hours():
    now = datetime.datetime.now()
    current_hour = now.hour % 12
    unique_hour_color = (0, 150, 0)
    standard_hour_color = (50, 50, 50)

    font = pygame.font.SysFont('Monospace', 36)
    for hour in range(1, 13):
        angle = hour * 30 - 90
        radian_angle = np.radians(angle)
        x = window_size // 2 + (ring_radius - 30) * np.cos(radian_angle)
        y = window_size // 2 + (ring_radius - 30) * np.sin(radian_angle)
        hour_color = unique_hour_color if hour == current_hour else standard_hour_color
        text_surface = font.render(str(hour), True, hour_color)
        text_rect = text_surface.get_rect(center=(int(x), int(y)))
        screen.blit(text_surface, text_rect)

def apply_ring_gravity(unit):
    now = datetime.datetime.now()
    second_angle = now.second * 6
    radian_angle = np.radians(second_angle - 90)
    ring_x = window_size // 2 + ring_radius * np.cos(radian_angle)
    ring_y = window_size // 2 + ring_radius * np.sin(radian_angle)
    direction = np.array([ring_x, ring_y]) - unit[:2]
    distance = np.linalg.norm(direction)
    gravitational_threshold = 100
    max_velocity = 0.05 
    if 0 < distance < gravitational_threshold:
        gravity_effect = attractor_mass / (distance ** 2) * direction / distance
        gravity_effect = np.clip(gravity_effect, -max_velocity, max_velocity)
        return gravity_effect
    return np.array([0, 0])

def apply_unit_gravity(source_unit, target_unit):
    direction = source_unit[:2] - target_unit[:2]
    distance = np.linalg.norm(direction)
    if distance > 0:
        return source_unit[2] / (distance ** 2) * direction / distance
    return np.array([0, 0])

def get_spatial_hash(x, y):
    return int(x / cell_size), int(y / cell_size)

def update_spatial_grid(units):
    spatial_grid = {}
    for i, unit in enumerate(units):
        cell = get_spatial_hash(unit[0], unit[1])
        if cell not in spatial_grid:
            spatial_grid[cell] = []
        spatial_grid[cell].append(i)
    return spatial_grid

def get_neighboring_cells(cell):
    x, y = cell
    neighbors = [(x - 1, y - 1), (x, y - 1), (x + 1, y - 1),
                 (x - 1, y), (x, y), (x + 1, y),
                 (x - 1, y + 1), (x, y + 1), (x + 1, y + 1)]
    return neighbors

def merge_units(units, i, j):
    if i < len(units) and j < len(units) and units[i][2] > units[j][2]:
        units[i][:2] = (units[i][:2] * units[i][2] + units[j][:2] * units[j][2]) / (units[i][2] + units[j][2])
        units[i][2] += units[j][2]
        units = np.delete(units, j, 0)
    return units

def add_new_unit(units):
    new_unit = np.zeros(5)
    new_unit[:2] = np.random.rand(2) * window_size 
    new_unit[2] = np.random.rand() * max_initial_mass
    new_unit[3:5] = np.random.rand(2) * 2 - 1
    return np.append(units, [new_unit], axis=0)

units = np.zeros((num_units, 5))
units[:, :2] = np.random.rand(num_units, 2) * window_size
units[:, 2] = np.random.rand(num_units) * max_initial_mass
units[:, 3:5] = np.random.rand(num_units, 2) * 2 - 1

running = True
clock = pygame.time.Clock()
unit_add_interval = 120
frame_count = 0

while running:
    if frame_count % unit_add_interval == 0:
        potential_source_units = [unit for unit in units if unit[2] < gravity_mass_threshold]
        
        if potential_source_units:
            source_unit_index = np.random.choice(len(potential_source_units))
            source_unit = potential_source_units[source_unit_index]
            spawn_position = source_unit[:2] + np.random.uniform(-50, 50, size=(2,))
            new_unit = np.zeros(5)
            new_unit[:2] = spawn_position
            new_unit[2] = np.random.rand() * max_initial_mass
            new_unit[3:5] = np.random.rand(2) * 2 - 1
            units = np.append(units, [new_unit], axis=0)

    draw_background()
    draw_clock_face()
    draw_ring()
    draw_hours()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_q:
            running = False

    spatial_grid = update_spatial_grid(units)
    for i, unit in enumerate(units):
        total_gravity_effect = np.array([0.0, 0.0], dtype=np.float64)
        ring_gravity_effect = apply_ring_gravity(unit)
        total_gravity_effect += ring_gravity_effect

        for j, other_unit in enumerate(units):
            if i != j and other_unit[2] >= gravity_mass_threshold:
                unit_gravity_effect = apply_unit_gravity(other_unit, unit)
                total_gravity_effect += np.array(unit_gravity_effect, dtype=np.float64)

        unit[:2] += total_gravity_effect * time_scale

        if unit[2] >= black_hole_mass_threshold:
                if unit[2] > max_black_hole_size:
                    unit[2] = max_black_hole_size
                for j, other_unit in enumerate(units):
                    if i != j:
                        distance = np.linalg.norm(unit[:2] - other_unit[:2])
                        if distance < (unit_radius + np.sqrt(other_unit[2])):
                            unit[2] += other_unit[2]
                            units = np.delete(units, j, 0)
                            break

    spatial_grid = update_spatial_grid(units)

    for cell, indices in spatial_grid.items():
        for i in list(indices):
            if i >= len(units):
                continue
            unit = units[i]
            neighbors = get_neighboring_cells(cell) + [cell]
            for neighbor_cell in neighbors:
                if neighbor_cell in spatial_grid:
                    for j in list(spatial_grid[neighbor_cell]):
                        if j >= len(units):
                            continue
                        if i != j:
                            other_unit = units[j]
                            if abs(unit[0] - other_unit[0]) < (unit_radius + np.sqrt(other_unit[2])) and \
                               abs(unit[1] - other_unit[1]) < (unit_radius + np.sqrt(other_unit[2])):
                                units = merge_units(units, i, j)
                                spatial_grid = update_spatial_grid(units)
                                break

    for unit in units:
        unit_size = unit_radius + int(np.sqrt(unit[2])) * 2
        if unit[2] >= black_hole_mass_threshold:
            unit_color = (10, 10, 10)
        else:
            color_intensity = int(min_color_value + (unit[2] / max_initial_mass) * (max_color_value - min_color_value))
            color_intensity = max(0, min(color_intensity, 255))
            unit_color = (color_intensity, color_intensity, color_intensity)
        unit_rect = pygame.Rect(unit[:2].astype(int) - unit_size // 2, (unit_size, unit_size))
        pygame.draw.rect(screen, unit_color, unit_rect)

    pygame.display.flip()
    clock.tick(60)

pygame.quit()