# BI Cruce Inspecciones (CPEH)

Streamlit: cruce de solicitudes **1×10** con inspecciones **Habitable**.

## Remoto

- **GitHub (código):** https://github.com/angelucv/bi-cruce-inspecciones
- **Producción (Render):** repo hermano https://github.com/angelucv/habitable
- **Espejo Drive:** `MisProyectos-Espejo\D-CPEH\bi-cruce-inspecciones`

## Laptop — primera vez

```powershell
cd $env:USERPROFILE\Projects\clients\comision-presidencial-habitabilidad
git clone https://github.com/angelucv/bi-cruce-inspecciones.git
cd bi-cruce-inspecciones
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Ajustar config.toml con rutas locales a los Excel fuente
# Generar parquet: python src\prepare_data.py
streamlit run app.py
```

## Uso local

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

Abrir http://localhost:8501

## Notas

- Los parquet con datos de contacto **no** van en Git (`.gitignore`). Generarlos con `prepare_data.py` o copiarlos por Drive si hace falta.
- Matching: radio 50 m (`config.toml`).
- **Cifrado en reposo:** en ministerio/producción defina `BI_DATA_KEY` (Fernet).
  Genere y cifre datos locales con:
  ```powershell
  $env:BI_DATA_KEY = (python scripts\encrypt_data_at_rest.py --generate)
  python scripts\encrypt_data_at_rest.py
  ```
  Sin clave, en desarrollo los archivos pueden quedar en claro; con `BI_REQUIRE_AUTH=1` la clave es obligatoria.
