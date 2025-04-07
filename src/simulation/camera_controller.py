import arcade
from arcade.types import Rect, LRBT

class MapBounds:
    def __init__(self, width, height, padding):
        self.width = width
        self.height = height
        self.padding = padding
        self.full_width = width + 2 * padding
        self.full_height = height + 2 * padding
        self.left = -padding
        self.right = width + padding
        self.bottom = -padding
        self.top = height + padding

    @property
    def center(self):
        return (self.width / 2, self.height / 2)



class CameraController:
    def __init__(self, camera_settings, window):
        self.camera = None
        self.window = window
        self.map_bounds = None
        self.padding = camera_settings["PADDING"] # pixels of padding allowed outside map bounds
        self.max_zoom = camera_settings["MAX_ZOOM"]
        self.min_zoom = camera_settings["MIN_ZOOM"]
        self.zoom_factor = camera_settings["ZOOM_FACTOR"]
        self.pan_rate = camera_settings["PAN_RATE"]         # pixels per second
        self.min_allowed_zoom = camera_settings["MIN_ZOOM"]

    def setup(self, map_width, map_height):
        self.camera = arcade.Camera2D()
        self.map_bounds = MapBounds(map_width, map_height, self.padding)
        self.update_min_zoom()
        self.center_camera()
    
    def update_min_zoom(self):
        print("update min zoom")
        if not self.map_bounds:
            print("no map bounds")
            return
        
        zoom_for_width = self.window.width / self.map_bounds.full_width
        zoom_for_height = self.window.height / self.map_bounds.full_height

        self.min_zoom = max(min(zoom_for_width, zoom_for_height), self.min_allowed_zoom)
        self.camera.zoom = max(self.min_zoom, self.camera.zoom)
        print(f"min_zoom: {self.min_zoom}")

    def center_camera(self):
        if not self.map_bounds:
            return

        self.camera.position = self.map_bounds.center

    def clamp_position(self, x=None, y=None):
        x = x or self.camera.position[0]
        y = y or self.camera.position[1]
        if not self.map_bounds:
            return x, y

        visible_width = self.camera.projection.width
        visible_height = self.camera.projection.height

        min_x = self.map_bounds.left + visible_width / 2
        max_x = self.map_bounds.right - visible_width / 2
        min_y = self.map_bounds.bottom + visible_height / 2
        max_y = self.map_bounds.top - visible_height / 2
        
        (center_x, center_y) = self.map_bounds.center

        # Handle map smaller than viewport
        if visible_width > self.map_bounds.full_width:
            x = center_x
        else:
            x = max(min_x, min(x, max_x))

        if visible_height > self.map_bounds.full_height:
            y = center_y
        else:
            y = max(min_y, min(y, max_y))

        self.camera.position = (x, y)

    def handle_resize(self, width, height):
        self.update_min_zoom()
        self.camera.viewport = self.window.rect
        h_w = width / 2 / self.camera.zoom # half width
        h_h = height / 2 / self.camera.zoom # half height
        self.camera.projection = LRBT(-h_w, h_w, -h_h, h_h)
        self.clamp_position()

    def apply_zoom(self, direction):
        if direction == "in":
            self.camera.zoom = min(self.camera.zoom * self.zoom_factor, self.max_zoom)
        elif direction == "out":
            self.camera.zoom = max(self.camera.zoom / self.zoom_factor, self.min_zoom)
        else:
            raise ValueError(f"Invalid zoom direction: {direction}. Only 'in' or 'out' are allowed.")
        
        print(f"zoom: {self.camera.zoom}")
        self.clamp_position()

    def handle_drag(self, dx, dy):
        world_dx = dx / self.camera.zoom
        world_dy = dy / self.camera.zoom
        new_x = self.camera.position[0] - world_dx
        new_y = self.camera.position[1] - world_dy
        self.clamp_position(new_x, new_y)

    def update_panning(self, pressed_keys, delta_time):
        dx = dy = 0
        if arcade.key.LEFT in pressed_keys:
            dx -= self.pan_rate * delta_time
        if arcade.key.RIGHT in pressed_keys:
            dx += self.pan_rate * delta_time
        if arcade.key.UP in pressed_keys:
            dy += self.pan_rate * delta_time
        if arcade.key.DOWN in pressed_keys:
            dy -= self.pan_rate * delta_time

        if dx or dy:
            (old_x, old_y) = self.camera.position
            new_x = old_x + dx
            new_y = old_y + dy
            self.clamp_position(new_x, new_y)
