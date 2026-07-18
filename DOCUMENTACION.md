# Documentación del BI — Cruce 1×10 × Habitable

Documento para el equipo colaborativo. Explica **qué se construyó**, **cómo funciona** y **cómo desplegarlo en Render**.

---

## 1. Contexto y objetivo

Tras los sismos en Venezuela, coexisten dos mundos de datos:

1. **Solicitudes 1×10** — la ciudadanía pide inspección de una edificación.
2. **Inspecciones Habitable** — equipos de campo ya evaluaron edificios (etiqueta verde / amarillo / rojo / negro).

Este BI **no reemplaza** el sistema Django de capacitación/inspecciones ERD de la Comisión. Es un **tablero de cruce operativo**: une ambas fuentes por cercanía geográfica y similitud de nombre, para priorizar pendientes y visualizar cobertura.

### Preguntas de negocio que responde

- ¿Cuántas solicitudes 1×10 ya tienen una inspección Habitable “cerca” y con nombre coherente?
- ¿Cuántas siguen pendientes (solo en 1×10)?
- ¿Cuáles son dudosas (cerca en mapa, nombre distinto) y hay que revisar a mano?
- ¿Dónde se concentran pendientes / daños (mapa y reportes Habitable)?

---

## 2. Arquitectura lógica

```
┌─────────────────┐     ┌──────────────────┐
│ Excel 1×10      │     │ Excel Habitable  │
└────────┬────────┘     └────────┬─────────┘
         │                       │
         ▼                       ▼
   prepare_solicitudes     prepare_habitable
         │                       │
         └──────────┬────────────┘
                    ▼
            match_solicitudes
            (BallTree + rapidfuzz)
                    ▼
            dedupe_solicitudes
            (unificar sitios ~20 m)
                    ▼
         data/processed/*.parquet
                    ▼
              Streamlit BI
         (mapa · 1×10 · Habitable)
```

### Componentes

| Pieza | Tecnología | Función |
|-------|------------|---------|
| UI | Streamlit | Pestañas, carga de archivos, KPIs |
| Mapa | Folium + FastMarkerCluster | Capas operativas |
| Gráficos | ECharts (streamlit-echarts) | Barras / donuts |
| Matching | scikit-learn BallTree + rapidfuzz | Vecino más cercano + nombre |
| Persistencia intermedia | Parquet (PyArrow) | Lectura rápida en el BI |
| Contenedor | Docker | Deploy en Render |

No hay base de datos propia en esta fase: el estado “oficial” del cruce son los parquet regenerados al procesar Excel.

---

## 3. Flujo de datos paso a paso

### 3.1 Carga (UI o `prepare_data.py`)

1. El usuario sube dos Excel (o, en desarrollo, se leen rutas de `config.toml`).
2. Archivos quedan en `data/uploads/`.
3. Se ejecuta `run_pipeline()` en `src/prepare_data.py`.

### 3.2 Limpieza geográfica (`geo_utils.py`)

- Repara lat/lng mal tipificados (coma decimal, dígitos pegados).
- Marca `mapeable` si el punto cae en el bounding box de Venezuela.
- Detecta **hotspot** Habitable (mismo pin usado por cientos de edificios distintos) → `alta_confianza = False`.
- Clasifica calidad (`mapa_ok`, costa, etc.).

### 3.3 Matching 1×10 ↔ Habitable

Para cada solicitud mapeable:

1. Buscar la inspección Habitable de **alta confianza** más cercana (haversine).
2. Si distancia > `radius_m` (50 m) → categoría `solo_1x10` (pendiente).
3. Si está dentro del radio, comparar nombres normalizados (`token_set_ratio`):
   - ≥ `name_score_high` → `coincide_alta`
   - ≥ `name_score_medium` (o ≤20 m y score ≥50) → `coincide_media`
   - ≥ `name_score_geo_min` → `coincide_geo_solo` (dudoso / por revisar)
   - &lt; `name_score_geo_min` → se trata como **pendiente** (vecino distinto)

**Coincidencias automáticas (ya atendidas)** = alta + media.

### 3.4 Deduplicación espacial 1×10

Varias personas pueden reportar el mismo edificio. Se agrupan puntos a `dedupe_radius_m` (20 m) y se guarda un representante con `n_reportes`.

### 3.5 Salida

- `data/processed/solicitudes.parquet`
- `data/processed/inspecciones.parquet`
- `data/processed/summary.json` (KPIs nacionales)

El BI lee esos archivos en cada sesión (con caché Streamlit).

---

## 4. Interfaz del tablero

### 4.1 Pestañas principales

1. **Mapa operativo** — capas Habitable, coincidencias, pendientes, dudosos; búsqueda; embudo; tabla por estado.
2. **Análisis 1×10** — demanda, % atendidas/pendientes, territorio, listados.
3. **Análisis Habitable** — semáforo y **tres secciones de reportes de daños**:
   - No estructurales
   - Estructurales moderados
   - Severos y externos  

   (Criterios alineados a la especificación de reportes de daños de la Comisión.)

### 4.2 Tema visual

- Navy institucional + acentos de bandera VE (cinta amarillo/azul/rojo y 8 estrellas blancas).
- Sidebar con panorama nacional y crédito del elaborador.

### 4.3 Carga colaborativa

Cualquier usuario autenticado puede subir nuevos Excel y regenerar el cruce; las tres pestañas se actualizan al terminar el pipeline.

---

## 5. Parámetros (`config.toml`)

| Clave | Default | Significado |
|-------|---------|-------------|
| `matching.radius_m` | 50 | Radio de búsqueda Habitable |
| `matching.name_score_high` | 85 | Umbral match alta |
| `matching.name_score_medium` | 70 | Umbral match media |
| `matching.name_score_geo_min` | 40 | Mínimo para “dudoso” |
| `matching.dedupe_radius_m` | 20 | Unificación de reportes 1×10 |
| `geo.hotspot_*` | pin Libertador | Exclusión de confianza |

---

## 6. Guía para colaboradores

### Convenciones

- Comentarios y documentación en **español**.
- Código Python con docstrings en módulos y funciones públicas.
- No commitear Excel, parquet ni `.streamlit/secrets.toml`.
- Cambios de reglas de matching: actualizar `config.toml` **y** esta documentación.

### Cómo probar un cambio

```bash
pip install -r requirements.txt
# Con datos ya procesados:
streamlit run app.py
# Regenerar desde uploads o rutas locales:
python src/prepare_data.py
```

### Archivos que casi siempre tocan juntos

- Nueva regla de match → `prepare_data.py` + `config.toml` + sección 3 de este doc.
- Nuevo gráfico 1×10 → `pages_analysis.py` + `charts_echarts.py`.
- Mapa → `map_robust.py` + llamada desde `app.py`.
- Estilos / pestañas → `ui_theme.py`.

---

## 7. Despliegue en Render

### 7.1 Crear el servicio

1. Dashboard Render → **New** → **Web Service**.
2. Conectar GitHub `angelucv/habitable`.
3. Runtime: **Docker** (detectará el `Dockerfile`).
4. Branch: `main`.
5. Crear servicio.

### 7.2 Variables de entorno recomendadas

| Variable | Uso |
|----------|-----|
| `BI_PASSWORD` | Contraseña para entrar al tablero |
| `PYTHONUNBUFFERED` | `1` (logs inmediatos) |
| `BI_LOW_MEMORY` | `1` = mapa con tope de marcadores (activo en Docker/Render) |
| `BI_MAP_MAX_MARKERS` | Tope por capa (default `900` en bajo consumo) |
| `BI_ALLOW_HEAVY_PIPELINE` | `1` = permite «Procesar cruce» en bajo consumo (riesgo OOM) |
| `MALLOC_ARENA_MAX` | `2` (reduce fragmentación de RAM en Linux) |

### 7.3 Memoria (alerta Render «exceeded its memory limit»)

El plan free (~512 MB) se reinicia si el mapa pinta decenas de miles de marcadores Folium o si se regenera el cruce desde Excel in-process.

Mitigaciones ya incluidas:

- Modo bajo consumo automático en Render.
- Por defecto: marcadores Habitable + coincidencias; **pendientes en heatmap**.
- Tope ~900 marcadores/capa (ajustable en Extras del mapa).
- Pipeline Excel bloqueado salvo `BI_ALLOW_HEAVY_PIPELINE=1`.

Si sigue fallando: subir el servicio a **Starter (1 GB)** o filtrar territorio antes de abrir el mapa nacional con todas las capas de marcadores.

### 7.4 Disco persistente (importante)

En el plan free de Render el sistema de archivos puede **reiniciarse**. Los Excel/parquet subidos se pierden al redeploy si no hay disco.

Opciones:

- **Render Disk** montado en `/app/data` (recomendado en producción real).
- O volver a subir Excel tras cada deploy (aceptable en piloto).
- En free: procesar el cruce **en local** y desplegar los parquet ya generados (el botón de procesar está bloqueado en bajo consumo).

### 7.5 Primera visita en producción

1. Abrir la URL de Render.
2. Introducir la contraseña (`BI_PASSWORD`).
3. El tablero **ya muestra el cruce precargado** (parquet en `data/processed/`).
4. Para sustituirlo: expander **Actualizar datos** → subir Excel → **Sustituir cruce**.

Los Excel crudos no van en Git. Solo el resultado procesado (sin columnas de texto libre sensibles como observaciones).

### 7.6 Comando equivalente local al contenedor

```bash
docker build -t bi-habitable .
docker run -p 10000:10000 -e BI_PASSWORD=demo -e BI_LOW_MEMORY=0 bi-habitable
```

---

## 8. Seguridad y datos personales

Los Excel 1×10 pueden incluir **cédula y teléfono**. Por eso:

- Autenticación obligatoria en producción.
- No versionar archivos Excel fuente.
- El seed en Git es el **resultado del cruce** (direcciones/coords), no los Excel crudos.
- En el futuro: anonimizar columnas sensibles o migrar a un backend con roles (p. ej. módulo en el Django CPEH).

---

## 9. Roadmap sugerido (sin implementar aún)

1. Disco persistente en Render + backup de parquet (las cargas UI se pierden al redeploy sin disco).
2. Auth por usuario (no solo contraseña compartida).
3. Export CSV de pendientes para cuadrillas.
4. Si surge gestión de casos (estados, asignación): extender el **Django de la Comisión**, no un segundo Django paralelo; el BI pasaría a leer BD.

---

## 10. Contacto

Elaborado por: **angelc.cvea@gmail.com**  
Producto: BI Cruce Inspecciones — Habitable × 1×10.
