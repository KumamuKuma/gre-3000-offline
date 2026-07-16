from __future__ import annotations

import argparse
import io
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QRectF, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)
RASTER_SIZE = 1024


def svg_to_png(svg_path: Path) -> bytes:
    renderer = QSvgRenderer(QByteArray(svg_path.read_bytes()))
    if not renderer.isValid():
        raise RuntimeError(f"Invalid SVG icon: {svg_path}")

    image = QImage(RASTER_SIZE, RASTER_SIZE, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    try:
        renderer.render(painter, QRectF(0, 0, RASTER_SIZE, RASTER_SIZE))
    finally:
        painter.end()

    buffer = QBuffer()
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
        raise RuntimeError("Unable to allocate the icon render buffer")
    if not image.save(buffer, "PNG"):
        raise RuntimeError("Qt failed to rasterize the SVG icon")
    return bytes(buffer.data())


def generate_icon(svg_path: Path, output_path: Path) -> None:
    if not svg_path.is_file():
        raise FileNotFoundError(f"SVG icon not found: {svg_path}")

    QGuiApplication.instance() or QGuiApplication(
        ["generate-icon", "-platform", "offscreen"]
    )
    with Image.open(io.BytesIO(svg_to_png(svg_path))) as rendered:
        source = rendered.convert("RGBA")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        source.save(
            output_path,
            format="ICO",
            sizes=[(size, size) for size in ICON_SIZES],
        )

    with Image.open(output_path) as generated:
        actual_sizes = set(generated.ico.sizes())
    missing_sizes = set((size, size) for size in ICON_SIZES) - actual_sizes
    if missing_sizes:
        raise RuntimeError(f"ICO is missing required sizes: {sorted(missing_sizes)}")
    print(
        f"icon_generated path={output_path} sizes="
        + ",".join(str(size) for size in ICON_SIZES)
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rasterize the project SVG with Qt and create a multi-size ICO with Pillow."
    )
    parser.add_argument("svg", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    generate_icon(arguments.svg.resolve(), arguments.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
