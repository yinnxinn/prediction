"""
大模型配置连通性测试

用法：python -m scripts.test_llm_config
"""
from __future__ import annotations

import base64
import io
import sys

# 50x50 白色 PNG（部分模型对 1x1 图会报 Invalid image data）
def _make_test_png() -> bytes:
    from PIL import Image
    img = Image.new("RGB", (50, 50), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_llm_config() -> None:
    from app.config import settings

    print("=== 大模型配置检查 ===")
    print(f"  LLM_API_KEY: {'已配置' if settings.llm_api_key else '未配置'}")
    print(f"  LLM_MODEL: {settings.llm_model}")
    if settings.azure_endpoint:
        print(f"  模式: Azure OpenAI")
        print(f"  AZURE_ENDPOINT: {settings.azure_endpoint[:50]}...")
    else:
        print(f"  模式: OpenAI 兼容")
        print(f"  LLM_BASE_URL: {settings.llm_base_url or '(默认)'}")
    print()

    if not settings.llm_api_key:
        print("[FAIL] 未配置 LLM_API_KEY，请在 .env 中设置")
        sys.exit(1)

    print("发起视觉 API 测试请求（50x50 占位图）...")
    try:
        from app.llm_extractor import extract_from_image

        png_bytes = _make_test_png()
        result = extract_from_image(png_bytes, page_no=1)
        if result is not None:
            print("[OK] 视觉 API 连通成功")
            print(f"    返回: {result}")
        else:
            print("[OK] API 调用成功（模型返回 skip/null，属正常）")
    except Exception as e:
        print(f"[FAIL] 调用失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    test_llm_config()
