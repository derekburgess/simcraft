import pygame
import math
import random

RING_RADIUS = 500 #Default: 500
RING_ROTATION_SPEED = 0.1 #Default: 0.1
RING_GRAVITY_CONSTANT = 20 #Default: 20 -- Increase create my drag on units
RING_COLOR = (0, 0, 255) #Default: (0, 0, 255) -- Blue
RING_OPACITY = 50 #Range: 0-255 #Default: 0

UNIT_COUNT = 5000 #Default: 5000
UNIT_START_SIZE = 15 #Default: 15
UNIT_START_MASS = 1.25 #Default: 1.25
UNIT_MAX_MASS = 60 #Default: 60
UNIT_GRAVITY_CONSTANT = 0.5 #Default: 0.5
UNIT_START_COLOR = (100, 0, 100) #Default: (60, 0, 60) -- Purple
UNIT_END_COLOR = (255, 255, 255) #Default: (255, 255, 255) -- White

BLACK_HOLE_THRESHOLD = 59 #Default: 59
BLACK_HOLE_GRAVITY_CONSTANT = 0.0005 #Default: 0.0005
BLACK_HOLE_DECAY_RATE = 0.75 #Default: 0.75
BLACK_HOLE_DECAY_THRESHOLD = 10 #Default: 10

GRID_COLOR = (20, 20, 20) #Default: (20, 20, 20) -- Dark gray
GRID_OPACITY = 10 #Range: 0-255 #Default: 10
GRID_LINES_HORIZONTAL = 6 #Default: 6
GRID_LINES_VERTICAL = 6 #Default: 6

SCREEN_WIDTH = 1400 #Default: 1080
SCREEN_HEIGHT = 1200 #Default: 1080

objects_with_gravity = [] #Units and black holes
black_holes = [] #Black holes

pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT)) #Set screen size
pygame.display.set_caption("simcraft") #Default: "simcraft" -- Change to whatever you want

#Interpolate color between two colors, used for units as they transition from molecular clouds to stars.
def interpolate_color(start_color, end_color, factor):
    r = start_color[0] + factor * (end_color[0] - start_color[0])
    g = start_color[1] + factor * (end_color[1] - start_color[1])
    b = start_color[2] + factor * (end_color[2] - start_color[2])
    return int(r), int(g), int(b)

#Draw grid on screen
def draw_grid(screen, color, opacity, lines_horizontal, lines_vertical):
    grid_color = color + (opacity,)
    screen_width, screen_height = screen.get_size()
    #Draw horizontal and vertical lines
    for i in range(lines_horizontal + 1):
        y = screen_height / lines_horizontal * i
        pygame.draw.line(screen, grid_color, (0, y), (screen_width, y))
    #Draw vertical lines
    for i in range(lines_vertical + 1):
        x = screen_width / lines_vertical * i
        pygame.draw.line(screen, grid_color, (x, 0), (x, screen_height))

#Unit class, also known as SpaceTimeUnit, probably because I described these as "units of spacetime" to OpenAI.
#This class is to represent the molecular clouds as they transition into stars. It also handles gravity for each "unit".
#A unit is represented by the square pixels that start out as large, low-mass molecular clouds and transition into small, high-mass stars.
class SpaceTimeUnit:
    def __init__(self, x, y, size, mass):
        self.x = x
        self.y = y
        self.size = size
        self.mass = mass
        self.gravity_sources = []

    #Draw unit on screen
    def draw(self, screen):
        #Interpolate color between start and end color based on mass
        factor = self.mass / UNIT_MAX_MASS
        color = interpolate_color(UNIT_START_COLOR, UNIT_END_COLOR, factor)
        pygame.draw.rect(screen, color, (self.x, self.y, self.size, self.size))

    #Update unit size and mass
    def update(self):
        self.size = max(5, UNIT_START_SIZE - int((self.mass - UNIT_START_MASS) * 0.5))
        self.mass = min(self.mass, UNIT_MAX_MASS)

    #Update gravity for unit
    def check_collision(self, other):
        #Check if unit collides with another unit and return True if it does, use this to inform handle_collisions()
        return (self.x < other.x + other.size and
                self.x + self.size > other.x and
                self.y < other.y + other.size and
                self.y + self.size > other.y)
    
    #Update gravity for unit
    def update_gravity(self):
        for source in self.gravity_sources:
            #Update gravity for unit based on gravity sources
            dx = source.x - self.x
            dy = source.y - self.y
            distance = max(math.hypot(dx, dy), 1)
            force = UNIT_GRAVITY_CONSTANT * (self.mass * source.mass) / (distance**2)
            self.x += (dx / distance) * force
            self.y += (dy / distance) * force

#Black hole class, handles gravity for black holes.
#Black holes are represented by the yellow circles that appear when a unit reaches a mass of 59 or higher.
#Black holes are also the only objects that can remove other black holes from the simulation.
#Black holes also decay over time, and when they reach a mass of 1 or lower, they disappear.
#Black holes also have a border radius that is 1/10th of their mass. This represents the event horizon and remains as the black hole decays to represent the hot gasses that are emitted from the black hole.
#It would be cool to add: Black holes can collide with each other and merge, and the resulting black hole has a mass that is the sum of the two black holes that collided. With a "ring of gravity" that is emitted from the collision.
class BlackHole:
    def __init__(self, x, y, mass):
        self.x = x
        self.y = y
        self.mass = mass
        self.border_radius = int(mass // 10)

    #Draw black hole on screen
    def draw(self, screen):
        pygame.draw.circle(screen, (255, 191, 0), (self.x, self.y), self.border_radius)
        pygame.draw.circle(screen, (0, 0, 0), (self.x, self.y), self.mass // 10, 0)

    #Attract units to black hole
    def attract(self, units, black_holes):
        #Attract units to black hole and remove units that are smaller than the black hole
        units_to_remove = []
        for unit in units:
            #If unit is a black hole and its mass is less than the mass of the black hole it is being attracted to, remove it from the simulation
            if isinstance(unit, BlackHole) and unit.mass < self.mass:
                units_to_remove.append(unit)
            #If unit is not a black hole and its mass is less than the mass of the black hole it is being attracted to, remove it from the simulation
            else:
                dx = self.x - unit.x
                dy = self.y - unit.y
                distance = max(math.hypot(dx, dy), 1)
                force = BLACK_HOLE_GRAVITY_CONSTANT * (self.mass * unit.mass) / (distance**2)
                unit.x += (dx / distance) * force
                unit.y += (dy / distance) * force
                unit.gravity_sources.append(self)

        #Remove units that are smaller than the black hole
        for unit in units_to_remove:
            units.remove(unit)

    #Update gravity for black hole
    def update_gravity(self, units, other_black_holes):
        #Update gravity for black hole based on other black holes
        for obj in units + other_black_holes:
            #If object is not the black hole itself, update gravity for black hole based on other black holes
            if obj is not self:
                dx = obj.x - self.x
                dy = obj.y - self.y
                distance = max(math.hypot(dx, dy), 1)
                force = UNIT_GRAVITY_CONSTANT * (self.mass * obj.mass) / (distance**2)
                self.x += (dx / distance) * force
                self.y += (dy / distance) * force
    #Decay black hole
    def decay(self):
        #Decay black hole over time
        self.mass -= BLACK_HOLE_DECAY_RATE
        #If black hole mass is less than the decay threshold, remove it from the simulation
        if self.mass < BLACK_HOLE_DECAY_THRESHOLD:
            if self in black_holes:
                black_holes.remove(self)

#Set up Attractor Ring: This is important because a solid ring did not create the effect I was looking for. This allows for the creation gravitational sources that create a crude sudo-manifold around the units.
def get_ring_points(center, radius, num_points, angle):
    points = []
    for i in range(num_points):
        theta = angle + (2 * math.pi / num_points) * i
        x = center[0] + radius * math.cos(theta)
        y = center[1] + radius * math.sin(theta)
        points.append((x, y))
    return points

#Draw ring on screen
def draw_ring(points, color, opacity):
    for point in points:
        surface = pygame.Surface((10, 10), pygame.SRCALPHA) #Create surface, set source alpha.
        rgba_color = color + (opacity,)
        pygame.draw.circle(surface, rgba_color, (5, 5), 5) #Draw circle on surface, set alpha.
        screen.blit(surface, (point[0] - 5, point[1] - 5)) #Blit surface to screen. Blitting is a term used in computer graphics to refer to the process of combining two images to form a third, resulting in a new image.

#Apply gravity to units based on ring points. This creates the gravitational effect for each point as it passes by a section of the universe it will attract units toward it.
def apply_gravity(units, ring_points):
    #Apply gravity to units based on ring points
    for unit in units:
        for point in ring_points:
            dx = point[0] - unit.x
            dy = point[1] - unit.y
            #Distance is set to 1 to prevent division by zero
            distance = max(math.hypot(dx, dy), 1)
            #If distance is greater than unit size, apply gravity to unit
            force = RING_GRAVITY_CONSTANT * unit.mass / (distance**2)
            if distance > unit.size / 2:
                unit.x += (dx / distance) * force
                unit.y += (dy / distance) * force

#Handle collisions between units   
def handle_collisions(units):
    for i, unit in enumerate(units):
        #Check if unit collides with another unit
        for other in units[i+1:]:
            #If unit collides with another unit, merge the two units
            if unit.check_collision(other):
                #Merge units
                merged_mass = unit.mass + other.mass
                units.remove(other)
                #Update unit size and mass
                unit.mass = min(merged_mass, UNIT_MAX_MASS)
                unit.update()
                break

#Update units including blackholes, handle collisions, and apply gravity.
def update_units(units):
    global black_holes
    handle_collisions(units)
    #Update units
    for unit in list(units):
        unit.update()
        #If unit mass is greater than black hole threshold, remove unit from units and add it to black holes
        if unit.mass > BLACK_HOLE_THRESHOLD:
            #If unit is not already a black hole, remove it from units and add it to black holes
            black_holes.append(BlackHole(unit.x, unit.y, unit.mass))
            units.remove(unit)

units = []
for _ in range(UNIT_COUNT):
    radius = random.uniform(0, RING_RADIUS)
    angle = random.uniform(0, 2 * math.pi)
    x = SCREEN_WIDTH // 2 + radius * math.cos(angle)
    y = SCREEN_HEIGHT // 2 + radius * math.sin(angle)

    unit = SpaceTimeUnit(x, y, UNIT_START_SIZE, UNIT_START_MASS)
    units.append(unit)

#Run simulation
def run_simulation():
    try:
        running = True #Set running to True, this will be used to control the main loop and is required by pygame.
        angle = 0 #Set angle to 0, this will be used to rotate the ring.
        ring_points = get_ring_points((SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2), RING_RADIUS, 20, 0) #Update '20' for ring count.
        decay_black_holes = [] #Set decay black holes to an empty list, this will be used to remove black holes from the simulation when they decay.
        years = 0 #Set years to 0, this will be used to keep track of the number of years that have passed in the simulation.
        pygame.font.init() #Initialize pygame font, this will be used to display the number of years that have passed in the simulation.
        font = pygame.font.SysFont('Monospace', 14) #Set font to Monospace, this will be used to display the number of years that have passed in the simulation.

        while running:
            #Handle keyboard events
            for event in pygame.event.get():
                #If event is quit or q, set running to False
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_q):
                    running = False
            #Fill screen with dark as fuck blue...
            screen.fill((0, 0, 20))
            #Draw the grid as configured...
            draw_grid(screen, GRID_COLOR, GRID_OPACITY, GRID_LINES_HORIZONTAL, GRID_LINES_VERTICAL)
            #Begin counting years... in the millions... lol.
            years += 1
            year_text = font.render(f"TIME(YEARS): {years}K", True, (200, 200, 200)) #Update label "YEARS(m):"
            screen.blit(year_text, (10, SCREEN_HEIGHT - 30))
            #Rotate the ring..
            angle += RING_ROTATION_SPEED
            ring_points = get_ring_points((SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2), RING_RADIUS, 20, angle) #Update '20' for ring count.
            #Call important methods and shit...                  
            draw_ring(ring_points, RING_COLOR, RING_OPACITY)
            #Update units on the screen
            update_units(units)
            #Update gravity for ring and units near ring
            apply_gravity(units, ring_points)
            #Iterate through black holes and update their state.
            for black_hole in black_holes:
                black_hole.attract(units, black_holes)
                black_hole.update_gravity(units, black_holes)
                black_hole.decay()
                black_hole.draw(screen)
                if black_hole.mass <= BLACK_HOLE_DECAY_THRESHOLD:
                    decay_black_holes.append(black_hole)
            #Check for decayed blackholes and remove them.
            for decayed_black_hole in decay_black_holes.copy():
                if decayed_black_hole in black_holes:
                    black_holes.remove(decayed_black_hole)
                decay_black_holes.remove(decayed_black_hole)
            #Update all units gravity... ha.
            for unit in units:
                unit.update_gravity()
            #Draw all units on the screen... haha.
            for unit in units:
                unit.draw(screen)
            #Update the display... HAHAHAHA.
            pygame.display.flip()
    
        print("Exiting simulation...")
    except Exception as e:
        print(f"Error occurred: {e}")
    finally:
        pygame.quit()

if __name__ == "__main__":
    print("Starting simulation...") #Print "Starting simulation..." to the console.
    run_simulation() #Create a universe...