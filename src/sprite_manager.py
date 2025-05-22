import arcade
from arcade.types.rect import LBWH, XYWH
from typing import Dict, Tuple, Optional
from sprite_config import SPRITE_CONFIGS, SPRITE_SHEETS

class SpriteManager:
    """
    Manages sprite loading and retrieval from sprite sheets.
    Handles sprite configurations and provides easy access to sprite textures.
    """
    
    def __init__(self):
        """Initialize the sprite manager."""
        self._sprite_sheets: Dict[str, arcade.SpriteSheet] = {}
        self._sprite_configs: Dict[str, Dict[str, Tuple[int, int, int, int]]] = {}
        self._adjustment_step = 1  # Default step size for adjustments
        self.handler_keys = [arcade.key.W, arcade.key.A, arcade.key.S, arcade.key.D, arcade.key.Q, arcade.key.E, arcade.key.F]
        
        # Default scaling for sprites
        self.default_scale = 1.0
        
        # Sprite adjustment helper
        self.adjustment_active = False
        self.adjustment_sprite_name = None
        self.adjustment_sprite = None
        self.adjustment_scene = None
        self.adjustment_spritesheet_sprite = None
        self.original_background_color = None
        
    def load_all_sprite_sheets(self) -> None:
        """
        Load all sprite sheets defined in SPRITE_SHEETS configuration.
        This automatically registers sprite configs for each sheet.
        """
        for sheet_name, path in SPRITE_SHEETS.items():
            print(f"Loading sprite sheet: {sheet_name} from {path}")
            self.load_sprite_sheet(sheet_name, path)
        
    def load_sprite_sheet(self, name: str, path: str) -> None:
        """
        Load a sprite sheet into memory and automatically register its sprite configurations.
        
        Args:
            name: Unique identifier for the sprite sheet
            path: Path to the sprite sheet image file
        """
        self._sprite_sheets[name] = arcade.load_spritesheet(path)
        
        # Automatically register sprite configs for this sheet
        if name in SPRITE_CONFIGS:
            for sprite_name, coords in SPRITE_CONFIGS[name].items():
                self.register_sprite_config(name, sprite_name, *coords)
        else:
            print(f"Warning: No sprite configs found for sheet '{name}'")
        
    def register_sprite_config(self, 
                             sheet_name: str,
                             sprite_name: str,
                             left: int,
                             bottom: int,
                             width: int,
                             height: int) -> None:
        """
        Register a sprite configuration for a specific sprite in a sprite sheet.
        
        Args:
            sheet_name: Name of the sprite sheet
            sprite_name: Unique identifier for the sprite
            left: Left coordinate in the sprite sheet
            bottom: Bottom coordinate in the sprite sheet
            width: Width of the sprite
            height: Height of the sprite
        """
        if sheet_name not in self._sprite_configs:
            self._sprite_configs[sheet_name] = {}
            
        self._sprite_configs[sheet_name][sprite_name] = (left, bottom, width, height)
        
    def get_sprite_texture(self, 
                          sheet_name: str,
                          sprite_name: str,
                          y_up: bool = True) -> Optional[arcade.Texture]:
        """
        Get a sprite texture from a sprite sheet.
        
        Args:
            sheet_name: Name of the sprite sheet
            sprite_name: Name of the sprite
            y_up: Whether the sprite sheet uses y-up coordinates
            
        Returns:
            The sprite texture or None if not found
        """
        if sheet_name not in self._sprite_sheets or sheet_name not in self._sprite_configs:
            return None
            
        if sprite_name not in self._sprite_configs[sheet_name]:
            return None
            
        left, bottom, width, height = self._sprite_configs[sheet_name][sprite_name]
        sprite_rect = LBWH(left, bottom, width, height)
        
        return self._sprite_sheets[sheet_name].get_texture(sprite_rect, y_up=y_up)
        
    def find_sprite_sheet(self, sprite_name: str) -> Optional[str]:
        """
        Find which sprite sheet contains the given sprite name.
        
        Args:
            sprite_name: Name of the sprite to search for
            
        Returns:
            The sheet name containing the sprite, or None if not found
        """
        for sheet_name, sprites in SPRITE_CONFIGS.items():
            if sprite_name in sprites:
                return sheet_name
        return None
        
    def create_sprite(self,
                     sprite_name: str,
                     scale: float = None,
                     y_up: bool = True) -> Optional[arcade.Sprite]:
        """
        Create a new sprite with the specified texture.
        Automatically finds the correct sprite sheet.
        
        Args:
            sprite_name: Name of the sprite (e.g., "smartie", "plant_stage_1")
            scale: Scale factor for the sprite (uses default_scale if None)
            y_up: Whether the sprite sheet uses y-up coordinates
            
        Returns:
            A new sprite with the specified texture or None if not found
        """
        if scale is None:
            scale = self.default_scale
        
        # Find which sheet contains this sprite
        sheet_name = self.find_sprite_sheet(sprite_name)
        if sheet_name is None:
            print(f"Warning: Sprite '{sprite_name}' not found in any sprite sheet")
            return None
            
        texture = self.get_sprite_texture(sheet_name, sprite_name, y_up)
        if texture is None:
            return None
            
        sprite = arcade.Sprite(scale=scale)
        sprite.texture = texture
        return sprite

    def adjust_sprite_position(self,
                             sheet_name: str,
                             sprite_name: str,
                             direction: str,
                             step: Optional[int] = None) -> bool:
        """
        Adjust the position of a sprite within the spritesheet using WASD keys.
        
        Args:
            sheet_name: Name of the sprite sheet
            sprite_name: Name of the sprite to adjust
            direction: Direction to move ('w', 'a', 's', 'd')
            step: Optional step size for the adjustment (defaults to self._adjustment_step)
            
        Returns:
            bool: True if adjustment was successful, False otherwise
        """
        if sheet_name not in self._sprite_configs or sprite_name not in self._sprite_configs[sheet_name]:
            return False
            
        step = step or self._adjustment_step
        left, bottom, width, height = self._sprite_configs[sheet_name][sprite_name]
        
        # Adjust position based on direction
        if direction.lower() == 'w':
            bottom += step
        elif direction.lower() == 's':
            bottom -= step
        elif direction.lower() == 'a':
            left -= step
        elif direction.lower() == 'd':
            left += step
        elif direction.lower() == 'q':
            self._adjustment_step += 1
        elif direction.lower() == 'e':
            self._adjustment_step -= 1
        elif direction.lower() == 'f':
            print(f"Adjustment info.\nSprite name: {sprite_name}\nSheet name: {sheet_name}\nBottom: {bottom}\nLeft: {left}\nWidth: {width}\nHeight: {height}")
        else:
            return False
            
        # Update the sprite configuration
        self._sprite_configs[sheet_name][sprite_name] = (left, bottom, width, height)
        return True
        
    def adjust_sprite_position_by_name(self,
                                     sprite_name: str,
                                     direction: str,
                                     step: Optional[int] = None) -> bool:
        """
        Adjust the position of a sprite within the spritesheet using just the sprite name.
        
        Args:
            sprite_name: Name of the sprite to adjust
            direction: Direction to move ('w', 'a', 's', 'd')
            step: Optional step size for the adjustment (defaults to self._adjustment_step)
            
        Returns:
            bool: True if adjustment was successful, False otherwise
        """
        sheet_name = self.find_sprite_sheet(sprite_name)
        if sheet_name is None:
            print(f"Warning: Sprite '{sprite_name}' not found for adjustment")
            return False
            
        return self.adjust_sprite_position(sheet_name, sprite_name, direction, step)
        
    def start_sprite_adjustment(self, sprite_name: str, main_scene, map_width: int, map_height: int, window) -> bool:
        """
        Start sprite adjustment mode for the given sprite.
        Creates a separate adjustment scene with spritesheet background.
        
        Args:
            sprite_name: Name of the sprite to adjust
            main_scene: The main game scene (for reference)
            map_width: Width of the map for centering
            map_height: Height of the map for centering
            window: The arcade window instance
            
        Returns:
            bool: True if adjustment mode started successfully
        """
        # Clean up any existing adjustment
        self.stop_sprite_adjustment()
        
        # Store original background color and change to amazon
        self.original_background_color = window.background_color
        window.background_color = arcade.color.AMAZON
        
        # Create adjustment scene
        self.adjustment_scene = arcade.Scene()
        print(f"Created adjustment scene: {self.adjustment_scene}")
        
        # Add spritesheet background layer FIRST (draws behind)
        spritesheet_layer = arcade.SpriteList()
        self.adjustment_scene.add_sprite_list("spritesheet", spritesheet_layer)
        print(f"Added spritesheet layer to scene")
        
        # Add adjustment sprite layer SECOND (draws on top)
        adjustment_layer = arcade.SpriteList()
        self.adjustment_scene.add_sprite_list("adjustment", adjustment_layer)
        print(f"Added adjustment layer to scene")
        
        # Find which sheet contains this sprite and display it
        sheet_name = self.find_sprite_sheet(sprite_name)
        if not sheet_name:
            print(f"Failed to find sprite sheet for '{sprite_name}'")
            return False
            
        # Create spritesheet background sprite
        if sheet_name in self._sprite_sheets:
            # Get the path to load the texture directly
            if sheet_name in SPRITE_SHEETS:
                sheet_path = SPRITE_SHEETS[sheet_name]
                sheet_texture = arcade.load_texture(sheet_path)
                
                print(f"Loaded spritesheet texture: {sheet_path}")
                print(f"Texture size: {sheet_texture.width}x{sheet_texture.height}")
                
                if sheet_texture and sheet_texture.width > 0 and sheet_texture.height > 0:
                    # Create a sprite from the entire spritesheet texture
                    self.adjustment_spritesheet_sprite = arcade.Sprite()
                    self.adjustment_spritesheet_sprite.texture = sheet_texture
                    self.adjustment_spritesheet_sprite.center_x = map_width / 2
                    self.adjustment_spritesheet_sprite.center_y = map_height / 2
                    # Scale down the spritesheet so it fits nicely as background
                    self.adjustment_spritesheet_sprite.scale = (0.5, 0.5)
                    self.adjustment_scene.add_sprite("spritesheet", self.adjustment_spritesheet_sprite)
                    
                    print(f"Spritesheet sprite created at ({map_width / 2}, {map_height / 2}) with scale (0.5, 0.5)")
                    print(f"Spritesheet layer now has {len(self.adjustment_scene['spritesheet'])} sprites")
                else:
                    print(f"Failed to load valid texture for spritesheet: {sheet_path}")
            else:
                print(f"Sheet '{sheet_name}' not found in SPRITE_SHEETS")
        
        # Create adjustment sprite
        self.adjustment_sprite = self.create_sprite(sprite_name)
        if not self.adjustment_sprite:
            print(f"Failed to create sprite '{sprite_name}' for adjustment")
            return False
            
        # Position adjustment sprite at map center (on top of spritesheet)
        self.adjustment_sprite.center_x = map_width / 2
        self.adjustment_sprite.center_y = map_height / 2
        self.adjustment_scene.add_sprite("adjustment", self.adjustment_sprite)
        
        print(f"Adjustment sprite created at ({map_width / 2}, {map_height / 2})")
        print(f"Adjustment layer now has {len(self.adjustment_scene['adjustment'])} sprites")
        
        # Set adjustment state
        self.adjustment_active = True
        self.adjustment_sprite_name = sprite_name
        
        print(f"Started sprite adjustment for '{sprite_name}'")
        print("Controls:")
        print("  WASD - Adjust sprite position in spritesheet")
        print("  Q/E - Change step size")
        print("  F - Show sprite info")
        print("  ESC - Exit adjustment mode")
        print("  Arrow Keys - Pan around the spritesheet")
        return True
        
    def stop_sprite_adjustment(self):
        """Stop sprite adjustment mode and clean up."""
        if hasattr(self, 'original_background_color') and self.original_background_color:
            # Restore original background color
            import arcade
            window = arcade.get_window()
            if window:
                window.background_color = self.original_background_color
            self.original_background_color = None
            
        # Clean up sprites
        if self.adjustment_sprite:
            self.adjustment_sprite.remove_from_sprite_lists()
            self.adjustment_sprite = None
            
        if self.adjustment_spritesheet_sprite:
            self.adjustment_spritesheet_sprite.remove_from_sprite_lists()
            self.adjustment_spritesheet_sprite = None
            
        # Clean up scene
        self.adjustment_scene = None
            
        self.adjustment_active = False
        self.adjustment_sprite_name = None
        print("Stopped sprite adjustment")
        
    def handle_adjustment_key(self, key) -> bool:
        """
        Handle key press for sprite adjustment.
        Returns True if key was handled (blocking normal game keys).
        
        Args:
            key: The key that was pressed
            
        Returns:
            bool: True if the key was handled, False otherwise
        """
        if not self.adjustment_active or not self.adjustment_sprite_name:
            return False
            
        # Handle sprite position adjustment
        if key in self.handler_keys:
            direction = chr(key).lower()
            if self.adjust_sprite_position_by_name(self.adjustment_sprite_name, direction):
                # Update sprite texture
                new_texture = self.get_sprite_texture(
                    self.find_sprite_sheet(self.adjustment_sprite_name),
                    self.adjustment_sprite_name
                )
                if new_texture:
                    self.adjustment_sprite.texture = new_texture
            return True
            
        # Handle scene navigation with arrow keys
        elif key == arcade.key.LEFT:
            if self.adjustment_spritesheet_sprite:
                self.adjustment_spritesheet_sprite.center_x += 5
                # Don't move the adjustment sprite - keep it centered
            return True
        elif key == arcade.key.RIGHT:
            if self.adjustment_spritesheet_sprite:
                self.adjustment_spritesheet_sprite.center_x -= 5
                # Don't move the adjustment sprite - keep it centered
            return True
        elif key == arcade.key.UP:
            if self.adjustment_spritesheet_sprite:
                self.adjustment_spritesheet_sprite.center_y -= 5
                # Don't move the adjustment sprite - keep it centered
            return True
        elif key == arcade.key.DOWN:
            if self.adjustment_spritesheet_sprite:
                self.adjustment_spritesheet_sprite.center_y += 5
                # Don't move the adjustment sprite - keep it centered
            return True
            
        # Handle zoom with +/- keys
        elif key == arcade.key.PLUS or key == arcade.key.EQUAL:
            if self.adjustment_spritesheet_sprite:
                scale_x, scale_y = self.adjustment_spritesheet_sprite.scale
                self.adjustment_spritesheet_sprite.scale = (scale_x * 1.1, scale_y * 1.1)
            return True
        elif key == arcade.key.MINUS:
            if self.adjustment_spritesheet_sprite:
                scale_x, scale_y = self.adjustment_spritesheet_sprite.scale
                self.adjustment_spritesheet_sprite.scale = (scale_x * 0.9, scale_y * 0.9)
            return True
            
        # Handle exit
        elif key == arcade.key.ESCAPE:
            self.stop_sprite_adjustment()
            return True
            
        # Block all other keys when in adjustment mode
        return True
        
    def draw_adjustment_outline(self):
        """Draw outline for the adjustment sprite if active."""
        if not self.adjustment_active or not self.adjustment_sprite:
            return
            
        # Get sprite config
        sheet_name = self.find_sprite_sheet(self.adjustment_sprite_name)
        if not sheet_name or sheet_name not in self._sprite_configs:
            return
            
        config = self._sprite_configs[sheet_name][self.adjustment_sprite_name]
        left, bottom, width, height = config
        
        # Draw outline using LBWH (convert center coordinates to bottom-left)
        sprite_x = self.adjustment_sprite.center_x
        sprite_y = self.adjustment_sprite.center_y
        
        # Handle scale properly - it's a tuple (scale_x, scale_y)
        scale_x, scale_y = self.adjustment_sprite.scale
        sprite_width = width * scale_x
        sprite_height = height * scale_y
        
        # Convert center to bottom-left for LBWH
        left_pos = sprite_x - sprite_width / 2
        bottom_pos = sprite_y - sprite_height / 2
        
        # Draw red outline around the sprite (stays centered)
        arcade.draw_rect_outline(
            LBWH(left_pos, bottom_pos, sprite_width, sprite_height),
            arcade.color.RED, 3
        )
        
        # Draw sprite position indicator on the spritesheet background
        if self.adjustment_spritesheet_sprite:
            # Calculate position on the spritesheet
            sheet_texture = self.adjustment_spritesheet_sprite.texture
            sheet_scale_x, sheet_scale_y = self.adjustment_spritesheet_sprite.scale
            sheet_x = self.adjustment_spritesheet_sprite.center_x
            sheet_y = self.adjustment_spritesheet_sprite.center_y
            
            # Calculate where this sprite appears on the sheet background
            sprite_on_sheet_x = sheet_x + (left - sheet_texture.width/2) * sheet_scale_x
            sprite_on_sheet_y = sheet_y + (bottom - sheet_texture.height/2) * sheet_scale_y
            sprite_on_sheet_w = width * sheet_scale_x
            sprite_on_sheet_h = height * sheet_scale_y
            
            # Draw yellow outline on the spritesheet to show current selection
            arcade.draw_rect_outline(
                LBWH(sprite_on_sheet_x, sprite_on_sheet_y, sprite_on_sheet_w, sprite_on_sheet_h),
                arcade.color.YELLOW, 2
            )
            
    def get_adjustment_scene(self):
        """Get the adjustment scene for drawing."""
        return self.adjustment_scene if self.adjustment_active else None 