from __future__ import annotations

import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.modeling import (
    ActiveComponentPredictor,
    ConsumptionModelService,
    PriceModelService,
    ReadingDiffPredictor,
    predict_with_reasons,
)
from app.pipeline import PdfBillPipeline
from app.schemas import (
    PipelineRunResponse,
    PredictRequest,
    PredictResponse,
    PredictPoint,
    TrainResponse,
    WorkflowResponse,
)

app = FastAPI(title=settings.app_name, version=settings.app_version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_WEB_DIST = settings.project_root / "web" / "dist"
_WEB_ASSETS = _WEB_DIST / "assets"


def _spa_index() -> FileResponse:
    idx = _WEB_DIST / "index.html"
    if idx.exists():
        return FileResponse(idx)
    legacy = settings.project_root / "templates" / "index.html"
    if legacy.exists():
        return FileResponse(legacy)
    raise HTTPException(status_code=404, detail="前端未构建：请在 web 目录执行 npm run build，或保留 templates/index.html。")


def _spa_path_is_api(full_path: str) -> bool:
    first = full_path.split("/")[0] if full_path else ""
    return first in {
        "docs",
        "openapi.json",
        "redoc",
        "ui",
        "health",
        "reading-diff",
        "workflow",
        "pipeline",
        "dataset",
        "paths",
        "active-components",
        "train",
        "predict",
        "assets",
    }


@app.get("/", include_in_schema=False)
def spa_root() -> FileResponse:
    return _spa_index()


if _WEB_ASSETS.exists():
    app.mount("/assets", StaticFiles(directory=str(_WEB_ASSETS)), name="spa_assets")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name, "version": settings.app_version}


@app.post("/pipeline/run", response_model=PipelineRunResponse)
def run_pipeline(page_limit: int = 38) -> PipelineRunResponse:
    if not settings.pdf_path.exists():
        raise HTTPException(status_code=404, detail=f"未找到 PDF: {settings.pdf_path}")
    try:
        summary = PdfBillPipeline(pdf_path=settings.pdf_path, page_limit=page_limit).run()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return PipelineRunResponse(
        pdf_path=str(settings.pdf_path),
        parse_mode=summary.parse_mode,
        pages=summary.pages,
        extracted_records=summary.extracted_records,
        dataset_path=str(summary.dataset_path),
        report_path=str(summary.report_path),
        message="PDF 解析完成并已生成结构化数据集。",
    )


@app.post("/train", response_model=TrainResponse)
def train_model() -> TrainResponse:
    dataset_path = settings.processed_dir / "electricity_price_monthly.csv"
    if not dataset_path.exists():
        raise HTTPException(
            status_code=400,
            detail="尚未生成数据集，请先调用 /pipeline/run。",
        )
    try:
        result = PriceModelService().train(dataset_path=dataset_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return TrainResponse(
        model_path=str(result.model_path),
        metrics_path=str(result.metrics_path),
        train_rows=result.train_rows,
        test_rows=result.test_rows,
        mae=result.mae,
        rmse=result.rmse,
        mape=result.mape,
    )


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest) -> PredictResponse:
    dataset_path = settings.processed_dir / "electricity_price_monthly.csv"
    if not dataset_path.exists():
        raise HTTPException(status_code=400, detail="尚未生成数据集，请先调用 /pipeline/run。")

    try:
        pred_df = PriceModelService().predict(dataset_path=dataset_path, months=req.months)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return PredictResponse(
        model_path=str(settings.model_dir / "price_model.pkl"),
        horizon_months=req.months,
        predictions=[
            PredictPoint(timestamp=row["timestamp"], predicted_price=row["predicted_price"])
            for _, row in pred_df.iterrows()
        ],
    )


@app.get("/dataset/preview")
def dataset_preview(limit: int = 20) -> list[dict]:
    dataset_path = settings.processed_dir / "electricity_price_monthly.csv"
    if not dataset_path.exists():
        raise HTTPException(status_code=404, detail="数据集不存在，请先调用 /pipeline/run。")

    import pandas as pd

    df = pd.read_csv(dataset_path).head(limit)
    return df.to_dict(orient="records")


def _reading_diff_csv_path() -> Path:
    cand = settings.processed_dir / "2025年1-12月电费核查联_有功示数.csv"
    if cand.exists():
        return cand
    for p in settings.processed_dir.glob("*有功示数*.csv"):
        return p
    raise FileNotFoundError("未找到有功示数差 CSV，请先运行 scripts/parse_active_readings.py")


@app.get("/reading-diff/dataset")
def reading_diff_dataset() -> list[dict]:
    path = _reading_diff_csv_path()
    import pandas as pd
    df = pd.read_csv(path).head(50)
    return df.to_dict(orient="records")


@app.post("/reading-diff/train")
def train_reading_diff() -> dict:
    path = _reading_diff_csv_path()
    try:
        return ReadingDiffPredictor().train(path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/reading-diff/predict")
def predict_reading_diff(months: int = 3) -> dict:
    path = _reading_diff_csv_path()
    try:
        preds = ReadingDiffPredictor().predict(path, months)
        return {"horizon_months": months, "predictions": preds}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/ui/reading-diff-overview")
def reading_diff_overview(months: int = 3) -> dict:
    try:
        path = _reading_diff_csv_path()
    except FileNotFoundError as e:
        return {
            "history": [],
            "predictions": [],
            "component_names": {
                "peak2_reading_diff": "尖峰",
                "peak_reading_diff": "峰",
                "flat_reading_diff": "平",
                "valley_reading_diff": "谷",
                "deep_valley_reading_diff": "深谷",
            },
            "status": "unavailable",
            "error": str(e),
        }

    import pandas as pd
    df = pd.read_csv(path)
    ts_col = "timestamp" if "timestamp" in df.columns else "日期"
    df["timestamp"] = pd.to_datetime(df[ts_col])
    df = df.sort_values("timestamp").reset_index(drop=True)

    comp_cols = [c for c in ["peak2_reading_diff", "peak_reading_diff", "flat_reading_diff", "valley_reading_diff", "deep_valley_reading_diff"] if c in df.columns]
    history = [
        {"timestamp": row["timestamp"].isoformat(), "components": {c: float(row[c]) for c in comp_cols if pd.notna(row.get(c))}}
        for _, row in df.iterrows()
    ]

    status = "ok"
    err = None
    predictions: list[dict] = []
    try:
        predictor = ReadingDiffPredictor()
        model_path = settings.model_dir / "reading_diff_model.pkl"
        if model_path.exists():
            predictions = predictor.predict(path, months)
        else:
            predictor.train(path)
            predictions = predictor.predict(path, months)
    except Exception as e:
        status = "degraded"
        err = str(e)

    return {
        "history": history,
        "predictions": predictions,
        "component_names": {"peak2_reading_diff": "尖峰", "peak_reading_diff": "峰", "flat_reading_diff": "平", "valley_reading_diff": "谷", "deep_valley_reading_diff": "深谷"},
        "status": status,
        "error": err,
    }


@app.get("/paths")
def app_paths() -> dict[str, str]:
    return {
        "project_root": str(settings.project_root),
        "pdf_path": str(settings.pdf_path),
        "processed_dir": str(settings.processed_dir),
        "model_dir": str(settings.model_dir),
    }


@app.get("/pipeline/report")
def pipeline_report() -> dict:
    report_path = settings.processed_dir / "pipeline_report.json"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="解析报告不存在，请先调用 /pipeline/run。")
    return json.loads(report_path.read_text(encoding="utf-8"))


@app.get("/active-components/dataset")
def active_components_dataset() -> list[dict]:
    path = settings.processed_dir / "active_components_monthly.csv"
    if not path.exists():
        raise HTTPException(status_code=404, detail="有功各部分数据集不存在，请先运行 /pipeline/run。")
    import pandas as pd

    df = pd.read_csv(path).head(50)
    return df.to_dict(orient="records")


@app.post("/active-components/train")
def train_active_components() -> dict:
    path = settings.processed_dir / "active_components_monthly.csv"
    if not path.exists():
        raise HTTPException(status_code=404, detail="有功各部分数据集不存在，请先运行 /pipeline/run。")
    try:
        result = ActiveComponentPredictor().train(path)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/active-components/predict")
def predict_active_components(months: int = 3) -> dict:
    path = settings.processed_dir / "active_components_monthly.csv"
    if not path.exists():
        raise HTTPException(status_code=404, detail="有功各部分数据集不存在，请先运行 /pipeline/run。")
    try:
        preds = ActiveComponentPredictor().predict(path, months)
        return {"horizon_months": months, "predictions": preds}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/ui/itemized-predictions")
def itemized_predictions(months: int = 3) -> dict:
    dataset_path = settings.processed_dir / "electricity_price_monthly.csv"
    if not dataset_path.exists():
        raise HTTPException(status_code=404, detail="数据集不存在，请先调用 /pipeline/run。")
    try:
        return predict_with_reasons(dataset_path, months=months)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/workflow/run", response_model=WorkflowResponse)
def run_workflow(page_limit: int = 38, months: int = 3) -> WorkflowResponse:
    if not settings.pdf_path.exists():
        raise HTTPException(status_code=404, detail=f"未找到 PDF: {settings.pdf_path}")

    try:
        summary = PdfBillPipeline(pdf_path=settings.pdf_path, page_limit=page_limit).run()
        ds = settings.processed_dir / "electricity_price_monthly.csv"
        train_result = PriceModelService().train(ds)
        ConsumptionModelService().train(ds)
        ac_path = settings.processed_dir / "active_components_monthly.csv"
        if ac_path.exists():
            try:
                ActiveComponentPredictor().train(ac_path)
            except Exception:
                pass
        pred_df = PriceModelService().predict(ds, months=months)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    pipeline_resp = PipelineRunResponse(
        pdf_path=str(settings.pdf_path),
        parse_mode=summary.parse_mode,
        pages=summary.pages,
        extracted_records=summary.extracted_records,
        dataset_path=str(summary.dataset_path),
        report_path=str(summary.report_path),
        message="PDF 解析完成并已生成结构化数据集。",
    )
    train_resp = TrainResponse(
        model_path=str(train_result.model_path),
        metrics_path=str(train_result.metrics_path),
        train_rows=train_result.train_rows,
        test_rows=train_result.test_rows,
        mae=train_result.mae,
        rmse=train_result.rmse,
        mape=train_result.mape,
    )
    predict_resp = PredictResponse(
        model_path=str(settings.model_dir / "price_model.pkl"),
        horizon_months=months,
        predictions=[
            PredictPoint(timestamp=row["timestamp"], predicted_price=row["predicted_price"])
            for _, row in pred_df.iterrows()
        ],
    )
    return WorkflowResponse(pipeline=pipeline_resp, train=train_resp, predict=predict_resp)


@app.get("/ui/price-overview")
def price_overview(months: int = 3) -> dict:
    """无电价 CSV 时仍返回 200，避免前端联调 404；示数差页可独立使用。"""
    import pandas as pd

    dataset_path = settings.processed_dir / "electricity_price_monthly.csv"
    if not dataset_path.exists() or not dataset_path.stat().st_size:
        return {
            "realtime": None,
            "next_prediction": None,
            "history": [],
            "forecast": [],
            "itemized": None,
            "prediction_status": "unavailable",
            "prediction_error": "尚未生成 electricity_price_monthly.csv，可先运行 /pipeline/run 或仅使用有功示数差数据。",
        }

    df = pd.read_csv(dataset_path)
    if df.empty:
        return {
            "realtime": None,
            "next_prediction": None,
            "history": [],
            "forecast": [],
            "itemized": None,
            "prediction_status": "unavailable",
            "prediction_error": "月度数据集为空。",
        }

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["total_kwh"] = pd.to_numeric(df["total_kwh"], errors="coerce")
    # 看板以用电量为主：仅保留同时具有时间与用电量的行
    df = df.dropna(subset=["timestamp", "total_kwh"]).sort_values("timestamp").reset_index(drop=True)
    if df.empty:
        return {
            "realtime": None,
            "next_prediction": None,
            "history": [],
            "forecast": [],
            "itemized": None,
            "prediction_status": "unavailable",
            "prediction_error": "无有效用电量行。",
        }

    last = df.iloc[-1]
    realtime = {
        "timestamp": last["timestamp"].isoformat(),
        "price": float(last["price"]) if pd.notna(last.get("price")) else None,
        "total_kwh": float(last["total_kwh"]) if pd.notna(last.get("total_kwh")) else None,
        "total_fee": float(last["total_fee"]) if "total_fee" in df.columns and pd.notna(last.get("total_fee")) else None,
    }

    prediction_status = "ok"
    prediction_error = None
    pred_points: list[dict] = []
    itemized: dict | None = None

    try:
        itemized = predict_with_reasons(dataset_path, months=months)
        pred_points = [
            {
                "timestamp": p["timestamp"],
                "price": next((x["prediction"] for x in p["items"] if x["item"] == "电价"), None),
                "total_kwh": next((x["prediction"] for x in p["items"] if x["item"] == "用电量"), None),
                "total_fee": next((x["prediction"] for x in p["items"] if x["item"] == "电费"), None),
                "items": p["items"],
            }
            for p in itemized["predictions"]
        ]
    except Exception as exc:
        prediction_status = "degraded"
        prediction_error = str(exc)

    history_points = [
        {
            "timestamp": row["timestamp"].isoformat(),
            "price": float(row["price"]) if pd.notna(row.get("price")) else None,
            "total_kwh": float(row["total_kwh"]) if pd.notna(row.get("total_kwh")) else None,
        }
        for _, row in df.iterrows()
    ]

    next_prediction = pred_points[0] if pred_points else None
    return {
        "realtime": realtime,
        "next_prediction": next_prediction,
        "history": history_points,
        "forecast": pred_points,
        "itemized": itemized,
        "prediction_status": prediction_status,
        "prediction_error": prediction_error,
    }


def _ensure_dirs() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.processed_dir.mkdir(parents=True, exist_ok=True)
    settings.model_dir.mkdir(parents=True, exist_ok=True)


@app.get("/{full_path:path}", include_in_schema=False)
def spa_client_routes(full_path: str) -> FileResponse:
    """React Router 等前端路由，返回 index.html。"""
    if _spa_path_is_api(full_path):
        raise HTTPException(status_code=404, detail="Not found")
    return _spa_index()


_ensure_dirs()

