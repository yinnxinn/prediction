"""
电费账单解析管道：PDF → 图片 → 大模型抽取 → 有功各部分数据集

流程：
1. PDF 每页渲染为图片
2. 调用大模型视觉 API 从图片中抽取有功各时段用电量
3. 按月份聚合，输出 active_components_monthly.csv、electricity_price_monthly.csv
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.config import settings
from app.llm_extractor import extract_from_image
from app.pdf_images import pdf_to_images


@dataclass
class ParseSummary:
    parse_mode: str
    pages: int
    extracted_records: int
    dataset_path: Path
    report_path: Path


class PdfBillPipeline:
    def __init__(self, pdf_path: Path | None = None, page_limit: int | None = None) -> None:
        self.pdf_path = pdf_path or settings.pdf_path
        self.page_limit = page_limit or settings.pdf_page_limit
        settings.processed_dir.mkdir(parents=True, exist_ok=True)

    def run(self) -> ParseSummary:
        # 1. PDF → 图片
        images = pdf_to_images(
            self.pdf_path,
            page_limit=self.page_limit,
            dpi=settings.pdf_image_dpi,
        )

        # 2. 大模型逐页抽取
        records: list[dict[str, Any]] = []
        for page_no, png_bytes in images:
            try:
                r = extract_from_image(png_bytes, page_no)
                if r and (r.get("billing_month") or r.get("total_fee")):
                    records.append(r)
            except Exception as e:
                # 单页失败不中断，可日志记录
                pass

        if not records:
            raise ValueError("未从 PDF 抽取到有效记录，请检查 LLM_API_KEY 及图片内容。")

        # 3. 按月份聚合
        df = pd.DataFrame(records)
        df = df.dropna(subset=["billing_month"])
        cols = [
            c
            for c in ["peak2_kwh", "peak_kwh", "flat_kwh", "valley_kwh", "deep_valley_kwh", "total_active_kwh"]
            if c in df.columns
        ]
        agg_dict = {c: "sum" for c in cols}
        if "total_fee" in df.columns:
            agg_dict["total_fee"] = "max"
        agg_dict["billing_month"] = "first"
        df = df.groupby("billing_month", as_index=False).agg({k: v for k, v in agg_dict.items() if k in df.columns})

        # 4. 保存有功各部分
        ac_df = df.rename(columns={"billing_month": "timestamp"}).sort_values("timestamp").reset_index(drop=True)
        ac_path = settings.processed_dir / "active_components_monthly.csv"
        ac_df.to_csv(ac_path, index=False, encoding="utf-8-sig")

        # 5. 派生 electricity_price_monthly（兼容旧接口）
        price_df = _derive_price_dataset(ac_df)
        price_path = settings.processed_dir / "electricity_price_monthly.csv"
        price_df.to_csv(price_path, index=False, encoding="utf-8-sig")

        # 6. 报告
        report = {
            "pdf_path": str(self.pdf_path),
            "parse_mode": "llm-vision",
            "pages": len(images),
            "extracted_pages": len(records),
            "timeseries_rows": len(ac_df),
            "active_components_path": str(ac_path),
            "price_dataset_path": str(price_path),
            "generated_at": datetime.utcnow().isoformat(),
        }
        report_path = settings.processed_dir / "pipeline_report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        return ParseSummary(
            parse_mode="llm-vision",
            pages=len(images),
            extracted_records=len(ac_df),
            dataset_path=price_path,
            report_path=report_path,
        )


def _derive_price_dataset(ac_df: pd.DataFrame) -> pd.DataFrame:
    """从有功各部分派生电价数据集"""
    df = ac_df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    total_cols = [c for c in ["peak2_kwh", "peak_kwh", "flat_kwh", "valley_kwh", "deep_valley_kwh"] if c in df.columns]
    if total_cols:
        df["total_kwh"] = df[total_cols].sum(axis=1)
    elif "total_active_kwh" in df.columns:
        df["total_kwh"] = df["total_active_kwh"]
    else:
        df["total_kwh"] = np.nan

    if "total_fee" in df.columns and "total_kwh" in df.columns:
        df["price"] = df["total_fee"] / df["total_kwh"]
    else:
        df["price"] = np.nan

    df["price"] = pd.to_numeric(df["price"], errors="coerce").interpolate(limit_direction="both")
    df = df.dropna(subset=["timestamp", "price"])

    out_cols = ["timestamp", "price", "total_fee", "total_kwh"]
    return df[[c for c in out_cols if c in df.columns]]
