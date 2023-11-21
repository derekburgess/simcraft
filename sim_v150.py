import os
import csv
import pygame
import math
import random

RING_RADIUS = 500 #Default: 500
RING_ATTRACTOR_COUNT = 10 #Default: 10
RING_ROTATION_SPEED = 0.75 #Default: 0.75
RING_GRAVITY_CONSTANT = 20 #Default: 20
RING_COLOR = (0, 0, 255) #Default: (0, 0, 255) -- Blue
RING_OPACITY = 0 #Default: 0, Range: 0-255

UNIT_COUNT = 5000 #Default: 5000
UNIT_START_SIZE = 15 #Default: 15
UNIT_MIN_SIZE = 3 #Default: 3
UNIT_GROWTH_RATE = 3 #Default: 3
UNIT_START_MASS = 1 #Default: 1
UNIT_GRAVITY_CONSTANT = 0.1 #Default: 0.05
UNIT_MAX_MASS = 60 #Default: 60
UNIT_START_COLOR = (60, 0, 60) #Default: (60, 0, 60) -- Dark Purple
UNIT_END_COLOR = (225, 200, 255) #Default: (225, 200, 255) -- Light Purple

BLACK_HOLE_THRESHOLD = 50 #Default: 50
BLACK_HOLE_CHANCE = 0.25 #Default: 0.6
BLACK_HOLE_RADIUS = 18 #Default: 18
BLACK_HOLE_GRAVITY_CONSTANT = 0.0005 #Default: 0.0005
BLACK_HOLE_DECAY_RATE = 0.5 #Default: 0.5

BLACK_HOLE_DECAY_THRESHOLD = 5 #Default: 5
BLACK_HOLE_COLOR = (0,0,0) #Black...
BLACK_HOLE_BORDER_COLOR = (255, 0, 0) #Red...

GRID_COLOR = (0, 0, 100) #Default: (0, 0, 100) -- Dark Blue
GRID_TEXT_COLOR = (0, 0, 255)  # White or choose another contrasting color
GRID_OPACITY = 10 #Default: 10, Range: 0-255
GRID_LINES_HORIZONTAL = 12 #Default: 12
GRID_LINES_VERTICAL = 16 #Default: 16
GRID_LABEL_OFFSET = 5 #Default: 5

LABEL_COLOR = (200, 200, 200) #Default: (200, 200, 200) -- Light Gray

BACKGROUND_COLOR = (0, 0, 10) #Default: (0, 0, 10) -- Dark Blue
SCREEN_WIDTH = 1600 #Default: 1600
SCREEN_HEIGHT = 1200 #Default: 1200

unit_id_counter = 0
objects_with_gravity = [] #Units and black holes
black_holes = [] #Black holes

pygame.init()
pygame.display.set_caption("simcraft")
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
font = pygame.font.SysFont('Monospace', 14) #Font for time text.

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
    #Draw horizontal lines and label them on the right
    for i in range(lines_horizontal + 1):
        y = screen_height / lines_horizontal * i
        pygame.draw.line(screen, grid_color, (0, y), (screen_width, y))
        # Add label (A-Z)
        if i < 26:  #Limit to 26 letters (A-Z)
            label = chr(65 + i)  # ASCII value for A is 65
            text_surface = font.render(label, True, GRID_TEXT_COLOR)
            screen.blit(text_surface, (screen_width - text_surface.get_width() - GRID_LABEL_OFFSET, y))
    #Draw vertical lines and label them at the bottom
    for i in range(lines_vertical + 1):
        x = screen_width / lines_vertical * i
        pygame.draw.line(screen, grid_color, (x, 0), (x, screen_height))
        #Add label (1-9, then 10, 11, ...)
        label = str(i + 1)
        text_surface = font.render(label, True, GRID_TEXT_COLOR)
        screen.blit(text_surface, (x, screen_height - text_surface.get_height() - GRID_LABEL_OFFSET))

def draw_static_key(screen):
    #Molecular Cloud Key
    molecular_cloud_pos = (25, 970) #Default: (15, 1050) Position of the molecular cloud key.
    pygame.draw.rect(screen, UNIT_START_COLOR, (molecular_cloud_pos[0], molecular_cloud_pos[1], 15, 15)) #Size of the molecular cloud key.
    screen.blit(font.render('MOLECULAR CLOUD', True, LABEL_COLOR), (molecular_cloud_pos[0] + 30, molecular_cloud_pos[1]))
    #Protostar Key
    protostar_pos = (31, 1003) #Default: (21, 1085) Position of the protostar key.
    pygame.draw.rect(screen, UNIT_END_COLOR, (protostar_pos[0], protostar_pos[1], 3, 3)) #Size of the protostar key.
    screen.blit(font.render('PROTOSTAR', True, LABEL_COLOR), (protostar_pos[0] + 25, protostar_pos[1] - 6))
    #Primordial Black Hole Key
    black_hole_pos = (32, 1030) #Default: (22, 1115) Position of the primordial black hole key.
    pygame.draw.circle(screen, (0, 0, 0), black_hole_pos, 6) #6 is the radius of the primordial black hole key.
    pygame.draw.circle(screen, (255, 0, 0), black_hole_pos, 6, 2) #2 is the width of the border of the primordial black hole key.
    screen.blit(font.render('PRIMORDIAL BLACK HOLE', True, LABEL_COLOR), (black_hole_pos[0] + 22, black_hole_pos[1] - 8))
    #Data Snapshot Key
    snapshot_pos = (25, 1075) #Default: (22, 1115) Position of the primordial black hole key.
    screen.blit(font.render('PRESS SPACEBAR FOR DATA SNAPSHOT', True, LABEL_COLOR), (snapshot_pos))
    snapshot_pos = (25, 1100)
    screen.blit(font.render('PRESS Q TO EXIT', True, LABEL_COLOR), (snapshot_pos))

def generate_unique_id():
    global unit_id_counter
    unit_id_counter += 1
    return unit_id_counter

#Unit class, also known as SpaceTimeUnit, probably because I described these as "units of spacetime" to OpenAI.
#This class is to represent the molecular clouds as they transition into stars. It also handles gravity for each "unit".
#A unit is represented by the square pixels that start out as large, low-mass molecular clouds and transition into small, high-mass stars.
class SpaceTimeUnit:
    def __init__(self, x, y, size, mass):
        self.id = generate_unique_id()
        self.selected = False
        self.x = x #X position of the unit, this will be used to set the X position of the unit.
        self.y = y #Y position of the unit, this will be used to set the Y position of the unit.
        self.size = size #Size of the unit, this will be used to set the size of the unit.
        self.mass = mass #Mass of the unit, this will be used to set the mass of the unit.
        self.opacity = 255  #Maximum opacity
        self.gravity_sources = [] #Set gravity sources to an empty list, this will be used to set the gravity sources of the unit.

    #Draw the unit on the screen.
    def draw(self, screen):
        if self.selected:
            highlight_color = (255, 165, 0)  # Orange color
            pygame.draw.rect(screen, highlight_color, (self.x, self.y, self.size, self.size))
        else:
            # Interpolate color
            factor = self.mass / UNIT_MAX_MASS
            color = interpolate_color(UNIT_START_COLOR, UNIT_END_COLOR, factor)
            #Add opacity to color for flicker effect (opacity is a random number between 0 and 255)
            color_with_opacity = color + (int(self.opacity),)
            # Draw the unit with flickering effect
            pygame.draw.rect(screen, color_with_opacity, (self.x, self.y, self.size, self.size))

    #Update the unit.
    def update(self):
        #Update the unit's size.
        self.size = max(UNIT_MIN_SIZE, UNIT_START_SIZE - int((self.mass - UNIT_START_MASS) * UNIT_GROWTH_RATE))
        #Update the unit's gravity.
        self.mass = min(self.mass, UNIT_MAX_MASS)
        #Update the unit's opacity.
        if self.size < 6:
            #Randomly adjust the opacity for flicker effect
            self.opacity = random.randint(0, 255)

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
            force = UNIT_GRAVITY_CONSTANT * (self.mass * source.mass) / (distance**2)   
            self.x += (dx / distance) * force
            self.y += (dy / distance) * force
    
    def is_clicked(self, click_x, click_y):
        return (self.x <= click_x <= self.x + self.size and
                self.y <= click_y <= self.y + self.size)
    
class BlackHole:
    def __init__(self, x, y, mass):
        self.id = generate_unique_id()
        self.x = x
        self.y = y
        self.mass = mass #Mass of the black hole, this will be used to set the mass of the black hole.
        self.border_radius = int(mass // BLACK_HOLE_RADIUS)

    #Draw the black hole on the screen.
    def draw(self, screen):
        pygame.draw.circle(screen, BLACK_HOLE_BORDER_COLOR, (self.x, self.y), self.border_radius)
        pygame.draw.circle(screen, BLACK_HOLE_COLOR, (self.x, self.y), self.mass // BLACK_HOLE_RADIUS, 0)

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
                force = UNIT_GRAVITY_CONSTANT * (self.mass * obj.mass) / (distance**2)
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

# Update units.
def update_units(units):
    global black_holes
    handle_collisions(units)
    units_to_remove = []
    for unit in units:
        unit.update()
        if unit.mass > BLACK_HOLE_THRESHOLD:
            #Randomly generate black holes.
            if random.random() < BLACK_HOLE_CHANCE: 
                #Create a black hole.
                black_holes.append(BlackHole(unit.x, unit.y, unit.mass))
                #Add the black hole to the objects with gravity list.
                units_to_remove.append(unit)
    for unit in units_to_remove:
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
    
#Define a global index counter for units and black holes
global_index_counter = 1
#Dump data to CSV
def dump_to_csv(units, black_holes, current_year, filename='data.csv'):
    global global_index_counter  #Declare the global index counter
    #Check if file exists
    file_exists = os.path.isfile(filename)
    with open(filename, mode='a' if file_exists else 'w', newline='') as file:
        writer = csv.writer(file)
        #Write header if the file is new
        if not file_exists:
            writer.writerow(['id', 'body', 'type', 'posx', 'posy', 'mass', 'size', 'flux', 'observation'])
        #Initialize the row_id with the last used ID + 1
        row_id = global_index_counter
        #Write data for each unit
        for unit in units:
            #Flux can be represented by the opacity attribute
            flux = unit.opacity if hasattr(unit, 'opacity') else 'N/A'
            writer.writerow([row_id, unit.id, 'Unit', unit.x, unit.y, unit.mass, unit.size, flux, current_year])
            row_id += 1
        #Write data for each black hole
        for black_hole in black_holes:
            writer.writerow([row_id, black_hole.id, 'BlackHole', black_hole.x, black_hole.y, black_hole.mass, black_hole.border_radius, 0, current_year])
            row_id += 1
        #Update the global index counter to the next available ID
        global_index_counter = row_id

#Run simulation.
def run_simulation():
    try:
        global font
        running = True
        angle = 0
        ring_points = get_ring_points((SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2), RING_RADIUS, RING_ATTRACTOR_COUNT, 0)
        decay_black_holes = []
        years = 0
        sub_window_rect = pygame.Rect(25, 580, 180, 360)
        close_button_rect = pygame.Rect(185, 580, 20, 20)
        sub_window_active = False
        selected_unit = None

        pygame.font.init()
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_q):
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                    dump_to_csv(units, black_holes, years)

                if event.type == pygame.MOUSEBUTTONDOWN:
                    click_x, click_y = event.pos
                    if sub_window_active:
                        if close_button_rect.collidepoint(click_x, click_y):
                            # Deselect unit and close sub-window
                            if selected_unit:
                                selected_unit.selected = False
                                selected_unit = None
                            sub_window_active = False
                        elif not sub_window_rect.collidepoint(click_x, click_y):
                            # Click is outside the sub-window
                            # Check for unit selection
                            for unit in units:
                                unit.selected = False  # Deselect all units
                                if unit.is_clicked(click_x, click_y):
                                    selected_unit = unit
                                    unit.selected = True
                                    sub_window_active = True
                    else:
                        # Sub-window is not active
                        # Check for unit selection
                        for unit in units:
                            unit.selected = False  # Deselect all units
                            if unit.is_clicked(click_x, click_y):
                                selected_unit = unit
                                unit.selected = True
                                sub_window_active = True

            #Fill screen with background color
            screen.fill(BACKGROUND_COLOR)

            #Draw grid on screen
            draw_grid(screen, font, GRID_COLOR, GRID_OPACITY, GRID_LINES_HORIZONTAL, GRID_LINES_VERTICAL)
            #Increment angle
            angle += RING_ROTATION_SPEED
            #Get ring points
            ring_points = get_ring_points((SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2), RING_RADIUS, RING_ATTRACTOR_COUNT, angle)
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
            #Draw static key on screen
            draw_static_key(screen)
            if years % 500 == 0:
                dump_to_csv(units, black_holes, years)

            #Increment years
            years += 1
            #Render time text
            year_text = font.render(f"TIME(YEARS): {years}M", True, LABEL_COLOR)
            #Blit time text to screen
            screen.blit(year_text, (25, SCREEN_HEIGHT - 50 ))

            def load_csv_data(file_path):
                with open(file_path, 'r') as file:
                    reader = csv.DictReader(file)
                    return {row['body']: row for row in reader}

            csv_data = load_csv_data('./data.csv')

            def display_unit_data(screen, selected_unit, rect, font, csv_data):
                if selected_unit is None:
                    return
                
                live_data_texts = [
                    "LIVE DATA:",
                    f"ID: {selected_unit.id}",
                    f"X-POS: {round(selected_unit.x, 5)}",
                    f"Y-POS: {round(selected_unit.y, 5)}",
                    f"SIZE: {selected_unit.size}",
                    f"MASS: {selected_unit.mass}",
                    f"FLUX: {selected_unit.opacity}"
                ]

                y_offset = 5
                for text in live_data_texts:
                    text_surface = font.render(text, True, LABEL_COLOR)
                    screen.blit(text_surface, (rect.x + 10, rect.y + y_offset))
                    y_offset += 20

                y_offset = 160
                unit_csv_data = csv_data.get(str(selected_unit.id))
                if unit_csv_data:
                    csv_header_text = "OBSERVATIONAL DATA:"
                    header_surface = font.render(csv_header_text, True, LABEL_COLOR)
                    screen.blit(header_surface, (rect.x + 10, rect.y + y_offset))
                    y_offset += 20

                    for key, value in unit_csv_data.items():
                        if key == 'posx' or key == 'posy':
                            value = round(float(value), 5)

                        csv_text = f"{key.upper()}: {value}"
                        text_surface = font.render(csv_text, True, LABEL_COLOR)
                        screen.blit(text_surface, (rect.x + 10, rect.y + y_offset))
                        y_offset += 20

            if sub_window_active:
                pygame.draw.rect(screen, LABEL_COLOR, sub_window_rect, 1)
                inner_rect = sub_window_rect.inflate(-2 * 1, -2 * 1)
                pygame.draw.rect(screen, BACKGROUND_COLOR, inner_rect)
                pygame.draw.rect(screen, LABEL_COLOR, close_button_rect)
                if selected_unit:
                    display_unit_data(screen, selected_unit, sub_window_rect, font, csv_data)
                
            pygame.display.flip()
        print("Exiting simulation...")
    except Exception as e:
        print(f"Error occurred: {e}")
    finally:
        pygame.quit()
if __name__ == "__main__":
    print("Starting simulation...")
    run_simulation()