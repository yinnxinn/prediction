# 阶段一：构建 React（Vite）静态资源
FROM node:20-alpine AS frontend
WORKDIR /build
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# 阶段二：Python 运行时
FROM python:3.12-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120

# 国内构建可传：--build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_INDEX_URL=https://pypi.org/simple

COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir \
      --retries 15 \
      --timeout 120 \
      -i "${PIP_INDEX_URL}" \
      -r requirements.txt

COPY . .
COPY --from=frontend /build/dist ./web/dist

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
