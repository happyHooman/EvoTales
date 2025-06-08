import arcade
from sim_window import SimulationWindow
from config import *

def main():
    # Create the simulation world window and run the Arcade event loop
    window = SimulationWindow()
    window.setup()
    arcade.run()

if __name__ == "__main__":
    main()
