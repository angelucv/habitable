# BI Cruce Habitable × 1×10

Tablero ejecutivo (Streamlit) para cruzar **solicitudes ciudadanas 1×10** con **inspecciones Habitable** tras los sismos en Venezuela.

Repositorio: [angelucv/habitable](https://github.com/angelucv/habitable)  
Destino de despliegue previsto: **Render** (Docker).

---

## Qué resuelve

| Fuente | Significado |
|--------|-------------|
| **1×10** | Pedidos de inspección hechos por la ciudadanía |
| **Habitable** | Inspecciones ya realizadas en campo (etiqueta semáforo) |

El BI responde: *¿qué solicitudes ya tienen inspección cercana?* y *¿qué queda pendiente?*

---

## Cómo empezar (local)

```bash
git clone https://github.com/angelucv/habitable.git
cd habitable
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1
# Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

1. Abre el navegador en la URL que indique Streamlit.
2. En **Cargar / actualizar archivos fuente**, sube el Excel 1×10 y el Excel Habitable.
3. Pulsa **Procesar cruce** (puede tardar 1–2 minutos).
4. Explora las tres pestañas: Mapa · Análisis 1×10 · Análisis Habitable.

Documentación amplia: **[DOCUMENTACION.md](DOCUMENTACION.md)**.

---

## Deploy en Render (resumen)

1. Conecta el repo `angelucv/habitable` en [Render](https://render.com).
2. Tipo: **Web Service** · Runtime: **Docker** (usa el `Dockerfile` del repo).
3. (Recomendado) Variable de entorno `BI_PASSWORD` = clave de acceso.
4. Deploy. Primera vez: entra, carga los dos Excel y procesa el cruce.

Detalle paso a paso: sección *Despliegue en Render* en `DOCUMENTACION.md`.

---

## Estructura del código (colaboradores)

| Ruta | Rol |
|------|-----|
| `app.py` | Entrada Streamlit: auth, pestañas, mapa |
| `src/prepare_data.py` | Pipeline: limpiar, matching, parquet |
| `src/data_ingest.py` | Carga de Excel desde la UI |
| `src/geo_utils.py` | Coordenadas, Venezuela, hotspot |
| `src/dedupe_1x10.py` | Unificar reportes del mismo sitio |
| `src/map_robust.py` | Mapa Folium multi-capa |
| `src/pages_analysis.py` | Análisis 1×10 y Habitable |
| `src/habitable_reports.py` | Criterios de reportes de daños |
| `src/ui_theme.py` | Tema ejecutivo + pestañas |
| `config.toml` | Radios y parámetros (sin secretos) |
| `Dockerfile` | Imagen para Render |

---

## Reglas de matching (por defecto)

- Radio geográfico: **50 m**
- Coincidencia automática: score nombre alta (≥85) o media (≥70, o ≤20 m y ≥50)
- Dudosos: cerca en mapa pero nombre solo medianamente parecido (≥40)
- Vecino con nombre muy distinto: se deja **pendiente**
- Unificación de reportes 1×10: **20 m**
- Hotspot Habitable (368 pines idénticos): excluido de alta confianza

Configurable en `config.toml`.

---

## Seguridad

- No subir Excel con cédulas/teléfonos a Git.
- Usar `BI_PASSWORD` o `.streamlit/secrets.toml` (ver ejemplo en el repo).
- `data/uploads` y `data/processed` están ignorados por `.gitignore`.

---

## Créditos

Elaborado por: angelc.cvea@gmail.com  
Contexto: Comisión Presidencial para la Evaluación de Habitabilidad (CPEH).
