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
        blurb="Volumen y distribución de cada fuente: 1×10 y Habitable.",
        items=(
            NavItem(
                "fuentes_1x10",
                "Fuente 1×10",
                "Registros, cruce, GPS y territorio de la demanda ciudadana.",
            ),
            NavItem(
                "fuentes_hab",
                "Fuente Habitable",
                "Semáforo (4 etiquetas), estado/municipio y tipología.",
            ),
        ),
    ),
    NavSection(
        id="mapa",
        label="Mapa operativo",
        blurb="Cruce espacial 1×10 × Habitable sobre el territorio.",
        items=(
            NavItem("mapa_vista", "Mapa y capas", "Vista, capas, búsqueda y puntos."),
        ),
    ),
    NavSection(
        id="x10",
        label="Análisis 1×10",
        blurb="Demanda ciudadana: depuración, territorio y cola.",
        items=(
            NavItem("x10_depuracion", "Depuración", "Limpieza del Excel y calidad GPS."),
            NavItem(
                "x10_analisis",
                "Territorio y cruce",
                "Volumen, estados, parroquias y % atendidas.",
            ),
            NavItem(
                "x10_cola",
                "Cola pendientes",
                "Casos 1×10 sin cruce, listos para contacto.",
            ),
        ),
    ),
    NavSection(
        id="hab",
        label="Análisis Habitable",
        blurb="Resultado de campo: semáforo y tipología de daños.",
        items=(
            NavItem("hab_matriz", "Matriz semáforo", "Mezcla verde/amarillo/rojo por territorio."),
            NavItem("hab_ne", "No estructurales", "Daños no estructurales."),
            NavItem("hab_mod", "Estructurales moderados", "Bandas moderadas."),
            NavItem("hab_sev", "Severos y externos", "Daño severo y riesgo externo."),
            NavItem("hab_explorar", "Explorar / reportería", "Análisis libre (PyGWalker)."),
        ),
    ),
    NavSection(
        id="pend",
        label="1×10 pendientes",
        blurb="Ubicaciones pendientes: mapa, listado y diagnóstico.",
        items=(
            NavItem("pend_mapa", "Mapa", "Puntos y densidad de pendientes."),
            NavItem("pend_listado", "Listado y descargas", "Filtros y Excel/CSV."),
            NavItem(
                "pend_descripcion",
                "Análisis de descripción",
                "Heurística sobre texto de la solicitud.",
            ),
            NavItem(
                "pend_diagnostico",
                "Por qué cruzan pocos",
                "Diagnóstico del matching espacial.",
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
