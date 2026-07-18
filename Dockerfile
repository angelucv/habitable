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
# Reduce fragmentación de arenas de malloc (ayuda en instancias ~512 MB)
ENV MALLOC_ARENA_MAX=2
# Tope de marcadores por capa en el mapa (override con BI_MAP_MAX_MARKERS)
ENV BI_LOW_MEMORY=1
ENV BI_MAP_MAX_MARKERS=900
EXPOSE 10000

# Arranque: puerto dinámico de Render + headless
CMD streamlit run app.py \
    --server.port=${PORT:-10000} \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.maxUploadSize=50 \
    --browser.gatherUsageStats=false
