import arcade
from arcade.types.rect import LBWH
from typing import Dict, Tuple, Optional

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
        
    def load_sprite_sheet(self, name: str, path: str) -> None:
        """
        Load a sprite sheet into memory.
        
        Args:
            name: Unique identifier for the sprite sheet
            path: Path to the sprite sheet image file
        """
        self._sprite_sheets[name] = arcade.load_spritesheet(path)
        
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
        
    def create_sprite(self,
                     sheet_name: str,
                     sprite_name: str,
                     scale: float = 1.0,
                     y_up: bool = True) -> Optional[arcade.Sprite]:
        """
        Create a new sprite with the specified texture.
        
        Args:
            sheet_name: Name of the sprite sheet
            sprite_name: Name of the sprite
            scale: Scale factor for the sprite
            y_up: Whether the sprite sheet uses y-up coordinates
            
        Returns:
            A new sprite with the specified texture or None if not found
        """
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