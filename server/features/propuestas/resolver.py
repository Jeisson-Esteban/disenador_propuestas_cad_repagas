"""
Resolucion de equipos contra el catalogo de Supabase.

`resolver_equipos` toma la PropuestaEquipos del LLM y devuelve EquipoResuelto con
modelo, dimensiones y precio reales. `buscar_equipo_por_tipo` hace la busqueda
individual con filtros de serie/alimentacion/ancho.
"""
from __future__ import annotations

from typing import Optional

from core.database import get_db_connection
from features.propuestas.schemas import EquipoResuelto, PropuestaEquipos


def buscar_equipo_por_tipo(
    tipo: str,
    alimentacion: str = "gas",
    ancho_preferido: Optional[int] = None,
    serie_preferida: str = "750",
) -> Optional[dict]:
    """
    Busca en la tabla `equipos` el mejor match para un tipo dado.

    Estrategia de matching:
      1. Filtra por tipo exacto y alimentación (case-insensitive)
      2. Prefiere la serie indicada (750 por defecto = fondo estándar)
      3. Si se pide un ancho específico, prioriza ese
      4. Desempata por precio (más barato primero, disponibilidad comercial)
    """
    conn = get_db_connection()
    cur = conn.cursor()

    # Query que hace JOIN con series para obtener el nombre de serie
    query = """
        SELECT e.modelo, e.tipo, e.ancho_mm, e.fondo_mm, e.alto_mm,
               e.pvp_eur, s.nombre as serie, e.alimentacion
        FROM equipos e
        LEFT JOIN series s ON e.serie_id = s.id
        WHERE LOWER(e.tipo) = LOWER(%s)
          AND LOWER(e.alimentacion) = LOWER(%s)
          AND e.ancho_mm IS NOT NULL
          AND e.fondo_mm IS NOT NULL
          AND e.alto_mm  IS NOT NULL
          AND e.activo = TRUE
        ORDER BY
            -- Priorizar serie preferida
            CASE WHEN s.nombre ILIKE %s THEN 0 ELSE 1 END,
            -- Priorizar ancho preferido si se especifica
            CASE WHEN %s IS NOT NULL THEN ABS(e.ancho_mm - %s) ELSE 0 END,
            -- Desempatar por precio (más económico = más estándar)
            COALESCE(e.pvp_eur, 999999)
        LIMIT 1
    """
    params = (tipo, alimentacion, f"%{serie_preferida}%", ancho_preferido, ancho_preferido)

    try:
        cur.execute(query, params)
        row = cur.fetchone()
        if row:
            return {
                "modelo": row[0],
                "tipo": row[1],
                "ancho_mm": row[2],
                "fondo_mm": row[3],
                "alto_mm": row[4],
                "pvp_eur": float(row[5]) if row[5] else None,
                "serie": row[6] or "",
            }
        return None
    finally:
        cur.close()
        conn.close()


def resolver_equipos(propuesta: PropuestaEquipos, serie_pref: str = "750") -> list[EquipoResuelto]:
    """
    Toma la propuesta del LLM y resuelve cada equipo contra la DB real.

    Para cada EquipoSeleccionado, busca el modelo concreto en `equipos`.
    Si no hay match exacto en DB, usa datos dummy de la Serie 750.
    """
    equipos_resueltos = []

    # Juntar todas las zonas en una sola lista
    todas_las_zonas = [
        ("coccion", propuesta.zona_coccion),
        ("frio", propuesta.zona_frio),
        ("lavado", propuesta.zona_lavado),
        ("horno", propuesta.zona_horno),
    ]

    for zona_nombre, zona_equipos in todas_las_zonas:
        for eq in zona_equipos:
            for _ in range(eq.cantidad):
                # Intentar resolver contra la DB
                match = buscar_equipo_por_tipo(
                    tipo=eq.tipo,
                    alimentacion=eq.alimentacion,
                    ancho_preferido=eq.ancho_mm_preferido,
                    serie_preferida=serie_pref,
                )

                if match:
                    equipos_resueltos.append(EquipoResuelto(
                        modelo=match["modelo"],
                        tipo=match["tipo"],
                        ancho_mm=match["ancho_mm"],
                        fondo_mm=match["fondo_mm"],
                        alto_mm=match["alto_mm"],
                        pvp_eur=match["pvp_eur"],
                        serie=match["serie"],
                        zona=zona_nombre,
                    ))
                    print(f"    [DB] {match['modelo']:25s} {match['ancho_mm']}x{match['fondo_mm']}mm  €{match['pvp_eur'] or '?'}  zona={zona_nombre}")
                else:
                    # Fallback: equipo genérico con dimensiones estándar
                    print(f"    [FALLBACK] {eq.tipo} — sin match en DB, usando dimensiones genéricas")
                    equipos_resueltos.append(EquipoResuelto(
                        modelo=f"GENERICO-{eq.tipo.upper()}",
                        tipo=eq.tipo,
                        ancho_mm=eq.ancho_mm_preferido or 800,
                        fondo_mm=750,
                        alto_mm=900,
                        serie="generico",
                        zona=zona_nombre,
                    ))

    return equipos_resueltos
