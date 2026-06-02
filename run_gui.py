import sys
import os

# Add src to the system path to allow importing modules from it
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from gui import main

if __name__ == "__main__":
    main()
