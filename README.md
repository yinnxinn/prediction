# prediction

# 电价预测后端（初步版）

该项目实现了一条完整后端链路：

1. 从 `docs/2025年1-12月电费核查联.pdf` 渲染每页为图片
2. 调用大模型视觉 API 从图片中抽取有功各部分（尖峰/峰/平/谷/深谷）
3. 按月份聚合，生成 `active_components_monthly.csv`、`electricity_price_monthly.csv`
4. 训练时序回归模型并预测未来用电量等（Web 功能页仅展示用电量预测，不展示电价）

## 1. 环境准备

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 大模型 API 配置

在项目根目录复制 `.env.example` 为 `.env`。

**Azure OpenAI：**

```env
LLM_API_KEY=your-azure-api-key
AZURE_ENDPOINT=https://your-resource.openai.azure.com/
LLM_MODEL=gpt-4o   # Azure 中的部署名称
```

**OpenAI 或兼容端点：**

```env
LLM_API_KEY=sk-xxx
# LLM_BASE_URL=    # 可选
# LLM_MODEL=gpt-4o
```

## 2. 启动服务

```bash
uvicorn app.main:app --reload --port 8001
```

Swagger 文档：`http://127.0.0.1:8001/docs`

### 前端（Vite + React，MAS 落地页 + 有功示数差功能页）

开发（热更新，API 经 Vite 代理到 **8001**，与 `uvicorn --port 8001` 一致；可复制 `web/.env.example` 为 `web/.env` 调整 `VITE_PROXY_TARGET`）：

```bash
cd web
npm install
npm run dev
```

浏览器打开 `http://127.0.0.1:5173`：落地页说明多 Agent 流程；`/studio` 为功能页。

若后端改端口，可在 `web/.env` 中设置 `VITE_PROXY_TARGET`，或在启动前执行：`set VITE_PROXY_TARGET=http://127.0.0.1:8080`（Windows）后再 `npm run dev`。

生产：在 `web` 目录执行 `npm run build` 后，静态资源输出到 `web/dist`。启动 FastAPI 后访问 `http://127.0.0.1:8001/` 即加载 React 构建产物（若已构建）；未构建时回退到 `templates/index.html`（若存在）。

### Docker 一键部署

前置：安装 Docker Desktop 或 Docker Engine + Compose。项目根目录执行：

- **Windows**：`.\deploy.ps1`（若提示执行策略，可用 `powershell -ExecutionPolicy Bypass -File .\deploy.ps1`）
- **Linux / macOS**：`chmod +x deploy.sh && ./deploy.sh`（或 `make deploy`）

脚本会在缺少 `.env` 时从 `.env.example` 复制一份；镜像内会执行 `web` 的 `npm run build`，与 FastAPI 同端口 **8001** 提供页面与 API。`data/`、`models/`、`docs/` 通过卷挂载，便于持久化与替换 PDF。停止：`docker compose down`；查看日志：`docker compose logs -f app` 或 `make logs`。

## 3. 推荐调用顺序

### 3.1 运行 PDF 解析管道

`POST /pipeline/run?page_limit=38`

流程：PDF → 每页渲染为图片 → 大模型视觉抽取 → 按月聚合。

产物：
- `data/processed/active_components_monthly.csv`（有功各部分：尖峰/峰/平/谷/深谷）
- `data/processed/electricity_price_monthly.csv`（派生自有功数据）
- `data/processed/pipeline_report.json`

### 3.2 训练模型

`POST /train`

产物：
- `models/price_model.pkl`
- `models/train_metrics.json`

### 3.3 预测未来电价（`/predict`，前端主站不展示电价）

`POST /predict`

请求体示例：

```json
{
  "months": 3
}
```

## 4. 有功各部分预测（尖峰/峰/平/谷/深谷）

- `GET /active-components/dataset`：查看抽取的有功各部分数据集
- `POST /active-components/train`：训练有功各部分预测模型
- `POST /active-components/predict?months=3`：预测未来 N 月各时段用电量及理由

## 5. 常用接口

- `GET /health`：健康检查
- `POST /pipeline/run`：解析 PDF 生成数据集
- `GET /pipeline/report`：读取最近一次解析报告
- `GET /dataset/preview`：预览已生成数据集
- `POST /predict`：未来 N 月预测
- `POST /workflow/run`：一键执行解析 + 训练 + 预测
- `GET /ui/price-overview`：看板聚合数据（实时+预测；React 页仅展示用电量）
- `GET /paths`：查看当前路径配置

## 6. 当前实现说明

- 数据源固定使用 `docs/2025年1-12月电费核查联.pdf`。
- 解析采用「PDF → 图片 → 大模型视觉抽取」方案，不依赖 OCR 正则，适应表格版面变化。
- 需在 `.env` 中配置 `LLM_API_KEY` 方可运行 `/pipeline/run`。

