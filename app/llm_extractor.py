"""
大模型视觉抽取：从电费账单图片中提取有功各部分

支持 OpenAI 兼容的视觉 API（GPT-4V、 Claude、通义千问、GLM-4V 等）。
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.config import settings
from app.pdf_images import image_to_base64

EXTRACT_PROMPT = """你是电力账单 OCR 助手。观察「江苏电费核查联」中分时电量表。

**表格格式**（典型）：
| 时段 | 示数差 | 单价 | 金额 |
| 尖峰 | 0.9113 | ... | ... |
| 峰 | 7.28 | ... | ... |
| 平 | 1.7056 | ... | ... |
| 谷 | 8.20 | ... | ... |
| 深谷 | 5.76 | ... | ... |

**任务**：找到第一列含「尖峰」「峰」「平」「谷」「深谷」的五行，取各自同一行第二列「示数差」。按**行名**对应，不按表格行序（有的表「峰」在「尖峰」前）。
忽略「定比」「合计」「小计」等非时段行。

返回 JSON（仅数据）：
{
  "billing_month": "YYYY-MM-01",
  "total_fee": 合计金额,
  "multiplier": 2000,
  "peak2_reading_diff": 尖峰行第二列,
  "peak_reading_diff": 峰行第二列,
  "flat_reading_diff": 平行第二列,
  "valley_reading_diff": 谷行第二列,
  "deep_valley_reading_diff": 深谷行第二列
}

无此分时表则 {"skip": true}。"""


def extract_from_image(
    png_bytes: bytes,
    page_no: int,
    debug: bool = False,
) -> dict[str, Any] | None:
    """
    调用大模型视觉 API，从单页图片抽取有功各部分。

    Returns:
        抽取结果 dict，或 None（跳过页/失败）
    """
    if not settings.llm_api_key:
        raise ValueError("未配置 LLM_API_KEY，请在 .env 中设置。")

    b64 = image_to_base64(png_bytes)
    content = _call_vision_api(b64, EXTRACT_PROMPT, debug=debug)

    if not content:
        if debug:
            print(f"    [DEBUG page{page_no}] API returned empty content")
        return None

    data = _parse_llm_response(content)
    if data is None:
        if debug:
            print(f"    [DEBUG page{page_no}] parse failed raw={content[:200]}...")
        return None
    if data.get("skip") is True:
        return None

    # 示数差 → 用电量(kWh) = 示数差 × 乘率
    mult = data.get("multiplier") or 2000
    try:
        mult = float(mult)
    except (TypeError, ValueError):
        mult = 2000.0

    for rd_key, kwh_key in [
        ("peak2_reading_diff", "peak2_kwh"),
        ("peak_reading_diff", "peak_kwh"),
        ("flat_reading_diff", "flat_kwh"),
        ("valley_reading_diff", "valley_kwh"),
        ("deep_valley_reading_diff", "deep_valley_kwh"),
    ]:
        v = data.get(rd_key)
        if v is not None:
            try:
                data[kwh_key] = float(v) * mult
            except (TypeError, ValueError):
                data[kwh_key] = None

    parts = [
        data.get("peak2_kwh"),
        data.get("peak_kwh"),
        data.get("flat_kwh"),
        data.get("valley_kwh"),
        data.get("deep_valley_kwh"),
    ]
    valid = [x for x in parts if x is not None]
    if valid and "total_active_kwh" not in data or data.get("total_active_kwh") is None:
        data["total_active_kwh"] = sum(valid)

    data["page_no"] = page_no
    return data


def _call_vision_api(image_base64: str, prompt: str, debug: bool = False) -> str | None:
    """调用 OpenAI 或 Azure OpenAI 视觉 API"""
    try:
        from openai import AzureOpenAI, OpenAI
    except ImportError:
        raise ImportError("请安装 openai: pip install openai")

    if settings.azure_endpoint:
        base = settings.azure_endpoint.rstrip("/")
        for suffix in ("/openai/v1", "/openai", "/v1"):
            if base.endswith(suffix):
                base = base[: -len(suffix)].rstrip("/")
                break
        client = AzureOpenAI(
            api_key=settings.llm_api_key,
            api_version=settings.azure_api_version,
            azure_endpoint=base,
        )
    else:
        client = OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url or None,
        )

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_base64}"},
                },
            ],
        }
    ]

    resp = client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        max_completion_tokens=4096,
    )
    content = resp.choices[0].message.content if resp.choices else None
    if debug and not content:
        n = len(resp.choices) if resp.choices else 0
        c0 = resp.choices[0] if resp.choices else None
        info = f"content={c0.message.content!r} finish_reason={c0.finish_reason}" if c0 else f"choices empty n={n}"
        print(f"    [DEBUG] {info}", flush=True)
    return content


def _parse_llm_response(content: str) -> dict[str, Any] | None:
    """解析 LLM 返回的 JSON"""
    content = content.strip()
    # 提取 JSON 块
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
    if m:
        content = m.group(1).strip()
    m = re.search(r"\{[\s\S]*\}", content)
    if m:
        content = m.group(0)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return None
