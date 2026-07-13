"""
PHASMIDA Core
==============================

Punto de entrada principal del núcleo de navegación.
"""

from core.nmea_state_manager import NMEAStateManager

def main() -> None:
    manager = NMEAStateManager()
    manager.run()


if __name__ == "__main__":
    main()
