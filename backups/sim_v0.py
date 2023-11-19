import pygame
import math
import random
import csv
import os

RING_RADIUS = 500 #Default: 500
RING_ROTATION_SPEED = 1 #Default: 1
RING_GRAVITY_CONSTANT = 20 #Default: 20
RING_COLOR = (0, 0, 255) #Default: (0, 0, 255) -- Blue
RING_OPACITY = 0 #Default: 0, Range: 0-255

GRAVITY_CONSTANT = 0.05 #Default: 0.05
UNIT_COUNT = 5000 #Default: 5000
UNIT_START_SIZE = 15 #Default: 15
UNIT_START_MASS = 1 #Default: 1
UNIT_MAX_MASS = 50 #Default: 50
UNIT_START_COLOR = (60, 0, 60) #Default: (60, 0, 60) -- Dark Purple
UNIT_END_COLOR = (225, 200, 255) #Default: (225, 200, 255) -- Light Purple

BLACK_HOLE_THRESHOLD = 49 #Default: 49
BLACK_HOLE_GRAVITY_CONSTANT = 0.01 #Default: 0.01
BLACK_HOLE_DECAY_RATE = 0.5 #Default: 1
BLACK_HOLE_DECAY_THRESHOLD = 10 #Default: 10

GRID_COLOR = (0, 0, 100) #Default: (0, 0, 100) -- Dark Blue
GRID_OPACITY = 10 #Default: 10, Range: 0-255
GRID_LINES_HORIZONTAL = 12 #Default: 12
GRID_LINES_VERTICAL = 12 #Default: 12

BACKGROUND_COLOR = (0, 0, 10) #Default: (0, 0, 10) -- Dark Blue
SCREEN_WIDTH = 1200 #Default: 1200
SCREEN_HEIGHT = 1200 #Default: 1200

objects_with_gravity = [] #Units and black holes
black_holes = [] #Black holes

pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
font = pygame.font.SysFont('Monospace', 14) #Font for time text.
pygame.display.set_caption("simcraft")

#Interpolate color between two colors, used for units as they transition from molecular clouds to stars.
def interpolate_color(start_color, end_color, factor):
    r = start_color[0] + factor * (end_color[0] - start_color[0])
    g = start_color[1] + factor * (end_color[1] - start_color[1])
    b = start_color[2] + factor * (end_color[2] - start_color[2])
    return int(r), int(g), int(b)

#Draw grid on screen
def draw_grid(screen, font, color, opacity, lines_horizontal, lines_vertical):
    grid_color = color + (opacity,)
    screen_width, screen_height = screen.get_size()
    text_color = (0, 0, 255)  # White or choose another contrasting color
    label_offset = 5  # Offset for label positioning

    # Draw horizontal lines and label them on the right
    for i in range(lines_horizontal + 1):
        y = screen_height / lines_horizontal * i
        pygame.draw.line(screen, grid_color, (0, y), (screen_width, y))
        # Add label (A-Z)
        if i < 26:  # Limit to 26 letters (A-Z)
            label = chr(65 + i)  # ASCII value for A is 65
            text_surface = font.render(label, True, text_color)
            screen.blit(text_surface, (screen_width - text_surface.get_width() - label_offset, y))

    # Draw vertical lines and label them at the bottom
    for i in range(lines_vertical + 1):
        x = screen_width / lines_vertical * i
        pygame.draw.line(screen, grid_color, (x, 0), (x, screen_height))
        # Add label (1-9, then 10, 11, ...)
        label = str(i + 1)
        text_surface = font.render(label, True, text_color)
        screen.blit(text_surface, (x, screen_height - text_surface.get_height() - label_offset))

def draw_static_key(screen):
    # Molecular Cloud Key
    molecular_cloud_pos = (15, 1050)
    pygame.draw.rect(screen, UNIT_START_COLOR, (molecular_cloud_pos[0], molecular_cloud_pos[1], 15, 15))
    screen.blit(font.render('MOLECULAR CLOUD', True, (200, 200, 200)), (molecular_cloud_pos[0] + 30, molecular_cloud_pos[1]))
    # Protostar Key
    protostar_pos = (21, 1085)
    pygame.draw.rect(screen, UNIT_END_COLOR, (protostar_pos[0], protostar_pos[1], 3, 3))
    screen.blit(font.render('PROTOSTAR', True, (200, 200, 200)), (protostar_pos[0] + 25, protostar_pos[1] - 6))
    # Primordial Black Hole Key
    black_hole_pos = (22, 1115)
    pygame.draw.circle(screen, (0, 0, 0), black_hole_pos, 6)
    pygame.draw.circle(screen, (255, 0, 0), black_hole_pos, 6, 2)
    screen.blit(font.render('PRIMORDIAL BLACK HOLE', True, (200, 200, 200)), (black_hole_pos[0] + 22, black_hole_pos[1] - 8))

#Unit class, also known as SpaceTimeUnit, probably because I described these as "units of spacetime" to OpenAI.
#This class is to represent the molecular clouds as they transition into stars. It also handles gravity for each "unit".
#A unit is represented by the square pixels that start out as large, low-mass molecular clouds and transition into small, high-mass stars.
class SpaceTimeUnit:
    def __init__(self, x, y, size, mass):
        self.x = x #X position of the unit, this will be used to set the X position of the unit.
        self.y = y #Y position of the unit, this will be used to set the Y position of the unit.
        self.size = size #Size of the unit, this will be used to set the size of the unit.
        self.mass = mass #Mass of the unit, this will be used to set the mass of the unit.
        self.gravity_sources = [] #Set gravity sources to an empty list, this will be used to set the gravity sources of the unit.

    #Draw the unit on the screen.
    def draw(self, screen):
        #Interpolate color between two colors, used for units as they transition from molecular clouds to stars.
        factor = self.mass / UNIT_MAX_MASS
        #Set color to the interpolated color.
        color = interpolate_color(UNIT_START_COLOR, UNIT_END_COLOR, factor)
        #Draw the unit on the screen.
        pygame.draw.rect(screen, color, (self.x, self.y, self.size, self.size))

    #Update the unit.
    def update(self):
        #3 is the minimum size of the unit. 0.5 is the rate at which the unit shrinks.
        self.size = max(3, UNIT_START_SIZE - int((self.mass - UNIT_START_MASS) * 0.5))
        #Update the unit's gravity.
        self.mass = min(self.mass, UNIT_MAX_MASS)

    #Check if unit collides with another unit and return True if it does, use this to inform handle_collisions().
    def check_collision(self, other):
        return (self.x < other.x + other.size and
                self.x + self.size > other.x and
                self.y < other.y + other.size and
                self.y + self.size > other.y)
    
    #Update the unit's gravity.
    def update_gravity(self):
        for source in self.gravity_sources:
            dx = source.x - self.x
            dy = source.y - self.y
            #Distance between the unit and the source. 1 is the minimum distance.
            distance = max(math.hypot(dx, dy), 1)
            #Force between the unit and the source.
            force = GRAVITY_CONSTANT * (self.mass * source.mass) / (distance**2)   
            self.x += (dx / distance) * force
            self.y += (dy / distance) * force
    
class BlackHole:
    def __init__(self, x, y, mass):
        self.x = x
        self.y = y
        self.mass = mass #Mass of the black hole, this will be used to set the mass of the black hole.
        self.border_radius = int(mass // 20) #Radius of the black hole's border, this will be used to set the radius of the black hole's border.

    #Draw the black hole on the screen.
    def draw(self, screen):
        pygame.draw.circle(screen, (255, 0, 0), (self.x, self.y), self.border_radius) #255, 0, 0 is red.
        pygame.draw.circle(screen, (0, 0, 0), (self.x, self.y), self.mass // 20, 0) #0, 0, 0 is black. 1/20th of the mass of the black hole is the radius of the black hole.

    #Attract units to the black hole.
    def attract(self, units, black_holes):
        #Remove units that are black holes and have a mass less than the mass of the black hole.
        units_to_remove = []
        for unit in units:
            #If unit is a black hole and its mass is less than the mass of the black hole it is being attracted to, remove it from the simulation.
            if isinstance(unit, BlackHole) and unit.mass < self.mass:
                units_to_remove.append(unit)
            else:
                dx = self.x - unit.x
                dy = self.y - unit.y
                #Distance between the unit and the black hole. 1 is the minimum distance. 1 is the minimum distance.
                distance = max(math.hypot(dx, dy), 1)
                #Force between the unit and the black hole.
                force = BLACK_HOLE_GRAVITY_CONSTANT * (self.mass * unit.mass) / (distance**2)
                unit.x += (dx / distance) * force
                unit.y += (dy / distance) * force
                unit.gravity_sources.append(self)
        #Remove units that are smaller than the black hole
        for unit in units_to_remove:
            units.remove(unit)

    #Update the black hole's gravity.
    def update_gravity(self, units, other_black_holes):
        for obj in units + other_black_holes:
            #If object is not the black hole, update the black hole's gravity.
            if obj is not self:
                dx = obj.x - self.x
                dy = obj.y - self.y
                #Distance between the black hole and the object. 1 is the minimum distance. 1 is the minimum distance.
                distance = max(math.hypot(dx, dy), 1)
                #Force between the black hole and the object.
                force = GRAVITY_CONSTANT * (self.mass * obj.mass) / (distance**2)
                self.x += (dx / distance) * force
                self.y += (dy / distance) * force

    #Decay the black hole.
    def decay(self):
        #Decay the black hole if its mass is less than the black hole decay threshold.
        self.mass -= BLACK_HOLE_DECAY_RATE
        #If the black hole's mass is less than the black hole decay threshold, remove it from the simulation.
        if self.mass < BLACK_HOLE_DECAY_THRESHOLD:
            #Remove the black hole from the simulation.
            if self in black_holes:
                black_holes.remove(self)

#Handle collisions between units.  
def handle_collisions(units):
    for i, unit in enumerate(units):
        #Check if unit collides with another unit.
        for other in units[i+1:]:
            #If unit collides with another unit, merge the units.
            if unit.check_collision(other):
                #Merge the units.
                merged_mass = unit.mass + other.mass
                #If unit is a black hole and its mass is greater than the mass of the other unit, remove the other unit from the simulation.
                units.remove(other)
                #If unit is a black hole and its mass is greater than the mass of the other unit, set the mass of the unit to the merged mass.
                unit.mass = min(merged_mass, UNIT_MAX_MASS)
                unit.update()
                break

#Set up Attractor Ring: This is important because a solid ring did not create the effect I was looking for. This allows for the creation gravitational sources that create a crude sudo-manifold around the units.
def get_ring_points(center, radius, num_points, angle):
    points = []
    for i in range(num_points):
        theta = angle + (2 * math.pi / num_points) * i
        x = center[0] + radius * math.cos(theta)
        y = center[1] + radius * math.sin(theta)
        points.append((x, y))
    return points

#Draw the ring on the screen.
def draw_ring(points, color, opacity):
    for point in points:
        #Create surface, set source alpha.
        surface = pygame.Surface((10, 10), pygame.SRCALPHA)
        rgba_color = color + (opacity,)
        pygame.draw.circle(surface, rgba_color, (5, 5), 5)
        screen.blit(surface, (point[0] - 5, point[1] - 5))
        #Blit surface to screen. Blitting is a term used in computer graphics to refer to the process of combining two images to form a third, resulting in a new image.

#Apply gravity to units based on ring points. This creates the gravitational effect for each point as it passes by a section of the universe it will attract units toward it.
def apply_gravity(units, ring_points):
    for unit in units:
        for point in ring_points:
            dx = point[0] - unit.x
            dy = point[1] - unit.y
            #Distance between the unit and the point. 1 is the minimum distance.
            distance = max(math.hypot(dx, dy), 1)
            #Force between the unit and the point.
            force = RING_GRAVITY_CONSTANT * unit.mass / (distance**2)
            if distance > unit.size / 2:
                unit.x += (dx / distance) * force
                unit.y += (dy / distance) * force

#Update units.
def update_units(units):
    #Use global objects_with_gravity and black_holes.
    global black_holes
    #Handle collisions between units.
    handle_collisions(units)
    #Update units.
    for unit in list(units):
        #If unit is a black hole, update the black hole.
        unit.update()
        #If unit is a black hole and its mass is greater than the black hole threshold, remove it from the simulation.
        if unit.mass > BLACK_HOLE_THRESHOLD:
            #Remove the black hole from the simulation.
            black_holes.append(BlackHole(unit.x, unit.y, unit.mass))
            units.remove(unit)

units = []
for _ in range(UNIT_COUNT):
    #Generate random radius and angle.
    radius = random.uniform(0, RING_RADIUS)
    #Generate random angle between 0 and 2 * pi.
    angle = random.uniform(0, 2 * math.pi)
    #Generate x and y coordinates.
    x = SCREEN_WIDTH // 2 + radius * math.cos(angle)
    y = SCREEN_HEIGHT // 2 + radius * math.sin(angle)
    #Create unit.
    unit = SpaceTimeUnit(x, y, UNIT_START_SIZE, UNIT_START_MASS)
    units.append(unit)

#Dump data to CSV
def dump_to_csv(units, black_holes, filename='data.csv'):
    #Check if file exists.
    file_exists = os.path.isfile(filename)
    with open(filename, mode='a' if file_exists else 'w', newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            #Write header.
            writer.writerow(['Type', 'X', 'Y', 'Mass', 'Size'])
        for unit in units:
            #Write unit data.
            writer.writerow(['Unit', unit.x, unit.y, unit.mass, unit.size])
        for black_hole in black_holes:
            #Write black hole data.
            writer.writerow(['BlackHole', black_hole.x, black_hole.y, black_hole.mass, black_hole.border_radius])

#Run simulation.
def run_simulation():
    try:
        running = True
        angle = 0
        ring_points = get_ring_points((SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2), RING_RADIUS, 20, 0)
        decay_black_holes = []
        years = 0
        pygame.font.init()

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_q):
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                    dump_to_csv(units, black_holes)

            #Fill screen with background color
            screen.fill(BACKGROUND_COLOR)
            #Draw grid on screen
            draw_grid(screen, font, GRID_COLOR, GRID_OPACITY, GRID_LINES_HORIZONTAL, GRID_LINES_VERTICAL)
            #Draw static key on screen
            draw_static_key(screen)
            #Increment years
            years += 1
            #Render time text
            year_text = font.render(f"TIME(YEARS): {years}M", True, (200, 200, 200))
            #Blit time text to screen
            screen.blit(year_text, (15, SCREEN_HEIGHT - 50))
            #Increment angle
            angle += RING_ROTATION_SPEED
            #Get ring points
            ring_points = get_ring_points((SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2), RING_RADIUS, 20, angle)
            draw_ring(ring_points, RING_COLOR, RING_OPACITY)
            update_units(units)
            apply_gravity(units, ring_points)
            
            #Update black holes
            for black_hole in black_holes:
                #Attract units to the black hole.
                black_hole.attract(units, black_holes)
                #Update the black hole's gravity.
                black_hole.update_gravity(units, black_holes)
                #Decay the black hole.
                black_hole.decay()
                #Draw the black hole on the screen.
                black_hole.draw(screen)
                #Remove the black hole from the simulation if its mass is less than the black hole decay threshold.
                if black_hole.mass <= BLACK_HOLE_DECAY_THRESHOLD:
                    #Add the black hole to the decay black holes list.
                    decay_black_holes.append(black_hole)
            #Remove the black hole from the simulation if its mass is less than the black hole decay threshold.
            for decayed_black_hole in decay_black_holes.copy():
                #Remove the black hole from the simulation.
                if decayed_black_hole in black_holes:
                    black_holes.remove(decayed_black_hole)
                decay_black_holes.remove(decayed_black_hole)
            
            #Update units
            for unit in units:
                unit.update_gravity()

            for unit in units:
                unit.draw(screen)

            #Update screen
            pygame.display.flip()

        print("Exiting simulation...")
    except Exception as e:
        print(f"Error occurred: {e}")
    finally:
        pygame.quit()

if __name__ == "__main__":
    print("Starting simulation...")
    run_simulation()