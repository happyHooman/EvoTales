import pygame
import numpy as np
import random
import math
from pettingzoo import ParallelEnv
from gymnasium.spaces import Box, Discrete, Dict

# Configuration
SCREEN_SIZE = (800, 600)
BACKGROUND_COLOR = (180, 180, 180)
SPAWN_PADDING = 10 + 20

# World boundaries - much larger than screen
WORLD_SIZE = (2400, 1800)  # 3x the screen size

# Camera controls
ZOOM_SPEED = 0.1
PAN_SPEED = 6000  # pixels per second

# Add a new variable to control FOV visibility near the top of the file after the ZOOM_SPEED definition
SHOW_FOV = True  # Can be toggled with F key
PERFORMANCE_MODE = False  # Can be toggled with P key

class Camera:
    """A camera that allows zooming and panning of the simulation world"""
    def __init__(self, screen_width, screen_height):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.zoom = 1.0  # 1.0 = no zoom
        self.position = [WORLD_SIZE[0] // 2, WORLD_SIZE[1] // 2]  # Center of the world
        # For mouse dragging
        self.dragging = False
        self.drag_start = None
        self.drag_last_pos = None
        
    def zoom_at_point(self, amount, screen_pos=None):
        """Zoom centered on a specific screen position"""
        # Store old zoom for ratio calculation
        old_zoom = self.zoom
        
        # Apply zoom
        if amount > 0:
            self.zoom = min(4.0, self.zoom * (1 + ZOOM_SPEED))
        else:
            self.zoom = max(0.25, self.zoom / (1 + ZOOM_SPEED))

        # If a screen position was provided, adjust camera position to keep that point stationary
        if screen_pos is not None:
            # Convert screen position to world position before zoom
            world_pos_before = self.screen_to_world(screen_pos)
            
            # Calculate how the world position would change after zoom
            zoom_ratio = self.zoom / old_zoom
            
            # Adjust camera position to keep the point under cursor
            dx = world_pos_before[0] - self.position[0]
            dy = world_pos_before[1] - self.position[1]
            
            self.position[0] += dx * (1 - 1/zoom_ratio)
            self.position[1] += dy * (1 - 1/zoom_ratio)
        
    def zoom_in(self, amount=ZOOM_SPEED, screen_pos=None):
        self.zoom_at_point(1, screen_pos)
        
    def zoom_out(self, amount=ZOOM_SPEED, screen_pos=None):
        self.zoom_at_point(-1, screen_pos)
    
    def start_drag(self, screen_pos):
        """Start dragging the camera from a screen position"""
        self.dragging = True
        self.drag_start = screen_pos
        self.drag_last_pos = screen_pos
        
    def update_drag(self, new_screen_pos):
        """Update camera position based on mouse drag"""
        if not self.dragging:
            return
            
        # Calculate movement in screen coordinates
        dx = new_screen_pos[0] - self.drag_last_pos[0]
        dy = new_screen_pos[1] - self.drag_last_pos[1]
        
        # Convert screen movement to world movement (reverse of camera movement)
        world_dx = -dx / self.zoom
        world_dy = -dy / self.zoom
        
        # Update camera position
        self.position[0] += world_dx
        self.position[1] += world_dy
        
        # Clamp position to world boundaries
        visible_width = self.screen_width / self.zoom
        visible_height = self.screen_height / self.zoom
        
        min_x = visible_width / 2
        max_x = WORLD_SIZE[0] - visible_width / 2
        min_y = visible_height / 2
        max_y = WORLD_SIZE[1] - visible_height / 2
        
        self.position[0] = max(min_x, min(max_x, self.position[0]))
        self.position[1] = max(min_y, min(max_y, self.position[1]))
        
        # Update last position for next drag update
        self.drag_last_pos = new_screen_pos
        
    def end_drag(self):
        """End camera dragging"""
        self.dragging = False
        self.drag_start = None
        self.drag_last_pos = None
        
    def pan(self, dx, dy, dt):
        """Pan the camera by the specified amount, scaled by delta time"""
        # Scale movement by delta time and zoom level (faster movement when zoomed out)
        speed = PAN_SPEED * dt / self.zoom
        self.position[0] += dx * speed
        self.position[1] += dy * speed
        
        # Clamp camera position to keep most of the world on screen
        # Calculate visible world dimensions based on zoom
        visible_width = self.screen_width / self.zoom
        visible_height = self.screen_height / self.zoom
        
        # Calculate boundaries to ensure we don't show too much empty space
        min_x = visible_width / 2
        max_x = WORLD_SIZE[0] - visible_width / 2
        min_y = visible_height / 2
        max_y = WORLD_SIZE[1] - visible_height / 2
        
        # Clamp position
        self.position[0] = max(min_x, min(max_x, self.position[0]))
        self.position[1] = max(min_y, min(max_y, self.position[1]))
    
    def world_to_screen(self, world_pos):
        """Convert world coordinates to screen coordinates"""
        # Calculate offset from camera position to center of screen
        offset_x = self.position[0] - self.screen_width / (2 * self.zoom)
        offset_y = self.position[1] - self.screen_height / (2 * self.zoom)
        
        # Convert world position to screen position
        screen_x = (world_pos[0] - offset_x) * self.zoom
        screen_y = (world_pos[1] - offset_y) * self.zoom
        
        return (int(screen_x), int(screen_y))
    
    def screen_to_world(self, screen_pos):
        """Convert screen coordinates to world coordinates"""
        # Calculate offset from camera position to center of screen
        offset_x = self.position[0] - self.screen_width / (2 * self.zoom)
        offset_y = self.position[1] - self.screen_height / (2 * self.zoom)
        
        # Convert screen position to world position
        world_x = screen_pos[0] / self.zoom + offset_x
        world_y = screen_pos[1] / self.zoom + offset_y
        
        return [world_x, world_y]

# Update spawn area to use the world size
SPAWN_AREA = {
    "x_min": SPAWN_PADDING,
    "x_max": WORLD_SIZE[0] - SPAWN_PADDING,
    "y_min": SPAWN_PADDING,
    "y_max": WORLD_SIZE[1] - SPAWN_PADDING
}

# Load the sprite sheet
SPRITE_SHEET = pygame.image.load('assets/images/sprites2.png')
# Constants for sprite dimensions
SPRITE_SIZE = 40
GRID_SIZE = 3

# Extract sprites from the sprite sheet
def get_sprite(i):
    x = i % GRID_SIZE
    y = i // GRID_SIZE
    return SPRITE_SHEET.subsurface((x * SPRITE_SIZE, y * SPRITE_SIZE, SPRITE_SIZE, SPRITE_SIZE))

PLANT_CONFIG = {
    "initial_plants": 150,
    "growth_stages": 4,
    "sprites": [get_sprite(3+i) for i in range(4)],
    "size": [5, 10, 20, 30],
    "energy_gain": [100, 200, 300, 400],
    "growth_rate": .1,  # Plants growth in stages per second
    "spawn_rate": 2,  # chance per second to spawn a new plant
    "spawn_attempts": 100
}

MAMMAL_CONFIG = {
    # default
    "sprite": get_sprite(0),
    "size": 16,
    "decay_timer": 3.0,  # Time in seconds before dead mammal despawns
    "spawn_attempts": 100,

    # movement
    "turn_rate": 180,     # Degrees per second  
    "max_speed": 60,      # Pixels per second
    "base_speed": 30,     # Pixels per second
    "random_turn_chance": 0.12,  # 12% chance per second of random turn
    "random_turn_angle": 25,     # Maximum turn angle in degrees

    # vision
    "view_distance": 100,
    "view_angle": 60,
    "fov_color": (90, 165, 0, 30),
    "fov_outline_color": (90, 165, 0, 40),

    # energy
    "initial_energy": 600,
    "max_energy": 1000,
    "move_cost": 1,
    "energy_gain": 100,
    "reproduction_energy_cost": 300,
    "offspring_initial_energy": 400,
    "hunger_threshold": 850,

    # reproductio
    "reproduction_cooldown_max": 5,         # Seconds before adult can reproduce
    "reproduction_energy_threshold": 800,
    "reproduction_cooldown_max_offspring": 15, # Seconds before offspring can reproduce

    #health bar
    "bar_width": 20,
    "bar_height": 3,
    "bar_padding": 2,
    "bar_background_color": (100, 100, 100),
}

HERBIVORE_CONFIG = {
    # default
    "initial_amount": 20,
    "sprite": get_sprite(0),

    # movement
    "turn_rate": 120,    # Degrees per second
    "max_speed": 36,     # Pixels per second
    "base_speed": 18,    # Pixels per second

    # vision
    "view_distance": 60,
    "view_angle": 270,

    # energy
    "initial_energy": 600,
    "max_energy": 1000,
    "energy_gain": 300,

    # reproduction
    "reproduction_cooldown_max": 1.5,          # Seconds
    "reproduction_cooldown_max_offspring": 2.5,  # Seconds
}

CARNIVORE_CONFIG = {
    # default
    "initial_amount": 5,
    "sprite": get_sprite(1),

    # movement
    "turn_rate": 96,     # Degrees per second
    "max_speed": 54,     # Pixels per second
    "base_speed": 24,    # Pixels per second

    # vision
    "view_distance": 90,
    "view_angle": 160,
    "fov_color": (180, 165, 0, 30),
    "fov_outline_color": (180, 165, 0, 40),

    # energy
    "max_energy": 900,
    "move_cost": .3,
    "hunger_threshold": 750,
    "energy_gain": 0,
    "reproduction_energy_cost": 300,
    "offspring_initial_energy": 250,

    # reproduction
    "reproduction_cooldown_max": 90,          # Seconds
    "reproduction_cooldown_max_offspring": 150, # Seconds
    "reproduction_energy_threshold": 650,
}

# Sprites for different entities
SMARTIE_SPRITE = get_sprite(2)


class Being:
    def __init__(self, screen, pos=None):
        self.screen = screen
        self.pos = self.spawn_location() if pos is None else pos

    def render(self, camera):
        # Convert world position to screen position
        screen_pos = camera.world_to_screen(self.pos)
        
        # Skip rendering if entity is completely off-screen
        if (screen_pos[0] < -50 or screen_pos[0] > camera.screen_width + 50 or
            screen_pos[1] < -50 or screen_pos[1] > camera.screen_height + 50):
            return
            
        if hasattr(self, 'angle'):
            # Optimize sprite rotation through caching
            # Only rotate when angle changes significantly
            if not hasattr(self, '_last_rendered_angle') or abs(self._last_rendered_angle - self.angle) > 2:
                self._last_rendered_angle = self.angle
                self._rotated_sprite = pygame.transform.rotate(self.sprite, -(self.angle + 90))
            sprite = self._rotated_sprite
        else:
            sprite = self.sprite

        # Scale the sprite based on zoom level
        if camera.zoom != 1.0:
            current_width, current_height = sprite.get_size()
            new_width = int(current_width * camera.zoom)
            new_height = int(current_height * camera.zoom)
            if new_width > 0 and new_height > 0:  # Ensure valid size
                # Cache scaled sprites at common zoom levels
                zoom_key = round(camera.zoom, 1)  # Round to nearest 0.1
                if not hasattr(self, '_scaled_sprites'):
                    self._scaled_sprites = {}
                if zoom_key not in self._scaled_sprites:
                    self._scaled_sprites[zoom_key] = pygame.transform.scale(sprite, (new_width, new_height))
                sprite = self._scaled_sprites[zoom_key]
        
        sprite_rect = sprite.get_rect(center=screen_pos)
        self.screen.blit(sprite, sprite_rect.topleft)

    def spawn_location(self):
        return [
            random.uniform(SPAWN_AREA["x_min"], SPAWN_AREA["x_max"]), 
            random.uniform(SPAWN_AREA["y_min"], SPAWN_AREA["y_max"])
        ]


class Plant(Being):
    @classmethod
    def create(cls, screen, plants_positions_list, growth_stage=None):
        """Factory method to create a plant only if a valid position can be found."""
        # First find a valid position
        full_growth_size = PLANT_CONFIG["size"][-1]
        min_distance = .9 * full_growth_size
        min_distance_squared = min_distance * min_distance
        
        valid_pos = None
        # Attempt placing the plant in an empty spot
        for _ in range(PLANT_CONFIG["spawn_attempts"]):
            pos = [
                random.uniform(SPAWN_AREA["x_min"], SPAWN_AREA["x_max"]),
                random.uniform(SPAWN_AREA["y_min"], SPAWN_AREA["y_max"])
            ]
            
            # First filter plants that are too far to matter
            nearby_plants = [
                p for p in plants_positions_list 
                if abs(p[0] - pos[0]) < min_distance and abs(p[1] - pos[1]) < min_distance
            ]
            
            # Check direct distances for nearby plants using squared distance
            valid = True
            for plant in nearby_plants:
                dx = pos[0] - plant[0]
                dy = pos[1] - plant[1]
                squared_dist = dx*dx + dy*dy
                if squared_dist < min_distance_squared:
                    valid = False
                    break
            
            if valid:
                valid_pos = pos
                break
        
        # Only create the plant if we found a valid position
        if valid_pos is None:
            return None
            
        return cls(screen, valid_pos, growth_stage)

    def __init__(self, screen, pos, growth_stage=None):
        if growth_stage is None:
            growth_stage = random.randint(0, len(PLANT_CONFIG["size"]) - 1)
        self.growth_stage = growth_stage
        self.sprite = PLANT_CONFIG["sprites"][growth_stage]
        self.size = PLANT_CONFIG["size"][growth_stage]
        self.energy_gain = PLANT_CONFIG["energy_gain"][growth_stage]
        self.reset_growth_timer()
        super().__init__(screen, pos)

    def reset_growth_timer(self):
        variability = 30  # 30% variability
        # Calculate growth time in seconds
        base_time = 1 / PLANT_CONFIG["growth_rate"]  # Base time in seconds
        variation = base_time * (random.randint(-variability, variability) / 100)
        self.growth_timer = base_time + variation

    def grow(self):
        full_grown = self.growth_stage == PLANT_CONFIG["growth_stages"] - 1
        if full_grown:
            return

        # Get delta time (from Mammal class if available, otherwise use default)
        dt = Mammal.simulation_delta_time if hasattr(Mammal, 'simulation_delta_time') else 0.016
        
        if self.growth_timer > 0:
            self.growth_timer -= dt
        else:
            self.growth_stage += 1
            self.size = PLANT_CONFIG["size"][self.growth_stage]
            self.sprite = PLANT_CONFIG["sprites"][self.growth_stage]
            self.energy_gain = PLANT_CONFIG["energy_gain"][self.growth_stage]
            self.reset_growth_timer()


class Mammal(Being):
    # Class variable to share delta time with all mammals
    simulation_delta_time = 1/60  # Default to 60 FPS
    # Shared FOV surface - will be initialized when first needed
    shared_fov_surface = None

    def __init__(self, screen, config):
        # default
        self.alive = True
        original_sprite = config.get("sprite", MAMMAL_CONFIG["sprite"])
        self.sprite = original_sprite.copy()
        self.size = config.get("size", MAMMAL_CONFIG["size"])
        self.decay_timer = config.get("decay_timer", MAMMAL_CONFIG["decay_timer"])

        # movement
        self.angle = random.uniform(0, 360)  # Current angle in degrees
        self.desired_angle = self.angle  # Initialize desired angle to match current angle
        self.direction = self.calculate_direction()
        self.turn_rate = config.get("turn_rate", MAMMAL_CONFIG["turn_rate"]) # how fast it can turn
        self.max_speed = config.get("max_speed", MAMMAL_CONFIG["max_speed"])
        self.base_speed = config.get("base_speed", MAMMAL_CONFIG["base_speed"])
        self.speed = self.base_speed
        self.random_turn_chance = config.get("random_turn_chance", MAMMAL_CONFIG["random_turn_chance"])
        self.random_turn_angle = config.get("random_turn_angle", MAMMAL_CONFIG["random_turn_angle"])

        # vision
        self.view_distance = config.get("view_distance", MAMMAL_CONFIG["view_distance"])
        self.view_angle = config.get("view_angle", MAMMAL_CONFIG["view_angle"])
        self.fov_color = config.get("fov_color", MAMMAL_CONFIG["fov_color"])
        self.fov_outline_color = config.get("fov_outline_color", MAMMAL_CONFIG["fov_outline_color"])

        # energy
        self.energy = config.get("initial_energy", MAMMAL_CONFIG["initial_energy"])
        self.max_energy = config.get("max_energy", MAMMAL_CONFIG["max_energy"])
        self.move_cost = config.get("move_cost", MAMMAL_CONFIG["move_cost"])
        self.energy_gain = config.get("energy_gain", MAMMAL_CONFIG["energy_gain"])        
        self.reproduction_energy_cost = config.get("reproduction_energy_cost", MAMMAL_CONFIG["reproduction_energy_cost"])
        self.offspring_initial_energy = config.get("offspring_initial_energy", MAMMAL_CONFIG["offspring_initial_energy"])
        self.hunger_threshold = config.get("hunger_threshold", MAMMAL_CONFIG["hunger_threshold"])
        
        # reproduction
        self.reproduction_cooldown = 0
        self.reproduction_cooldown_max = config.get("reproduction_cooldown_max", MAMMAL_CONFIG["reproduction_cooldown_max"])  # Frames before being able to reproduce again
        self.reproduction_cooldown_max_offspring = config.get("reproduction_cooldown_max_offspring", MAMMAL_CONFIG["reproduction_cooldown_max_offspring"])  # Frames before being able to reproduce again
        self.reproduction_energy_threshold = config.get("reproduction_energy_threshold", MAMMAL_CONFIG["reproduction_energy_threshold"])  # 80% energy required to reproduce

        # target
        self.current_target = None
        self.target_distance = 0

        super().__init__(screen)
        self.last_pos = self.pos.copy()

    def calculate_direction(self):
        radian_angle = math.radians(self.angle)
        return [math.cos(radian_angle), math.sin(radian_angle)]

    def turn(self, angle_change):
        # Update the desired angle instead of immediately changing current angle
        self.desired_angle = (self.angle + angle_change) % 360

    def update_turning(self):
        """
        Gradually update the current angle towards the desired angle
        """
        # Get delta time for current frame
        dt = Mammal.simulation_delta_time
        effective_turn_rate = self.turn_rate * dt / (1 + (self.speed/60)**2)
    
        angle_diff = (self.desired_angle - self.angle + 180) % 360 - 180
        # Apply clamping to prevent overshooting
        if abs(angle_diff) <= effective_turn_rate:
            self.angle = self.desired_angle
        else:
            turn_direction = 1 if angle_diff > 0 else -1
            self.angle = (self.angle + turn_direction * effective_turn_rate) % 360
        
        self.direction = self.calculate_direction()

    def move(self):
        # First update turning to ensure smooth rotation
        self.update_turning()
        
        # Get delta time for current frame
        dt = Mammal.simulation_delta_time
        
        # Apply movement based on speed per second and scale by delta time
        self.pos[0] += self.speed * self.direction[0] * dt
        self.pos[1] += self.speed * self.direction[1] * dt

        # Boundary checks using SPAWN_AREA
        self.pos[0] = max(SPAWN_AREA["x_min"], min(SPAWN_AREA["x_max"], self.pos[0]))
        self.pos[1] = max(SPAWN_AREA["y_min"], min(SPAWN_AREA["y_max"], self.pos[1]))

        # Scale energy consumption by delta time - move_cost is now energy per second
        energy_cost = self.move_cost * self.speed * dt
        self.energy -= max(energy_cost, 0)

    def turn_away(self):
        # Try multiple random angles to find one that leads back into the spawn area
        for _ in range(10):  # Try up to 10 times to find a good direction
            # Generate a random turn angle between -120 and 120 degrees
            turn_angle = random.uniform(-120, 120)
            
            # Calculate new direction after turning
            new_angle = (self.angle + turn_angle) % 360
            radian_angle = math.radians(new_angle)
            new_direction = [math.cos(radian_angle), math.sin(radian_angle)]
            
            # Project a point ahead in the new direction
            projected_x = self.pos[0] + new_direction[0] * self.view_distance
            projected_y = self.pos[1] + new_direction[1] * self.view_distance
            
            # Check if the new direction points inside the spawn area
            if (SPAWN_AREA["x_min"] < projected_x < SPAWN_AREA["x_max"] and
                SPAWN_AREA["y_min"] < projected_y < SPAWN_AREA["y_max"]):
                # Found a good direction, apply the turn
                self.turn(turn_angle)
                return
        
        # If we couldn't find a good direction, make a sharp turn (180 degrees)
        self.turn(180)

    def border_ahead(self):
        # Calculate the point at view_distance units ahead of the herbivore
        projected_x = self.pos[0] + self.direction[0] * self.view_distance
        projected_y = self.pos[1] + self.direction[1] * self.view_distance
        
        # Check if the projected point is outside the spawn area
        if (projected_x < SPAWN_AREA["x_min"] or 
            projected_x > SPAWN_AREA["x_max"] or
            projected_y < SPAWN_AREA["y_min"] or
            projected_y > SPAWN_AREA["y_max"]):
            return True
        
        return False

    def draw_fov(self, camera):
        global SHOW_FOV
        if not SHOW_FOV or self.view_distance <= 0 or not self.alive:
            return

        # Skip FOV rendering if mammal is off-screen
        screen_pos = camera.world_to_screen(self.pos)
        scaled_view_distance = self.view_distance * camera.zoom
        
        # Skip FOV rendering if completely off-screen (with extra margin for FOV)
        if (screen_pos[0] + scaled_view_distance < 0 or 
            screen_pos[0] - scaled_view_distance > camera.screen_width or
            screen_pos[1] + scaled_view_distance < 0 or 
            screen_pos[1] - scaled_view_distance > camera.screen_height):
            return

        # Initialize shared surface if needed
        if Mammal.shared_fov_surface is None or Mammal.shared_fov_surface.get_size() != (camera.screen_width, camera.screen_height):
            Mammal.shared_fov_surface = pygame.Surface((camera.screen_width, camera.screen_height), pygame.SRCALPHA)
        
        # Get references for clarity and performance
        fov_surface = Mammal.shared_fov_surface
        fov_color = self.fov_color
        fov_outline_color = self.fov_outline_color
        
        # Clear the surface for this rendering
        fov_surface.fill((0, 0, 0, 0))
        
        # Calculate FOV triangle points
        center = pygame.math.Vector2(screen_pos)
        angle = math.radians(self.angle)
        half_angle = math.radians(self.view_angle / 2)
        
        # Create FOV polygon points with fewer points for better performance
        points = [center]
        # Use fewer points for wider FOVs for better performance
        step_size = max(5, min(10, int(self.view_angle / 15)))
        steps = max(5, int(self.view_angle / step_size))
        
        # Calculate and add points along the arc
        for i in range(steps + 1):
            theta = angle - half_angle + math.radians(i * step_size)
            point = pygame.math.Vector2()
            point.from_polar((scaled_view_distance, math.degrees(theta)))
            points.append(center + point)
        
        # Draw the FOV shape with transparency
        pygame.draw.polygon(fov_surface, fov_color, points)
        
        # Blit the transparent surface onto the screen
        self.screen.blit(fov_surface, (0, 0))
        
        # Draw FOV outline
        start_point = pygame.math.Vector2()
        start_point.from_polar((scaled_view_distance, math.degrees(angle - half_angle)))
        end_point = pygame.math.Vector2()
        end_point.from_polar((scaled_view_distance, math.degrees(angle + half_angle)))
        
        # Draw vision cone outline
        pygame.draw.line(self.screen, fov_outline_color, center, center + start_point, max(1, int(camera.zoom/2)))
        pygame.draw.line(self.screen, fov_outline_color, center, center + end_point, max(1, int(camera.zoom/2)))

    def draw_energy_bar(self, camera):
        # Skip drawing energy bars in performance mode
        global PERFORMANCE_MODE
        if PERFORMANCE_MODE:
            return
            
        if not hasattr(self, 'energy'):
            return

        config = MAMMAL_CONFIG
        # Scale bar dimensions based on zoom
        bar_width = config["bar_width"] * camera.zoom
        bar_height = config["bar_height"] * camera.zoom
        bar_padding = config["bar_padding"] * camera.zoom
        bar_background_color = config["bar_background_color"]

        # Calculate energy percentage
        energy_percent = min(1, max(0, self.energy / self.max_energy))
        
        # Convert world position to screen position
        screen_pos = camera.world_to_screen(self.pos)
        
        # Calculate bar position (centered above the mammal)
        bar_x = int(screen_pos[0] - bar_width/2)
        scaled_size = self.size * camera.zoom
        bar_y = int(screen_pos[1] - scaled_size/2 - bar_height - bar_padding)
        
        # Ensure bar dimensions are at least 1 pixel
        bar_width = max(1, bar_width)
        bar_height = max(1, bar_height)
        
        # Draw bar background
        pygame.draw.rect(self.screen, bar_background_color, 
                         (bar_x, bar_y, bar_width, bar_height))
        
        if energy_percent > 0:
            # Simplify color calculation for better performance
            if energy_percent > 0.9:
                color = (0, 255, 0)  # Green
            elif energy_percent > 0.7:
                color = (255, 255, 0)  # Yellow
            elif energy_percent > 0.2:
                color = (255, 128, 0)  # Orange
            else:
                color = (255, 0, 0)  # Red
                
            filled_width = max(1, int(bar_width * energy_percent))
            pygame.draw.rect(self.screen, color,
                             (bar_x, bar_y, filled_width, bar_height))

    def render(self, camera):
        # Make sure living mammals have full opacity
        if self.alive and hasattr(self, 'sprite') and hasattr(self.sprite, 'set_alpha'):
            self.sprite.set_alpha(255)
        
        if self.alive and hasattr(self, 'view_distance') and self.view_distance > 0:
            self.draw_fov(camera)
        if self.alive:
            self.draw_energy_bar(camera)
        
        # Call the parent class render method with the camera
        super().render(camera)

    def is_alive(self):
        return self.alive
        
    def is_despawnable(self):
        """
        Check if a mammal can be removed from the simulation
        A mammal is despawnable if:
        1. It's dead AND
        2. Its decay timer has expired (less than or equal to zero)
        """
        return not self.alive and self.decay_timer <= 0
        
    def is_hungry(self):
        return self.energy <= self.hunger_threshold

    def can_reproduce(self):
        return self.reproduction_cooldown <= 0 and self.energy >= self.reproduction_energy_threshold

    def reproduce(self):
        """Create a new mammal of the same type"""
        offspring = None

        if self.can_reproduce():
            # If we're a Herbivore, create a Herbivore offspring
            if isinstance(self, Herbivore):
                offspring = Herbivore(self.screen)
            elif isinstance(self, Carnivore):
                offspring = Carnivore(self.screen)

            # Position offspring near parent
            max_distance = self.size * 2
            offspring.pos = [
                self.pos[0] + random.uniform(-max_distance, max_distance),
                self.pos[1] + random.uniform(-max_distance, max_distance)
            ]
            # Keep offspring within boundaries
            offspring.pos[0] = max(SPAWN_AREA["x_min"], min(SPAWN_AREA["x_max"], offspring.pos[0]))
            offspring.pos[1] = max(SPAWN_AREA["y_min"], min(SPAWN_AREA["y_max"], offspring.pos[1]))
                
            offspring.energy = self.offspring_initial_energy
            offspring.reproduction_cooldown = self.reproduction_cooldown_max_offspring
            self.energy -= self.reproduction_energy_cost
            self.reproduction_cooldown = self.reproduction_cooldown_max
        
        return offspring

    def update(self):
        """Update method to be called each frame"""
        dt = Mammal.simulation_delta_time
        
        if self.reproduction_cooldown > 0:
            self.reproduction_cooldown -= dt
        
        if self.energy <= 0:
            self.alive = False
            return
        
        self.move()
            
    def is_touching_entity(self, entity):
        entity_size = entity.size
        # Use squared distance for efficiency (avoids square root)
        dx = self.pos[0] - entity.pos[0]
        dy = self.pos[1] - entity.pos[1]
        squared_distance = dx*dx + dy*dy
        
        # Compare squared distances for better performance
        return squared_distance < ((self.size/2 + entity_size/2) ** 2)
    
    def consume_entity(self, entity, entity_list):
        self.energy = min(self.energy + entity.energy_gain, self.max_energy)
        if entity in entity_list:
            entity_list.remove(entity)            
                    
    def reset_target(self, target=None):
        self.current_target = target
        self.target_distance = 0
    
    def find_target_in_fov(self, entity_list, filter_function=None, order_function=None):
        if entity_list is None:
            return False
        if not order_function:
            order_function = lambda x: x[1]
        
        entities = {}
        
        # First filter entities that are too far or don't meet criteria
        nearby_entities = []
        view_distance_squared = self.view_distance ** 2
        
        for entity in entity_list:
            # Fast bounding box check
            if abs(entity.pos[0] - self.pos[0]) <= self.view_distance and \
               abs(entity.pos[1] - self.pos[1]) <= self.view_distance:
                if filter_function is None or filter_function(entity):
                    nearby_entities.append(entity)

        for entity in nearby_entities:
            # Use simpler arithmetic instead of np.array operations
            dx = entity.pos[0] - self.pos[0]
            dy = entity.pos[1] - self.pos[1]
            squared_distance = dx*dx + dy*dy
            
            if squared_distance < view_distance_squared:
                entity_angle = math.degrees(math.atan2(dy, dx))
                angle_diff = (entity_angle - self.angle + 180) % 360 - 180
                
                if abs(angle_diff) <= self.view_angle / 2:
                    # Store squared distance to avoid sqrt in sorting
                    entities[entity] = squared_distance
        
        sorted_entities = sorted(entities.items(), key=order_function)
        return sorted_entities[0][0] if sorted_entities else False
    
    def move_towards_entity(self, entity):
        entity_vector = [entity.pos[0] - self.pos[0], entity.pos[1] - self.pos[1]]
        target_angle = math.degrees(math.atan2(entity_vector[1], entity_vector[0]))
        angle_diff = (target_angle - self.angle + 180) % 360 - 180
        self.turn(angle_diff)

    def wander(self):
        self.reset_target()
        self.speed = self.base_speed
        if self.border_ahead():
            self.turn_away()
        else:
            dt = Mammal.simulation_delta_time
            time_adjusted_chance = self.random_turn_chance * dt
            if random.random() < time_adjusted_chance:
                random_direction = random.uniform(-self.random_turn_angle, self.random_turn_angle)
                self.turn(random_direction)

    def find_food(self, food_list=None):           
        target = self.find_target_in_fov(food_list)
        if target:
            self.reset_target(target)
            self.move_towards_entity(target)
        else:
            self.wander()

    def measure_travel_distance(self):
        # Avoid numpy operations for simple 2D distance
        dx = self.pos[0] - self.last_pos[0]
        dy = self.pos[1] - self.last_pos[1]
        d = math.sqrt(dx*dx + dy*dy)
        
        self.last_pos = self.pos.copy()
        self.target_distance += d
    
    def decay(self):
        if not self.alive:
            # Subtract actual elapsed seconds from decay timer
            dt = Mammal.simulation_delta_time
            self.decay_timer -= dt
            
            # Fade out sprite as it decays
            if hasattr(self, 'sprite') and hasattr(self.sprite, 'set_alpha'):
                self.sprite.set_alpha(60)
            
            return True
        return False
    
    def eat(self, food_list, filter_function=None):
        if not food_list:
            self.wander()
            return
        filtered_food_list = [entity for entity in food_list if filter_function(entity)] if filter_function else food_list
        if self.current_target and self.current_target in filtered_food_list:
            if self.is_touching_entity(self.current_target):
                self.consume_entity(self.current_target, food_list)
                self.reset_target()
                self.speed = self.base_speed
            else:
                self.move_towards_entity(self.current_target)
        else:
            self.find_food(filtered_food_list)


class Herbivore(Mammal):
    def __init__(self, screen):
        config = HERBIVORE_CONFIG
        super().__init__(screen, config)
    
    def food_filter(self, plant):
        return plant.growth_stage > 0

    def figure_out(self, plant_list=None):
        '''
        Hardcoded behaviour
        '''
        if self.decay():
            return None
        self.measure_travel_distance()
        new_offspring = self.reproduce()
        if self.is_hungry():
            self.eat(plant_list, self.food_filter)
        else:
            self.wander()
        self.update()
        return new_offspring


class Carnivore(Mammal):
    def __init__(self, screen):
        config = CARNIVORE_CONFIG
        super().__init__(screen, config)

    def figure_out(self, herbivore_list=None):
        '''
        Hardcoded behaviour
        '''
        if self.decay():
            return None
        self.measure_travel_distance()
        new_offspring = self.reproduce()
        if self.is_hungry():
            self.eat(herbivore_list)
        else:
            self.wander()
        self.update()
        return new_offspring


class Smartie(Mammal):
    def __init__(self, screen, pos, size):
        super().__init__(screen, pos, size)


class CreatureSimulation(ParallelEnv):
    metadata = {"render_modes": ["human"], "render_fps": 60}

    def __init__(self, render_mode=None):
        self.possible_agents = []
        self.agent_info = {}
        self.plants = []
        self.render_mode = render_mode
        self.frames = 0
        self.screen = None
        self.herbivores = []
        self.carnivores = []
        self.smarties = []
        
        # Time tracking for frame-rate independence
        self.delta_time = 1/60  # Default to 60 FPS (in seconds)
        self.last_frame_time = None
        
        # Initialize Pygame only if needed
        if self.render_mode == "human":
            pygame.init()
            self.screen = pygame.display.set_mode(SCREEN_SIZE)
            self.clock = pygame.time.Clock()
            self.last_frame_time = pygame.time.get_ticks() / 1000.0  # Initial time in seconds
            self.camera = Camera(SCREEN_SIZE[0], SCREEN_SIZE[1])
            
            # For displaying stats
            self.font = pygame.font.SysFont("Arial", 16)
            self.show_stats = True

        # Initialize populations
        self._spawn_initial_population()

        self.observation_spaces = Dict({
            "herbivore": Box(low=-np.inf, high=np.inf, shape=(8,)),  # x, y, vx, vy, energy, state, target_x, target_y
            "smartie": Box(low=-np.inf, high=np.inf, shape=(8,)),
            "carnivore": Box(low=-np.inf, high=np.inf, shape=(8,))
        })

        self.action_space = {"figure out": 0}  # Single action for herbivores

    def _spawn_initial_population(self):
        # Spawn plants with random growth stages
        for _ in range(PLANT_CONFIG["initial_plants"]):
            existing_plants = [p.pos for p in self.plants]
            plant = Plant.create(self.screen, existing_plants)
            if plant is not None:
                self.plants.append(plant)
            else:
                print("Failed to spawn initial plant - no valid position found")


        creature_list = [
            {
                "type": "herbivore",
                "initial_amount": HERBIVORE_CONFIG["initial_amount"],
                "constructor": Herbivore,
                "creature_list": self.herbivores
            },
            {
                "type": "carnivore",
                "initial_amount": CARNIVORE_CONFIG["initial_amount"],
                "constructor": Carnivore,
                "creature_list": self.carnivores
            }
        ]

        for creature in creature_list:
            for i in range(creature["initial_amount"]):
                mammal = creature["constructor"](self.screen)
                agent_name = f"{creature['type']}_{i}"
                self.possible_agents.append(agent_name)
                self.agent_info[agent_name] = mammal
                creature["creature_list"].append(mammal)

    def _spawn_new_plants(self):
        time_adjusted_chance = PLANT_CONFIG["spawn_rate"] * self.delta_time
        
        if random.random() < time_adjusted_chance:
            existing_plants = [p.pos for p in self.plants]
            plant = Plant.create(self.screen, existing_plants, growth_stage=0)
            if plant is not None:
                self.plants.append(plant)
            else:
                print("Failed to spawn plant")

    def reset(self):
        self.possible_agents = []
        self.agent_info = {}
        self.plants = []
        self.herbivores = []
        self.carnivores = []  # Reset carnivores list
        self._spawn_initial_population()
        return self._get_observations()

    def handle_mammals(self, mammal_list, prey_list=None, mammal_type="mammal"):
        """
        Generic handler for offspring generation and despawning
        
        Args:
            mammal_list: List of mammals to update
            prey_list: List of potential prey (plants for herbivores, herbivores for carnivores)
            mammal_type: String identifier for the type of mammal (for agent naming)
        """
        dead_mammals = []
        new_mammals = []
        
        for mammal in mammal_list:
            # Update behavior and check for reproduction
            offspring = mammal.figure_out(prey_list)
            
            if offspring:
                new_mammals.append(offspring)
            
            if mammal.is_despawnable():
                dead_mammals.append(mammal)
        
        # Add new mammals born this frame
        mammal_list.extend(new_mammals)
        
        # Remove despawnable mammals
        for dead_mammal in dead_mammals:
            if dead_mammal in mammal_list:
                mammal_list.remove(dead_mammal)
            
            # Find and remove associated agent references
            agents_to_remove = []
            for agent_name, agent_info in self.agent_info.items():
                if agent_info == dead_mammal:
                    agents_to_remove.append(agent_name)
            
            for agent_name in agents_to_remove:
                if agent_name in self.possible_agents:
                    self.possible_agents.remove(agent_name)
                if agent_name in self.agent_info:
                    del self.agent_info[agent_name]

    def step(self, actions):
        self.frames += 1
        rewards = {}
        dones = {}
        infos = {}

        # Make sure delta time is set for the simulation
        # This is critical if render() isn't called every step
        if self.last_frame_time is not None and self.render_mode == "human":
            current_time = pygame.time.get_ticks() / 1000.0
            self.delta_time = min(current_time - self.last_frame_time, 0.1)
            self.last_frame_time = current_time
        
        # Share delta time with all mammals
        Mammal.simulation_delta_time = self.delta_time

        # Update plants
        for plant in self.plants:
            plant.grow()
        self._spawn_new_plants()

        # Handle mammals (reproduction and death)
        self.handle_mammals(self.herbivores, self.plants, "herbivore")
        self.handle_mammals(self.carnivores, self.herbivores, "carnivore")

        return self._get_observations(), rewards, dones, infos

    def _handle_input(self):
        """Handle user input for camera controls"""
        global SHOW_FOV, PERFORMANCE_MODE
        
        keys = pygame.key.get_pressed()
        mouse_buttons = pygame.mouse.get_pressed()
        
        # Panning with arrow keys
        dx = 0
        dy = 0
        if keys[pygame.K_LEFT]:
            dx -= 1
        if keys[pygame.K_RIGHT]:
            dx += 1
        if keys[pygame.K_UP]:
            dy -= 1
        if keys[pygame.K_DOWN]:
            dy += 1
            
        # Apply panning if needed
        if dx != 0 or dy != 0:
            self.camera.pan(dx, dy, self.delta_time)
            
        # Handle mouse drag panning
        if mouse_buttons[2]:  # Right mouse button
            # Get current mouse position
            mouse_pos = pygame.mouse.get_pos()
            
            # If we haven't stored a previous position, store it now
            if not hasattr(self, '_last_mouse_pos'):
                self._last_mouse_pos = mouse_pos
                # Change cursor to indicate dragging
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_SIZEALL)
            else:
                # Calculate movement delta
                mouse_dx = self._last_mouse_pos[0] - mouse_pos[0]
                mouse_dy = self._last_mouse_pos[1] - mouse_pos[1]
                
                # Apply movement to camera (adjust for zoom level)
                world_dx = mouse_dx / self.camera.zoom
                world_dy = mouse_dy / self.camera.zoom
                
                # Update camera position
                self.camera.position[0] += world_dx
                self.camera.position[1] += world_dy
                
                # Ensure camera stays within bounds
                visible_width = self.camera.screen_width / self.camera.zoom
                visible_height = self.camera.screen_height / self.camera.zoom
                
                min_x = visible_width / 2
                max_x = WORLD_SIZE[0] - visible_width / 2
                min_y = visible_height / 2
                max_y = WORLD_SIZE[1] - visible_height / 2
                
                self.camera.position[0] = max(min_x, min(max_x, self.camera.position[0]))
                self.camera.position[1] = max(min_y, min(max_y, self.camera.position[1]))
                
                # Update last position
                self._last_mouse_pos = mouse_pos
        else:
            # Not dragging, reset cursor and stored position
            if hasattr(self, '_last_mouse_pos'):
                del self._last_mouse_pos
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
        
        # Process each event
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_EQUALS or event.key == pygame.K_PLUS:
                    self.camera.zoom_in()
                elif event.key == pygame.K_MINUS:
                    self.camera.zoom_out()
                elif event.key == pygame.K_TAB:
                    self.show_stats = not self.show_stats
                elif event.key == pygame.K_f:
                    # Toggle FOV visibility
                    SHOW_FOV = not SHOW_FOV
                elif event.key == pygame.K_p:
                    # Toggle performance mode
                    PERFORMANCE_MODE = not PERFORMANCE_MODE
                    # In performance mode, always disable FOV
                    if PERFORMANCE_MODE:
                        SHOW_FOV = False
                elif event.key == pygame.K_ESCAPE:
                    return False
            elif event.type == pygame.MOUSEWHEEL:
                if event.y > 0:
                    self.camera.zoom_in()
                elif event.y < 0:
                    self.camera.zoom_out()
                    
        return True

    def render(self):
        if self.render_mode != "human":
            return
        
        global SHOW_FOV, PERFORMANCE_MODE
        
        # Calculate delta time
        current_time = pygame.time.get_ticks() / 1000.0  # Current time in seconds
        if self.last_frame_time is not None:
            self.delta_time = current_time - self.last_frame_time
            # Clamp delta time to avoid huge jumps
            self.delta_time = min(self.delta_time, 0.1)
        self.last_frame_time = current_time
        
        # Update the Mammal class's delta time
        Mammal.simulation_delta_time = self.delta_time
        
        # Handle user input
        if not self._handle_input():
            pygame.quit()
            return
        
        # Clear the screen
        self.screen.fill(BACKGROUND_COLOR)
        
        # Render world entities
        for plant in self.plants:
            plant.render(self.camera)
        for herbivore in self.herbivores:
            herbivore.render(self.camera)
        for carnivore in self.carnivores:
            carnivore.render(self.camera)
        for smartie in self.smarties:
            smartie.render(self.camera)

        # Draw mini-map in the corner (optional) - skip in performance mode
        if not PERFORMANCE_MODE:
            self._draw_minimap()
        
        # Display stats if enabled
        if self.show_stats:
            self._draw_stats()
        
        # Display zoom level and performance mode status
        zoom_text = self.font.render(f"Zoom: {self.camera.zoom:.2f}x", True, (0, 0, 0))
        self.screen.blit(zoom_text, (10, SCREEN_SIZE[1] - 25))
        
        # Display FOV toggle status
        fov_status = "ON" if SHOW_FOV else "OFF"
        fov_color = (0, 120, 0) if SHOW_FOV else (120, 0, 0)
        fov_text = self.font.render(f"FOV: {fov_status} (F)", True, fov_color)
        self.screen.blit(fov_text, (150, SCREEN_SIZE[1] - 25))
        
        # Display performance mode status
        perf_status = "ON" if PERFORMANCE_MODE else "OFF"
        perf_color = (0, 120, 0) if PERFORMANCE_MODE else (120, 0, 0)
        perf_text = self.font.render(f"Performance Mode: {perf_status} (P)", True, perf_color)
        self.screen.blit(perf_text, (300, SCREEN_SIZE[1] - 25))
        
        # Display controls hint
        controls_text = self.font.render("Controls: Arrows/right-click drag to pan, +/- or mouse wheel to zoom, Tab for stats", True, (0, 0, 0))
        self.screen.blit(controls_text, (10, SCREEN_SIZE[1] - 50))

        pygame.display.flip()
        self.clock.tick(self.metadata["render_fps"])

    def _draw_minimap(self):
        """Draw a small minimap in the corner showing the camera position in the world"""
        # Skip minimap when zoomed out far enough (we can already see most of the world)
        if self.camera.zoom < 0.35:
            return
            
        # Constants for minimap
        minimap_size = 150
        minimap_padding = 10
        minimap_rect = pygame.Rect(
            SCREEN_SIZE[0] - minimap_size - minimap_padding,
            SCREEN_SIZE[1] - minimap_size - minimap_padding,
            minimap_size, minimap_size
        )
        
        # Draw minimap background
        pygame.draw.rect(self.screen, (240, 240, 240), minimap_rect)
        pygame.draw.rect(self.screen, (0, 0, 0), minimap_rect, 1)
        
        # Calculate ratio of world to minimap
        x_ratio = minimap_size / WORLD_SIZE[0]
        y_ratio = minimap_size / WORLD_SIZE[1]
        
        # Use more efficient drawing - only draw what's actually visible
        # Limit the number of entities drawn to avoid performance issues
        max_entities = 200
        
        # Draw dots for entities on minimap - limit to most important ones if too many
        plant_count = 0
        for plant in self.plants:
            # Apply a rate limit when many plants exist
            if len(self.plants) > max_entities and random.random() > max_entities / len(self.plants):
                continue
                
            pos = (minimap_rect.left + int(plant.pos[0] * x_ratio),
                minimap_rect.top + int(plant.pos[1] * y_ratio))
            # Use a smaller radius when many plants exist
            radius = 1
            pygame.draw.circle(self.screen, (0, 150, 0), pos, radius)
            plant_count += 1
            if plant_count > max_entities:
                break
            
        # Always draw all mammals (they're more important)
        for herbivore in self.herbivores:
            pos = (
                minimap_rect.left + int(herbivore.pos[0] * x_ratio),
                minimap_rect.top + int(herbivore.pos[1] * y_ratio)
            )
            pygame.draw.circle(self.screen, (0, 0, 255), pos, 2)
            
        for carnivore in self.carnivores:
            pos = (
                minimap_rect.left + int(carnivore.pos[0] * x_ratio),
                minimap_rect.top + int(carnivore.pos[1] * y_ratio)
            )
            pygame.draw.circle(self.screen, (255, 0, 0), pos, 2)
        
        # Draw current view area on minimap
        view_width = (self.camera.screen_width / self.camera.zoom) * x_ratio
        view_height = (self.camera.screen_height / self.camera.zoom) * y_ratio
        view_x = minimap_rect.left + int(
            (self.camera.position[0] - self.camera.screen_width / (2 * self.camera.zoom)) * x_ratio
        )
        view_y = minimap_rect.top + int(
            (self.camera.position[1] - self.camera.screen_height / (2 * self.camera.zoom)) * y_ratio
        )
        
        # Clamp view rectangle to minimap
        view_rect = pygame.Rect(view_x, view_y, view_width, view_height)
        pygame.draw.rect(self.screen, (255, 0, 0), view_rect, 1)

    def _draw_stats(self):
        """Draw simulation statistics"""
        # Calculate stats
        num_plants = len(self.plants)
        num_herbivores = len(self.herbivores)
        num_carnivores = len(self.carnivores)
        
        # Create text surfaces
        stats_text = [
            f"FPS: {int(self.clock.get_fps())}",
            f"Plants: {num_plants}",
            f"Herbivores: {num_herbivores}",
            f"Carnivores: {num_carnivores}",
            f"World: {WORLD_SIZE[0]}x{WORLD_SIZE[1]}"
        ]
        
        # Draw background for stats
        stats_width = 150
        stats_height = len(stats_text) * 20 + 10
        stats_rect = pygame.Rect(10, 10, stats_width, stats_height)
        pygame.draw.rect(self.screen, (240, 240, 240, 200), stats_rect)
        pygame.draw.rect(self.screen, (0, 0, 0), stats_rect, 1)
        
        # Draw each line of text
        for i, text in enumerate(stats_text):
            text_surf = self.font.render(text, True, (0, 0, 0))
            self.screen.blit(text_surf, (20, 15 + i * 20))

    def _get_observations(self):
        observations = {}
        for herbivore in self.herbivores:
            observations[herbivore] = {
                "position": herbivore.pos,
                "energy": herbivore.energy,
                "velocity": herbivore.direction,
                "state": "active",  # Example state
                "target": None  # Example target
            }
        return observations

if __name__ == "__main__":
    env = CreatureSimulation(render_mode="human")
    env.reset()
    running = True
    while running:
        # Create actions dictionary for all agents
        actions = {}
        for agent_id in env.possible_agents:
            # Use the "figure out" action for each agent
            actions[agent_id] = "figure out"
            
        # Update the simulation
        env.step(actions)
        
        # Render with camera system
        env.render()
        
        # Check if simulation should stop
        if pygame.key.get_pressed()[pygame.K_ESCAPE]:
            running = False

    env.close()
    pygame.quit()