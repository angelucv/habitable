# Imagen base liviana con Python 3.11 (adecuado para Streamlit en Render)
FROM python:3.11-slim

# Directorio de trabajo dentro del contenedor
WORKDIR /app

# Dependencias del sistema mínimas (geo/compresión a veces las necesitan)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python primero (mejor cache de capas Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código de la aplicación
COPY . .

# Render inyecta la variable PORT; Streamlit debe escuchar en 0.0.0.0
ENV PYTHONUNBUFFERED=1
# Reduce fragmentación de arenas de malloc
ENV MALLOC_ARENA_MAX=2
# Plan con más RAM: mapa más completo; pipeline de reemplazo habilitado
ENV BI_LOW_MEMORY=0
ENV BI_MAP_MAX_MARKERS=5000
EXPOSE 10000

# Arranque: puerto dinámico de Render + headless
CMD streamlit run app.py \
    --server.port=${PORT:-10000} \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.maxUploadSize=80 \
    --browser.gatherUsageStats=false
