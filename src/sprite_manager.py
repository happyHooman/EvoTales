import arcade
from arcade.types.rect import LBWH, XYWH
from typing import Dict, Tuple, Optional
from sprite_config import SPRITE_CONFIGS, SPRITE_SHEETS

SPRITE_SCALE = 1.0

class SpriteManager:
    """
    Manages sprite loading and retrieval from sprite sheets.
    Handles sprite configurations and provides easy access to sprite textures.
    """
    
    def __init__(self):
        """Initialize the sprite manager."""
        self._sprite_sheets: Dict[str, arcade.SpriteSheet] = {}
        self._sprite_configs: Dict[str, Dict[str, Tuple[int, int, int, int, float]]] = {}
        self._adjustment_step = 1  # Default step size for adjustments
        # self.handler_keys = [arcade.key.W, arcade.key.A, arcade.key.S, arcade.key.D, arcade.key.Q, arcade.key.E, arcade.key.F]
        
        # Default scaling for sprites
        self.default_scale = SPRITE_SCALE
        
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
                             height: int,
                             scale: float = 1.0) -> None:
        """
        Register a sprite configuration for a specific sprite in a sprite sheet.

        Args:
            sheet_name: Name of the sprite sheet
            sprite_name: Unique identifier for the sprite
            left: Left coordinate in the sprite sheet
            bottom: Bottom coordinate in the sprite sheet
            width: Width of the sprite
            height: Height of the sprite
            scale: Default scale factor for the sprite
        """
        if sheet_name not in self._sprite_configs:
            self._sprite_configs[sheet_name] = {}

        self._sprite_configs[sheet_name][sprite_name] = (left, bottom, width, height, scale)
        
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
            
        left, bottom, width, height, _ = self._sprite_configs[sheet_name][sprite_name]
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
                     scale: float = 1.0,
                     y_up: bool = True) -> Optional[arcade.Sprite]:
        """
        Create a new sprite with the specified texture.
        Automatically finds the correct sprite sheet.

        Args:
            sprite_name: Name of the sprite (e.g., "smartie", "plant_stage_1")
            scale: Scale factor for the sprite (uses config scale if None, falls back to default_scale)
            y_up: Whether the sprite sheet uses y-up coordinates

        Returns:
            A new sprite with the specified texture or None if not found
        """
        # Find which sheet contains this sprite
        sheet_name = self.find_sprite_sheet(sprite_name)
        if sheet_name is None:
            print(f"Warning: Sprite '{sprite_name}' not found in any sprite sheet")
            return None

        # Use config scale as default if no scale provided
        if scale is None:
            if sprite_name in self._sprite_configs[sheet_name]:
                _, _, _, _, config_scale = self._sprite_configs[sheet_name][sprite_name]
                scale = config_scale
            else:
                scale = self.default_scale

        texture = self.get_sprite_texture(sheet_name, sprite_name, y_up)
        if texture is None:
            return None
            
        sprite = arcade.Sprite(scale=scale)
        sprite.texture = texture
        return sprite

    def get_texture(self, 
                     sprite_name_or_list: str | list[str],
                     y_up: bool = True) -> Optional[arcade.Texture | list[arcade.Texture]]:
        """
        Get a single texture or a list of textures by sprite name(s).
        Automatically finds the correct sprite sheet for each name.

        Args:
            sprite_name_or_list: A single sprite name (str) or a list of sprite names (list[str]).
            y_up: Whether the sprite sheet uses y-up coordinates.

        Returns:
            An arcade.Texture if a single name was given,
            A list of arcade.Texture objects if a list of names was given,
            Or None if any sprite name is not found or an error occurs.
        """
        if isinstance(sprite_name_or_list, str):
            # Handle single sprite name
            sprite_name = sprite_name_or_list
            sheet_name = self.find_sprite_sheet(sprite_name)
            if sheet_name is None:
                print(f"Warning: Sprite '{sprite_name}' not found in any sprite sheet configuration.")
                return None
            texture = self.get_sprite_texture(sheet_name, sprite_name, y_up)
            if texture is None:
                # get_sprite_texture would have printed a warning if config was missing for a found sheet
                print(f"Warning: Could not load texture for sprite '{sprite_name}' from sheet '{sheet_name}'.")
            return texture
        
        elif isinstance(sprite_name_or_list, list):
            # Handle list of sprite names
            textures = []
            for sprite_name in sprite_name_or_list:
                if not isinstance(sprite_name, str):
                    print(f"Warning: Item '{sprite_name}' in list is not a string. Skipping.")
                    textures.append(None) # Or handle error differently
                    continue
                
                sheet_name = self.find_sprite_sheet(sprite_name)
                if sheet_name is None:
                    print(f"Warning: Sprite '{sprite_name}' not found in any sprite sheet configuration. Appending None.")
                    textures.append(None)
                    continue
                
                texture = self.get_sprite_texture(sheet_name, sprite_name, y_up)
                if texture is None:
                    print(f"Warning: Could not load texture for sprite '{sprite_name}' from sheet '{sheet_name}'. Appending None.")
                textures.append(texture)
            return textures
        
        else:
            print(f"Warning: Invalid type for sprite_name_or_list. Expected str or list, got {type(sprite_name_or_list)}.")
            return None


sprite_manager = SpriteManager()
sprite_manager.load_all_sprite_sheets()