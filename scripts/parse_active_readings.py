"""
从 PDF 电费账单中解析有功示数差，并保存为 CSV

用法：
  python -m scripts.parse_active_readings
  python -m scripts.parse_active_readings --pdf docs/xxx.pdf
  python -m scripts.parse_active_readings --pdf docs/xxx.pdf --out data/processed/xxx.csv

输出文件名与 PDF 对应：{pdf 主文件名}_有功示数.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from app.config import settings
from app.llm_extractor import extract_from_image
from app.pdf_images import pdf_to_images


def parse_pdf_to_active_readings(
    pdf_path: Path,
    output_path: Path | None = None,
    page_limit: int | None = None,
    start_page: int = 0,
    dpi: int | None = None,
    verbose: bool = False,
) -> Path:
    """
    从 PDF 解析有功各部分（尖峰/峰/平/谷/深谷 kWh）并保存到 CSV。

    Returns:
        输出 CSV 的路径
    """
    pdf_path = Path(pdf_path).resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF 不存在: {pdf_path}")

    # 输出路径：与 PDF 主文件名对应
    if output_path is None:
        stem = pdf_path.stem
        out_dir = Path(settings.processed_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = out_dir / f"{stem}_有功示数.csv"
    else:
        output_path = Path(output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

    limit = page_limit or settings.pdf_page_limit
    dpi = dpi or settings.pdf_image_dpi
    def _log(*args, **kwargs):
        if verbose:
            print(*args, **kwargs, flush=True)

    _log(f"[1] PDF: {pdf_path}")
    _log(f"    从第 {start_page + 1} 页起, 最多 {limit} 页, DPI: {dpi}")

    # 1. PDF -> 图片
    images = pdf_to_images(pdf_path, page_limit=limit, start_page=start_page, dpi=dpi)
    _log(f"[2] 渲染完成: 共 {len(images)} 页")

    # 2. 大模型逐页抽取
    records = []
    for page_no, png_bytes in images:
        try:
            r = extract_from_image(png_bytes, page_no, debug=verbose)
            if r:
                # 接受任意有内容的记录（billing_month/total_fee/kwh 任一非空即可）
                has_data = any(
                    r.get(k) is not None
                    for k in ("billing_month", "total_fee", "peak2_kwh", "peak_kwh", "flat_kwh", "valley_kwh", "deep_valley_kwh", "total_active_kwh")
                )
                if has_data:
                    records.append(r)
                    rd = f"peak2={r.get('peak2_reading_diff')} peak={r.get('peak_reading_diff')} flat={r.get('flat_reading_diff')} valley={r.get('valley_reading_diff')} deep={r.get('deep_valley_reading_diff')} | fee={r.get('total_fee')}"
                    _log(f"    页 {page_no}: 示数差 {rd}")
                else:
                    _log(f"    页 {page_no}: 跳过（无有效字段）raw={r}")
            else:
                _log(f"    页 {page_no}: 返回 None（可能 skip）")
        except Exception as e:
            _log(f"    页 {page_no}: 异常 {e}")

    _log(f"[3] 有效记录数: {len(records)}")

    if not records:
        raise ValueError("未抽取到有效记录，请检查 LLM 配置及 PDF 内容。")

    # 3. 按月份聚合
    raw_df = pd.DataFrame(records)
    _log(f"    聚合前记录: {len(raw_df)} 行")
    if verbose and not raw_df.empty:
        _log("    聚合前明细:")
        for _, row in raw_df.iterrows():
            _log(f"      - {row.to_dict()}")

    df = raw_df.dropna(subset=["billing_month"])
    _log(f"    聚合前（含 billing_month）: {len(df)} 行")
    agg = {}
    for rd in ["peak2_reading_diff", "peak_reading_diff", "flat_reading_diff", "valley_reading_diff", "deep_valley_reading_diff"]:
        if rd in df.columns:
            agg[rd] = "first"
    if "total_fee" in df.columns:
        agg["total_fee"] = "max"
    if "multiplier" in df.columns:
        agg["multiplier"] = "first"
    agg["billing_month"] = "first"
    df = df.groupby("billing_month", as_index=False).agg(
        {k: v for k, v in agg.items() if k in df.columns}
    )
    _log(f"[4] 聚合后: {len(df)} 个月份")

    # 5. 列顺序（含日期）
    df = df.rename(columns={"billing_month": "timestamp"})
    df["日期"] = df["timestamp"]
    out_cols = [
        "日期", "timestamp",
        "peak2_reading_diff", "peak_reading_diff", "flat_reading_diff", "valley_reading_diff", "deep_valley_reading_diff",
        "multiplier", "total_fee",
    ]
    df = df[[c for c in out_cols if c in df.columns]]
    df = df.sort_values("timestamp").reset_index(drop=True)

    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    _log(f"[5] 已写入: {output_path}")
    if verbose:
        _log("    最终数据:")
        _log(df.to_string())
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="从 PDF 解析有功示数差并保存为 CSV")
    parser.add_argument(
        "--pdf",
        type=Path,
        default=settings.pdf_path,
        help="PDF 文件路径",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="输出 CSV 路径（默认: data/processed/{pdf主文件名}_有功示数.csv）",
    )
    parser.add_argument(
        "--page-limit",
        type=int,
        default=None,
        help="最多解析页数",
    )
    parser.add_argument(
        "--start-page",
        type=int,
        default=0,
        help="起始页(0-based)，跳过前 N 页（如封面）",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=None,
        help="渲染 DPI（默认 150）",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="输出详细日志",
    )
    args = parser.parse_args()

    try:
        out = parse_pdf_to_active_readings(
            pdf_path=args.pdf,
            output_path=args.out,
            page_limit=args.page_limit,
            start_page=args.start_page,
            dpi=args.dpi or settings.pdf_image_dpi,
            verbose=args.verbose,
        )
        print(f"已保存: {out}")
    except Exception as e:
        print(f"解析失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
