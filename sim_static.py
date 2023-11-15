import pygame
import math
import random

RING_RADIUS = 500 #Default: 500
RING_ROTATION_SPEED = 0.1 #Default: 0.1
RING_GRAVITY_CONSTANT = 5 #Default: 5 -- Increase create my drag on units
RING_COLOR = (0, 0, 255) #Default: (0, 0, 255) -- Blue
RING_OPACITY = 50 #Range: 0-255

GRAVITY_CONSTANT = 0.1 #Unit gravity.

UNIT_COUNT = 5000
UNIT_START_SIZE = 25
UNIT_START_MASS = 2
UNIT_MAX_MASS = 100
UNIT_START_COLOR = (10, 0, 10) 
UNIT_END_COLOR = (255, 255, 255)

BLACK_HOLE_THRESHOLD = 99
BLACK_HOLE_GRAVITY_CONSTANT = 0.0001
BLACK_HOLE_DECAY_RATE = 1
BLACK_HOLE_DECAY_THRESHOLD = 1

SCREEN_WIDTH = 1080 #Default: 1080
SCREEN_HEIGHT = 1080 #Default: 1080

objects_with_gravity = [] #Units and black holes
black_holes = [] #Black holes

pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))

def interpolate_color(start_color, end_color, factor):
    r = start_color[0] + factor * (end_color[0] - start_color[0])
    g = start_color[1] + factor * (end_color[1] - start_color[1])
    b = start_color[2] + factor * (end_color[2] - start_color[2])
    return int(r), int(g), int(b)

class SpaceTimeUnit:
    def __init__(self, x, y, size, mass):
        self.x = x
        self.y = y
        self.size = size
        self.mass = mass
        self.gravity_sources = []

    def draw(self, screen):
        factor = self.mass / UNIT_MAX_MASS
        color = interpolate_color(UNIT_START_COLOR, UNIT_END_COLOR, factor)
        pygame.draw.rect(screen, color, (self.x, self.y, self.size, self.size))

    def update(self):
        self.size = max(5, UNIT_START_SIZE - int((self.mass - UNIT_START_MASS) * 0.5))
        self.mass = min(self.mass, UNIT_MAX_MASS)

    def check_collision(self, other):
        return (self.x < other.x + other.size and
                self.x + self.size > other.x and
                self.y < other.y + other.size and
                self.y + self.size > other.y)
    
    def update_gravity(self):
        for source in self.gravity_sources:
            dx = source.x - self.x
            dy = source.y - self.y
            distance = max(math.hypot(dx, dy), 1)
            force = GRAVITY_CONSTANT * (self.mass * source.mass) / (distance**2)
            self.x += (dx / distance) * force
            self.y += (dy / distance) * force
    
class BlackHole:
    def __init__(self, x, y, mass):
        self.x = x
        self.y = y
        self.mass = mass
        self.border_radius = int(mass // 10)

    def draw(self, screen):
        pygame.draw.circle(screen, (50, 0, 50), (self.x, self.y), self.border_radius)
        pygame.draw.circle(screen, (0, 0, 0), (self.x, self.y), self.mass // 10, 0)

    def attract(self, units, black_holes):
        units_to_remove = []
        for unit in units:
            if isinstance(unit, BlackHole) and unit.mass < self.mass:
                units_to_remove.append(unit)
            else:
                dx = self.x - unit.x
                dy = self.y - unit.y
                distance = max(math.hypot(dx, dy), 1)
                force = BLACK_HOLE_GRAVITY_CONSTANT * (self.mass * unit.mass) / (distance**2)
                unit.x += (dx / distance) * force
                unit.y += (dy / distance) * force

                unit.gravity_sources.append(self)

        for unit in units_to_remove:
            units.remove(unit)

    def decay(self):
        self.mass -= BLACK_HOLE_DECAY_RATE
        if self.mass < BLACK_HOLE_DECAY_THRESHOLD:
            if self in black_holes:
                black_holes.remove(self)
            
def handle_collisions(units):
    for i, unit in enumerate(units):
        for other in units[i+1:]:
            if unit.check_collision(other):
                merged_mass = unit.mass + other.mass
                units.remove(other)
                unit.mass = min(merged_mass, UNIT_MAX_MASS)
                unit.update()
                break

def get_ring_points(center, radius, num_points, angle):
    points = []
    for i in range(num_points):
        theta = angle + (2 * math.pi / num_points) * i
        x = center[0] + radius * math.cos(theta)
        y = center[1] + radius * math.sin(theta)
        points.append((x, y))
    return points

def draw_ring(points, color, opacity):
    for point in points:
        surface = pygame.Surface((10, 10), pygame.SRCALPHA)
        rgba_color = color + (opacity,)
        pygame.draw.circle(surface, rgba_color, (5, 5), 5)
        screen.blit(surface, (point[0] - 5, point[1] - 5))
"""
def apply_gravity(units, ring_points):
    for unit in units:
        for point in ring_points:
            dx = unit.x - point[0]
            dy = unit.y - point[1]
            distance = math.hypot(dx, dy)
            if distance > 0:
                force = RING_GRAVITY_CONSTANT * unit.mass / (distance**2)
                unit.x += (dx / distance) * force
                unit.y += (dy / distance) * force

"""
def apply_gravity(units, ring_points):
    for unit in units:
        for point in ring_points:
            dx = point[0] - unit.x
            dy = point[1] - unit.y
            distance = max(math.hypot(dx, dy), 1)
            force = RING_GRAVITY_CONSTANT * unit.mass / (distance**2)
            
            # Check if the unit is too close to the ring
            if distance > unit.size / 2:
                unit.x += (dx / distance) * force
                unit.y += (dy / distance) * force
                
def update_units(units):
    global black_holes
    handle_collisions(units)
    for unit in list(units):
        unit.update()
        if unit.mass > BLACK_HOLE_THRESHOLD:
            black_holes.append(BlackHole(unit.x, unit.y, unit.mass))
            units.remove(unit)

#units = [SpaceTimeUnit(random.randint(0, SCREEN_WIDTH), random.randint(0, SCREEN_HEIGHT), UNIT_START_SIZE, UNIT_START_MASS) for _ in range(UNIT_COUNT)]
units = []
for _ in range(UNIT_COUNT):
    radius = random.uniform(0, RING_RADIUS)
    angle = random.uniform(0, 2 * math.pi)
    x = SCREEN_WIDTH // 2 + radius * math.cos(angle)
    y = SCREEN_HEIGHT // 2 + radius * math.sin(angle)

    unit = SpaceTimeUnit(x, y, UNIT_START_SIZE, UNIT_START_MASS)
    units.append(unit)

def run_simulation():
    try:
        running = True
        angle = 0
        ring_points = get_ring_points((SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2), RING_RADIUS, 20, 0)

        decay_black_holes = []

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_q):
                    running = False

            screen.fill((0, 0, 5))

            angle += RING_ROTATION_SPEED
            ring_points = get_ring_points((SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2), RING_RADIUS, 20, angle)

            draw_ring(ring_points, RING_COLOR, RING_OPACITY)
            update_units(units)
            apply_gravity(units, ring_points)

            for black_hole in black_holes:
                black_hole.attract(units, black_holes)
                black_hole.decay()
                black_hole.draw(screen)
                if black_hole.mass <= BLACK_HOLE_DECAY_THRESHOLD:
                    decay_black_holes.append(black_hole)

            for decayed_black_hole in decay_black_holes.copy():
                if decayed_black_hole in black_holes:
                    black_holes.remove(decayed_black_hole)
                decay_black_holes.remove(decayed_black_hole)

            for unit in units:
                unit.update_gravity()

            for unit in units:
                unit.draw(screen)

            pygame.display.flip()

        print("Exiting simulation...")
    except Exception as e:
        print(f"Error occurred: {e}")
    finally:
        pygame.quit()

if __name__ == "__main__":
    print("Starting simulation...")
    run_simulation()