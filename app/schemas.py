from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PipelineRunResponse(BaseModel):
    pdf_path: str
    parse_mode: str
    pages: int
    extracted_records: int
    dataset_path: str
    report_path: str
    message: str


class TrainResponse(BaseModel):
    model_path: str
    metrics_path: str
    train_rows: int
    test_rows: int
    mae: float
    rmse: float
    mape: Optional[float]


class PredictRequest(BaseModel):
    months: int = Field(default=3, ge=1, le=12)


class PredictPoint(BaseModel):
    timestamp: datetime
    predicted_price: float


class PredictResponse(BaseModel):
    model_path: str
    horizon_months: int
    predictions: list[PredictPoint]


class WorkflowResponse(BaseModel):
    pipeline: PipelineRunResponse
    train: TrainResponse
    predict: PredictResponse

