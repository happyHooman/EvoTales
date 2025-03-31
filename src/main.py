import arcade
from environment import EvoTalesWorld

def main():
    # Create the simulation world window and run the Arcade event loop
    window = EvoTalesWorld()
    window.setup()
    arcade.run()

if __name__ == "__main__":
    main()
