FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src \
    MODELS_DIR=/app/models

# libsndfile: leitura de áudio | libasound2/libssl3: Azure Speech SDK | libglib2.0-0: OpenCV
RUN apt-get update \
 && apt-get install -y --no-install-recommends libsndfile1 libasound2 libssl3 libglib2.0-0 ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# PyTorch somente-CPU (imagem bem menor que a build CUDA padrão)
RUN pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install -r requirements.txt

# Pesos YOLOv8 embutidos na imagem: sem download em tempo de execução
RUN mkdir -p /app/models && cd /app/models \
 && python -c "from ultralytics import YOLO; YOLO('yolov8n.pt'); YOLO('yolov8n-pose.pt')"

COPY src ./src
COPY app ./app
COPY .streamlit ./.streamlit

RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s \
  CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8501/_stcore/health')" || exit 1

CMD ["streamlit", "run", "app/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
