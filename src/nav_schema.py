"""Esquema de navegación del BI (secciones → pestañas en pantalla)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NavItem:
    id: str
    label: str
    blurb: str = ""


@dataclass(frozen=True)
class NavSection:
    id: str
    label: str
    blurb: str
    items: tuple[NavItem, ...]


NAV_SECTIONS: tuple[NavSection, ...] = (
    NavSection(
        id="fuentes",
        label="Información general por fuentes",
        blurb="Panorama de cada origen de datos por separado: volumen, calidad y tipología.",
        items=(
            NavItem(
                "fuentes_1x10",
                "Fuente 1×10",
                "Conteos de demanda ciudadana, cruce con Habitable, calidad GPS y territorio.",
            ),
            NavItem(
                "fuentes_hab",
                "Fuente Habitable",
                "Semáforo V/A/R/N, tipología de daños y corte por estado o municipio.",
            ),
        ),
    ),
    NavSection(
        id="mapa",
        label="Mapa operativo",
        blurb="Vista territorial del cruce espacial entre solicitudes 1×10 e inspecciones.",
        items=(
            NavItem(
                "mapa_vista",
                "Mapa y capas",
                "Capas del cruce, búsqueda de puntos y lectura operativa del territorio.",
            ),
        ),
    ),
    NavSection(
        id="x10",
        label="Análisis 1×10",
        blurb="De la calidad del Excel a la cola de casos aún sin inspección cercana.",
        items=(
            NavItem(
                "x10_depuracion",
                "Depuración",
                "Limpieza del archivo 1×10, duplicados y calidad de coordenadas.",
            ),
            NavItem(
                "x10_analisis",
                "Territorio y cruce",
                "Volumen por estado y parroquia, y porcentaje ya atendido vía cruce.",
            ),
            NavItem(
                "x10_cola",
                "Cola pendientes",
                "Casos sin cruce útil, priorizados para contacto o visita de campo.",
            ),
        ),
    ),
    NavSection(
        id="hab",
        label="Análisis Habitable",
        blurb="Resultado de las inspecciones de campo: semáforo y tipología de daños.",
        items=(
            NavItem(
                "hab_matriz",
                "Matriz semáforo",
                "Mezcla verde / amarillo / rojo / negro por territorio.",
            ),
            NavItem(
                "hab_ne",
                "No estructurales",
                "Daños no estructurales: foco operativo y volumen por zona.",
            ),
            NavItem(
                "hab_mod",
                "Estructurales moderados",
                "Bandas de daño estructural moderado para seguimiento.",
            ),
            NavItem(
                "hab_sev",
                "Severos y externos",
                "Daño severo y riesgo externo: prioridad de evacuación o refuerzo.",
            ),
            NavItem(
                "hab_explorar",
                "Explorar / reportería",
                "Análisis libre: Perspective en local; PyGWalker si el paquete no está instalado.",
            ),
        ),
    ),
    NavSection(
        id="pend",
        label="1×10 pendientes",
        blurb="Operación sobre la cola pendiente: mapa, listados y diagnóstico del cruce.",
        items=(
            NavItem(
                "pend_mapa",
                "Mapa",
                "Puntos pendientes y densidad para orientar despliegue en campo.",
            ),
            NavItem(
                "pend_listado",
                "Listado y descargas",
                "Filtros, tablas y exportación Excel/CSV para equipos territoriales.",
            ),
            NavItem(
                "pend_descripcion",
                "Análisis de descripción",
                "Lectura heurística del texto de la solicitud (señales de urgencia).",
            ),
            NavItem(
                "pend_diagnostico",
                "Por qué cruzan pocos",
                "Diagnóstico del matching espacial: radio, nombres y GPS dudoso.",
            ),
        ),
    ),
    NavSection(
        id="abordaje",
        label="Mapas de abordaje",
        blurb="Planificación territorial con máscaras, cuadrículas y semáforo Habitable.",
        items=(
            NavItem(
                "abordaje_capas",
                "Capas y puntos del cruce",
                "Máscaras, cuadrículas de abordaje, pendientes 1×10 y etiqueta de campo.",
            ),
        ),
    ),
    NavSection(
        id="nasa",
        label="Mapa NASA",
        blurb="Señal Sentinel-1 cruzada con 1×10, Habitable e inventario IA.",
        items=(
            NavItem(
                "nasa_mapa",
                "Capas NASA y cruces",
                "Daño probable por radar, coincidencias con fuentes locales e inventario.",
            ),
            NavItem(
                "nasa_1x10",
                "Análisis 1×10 × NASA",
                "Cola prioritaria y mapas de calor para orientar los siguientes casos.",
            ),
            NavItem(
                "nasa_hab",
                "Análisis Habitable × NASA",
                "Confiabilidad radar vs semáforo de campo; zonas de mayor divergencia.",
            ),
            NavItem(
                "nasa_ia",
                "Análisis IA × NASA",
                "Acuerdo óptico↔radar, doble alerta y calor para priorización.",
            ),
        ),
    ),
)

HOME_ID = "inicio"
DEFAULT_SECTION = "fuentes"
DEFAULT_ITEM = "fuentes_1x10"

ITEM_INDEX: dict[str, tuple[str, str]] = {
    it.id: (sec.id, it.id) for sec in NAV_SECTIONS for it in sec.items
}
SECTION_INDEX: dict[str, NavSection] = {sec.id: sec for sec in NAV_SECTIONS}


def resolve_nav(item_id: str | None) -> tuple[str, str]:
    """Devuelve (section_id, item_id) válido."""
    if not item_id or item_id == HOME_ID:
        return HOME_ID, HOME_ID
    if item_id in SECTION_INDEX:
        sec = SECTION_INDEX[item_id]
        return sec.id, sec.items[0].id
    if item_id in ITEM_INDEX:
        return ITEM_INDEX[item_id]
    # legacy
    if item_id in ("mapa_diagnostico", "mapa_caracteristicas"):
        return "fuentes", "fuentes_1x10"
    return ITEM_INDEX[DEFAULT_ITEM]


def find_item(item_id: str) -> NavItem | None:
    for sec in NAV_SECTIONS:
        for it in sec.items:
            if it.id == item_id:
                return it
    return None


def find_section(section_id: str) -> NavSection | None:
    return SECTION_INDEX.get(section_id)
