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
EXPOSE 10000

# Arranque: puerto dinámico de Render + headless
CMD streamlit run app.py \
    --server.port=${PORT:-10000} \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.gatherUsageStats=false
