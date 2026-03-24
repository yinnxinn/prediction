from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

from app.config import settings


@dataclass
class TrainResult:
    model_path: Path
    metrics_path: Path
    train_rows: int
    test_rows: int
    mae: float
    rmse: float
    mape: float | None


def _safe_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


class PriceModelService:
    feature_cols = ["lag_1", "lag_2", "lag_3", "rolling_mean_3", "month", "quarter"]

    def __init__(self) -> None:
        settings.model_dir.mkdir(parents=True, exist_ok=True)
        settings.processed_dir.mkdir(parents=True, exist_ok=True)

    def train(self, dataset_path: Path) -> TrainResult:
        df = pd.read_csv(dataset_path)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        feat_df = self._build_features(df)

        if len(feat_df) < settings.min_train_rows:
            raise ValueError(
                f"可训练样本不足。当前 {len(feat_df)} 条，至少需要 {settings.min_train_rows} 条。"
            )

        split = max(int(len(feat_df) * 0.8), len(feat_df) - 2)
        train_df = feat_df.iloc[:split].copy()
        test_df = feat_df.iloc[split:].copy()

        x_train = train_df[self.feature_cols]
        y_train = train_df["price"]
        x_test = test_df[self.feature_cols]
        y_test = test_df["price"]

        model = RandomForestRegressor(
            n_estimators=300,
            max_depth=6,
            random_state=42,
            min_samples_leaf=2,
        )
        model.fit(x_train, y_train)
        pred = model.predict(x_test)

        mae = float(mean_absolute_error(y_test, pred))
        rmse = float(np.sqrt(mean_squared_error(y_test, pred)))
        mape = (
            float(np.mean(np.abs((y_test - pred) / y_test)))
            if (y_test != 0).all()
            else None
        )

        model_payload = {
            "model": model,
            "feature_cols": self.feature_cols,
            "trained_at": datetime.utcnow().isoformat(),
        }
        model_path = settings.model_dir / "price_model.pkl"
        with model_path.open("wb") as f:
            pickle.dump(model_payload, f)

        metrics = {
            "mae": mae,
            "rmse": rmse,
            "mape": mape,
            "train_rows": int(len(train_df)),
            "test_rows": int(len(test_df)),
            "dataset_path": str(dataset_path),
            "trained_at": datetime.utcnow().isoformat(),
        }
        metrics_path = settings.model_dir / "train_metrics.json"
        metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

        return TrainResult(
            model_path=model_path,
            metrics_path=metrics_path,
            train_rows=len(train_df),
            test_rows=len(test_df),
            mae=mae,
            rmse=rmse,
            mape=mape,
        )

    def predict(self, dataset_path: Path, months: int) -> pd.DataFrame:
        model_path = settings.model_dir / "price_model.pkl"
        if not model_path.exists():
            raise FileNotFoundError("模型不存在，请先调用 /train 训练模型。")

        with model_path.open("rb") as f:
            payload = pickle.load(f)

        model = payload["model"]
        df = pd.read_csv(dataset_path)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)

        history = df[["timestamp", "price"]].copy()
        preds: list[dict[str, float | datetime]] = []

        for _ in range(months):
            next_ts = (history["timestamp"].max() + pd.offsets.MonthBegin(1)).to_pydatetime()
            feat_row = self._build_next_feature_row(history, next_ts)
            y_hat = float(model.predict(pd.DataFrame([feat_row], columns=self.feature_cols))[0])

            preds.append({"timestamp": next_ts, "predicted_price": y_hat})
            history = pd.concat(
                [
                    history,
                    pd.DataFrame([{"timestamp": next_ts, "price": y_hat}]),
                ],
                ignore_index=True,
            )

        return pd.DataFrame(preds)

    def _build_features(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out = out.sort_values("timestamp").reset_index(drop=True)
        out["price"] = pd.to_numeric(out["price"], errors="coerce")
        out["lag_1"] = out["price"].shift(1)
        out["lag_2"] = out["price"].shift(2)
        out["lag_3"] = out["price"].shift(3)
        out["rolling_mean_3"] = out["price"].rolling(window=3).mean().shift(1)
        out["month"] = out["timestamp"].dt.month
        out["quarter"] = out["timestamp"].dt.quarter
        out = out.dropna(subset=["price", *self.feature_cols]).reset_index(drop=True)
        return out

    def _build_next_feature_row(self, history: pd.DataFrame, next_ts: datetime) -> dict[str, float | int]:
        prices = history["price"].tolist()
        if len(prices) < 3:
            raise ValueError("历史数据不足 3 条，无法预测下一期。")
        return {
            "lag_1": float(prices[-1]),
            "lag_2": float(prices[-2]),
            "lag_3": float(prices[-3]),
            "rolling_mean_3": float(np.mean(prices[-3:])),
            "month": int(next_ts.month),
            "quarter": int((next_ts.month - 1) // 3 + 1),
        }


# --- 用电量预测 ---
KWH_FEATURE_COLS = ["lag_1", "lag_2", "lag_3", "rolling_mean_3", "month", "quarter"]
KWH_MIN, KWH_MAX = 1000.0, 500000.0  # 合理用电量区间（kWh）


class ConsumptionModelService:
    feature_cols = KWH_FEATURE_COLS

    def __init__(self) -> None:
        settings.model_dir.mkdir(parents=True, exist_ok=True)
        settings.processed_dir.mkdir(parents=True, exist_ok=True)

    def train(self, dataset_path: Path) -> TrainResult:
        df = pd.read_csv(dataset_path)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["total_kwh"] = _safe_numeric(df["total_kwh"])
        df = df.dropna(subset=["timestamp", "total_kwh"]).sort_values("timestamp").reset_index(drop=True)
        valid = (df["total_kwh"] >= KWH_MIN) & (df["total_kwh"] <= KWH_MAX)
        if valid.sum() < 4:
            df["total_kwh"] = df["total_kwh"].clip(lower=KWH_MIN, upper=KWH_MAX)
        else:
            df = df[valid].copy()
        df["total_kwh"] = df["total_kwh"].interpolate(limit_direction="both")
        feat_df = self._build_features(df)

        min_rows = max(4, settings.min_train_rows - 2)
        if len(feat_df) < min_rows:
            raise ValueError(
                f"用电量可训练样本不足。当前 {len(feat_df)} 条，至少需要 {min_rows} 条。"
            )

        split = max(int(len(feat_df) * 0.8), len(feat_df) - 2)
        train_df = feat_df.iloc[:split].copy()
        test_df = feat_df.iloc[split:].copy()

        x_train = train_df[self.feature_cols]
        y_train = train_df["total_kwh"]
        x_test = test_df[self.feature_cols]
        y_test = test_df["total_kwh"]

        model = RandomForestRegressor(
            n_estimators=300,
            max_depth=6,
            random_state=42,
            min_samples_leaf=2,
        )
        model.fit(x_train, y_train)
        pred = model.predict(x_test)

        mae = float(mean_absolute_error(y_test, pred))
        rmse = float(np.sqrt(mean_squared_error(y_test, pred)))
        mape = (
            float(np.mean(np.abs((y_test - pred) / y_test)))
            if (y_test != 0).all()
            else None
        )

        payload = {
            "model": model,
            "feature_cols": self.feature_cols,
            "trained_at": datetime.utcnow().isoformat(),
        }
        model_path = settings.model_dir / "consumption_model.pkl"
        with model_path.open("wb") as f:
            pickle.dump(payload, f)

        metrics = {
            "mae": mae,
            "rmse": rmse,
            "mape": mape,
            "train_rows": int(len(train_df)),
            "test_rows": int(len(test_df)),
            "dataset_path": str(dataset_path),
            "trained_at": datetime.utcnow().isoformat(),
        }
        metrics_path = settings.model_dir / "consumption_train_metrics.json"
        metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

        return TrainResult(
            model_path=model_path,
            metrics_path=metrics_path,
            train_rows=len(train_df),
            test_rows=len(test_df),
            mae=mae,
            rmse=rmse,
            mape=mape,
        )

    def predict(self, dataset_path: Path, months: int) -> pd.DataFrame:
        model_path = settings.model_dir / "consumption_model.pkl"
        if not model_path.exists():
            raise FileNotFoundError("用电量模型不存在，请先调用训练。")

        with model_path.open("rb") as f:
            payload = pickle.load(f)

        model = payload["model"]
        df = pd.read_csv(dataset_path)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["total_kwh"] = _safe_numeric(df["total_kwh"])
        df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
        df["total_kwh"] = df["total_kwh"].ffill().bfill()
        valid_kwh = df["total_kwh"][(df["total_kwh"] >= KWH_MIN) & (df["total_kwh"] <= KWH_MAX)]
        if valid_kwh.empty:
            df["total_kwh"] = df["total_kwh"].clip(lower=KWH_MIN, upper=KWH_MAX)
        else:
            df.loc[~df["total_kwh"].between(KWH_MIN, KWH_MAX), "total_kwh"] = valid_kwh.median()

        history = df[["timestamp", "total_kwh"]].copy()
        preds: list[dict[str, Any]] = []

        for _ in range(months):
            next_ts = (history["timestamp"].max() + pd.offsets.MonthBegin(1)).to_pydatetime()
            feat_row = self._build_next_feature_row(history, next_ts)
            y_hat = float(model.predict(pd.DataFrame([feat_row], columns=self.feature_cols))[0])
            y_hat = max(KWH_MIN, min(KWH_MAX, y_hat))

            preds.append({"timestamp": next_ts, "predicted_kwh": y_hat})
            history = pd.concat(
                [
                    history,
                    pd.DataFrame([{"timestamp": next_ts, "total_kwh": y_hat}]),
                ],
                ignore_index=True,
            )

        return pd.DataFrame(preds)

    def _build_features(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out = out.sort_values("timestamp").reset_index(drop=True)
        out["lag_1"] = out["total_kwh"].shift(1)
        out["lag_2"] = out["total_kwh"].shift(2)
        out["lag_3"] = out["total_kwh"].shift(3)
        out["rolling_mean_3"] = out["total_kwh"].rolling(window=3).mean().shift(1)
        out["month"] = out["timestamp"].dt.month
        out["quarter"] = out["timestamp"].dt.quarter
        out = out.dropna(subset=["total_kwh", *self.feature_cols]).reset_index(drop=True)
        return out

    def _build_next_feature_row(self, history: pd.DataFrame, next_ts: datetime) -> dict[str, float | int]:
        kwh = history["total_kwh"].tolist()
        if len(kwh) < 3:
            raise ValueError("历史用电量不足 3 条，无法预测下一期。")
        return {
            "lag_1": float(kwh[-1]),
            "lag_2": float(kwh[-2]),
            "lag_3": float(kwh[-3]),
            "rolling_mean_3": float(np.mean(kwh[-3:])),
            "month": int(next_ts.month),
            "quarter": int((next_ts.month - 1) // 3 + 1),
        }


# --- 带预测理由的统一预测 ---
REASON_TEMPLATES = {
    "price": {
        "lag_1": "上月电价 {value:.4f} 元/kWh，历史电价具有较强延续性",
        "lag_2": "前两月电价 {value:.4f} 元/kWh，参与趋势判断",
        "lag_3": "前三月电价 {value:.4f} 元/kWh，参与趋势判断",
        "rolling_mean_3": "近三月均价 {value:.4f} 元/kWh，反映近期水平",
        "month": "预测月份为 {value} 月，存在季节性因素",
        "quarter": "预测季度为第 {value} 季度，工商业用电存在季度规律",
    },
    "kwh": {
        "lag_1": "上月用电量 {value:,.0f} kWh，历史用电量具有延续性",
        "lag_2": "前两月用电量 {value:,.0f} kWh，参与趋势判断",
        "lag_3": "前三月用电量 {value:,.0f} kWh，参与趋势判断",
        "rolling_mean_3": "近三月均用电量 {value:,.0f} kWh，反映近期负荷水平",
        "month": "预测月份为 {value} 月，存在季节性用电规律",
        "quarter": "预测季度为第 {value} 季度，工商业负荷存在季度规律",
    },
}


def _get_feature_importance(model: Any, feature_cols: list[str]) -> dict[str, float]:
    if not hasattr(model, "feature_importances_"):
        return {c: 1.0 / len(feature_cols) for c in feature_cols}
    return dict(zip(feature_cols, map(float, model.feature_importances_)))


def predict_with_reasons(
    dataset_path: Path,
    months: int = 3,
) -> dict[str, Any]:
    df = pd.read_csv(dataset_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    price_svc = PriceModelService()
    kwh_svc = ConsumptionModelService()

    price_model_path = settings.model_dir / "price_model.pkl"
    kwh_model_path = settings.model_dir / "consumption_model.pkl"

    if not price_model_path.exists():
        price_svc.train(dataset_path)
    if not kwh_model_path.exists():
        kwh_svc.train(dataset_path)

    price_pred = price_svc.predict(dataset_path, months)
    kwh_pred = kwh_svc.predict(dataset_path, months)

    with price_model_path.open("rb") as f:
        price_payload = pickle.load(f)
    with kwh_model_path.open("rb") as f:
        kwh_payload = pickle.load(f)

    price_imp = _get_feature_importance(price_payload["model"], price_svc.feature_cols)
    kwh_imp = _get_feature_importance(kwh_payload["model"], kwh_svc.feature_cols)

    price_df = df[["timestamp", "price"]].copy()
    price_df["price"] = _safe_numeric(price_df["price"])
    price_df = price_df.dropna(subset=["price"]).sort_values("timestamp").reset_index(drop=True)

    kwh_df = df[["timestamp", "total_kwh"]].copy()
    kwh_df["total_kwh"] = _safe_numeric(kwh_df["total_kwh"])
    kwh_df = kwh_df.dropna(subset=["total_kwh"]).sort_values("timestamp").reset_index(drop=True)
    valid = (kwh_df["total_kwh"] >= KWH_MIN) & (kwh_df["total_kwh"] <= KWH_MAX)
    if valid.sum() < 2:
        kwh_df["total_kwh"] = kwh_df["total_kwh"].clip(lower=KWH_MIN, upper=KWH_MAX)
    else:
        kwh_df = kwh_df[valid].copy()
    kwh_df["total_kwh"] = kwh_df["total_kwh"].interpolate(limit_direction="both")

    items: list[dict[str, Any]] = []
    for i in range(months):
        ts = price_pred.iloc[i]["timestamp"]
        price_val = float(price_pred.iloc[i]["predicted_price"])
        kwh_val = float(kwh_pred.iloc[i]["predicted_kwh"])
        fee_val = price_val * kwh_val

        price_hist = pd.concat([
            price_df,
            pd.DataFrame([
                {"timestamp": price_pred.iloc[j]["timestamp"], "price": price_pred.iloc[j]["predicted_price"]}
                for j in range(i)
            ]),
        ], ignore_index=True).sort_values("timestamp").reset_index(drop=True)
        kwh_hist = pd.concat([
            kwh_df,
            pd.DataFrame([
                {"timestamp": kwh_pred.iloc[j]["timestamp"], "total_kwh": kwh_pred.iloc[j]["predicted_kwh"]}
                for j in range(i)
            ]),
        ], ignore_index=True).sort_values("timestamp").reset_index(drop=True)

        price_feat = price_svc._build_next_feature_row(price_hist, ts)
        kwh_feat = kwh_svc._build_next_feature_row(kwh_hist, ts)

        price_reasons = [
            {
                "factor": col,
                "value": price_feat[col],
                "importance": round(price_imp.get(col, 0), 3),
                "description": REASON_TEMPLATES["price"][col].format(value=price_feat[col]),
            }
            for col in price_svc.feature_cols
        ]
        price_reasons.sort(key=lambda x: -x["importance"])

        kwh_reasons = [
            {
                "factor": col,
                "value": kwh_feat[col],
                "importance": round(kwh_imp.get(col, 0), 3),
                "description": REASON_TEMPLATES["kwh"][col].format(value=kwh_feat[col]),
            }
            for col in kwh_svc.feature_cols
        ]
        kwh_reasons.sort(key=lambda x: -x["importance"])

        # 每项预测的简要依据（取重要性最高的 1–2 条）
        kwh_summary = kwh_reasons[0]["description"] if kwh_reasons else ""
        price_summary = price_reasons[0]["description"] if price_reasons else ""
        fee_summary = f"电费 = 用电量 × 电价 = {kwh_val:,.0f} kWh × {price_val:.4f} 元/kWh ≈ {fee_val:,.2f} 元"

        items.append({
            "timestamp": ts.isoformat(),
            "items": [
                {
                    "item": "用电量",
                    "unit": "kWh",
                    "prediction": round(kwh_val, 2),
                    "summary": kwh_summary,
                    "reasons": kwh_reasons,
                },
                {
                    "item": "电价",
                    "unit": "元/kWh",
                    "prediction": round(price_val, 4),
                    "summary": price_summary,
                    "reasons": price_reasons,
                },
                {
                    "item": "电费",
                    "unit": "元",
                    "prediction": round(fee_val, 2),
                    "summary": fee_summary,
                    "reasons": [
                        {
                            "factor": "用电量 × 电价",
                            "value": f"{kwh_val:,.0f} × {price_val:.4f}",
                            "importance": 1.0,
                            "description": f"电费 = 用电量 × 电价 = {kwh_val:,.0f} kWh × {price_val:.4f} 元/kWh ≈ {fee_val:,.2f} 元",
                        }
                    ],
                },
            ],
        })

    return {"horizon_months": months, "predictions": items}


# --- 有功各部分预测 ---
ACTIVE_COMPS = ["peak2_kwh", "peak_kwh", "flat_kwh", "valley_kwh", "deep_valley_kwh"]
ACTIVE_NAMES = {"peak2_kwh": "尖峰", "peak_kwh": "峰", "flat_kwh": "平", "valley_kwh": "谷", "deep_valley_kwh": "深谷"}

# --- 有功示数差预测 ---
READING_DIFF_COLS = ["peak2_reading_diff", "peak_reading_diff", "flat_reading_diff", "valley_reading_diff", "deep_valley_reading_diff"]
READING_DIFF_NAMES = {"peak2_reading_diff": "尖峰", "peak_reading_diff": "峰", "flat_reading_diff": "平", "valley_reading_diff": "谷", "deep_valley_reading_diff": "深谷"}
FEAT_COLS = ["lag_1", "lag_2", "rolling_mean_3", "month", "quarter"]


class ActiveComponentPredictor:
    """有功各部分（尖峰/峰/平/谷/深谷）用电量预测"""

    def __init__(self) -> None:
        settings.model_dir.mkdir(parents=True, exist_ok=True)
        settings.processed_dir.mkdir(parents=True, exist_ok=True)

    def train(self, dataset_path: Path) -> dict[str, Any]:
        df = pd.read_csv(dataset_path)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)
        avail = [c for c in ACTIVE_COMPS if c in df.columns and df[c].notna().sum() >= 3]
        if not avail:
            raise ValueError("有功各时段数据不足，至少需要一列有≥3条有效记录。")

        models: dict[str, Any] = {}
        metrics: dict[str, Any] = {}
        for col in avail:
            feat_df = self._build_features(df, col)
            if len(feat_df) < 3:
                continue
            split = max(int(len(feat_df) * 0.8), len(feat_df) - 2)
            train_df, test_df = feat_df.iloc[:split], feat_df.iloc[split:]
            x_tr, y_tr = train_df[FEAT_COLS], train_df[col]
            x_te, y_te = test_df[FEAT_COLS], test_df[col]
            model = RandomForestRegressor(n_estimators=200, max_depth=5, random_state=42)
            model.fit(x_tr, y_tr)
            pred = model.predict(x_te)
            mae = float(mean_absolute_error(y_te, pred))
            rmse = float(np.sqrt(mean_squared_error(y_te, pred)))
            metrics[col] = (mae, rmse)
            models[col] = model

        payload = {"models": models, "trained_at": datetime.utcnow().isoformat()}
        path = settings.model_dir / "active_components_model.pkl"
        with path.open("wb") as f:
            pickle.dump(payload, f)
        mpath = settings.model_dir / "active_components_metrics.json"
        mpath.write_text(
            json.dumps(
                {k: {"mae": v[0], "rmse": v[1]} for k, v in metrics.items()},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"model_path": str(path), "metrics": metrics}

    def predict(self, dataset_path: Path, months: int) -> list[dict[str, Any]]:
        path = settings.model_dir / "active_components_model.pkl"
        if not path.exists():
            raise FileNotFoundError("有功各部分模型不存在，请先训练。")
        with path.open("rb") as f:
            payload = pickle.load(f)
        models = payload["models"]
        df = pd.read_csv(dataset_path)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)

        preds: list[dict[str, Any]] = []
        for _ in range(months):
            next_ts = (df["timestamp"].max() + pd.offsets.MonthBegin(1)).to_pydatetime()
            row: dict[str, Any] = {"timestamp": next_ts.isoformat(), "components": {}, "reasons": {}}
            for col, model in models.items():
                if col not in df.columns:
                    continue
                hist = df[["timestamp", col]].dropna(subset=[col])
                if len(hist) < 3:
                    continue
                feat = self._next_feature(hist, col, next_ts)
                y_hat = float(model.predict(pd.DataFrame([feat], columns=FEAT_COLS))[0])
                y_hat = max(0, y_hat)
                row["components"][col] = round(y_hat, 2)
                imp = dict(zip(FEAT_COLS, model.feature_importances_)) if hasattr(model, "feature_importances_") else {}
                top = sorted(imp.items(), key=lambda x: -x[1])[0] if imp else ("lag_1", 0.3)
                row["reasons"][col] = f"上月{ACTIVE_NAMES.get(col, col)}用电 {hist.iloc[-1][col]:,.0f} kWh，历史延续性高（特征{top[0]}权重{top[1]:.2f}）"
                df = pd.concat([df, pd.DataFrame([{"timestamp": next_ts, col: y_hat}])], ignore_index=True)
            preds.append(row)
        return preds

    def _build_features(self, df: pd.DataFrame, target_col: str) -> pd.DataFrame:
        out = df[["timestamp", target_col]].copy().dropna()
        out = out.sort_values("timestamp").reset_index(drop=True)
        out["lag_1"] = out[target_col].shift(1)
        out["lag_2"] = out[target_col].shift(2)
        out["rolling_mean_3"] = out[target_col].rolling(3, min_periods=1).mean().shift(1)
        out["month"] = out["timestamp"].dt.month
        out["quarter"] = out["timestamp"].dt.quarter
        return out.dropna(subset=FEAT_COLS + [target_col])

    def _next_feature(self, hist: pd.DataFrame, col: str, next_ts: datetime) -> dict[str, float | int]:
        v = hist[col].tolist()
        return {
            "lag_1": float(v[-1]),
            "lag_2": float(v[-2]) if len(v) >= 2 else float(v[-1]),
            "rolling_mean_3": float(np.mean(v[-3:])) if len(v) >= 1 else 0.0,
            "month": int(next_ts.month),
            "quarter": int((next_ts.month - 1) // 3 + 1),
        }


class ReadingDiffPredictor:
    """有功示数差（尖峰/峰/平/谷/深谷）分项预测"""

    def __init__(self) -> None:
        settings.model_dir.mkdir(parents=True, exist_ok=True)
        settings.processed_dir.mkdir(parents=True, exist_ok=True)
        self.model_key = "reading_diff"

    def train(self, dataset_path: Path) -> dict[str, Any]:
        df = pd.read_csv(dataset_path)
        ts_col = "timestamp" if "timestamp" in df.columns else "日期"
        df["timestamp"] = pd.to_datetime(df[ts_col])
        df = df.sort_values("timestamp").reset_index(drop=True)

        avail = [c for c in READING_DIFF_COLS if c in df.columns and df[c].notna().sum() >= 3]
        if not avail:
            raise ValueError("示数差数据不足，至少需要一列有≥3条有效记录。")

        models: dict[str, Any] = {}
        metrics: dict[str, Any] = {}
        for col in avail:
            feat_df = self._build_features(df, col)
            if len(feat_df) < 3:
                continue
            split = max(int(len(feat_df) * 0.8), len(feat_df) - 2)
            train_df, test_df = feat_df.iloc[:split], feat_df.iloc[split:]
            x_tr, y_tr = train_df[FEAT_COLS], train_df[col]
            x_te, y_te = test_df[FEAT_COLS], test_df[col]
            model = RandomForestRegressor(n_estimators=200, max_depth=5, random_state=42)
            model.fit(x_tr, y_tr)
            pred = model.predict(x_te)
            mae = float(mean_absolute_error(y_te, pred))
            rmse = float(np.sqrt(mean_squared_error(y_te, pred)))
            metrics[col] = {"mae": mae, "rmse": rmse}
            models[col] = model

        path = settings.model_dir / "reading_diff_model.pkl"
        with path.open("wb") as f:
            pickle.dump({"models": models, "trained_at": datetime.utcnow().isoformat()}, f)
        (settings.model_dir / "reading_diff_metrics.json").write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return {"model_path": str(path), "metrics": metrics}

    def predict(self, dataset_path: Path, months: int) -> list[dict[str, Any]]:
        path = settings.model_dir / "reading_diff_model.pkl"
        if not path.exists():
            raise FileNotFoundError("示数差模型不存在，请先训练。")
        with path.open("rb") as f:
            payload = pickle.load(f)
        models = payload["models"]
        df = pd.read_csv(dataset_path)
        ts_col = "timestamp" if "timestamp" in df.columns else "日期"
        df["timestamp"] = pd.to_datetime(df[ts_col])
        df = df.sort_values("timestamp").reset_index(drop=True)

        preds: list[dict[str, Any]] = []
        for _ in range(months):
            next_ts = (df["timestamp"].max() + pd.offsets.MonthBegin(1)).to_pydatetime()
            row: dict[str, Any] = {"timestamp": next_ts.isoformat(), "components": {}, "reasons": {}}
            for col, model in models.items():
                if col not in df.columns:
                    continue
                hist = df[["timestamp", col]].dropna(subset=[col])
                if len(hist) < 3:
                    continue
                feat = self._next_feature(hist, col, next_ts)
                y_hat = float(model.predict(pd.DataFrame([feat], columns=FEAT_COLS))[0])
                y_hat = max(0, y_hat)
                row["components"][col] = round(y_hat, 4)
                imp = dict(zip(FEAT_COLS, model.feature_importances_)) if hasattr(model, "feature_importances_") else {}
                top = sorted(imp.items(), key=lambda x: -x[1])[0] if imp else ("lag_1", 0.3)
                last_val = hist.iloc[-1][col]
                row["reasons"][col] = f"上月{READING_DIFF_NAMES.get(col, col)}示数差 {last_val:.4f}，历史延续性高（{top[0]}权重{top[1]:.2f}）"
                df = pd.concat([df, pd.DataFrame([{"timestamp": next_ts, col: y_hat}])], ignore_index=True)
            preds.append(row)
        return preds

    def _build_features(self, df: pd.DataFrame, target_col: str) -> pd.DataFrame:
        out = df[["timestamp", target_col]].copy().dropna()
        out = out.sort_values("timestamp").reset_index(drop=True)
        out["lag_1"] = out[target_col].shift(1)
        out["lag_2"] = out[target_col].shift(2)
        out["rolling_mean_3"] = out[target_col].rolling(3, min_periods=1).mean().shift(1)
        out["month"] = out["timestamp"].dt.month
        out["quarter"] = out["timestamp"].dt.quarter
        return out.dropna(subset=FEAT_COLS + [target_col])

    def _next_feature(self, hist: pd.DataFrame, col: str, next_ts: datetime) -> dict[str, float | int]:
        v = hist[col].tolist()
        return {
            "lag_1": float(v[-1]),
            "lag_2": float(v[-2]) if len(v) >= 2 else float(v[-1]),
            "rolling_mean_3": float(np.mean(v[-3:])) if len(v) >= 1 else 0.0,
            "month": int(next_ts.month),
            "quarter": int((next_ts.month - 1) // 3 + 1),
        }

