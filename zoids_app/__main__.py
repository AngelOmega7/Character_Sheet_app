"""Launch the offline desktop app: python -m zoids_app."""
import flet as ft

from .ui import ASSETS_DIR, main

if __name__ == "__main__":
    ft.run(main, assets_dir=str(ASSETS_DIR))
