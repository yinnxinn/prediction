from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "Electricity Price Predictor"
    app_version: str = "0.1.0"

    project_root: Path = Path(__file__).resolve().parents[1]
    pdf_path: Path = project_root / "docs" / "2025年1-12月电费核查联.pdf"
    data_dir: Path = project_root / "data"
    processed_dir: Path = data_dir / "processed"
    model_dir: Path = project_root / "models"

    # Data quality settings
    min_valid_price: float = 0.05
    max_valid_price: float = 10.0

    # Modeling settings
    horizon_months: int = 3
    min_train_rows: int = 8

    # 大模型视觉 API（密钥请放在项目根目录 .env，勿提交）
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o"

    # Azure OpenAI 专用（配置后优先使用 Azure）
    azure_endpoint: str = ""
    azure_api_version: str = "2024-02-15-preview"  # 视觉模型需 2024-02-15 及以上

    pdf_image_dpi: int = 150
    pdf_page_limit: int = 38


settings = Settings()

