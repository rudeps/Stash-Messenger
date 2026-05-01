#!/usr/bin/env python3
import sys
import argparse
from core_client import CoreClient
from gui import TelegramStyleGUI

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, help='Listen port')
    parser.add_argument('--bootstrap', type=str, help='Bootstrap node ip:port')
    args = parser.parse_args()

    try:
        import tkinter
    except ImportError:
        print("Error: tkinter required.")
        sys.exit(1)

    core = CoreClient(port=args.port)
    core.start(bootstrap=args.bootstrap)

    gui = TelegramStyleGUI(core)
    gui.root.mainloop()

if __name__ == "__main__":
    main()