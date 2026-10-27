"""Renderuje wektorową ikonę projektu do formatów używanych w wydaniach."""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def create_icons(root: Path):
    from PIL import Image
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    assets = root / "moviecheck" / "assets"
    output = root / "build" / "icons"
    output.mkdir(parents=True, exist_ok=True)
    renderer = QSvgRenderer(str(assets / "moviecheck.svg"))
    if not renderer.isValid():
        raise RuntimeError("Nieprawidłowy źródłowy plik SVG ikony.")
    image = QImage(1024, 1024, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    master = output / "moviecheck-1024.png"
    if not image.save(str(master)):
        raise RuntimeError("Nie udało się zapisać ikony PNG.")
    with Image.open(master) as source:
        source.resize((512, 512), Image.Resampling.LANCZOS).save(assets / "moviecheck.png")
        source.resize((128, 128), Image.Resampling.LANCZOS).save(output / "preview.png")
        source.save(output / "moviecheck.ico", sizes=[(size, size) for size in (16, 24, 32, 48, 64, 128, 256)])
        source.save(output / "moviecheck.icns")
    print(f"Ikony PNG, ICO i ICNS: {output}", flush=True)


if __name__ == "__main__":
    create_icons(Path(__file__).resolve().parents[1])
