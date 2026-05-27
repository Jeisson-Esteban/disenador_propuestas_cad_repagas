"""
generar_tabla_equipos_dxf.py -- Genera un DXF con la tabla de equipos de la propuesta.

Pensado para incluirse en el ZIP de salida (convertido a DWG) y poder pegarse en el
plano tecnico de AutoCAD. Replica el formato del Excel de referencia usado por
el cliente: tabla por zonas con codigo numerado y columna de unidades.

Estructura del DXF:
  - Titulo: nombre del proyecto en mayusculas
  - Por zona (COCCION / REFRIGERACION / LAVADO):
      - Cabecera: "0N ZONA NOMBRE" | "UNIDADES"
      - Filas: "N.MM <descripcion>" | <cantidad>
  - Cuadricula con bordes y separadores en la capa GRID
  - Textos en la capa TEXT, cabeceras en HEADER

Uso:
    from features.documentos.tabla import generar_tabla_equipos_dxf
    generar_tabla_equipos_dxf(equipos, "Demo Bar", "tabla_equipos.dxf")
"""

from __future__ import annotations

import os
from collections import OrderedDict

import ezdxf


# ─── Configuracion visual de la tabla (mm) ──────────────────────────────

LEFT = 10.0
COL_DESC_W = 250.0
COL_UDS_W = 75.0
TABLE_W = COL_DESC_W + COL_UDS_W

TITLE_H = 25.0
ROW_H = 12.0
HEADER_H = 16.0
GAP_BETWEEN_ZONES = 8.0

TITLE_TEXT_H = 12.0
HEADER_TEXT_H = 6.0
ROW_TEXT_H = 5.0
TEXT_PAD_X = 3.0
TEXT_PAD_Y = 3.5

# Colores ACI
COLOR_BLACK = 7
COLOR_BLUE = 5
COLOR_GRAY = 8

# Mapeo de zonas internas -> nombre/orden en la tabla
ZONA_AGRUPACION = {
    "coccion": "COCCION",
    "horno": "COCCION",
    "frio": "REFRIGERACION",
    "refrigeracion": "REFRIGERACION",
    "lavado": "LAVADO",
    "barra": "BARRA",
}

ZONA_ORDEN = ["COCCION", "REFRIGERACION", "LAVADO", "BARRA"]


def _tipo_legible(tipo: str) -> str:
    """Convierte 'cocina_gas' -> 'COCINA GAS'."""
    if not tipo:
        return ""
    return tipo.replace("_", " ").upper()


def _normalizar_serie(serie: str) -> str:
    """Normaliza 'Serie 750', '750', 'S750' -> 'S750'."""
    if not serie:
        return ""
    s = str(serie).strip()
    s_up = s.upper().replace("SERIE", "").strip()
    if s_up.startswith("S") and s_up[1:].lstrip().isdigit():
        return "S" + s_up[1:].lstrip()
    return f"S{s_up}" if s_up else ""


def _descripcion_equipo(modelo: str, tipo: str, serie: str = "") -> str:
    """Construye la descripcion estilo 'TIPO - MODELO (S750)'."""
    partes = []
    tipo_legible = _tipo_legible(tipo)
    if tipo_legible:
        partes.append(tipo_legible)
    if modelo:
        partes.append(modelo.upper())
    txt = " - ".join(partes) if partes else (modelo or "?").upper()
    s_norm = _normalizar_serie(serie)
    if s_norm:
        txt += f" ({s_norm})"
    return txt


def _agrupar_por_zona_y_modelo(equipos: list) -> "OrderedDict[str, OrderedDict[str, dict]]":
    """
    Devuelve {zona_pretty: {modelo: {'tipo': ..., 'serie': ..., 'cantidad': N}}}
    Suma cantidades para modelos repetidos dentro de la misma zona.
    """
    out: "OrderedDict[str, OrderedDict[str, dict]]" = OrderedDict()
    for nombre in ZONA_ORDEN:
        out[nombre] = OrderedDict()

    for ep in equipos:
        zona_raw = (getattr(ep, "zona", None) or "coccion").lower().strip()
        zona_pretty = ZONA_AGRUPACION.get(zona_raw, zona_raw.upper())
        if zona_pretty not in out:
            out[zona_pretty] = OrderedDict()

        modelo = (getattr(ep, "modelo", "") or "?").strip()
        tipo = getattr(ep, "tipo", "") or ""
        serie = getattr(ep, "serie", "") or ""
        cant = int(getattr(ep, "cantidad", 1) or 1)

        if modelo in out[zona_pretty]:
            out[zona_pretty][modelo]["cantidad"] += cant
        else:
            out[zona_pretty][modelo] = {
                "tipo": tipo,
                "serie": serie,
                "cantidad": cant,
            }

    # Quitar zonas vacias preservando orden
    return OrderedDict((k, v) for k, v in out.items() if v)


def _add_text(msp, txt: str, x: float, y: float, height: float, color: int = COLOR_BLACK):
    """Helper para insertar texto en el DXF."""
    msp.add_text(
        txt,
        dxfattribs={
            "height": height,
            "color": color,
            "layer": "TEXT",
            "style": "Standard",
            "insert": (x, y),
        },
    )


def generar_tabla_equipos_dxf(
    equipos: list,
    nombre_proyecto: str = "",
    filepath: str = "tabla_equipos.dxf",
) -> str:
    """
    Genera el DXF con la tabla de equipos.

    Args:
        equipos: lista con atributos modelo, tipo, zona, serie, cantidad
        nombre_proyecto: texto del titulo en mayusculas
        filepath: ruta de salida del DXF

    Returns:
        Ruta absoluta del DXF generado
    """
    abs_path = os.path.abspath(filepath)
    doc = ezdxf.new(dxfversion="R2018", setup=True)
    doc.units = 4  # mm
    msp = doc.modelspace()

    # Capas
    if "GRID" not in doc.layers:
        doc.layers.add(name="GRID", color=COLOR_GRAY)
    if "TEXT" not in doc.layers:
        doc.layers.add(name="TEXT", color=COLOR_BLACK)
    if "HEADER" not in doc.layers:
        doc.layers.add(name="HEADER", color=COLOR_BLUE)

    # ── Titulo ──────────────────────────────────────────────────────────
    y = 0.0
    titulo = (nombre_proyecto or "PROPUESTA DE EQUIPAMIENTO").upper()
    _add_text(msp, titulo, LEFT, y - TITLE_TEXT_H - 2, TITLE_TEXT_H, COLOR_BLUE)
    y -= TITLE_H

    # Linea horizontal bajo titulo
    msp.add_line(
        (LEFT, y),
        (LEFT + TABLE_W, y),
        dxfattribs={"layer": "GRID", "color": COLOR_BLACK, "lineweight": 50},
    )

    y_top_table = y  # marcamos donde empieza la tabla

    # ── Zonas ───────────────────────────────────────────────────────────
    grupos = _agrupar_por_zona_y_modelo(equipos)
    zona_idx = 0
    for zona_pretty, items in grupos.items():
        zona_idx += 1

        # Cabecera de zona
        cab_zona = f"{zona_idx:02d} ZONA {zona_pretty}"
        _add_text(
            msp, cab_zona, LEFT + TEXT_PAD_X, y - HEADER_H + TEXT_PAD_Y,
            HEADER_TEXT_H, COLOR_BLUE,
        )
        _add_text(
            msp, "UNIDADES", LEFT + COL_DESC_W + TEXT_PAD_X, y - HEADER_H + TEXT_PAD_Y,
            HEADER_TEXT_H, COLOR_BLUE,
        )

        # Linea bajo cabecera
        y_below_header = y - HEADER_H
        msp.add_line(
            (LEFT, y_below_header),
            (LEFT + TABLE_W, y_below_header),
            dxfattribs={"layer": "GRID", "color": COLOR_BLACK},
        )
        y = y_below_header

        # Filas
        for i, (modelo, info) in enumerate(items.items(), start=1):
            desc = _descripcion_equipo(modelo, info["tipo"], info["serie"])
            row_label = f"{zona_idx}.{i:02d}  {desc}"
            _add_text(
                msp, row_label[:80], LEFT + TEXT_PAD_X, y - ROW_H + TEXT_PAD_Y,
                ROW_TEXT_H, COLOR_BLACK,
            )
            _add_text(
                msp, str(info["cantidad"]),
                LEFT + COL_DESC_W + (COL_UDS_W / 2) - 5,
                y - ROW_H + TEXT_PAD_Y,
                ROW_TEXT_H, COLOR_BLACK,
            )
            y_row_bottom = y - ROW_H
            msp.add_line(
                (LEFT, y_row_bottom),
                (LEFT + TABLE_W, y_row_bottom),
                dxfattribs={"layer": "GRID", "color": COLOR_GRAY},
            )
            y = y_row_bottom

        # Separacion entre zonas
        y -= GAP_BETWEEN_ZONES

    y_bottom = y + GAP_BETWEEN_ZONES  # ultimo y_row_bottom valido

    # ── Bordes verticales del cuerpo ────────────────────────────────────
    msp.add_line(
        (LEFT, y_top_table), (LEFT, y_bottom),
        dxfattribs={"layer": "GRID", "color": COLOR_BLACK},
    )
    msp.add_line(
        (LEFT + COL_DESC_W, y_top_table), (LEFT + COL_DESC_W, y_bottom),
        dxfattribs={"layer": "GRID", "color": COLOR_BLACK},
    )
    msp.add_line(
        (LEFT + TABLE_W, y_top_table), (LEFT + TABLE_W, y_bottom),
        dxfattribs={"layer": "GRID", "color": COLOR_BLACK},
    )

    doc.saveas(abs_path)
    print(f"[TABLA] DXF generado: {abs_path}")
    return abs_path


# ─── CLI ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Demo con equipos de prueba
    class _Eq:
        def __init__(self, modelo, tipo, zona, cantidad=1, serie="", **kw):
            self.modelo = modelo
            self.tipo = tipo
            self.zona = zona
            self.cantidad = cantidad
            self.serie = serie

    demo = [
        _Eq("CG-960 POW", "cocina_gas", "coccion", 1, "900"),
        _Eq("FTG-91/S POW", "fry_top_gas", "coccion", 1, "900"),
        _Eq("BARG-92/S POW", "barbacoa", "coccion", 2, "900"),
        _Eq("FG-92/16", "freidora_gas", "coccion", 1, "900"),
        _Eq("ARG700", "armario_conservacion", "frio", 2, "700"),
        _Eq("MBR2500", "mesa_refrigerada", "frio", 1),
        _Eq("MP-6V", "lavavajillas", "lavado", 1),
        _Eq("J-6-2", "fregadero", "lavado", 1),
    ]
    out = generar_tabla_equipos_dxf(
        demo, "Restaurante Argentino", "output/tabla_demo.dxf"
    )
    print(out)
