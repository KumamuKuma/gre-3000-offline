from __future__ import annotations

import argparse
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


def render(svg: Path, output: Path, size: int) -> None:
    renderer = QSvgRenderer(str(svg))
    if not renderer.isValid():
        raise ValueError(f"invalid SVG: {svg}")
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(QColor("#f5f2ea"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    output.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(output), "PNG"):
        raise OSError(f"unable to save {output}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("svg", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    for name, size in (
        ("icon-192.png", 192),
        ("icon-512.png", 512),
        ("apple-touch-icon.png", 180),
    ):
        render(args.svg, args.output_dir / name, size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
