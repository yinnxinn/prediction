"""
PDF 转图片模块

将 PDF 每页渲染为 PNG 图片，用于大模型视觉识别。
"""

from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Any

from PIL import Image


def pdf_to_images(
    pdf_path: Path,
    page_limit: int | None = None,
    start_page: int = 0,
    dpi: int = 150,
) -> list[tuple[int, bytes]]:
    """
    将 PDF 每页渲染为 PNG 字节流。

    Args:
        start_page: 起始页索引(0-based)，跳过前 N 页
    Returns:
        list of (page_no, png_bytes)，page_no 从 1 起
    """
    import fitz

    images: list[tuple[int, bytes]] = []
    zoom = max(dpi / 72.0, 1.5)
    mat = fitz.Matrix(zoom, zoom)

    with fitz.open(str(pdf_path)) as doc:
        total = len(doc)
        end = min(start_page + (page_limit or total - start_page), total)
        for idx in range(start_page, end):
            page = doc.load_page(idx)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            images.append((idx + 1, buf.getvalue()))
    return images


def image_to_base64(png_bytes: bytes) -> str:
    """PNG 字节转 base64，供 API 使用"""
    return base64.standard_b64encode(png_bytes).decode("ascii")
