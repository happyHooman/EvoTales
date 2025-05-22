import arcade
from arcade.types.rect import LBWH
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