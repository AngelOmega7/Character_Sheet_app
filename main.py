"""Entry point used by Flet's Windows and Android builders."""
import flet as ft

from zoids_app.ui import ASSETS_DIR, main


if __name__ == "__main__":
    ft.run(main, assets_dir=str(ASSETS_DIR))
