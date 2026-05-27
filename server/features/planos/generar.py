"""
Generacion de planos DXF: standalone y/o integrado sobre el plano del cliente.

Usa la libreria de bloques CAD (server/data/libreria_bloques.dxf) y el mapeo
server/data/bloque_map.json. La logica de posicionamiento real vive en
features.planos.posicionar; aqui solo se ENSAMBLA el DXF resultante.
"""
from __future__ import annotations

import json
import os
import re
from typing import Optional

import ezdxf
from ezdxf import xref as ezdxf_xref

from features.propuestas.schemas import EquipoResuelto, FormularioCliente
from features.propuestas.llm import COLORES_ZONA, COLORES_ZONA_LAYOUT, LAYOUTS

# Libreria de bloques CAD (catalogo real Repagas)
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LIBRERIA_DXF    = os.path.join(_BASE_DIR, "..", "..", "data", "libreria_bloques.dxf")
BLOQUE_MAP_JSON = os.path.join(_BASE_DIR, "..", "..", "data", "bloque_map.json")

_bloque_map: dict = {}
if os.path.exists(BLOQUE_MAP_JSON):
    with open(BLOQUE_MAP_JSON, encoding="utf-8") as _f:
        _bloque_map = json.load(_f)
    print(f"[INFO] Libreria CAD cargada: {len(_bloque_map)} bloques disponibles")


def _buscar_bloque(modelo: str) -> Optional[str]:
    """
    Encuentra el nombre de bloque DXF que mejor corresponde a un modelo de DB.

    Estrategia de normalización:
      "CG-740/M POW"  -> prueba "CG-740-P"  -> OK
      "FTG-72/S"      -> prueba "FTG-72-P"  -> OK
      "MN-49"         -> prueba "MN-49-P"   -> OK
      "HP-14"         -> prueba "HP-14-P" (falla) -> prueba "HP-14" -> OK
      "LAVAVAJILLAS"  -> prueba prefix match -> OK

    Solo devuelve bloques con dimensiones validas (width_mm > 50).
    """
    if not _bloque_map:
        return None

    # 1. Coincidencia exacta
    info = _bloque_map.get(modelo)
    if info and info["width_mm"] > 50:
        return modelo

    # 2. Normalizar: quitar sufijo de variante (/M, /S, /L, /2...) y de línea (POW, PRO...)
    normalizado = re.sub(r'/[A-Z0-9]+', '', modelo).strip()
    normalizado = re.sub(
        r'\s+(POW|PRO|POWER|PROFESSIONAL|BASIC|ELECTRIC).*$', '',
        normalizado, flags=re.IGNORECASE
    ).strip()

    # 3. Con sufijo -P (convencion Repagas: vista en planta)
    con_p = normalizado + "-P"
    info = _bloque_map.get(con_p)
    if info and info["width_mm"] > 50:
        return con_p

    # 4. Sin sufijo -P
    info = _bloque_map.get(normalizado)
    if info and info["width_mm"] > 50:
        return normalizado

    # 5. Prefijo: los primeros N chars antes del último guion
    # Ej: "LAVAVAJILLAS-60" busca bloques que empiecen por "LAVAVAJILLAS"
    partes = normalizado.rsplit("-", 1)
    if len(partes) > 1:
        prefix = partes[0]
        for bname, binfo in _bloque_map.items():
            if bname.startswith(prefix) and binfo["width_mm"] > 50:
                return bname

    return None


def generar_plano(
    equipos: list[EquipoResuelto],
    filepath: str = "propuesta_cocina_v1.dxf",
    layout_tipo: str = "L",
    margen_entre_equipos: float = 0,  # mm entre equipos dentro de una zona (0 = pegados)
) -> str:
    """
    Genera un archivo DXF con layout multi-zona.

    Distribuye los equipos en zonas separadas según el tipo de layout
    (lineal, L, U, paralelo), basado en análisis de planos reales.

    Args:
        equipos: Lista de equipos resueltos con medidas reales y zona asignada
        filepath: Ruta del archivo DXF de salida
        layout_tipo: Tipo de distribución ("lineal", "L", "U", "paralelo")
        margen_entre_equipos: Separación en mm entre equipos dentro de una zona

    Returns:
        Ruta absoluta del archivo generado
    """
    doc = ezdxf.new("R2010")
    ezdxf.setup_linetypes(doc)
    msp = doc.modelspace()

    # --Crear layers --
    for tipo, color in COLORES_ZONA.items():
        doc.layers.add(tipo, color=color)
    doc.layers.add("textos", color=7)
    doc.layers.add("cotas", color=3)
    doc.layers.add("contorno", color=2)
    doc.layers.add("bbox", color=8)
    doc.layers.add("zona_contorno", color=2)
    doc.layers.add("pasillo", color=9)
    doc.styles.add("EQUIPO", font="Arial")

    # --Importar bloques CAD desde la libreria --
    bloques_por_equipo: dict[int, str] = {}
    bloques_importados: set[str] = set()

    if _bloque_map and os.path.exists(LIBRERIA_DXF):
        try:
            libreria_doc = ezdxf.readfile(LIBRERIA_DXF)
            loader = ezdxf_xref.Loader(
                libreria_doc, doc,
                conflict_policy=ezdxf_xref.ConflictPolicy.KEEP,
            )
            for i, eq in enumerate(equipos):
                bname = _buscar_bloque(eq.modelo)
                if bname:
                    bloques_por_equipo[i] = bname
                    if bname not in bloques_importados:
                        block_layout = libreria_doc.blocks.get(bname)
                        if block_layout:
                            loader.load_block_layout(block_layout)
                            bloques_importados.add(bname)
            loader.execute()
            print(f"  Bloques CAD importados: {len(bloques_importados)}")
        except Exception as e:
            print(f"  WARN: No se pudo cargar libreria CAD: {e}")
            bloques_por_equipo.clear()
            bloques_importados.clear()
    else:
        print("  INFO: Sin libreria CAD -- usando rectangulos (ejecuta extraer_bloques.py)")

    # --Agrupar equipos por zona --
    zonas_equipos: dict[str, list[tuple[int, EquipoResuelto]]] = {
        "coccion": [], "frio": [], "lavado": [], "horno": [],
    }
    for i, eq in enumerate(equipos):
        zona = eq.zona if eq.zona in zonas_equipos else "coccion"
        zonas_equipos[zona].append((i, eq))

    # --Seleccionar layout --
    layout_key = layout_tipo.lower().replace("_shape", "").replace("-", "").strip()
    if layout_key not in LAYOUTS:
        print(f"  WARN: Layout '{layout_tipo}' no reconocido, usando 'L'")
        layout_key = "l"
    layout = LAYOUTS[layout_key]

    print(f"\n  Layout: {layout_key.upper()}")
    print(f"  Generando plano DXF con {len(equipos)} equipos en {sum(1 for z in zonas_equipos.values() if z)} zonas...")

    # --Posicionar equipos por zona --
    # Tracking de fin de cada zona para resolver "auto" y "end"
    zona_bounds: dict[str, dict] = {}  # zona -> {end_x, end_y, min_x, min_y, max_x, max_y}
    all_bounds = {"min_x": float("inf"), "min_y": float("inf"),
                  "max_x": float("-inf"), "max_y": float("-inf")}
    eq_counter = 0

    zona_orden = ["coccion", "frio", "lavado", "horno"]
    prev_zona_end = None  # Referencia al final de la zona anterior

    for zona_nombre in zona_orden:
        zona_eqs = zonas_equipos.get(zona_nombre, [])
        if not zona_eqs:
            continue

        zona_cfg = layout.get(zona_nombre)
        if not zona_cfg:
            continue

        start_x_cfg, start_y_cfg, direccion = zona_cfg

        # Resolver posiciones especiales
        if start_x_cfg == "auto" and prev_zona_end:
            # Continúa donde terminó la zona anterior (mismo tramo)
            start_x = prev_zona_end["cursor_x"]
            start_y = prev_zona_end["cursor_y"]
        elif start_x_cfg == "end" and "coccion" in zona_bounds:
            # Esquina: empieza donde terminó la primera zona (cocción)
            # El fondo del equipo se pega al borde derecho (alineado con cocción)
            # Se deja un pasillo de ~1200mm entre muros
            PASILLO_MM = 1200
            cb = zona_bounds["coccion"]
            if direccion in ("-Y", "Y"):
                start_x = cb["end_x"] - float(zona_eqs[0][1].fondo_mm)
                start_y = cb["min_y"] - PASILLO_MM
            else:
                start_x = cb["end_x"]
                start_y = cb["end_y"]
        elif start_x_cfg == "end_u" and "frio" in zona_bounds:
            # U-shape: tercer tramo (inferior) empieza en el borde IZQUIERDO del
            # muro vertical y va hacia la izquierda ("-X").  Así no solapa con frio.
            fb = zona_bounds["frio"]
            start_x = fb["min_x"]   # borde izquierdo del muro vertical
            start_y = fb["end_y"]   # fondo del muro vertical
        elif isinstance(start_x_cfg, (int, float)):
            start_x = float(start_x_cfg)
            start_y = float(start_y_cfg)
        else:
            start_x = 0.0
            start_y = 0.0

        cursor_x = start_x
        cursor_y = start_y
        zona_min_x = float("inf")
        zona_min_y = float("inf")
        zona_max_x = float("-inf")
        zona_max_y = float("-inf")

        for idx, (i, eq) in enumerate(zona_eqs):
            w = float(eq.ancho_mm)
            d = float(eq.fondo_mm)

            # Calcular posición según dirección
            if direccion == "X":
                x0, y0 = cursor_x, cursor_y
                x1, y1 = x0 + w, y0 + d
                cursor_x = x1 + margen_entre_equipos
                rotacion = 0.0
            elif direccion == "-X":
                x1 = cursor_x
                x0 = x1 - w
                y0 = cursor_y
                y1 = y0 + d
                cursor_x = x0 - margen_entre_equipos
                rotacion = 0.0
            elif direccion == "-Y":
                # Vertical hacia abajo: ancho en Y, fondo en X
                x0 = cursor_x
                y1 = cursor_y
                x1 = x0 + d  # fondo en X
                y0 = y1 - w  # ancho en -Y
                cursor_y = y0 - margen_entre_equipos
                rotacion = 90.0
            elif direccion == "Y":
                # Vertical hacia arriba
                x0 = cursor_x
                y0 = cursor_y
                x1 = x0 + d  # fondo en X
                y1 = y0 + w  # ancho en Y
                cursor_y = y1 + margen_entre_equipos
                rotacion = 90.0
            else:
                x0, y0 = cursor_x, cursor_y
                x1, y1 = x0 + w, y0 + d
                cursor_x = x1 + margen_entre_equipos
                rotacion = 0.0

            # Actualizar bounds
            zona_min_x = min(zona_min_x, x0)
            zona_min_y = min(zona_min_y, y0)
            zona_max_x = max(zona_max_x, x1)
            zona_max_y = max(zona_max_y, y1)

            # Layer según tipo
            layer = eq.tipo if eq.tipo in COLORES_ZONA else "neutro"

            # --Insertar bloque CAD o fallback --
            bname = bloques_por_equipo.get(i)
            binfo = _bloque_map.get(bname) if bname else None
            usa_bloque = bname and bname in bloques_importados and binfo and binfo["width_mm"] > 50

            if usa_bloque:
                bw = binfo["width_mm"]
                bd = binfo["depth_mm"]
                scale_x = w / bw if bw > 0 else 1.0
                scale_y = d / bd if bd > 0 else 1.0

                if abs(rotacion) < 1.0:
                    # Sin rotación
                    insert_x = x0 - binfo["extmin"][0] * scale_x
                    insert_y = y0 - binfo["extmin"][1] * scale_y
                    msp.add_blockref(bname, (insert_x, insert_y), dxfattribs={
                        "layer": layer, "xscale": scale_x, "yscale": scale_y,
                    })
                else:
                    # Rotado 90°: el bloque se gira, swap scales
                    insert_x = x1 + binfo["extmin"][1] * scale_y
                    insert_y = y0 - binfo["extmin"][0] * scale_x
                    msp.add_blockref(bname, (insert_x, insert_y), dxfattribs={
                        "layer": layer, "xscale": scale_x, "yscale": scale_y,
                        "rotation": 90.0,
                    })

                pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
                msp.add_lwpolyline(pts, dxfattribs={"layer": "bbox", "linetype": "DASHED"})
                eq_counter += 1
                print(f"    [{eq_counter:2d}] BLOQUE {bname:20s}  ({int(x0)},{int(y0)})  {int(w)}x{int(d)}mm  zona={zona_nombre}  rot={rotacion}")
            else:
                pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
                msp.add_lwpolyline(pts, dxfattribs={"layer": layer})
                msp.add_line((x0, y0), (x1, y1), dxfattribs={"layer": layer, "color": 9})
                eq_counter += 1
                print(f"    [{eq_counter:2d}] RECT  {eq.modelo:25s}  ({int(x0)},{int(y0)})  {int(w)}x{int(d)}mm  zona={zona_nombre}")

            # --Etiqueta --
            cx = (x0 + x1) / 2
            cy = (y0 + y1) / 2
            txt_height = max(25, min(50, min(w, d) / 12))

            if abs(rotacion) < 1.0:
                label_x, label_y = cx, y1 + 30
            else:
                label_x, label_y = x1 + 30, cy

            msp.add_text(
                eq.modelo,
                height=txt_height,
                dxfattribs={
                    "layer": "textos", "style": "EQUIPO",
                    "halign": ezdxf.const.CENTER, "valign": ezdxf.const.BOTTOM,
                    "insert": (label_x, label_y), "align_point": (label_x, label_y),
                },
            )
            dim_text = f"{int(w)}x{int(d)}mm"
            msp.add_text(
                dim_text,
                height=txt_height * 0.65,
                dxfattribs={
                    "layer": "cotas", "style": "EQUIPO",
                    "halign": ezdxf.const.CENTER, "valign": ezdxf.const.BOTTOM,
                    "insert": (label_x, label_y + txt_height + 5),
                    "align_point": (label_x, label_y + txt_height + 5),
                },
            )

        # Guardar bounds de esta zona
        zona_bounds[zona_nombre] = {
            "min_x": zona_min_x, "min_y": zona_min_y,
            "max_x": zona_max_x, "max_y": zona_max_y,
            "end_x": cursor_x if direccion in ("X", "-X") else (x1 if direccion == "-Y" else x0),
            "end_y": cursor_y if direccion in ("-Y", "Y") else (y0 if direccion == "-X" else y1),
        }
        prev_zona_end = {"cursor_x": cursor_x, "cursor_y": cursor_y}

        all_bounds["min_x"] = min(all_bounds["min_x"], zona_min_x)
        all_bounds["min_y"] = min(all_bounds["min_y"], zona_min_y)
        all_bounds["max_x"] = max(all_bounds["max_x"], zona_max_x)
        all_bounds["max_y"] = max(all_bounds["max_y"], zona_max_y)

        # --Contorno de zona + etiqueta --
        zona_color = COLORES_ZONA_LAYOUT.get(zona_nombre, 2)
        margen_z = 80  # margen alrededor de la zona
        z_pts = [
            (zona_min_x - margen_z, zona_min_y - margen_z),
            (zona_max_x + margen_z, zona_min_y - margen_z),
            (zona_max_x + margen_z, zona_max_y + margen_z),
            (zona_min_x - margen_z, zona_max_y + margen_z),
            (zona_min_x - margen_z, zona_min_y - margen_z),
        ]
        msp.add_lwpolyline(z_pts, dxfattribs={
            "layer": "zona_contorno", "color": zona_color, "linetype": "DASHED",
        })
        msp.add_text(
            f"ZONA {zona_nombre.upper()}",
            height=60,
            dxfattribs={
                "layer": "zona_contorno", "color": zona_color, "style": "EQUIPO",
                "halign": ezdxf.const.LEFT, "valign": ezdxf.const.TOP,
                "insert": (zona_min_x - margen_z, zona_max_y + margen_z + 70),
                "align_point": (zona_min_x - margen_z, zona_max_y + margen_z + 70),
            },
        )

    # --Pasillo para layout paralelo --
    if layout_key == "paralelo" and "coccion" in zona_bounds and any(
        z in zona_bounds for z in ("frio", "lavado", "horno")
    ):
        cb = zona_bounds["coccion"]
        # Encontrar la línea inferior más alta
        inf_max_y = max(
            zona_bounds[z]["max_y"]
            for z in ("frio", "lavado", "horno") if z in zona_bounds
        )
        pasillo_y_top = cb["min_y"] - 100
        pasillo_y_bot = inf_max_y + 100
        pasillo_x_min = all_bounds["min_x"] - 50
        pasillo_x_max = all_bounds["max_x"] + 50
        # Líneas punteadas del pasillo
        msp.add_line(
            (pasillo_x_min, pasillo_y_top), (pasillo_x_max, pasillo_y_top),
            dxfattribs={"layer": "pasillo", "linetype": "DASHED"},
        )
        msp.add_line(
            (pasillo_x_min, pasillo_y_bot), (pasillo_x_max, pasillo_y_bot),
            dxfattribs={"layer": "pasillo", "linetype": "DASHED"},
        )
        pasillo_cx = (pasillo_x_min + pasillo_x_max) / 2
        pasillo_cy = (pasillo_y_top + pasillo_y_bot) / 2
        msp.add_text(
            "PASILLO DE TRABAJO",
            height=50,
            dxfattribs={
                "layer": "pasillo", "style": "EQUIPO",
                "halign": ezdxf.const.CENTER, "valign": ezdxf.const.MIDDLE,
                "insert": (pasillo_cx, pasillo_cy),
                "align_point": (pasillo_cx, pasillo_cy),
            },
        )

    # --Contorno total --
    pad = 150
    contorno = [
        (all_bounds["min_x"] - pad, all_bounds["min_y"] - pad),
        (all_bounds["max_x"] + pad, all_bounds["min_y"] - pad),
        (all_bounds["max_x"] + pad, all_bounds["max_y"] + pad),
        (all_bounds["min_x"] - pad, all_bounds["max_y"] + pad),
        (all_bounds["min_x"] - pad, all_bounds["min_y"] - pad),
    ]
    msp.add_lwpolyline(contorno, dxfattribs={"layer": "contorno", "linetype": "DASHED"})

    # --Título --
    total_w = all_bounds["max_x"] - all_bounds["min_x"]
    total_h = all_bounds["max_y"] - all_bounds["min_y"]
    titulo_x = (all_bounds["min_x"] + all_bounds["max_x"]) / 2
    titulo_y = all_bounds["max_y"] + pad + 100
    layout_label = {"lineal": "LINEAL", "l": "EN L", "u": "EN U", "paralelo": "PARALELO"}
    msp.add_text(
        f"COCINA INDUSTRIAL — LAYOUT {layout_label.get(layout_key, layout_key.upper())}",
        height=80,
        dxfattribs={
            "layer": "textos", "style": "EQUIPO",
            "halign": ezdxf.const.CENTER, "valign": ezdxf.const.MIDDLE,
            "insert": (titulo_x, titulo_y), "align_point": (titulo_x, titulo_y),
        },
    )
    msp.add_text(
        f"DIMENSIONES: {int(total_w)}mm x {int(total_h)}mm ({total_w/1000:.2f}m x {total_h/1000:.2f}m)",
        height=50,
        dxfattribs={
            "layer": "cotas", "style": "EQUIPO",
            "halign": ezdxf.const.CENTER, "valign": ezdxf.const.MIDDLE,
            "insert": (titulo_x, all_bounds["min_y"] - pad - 80),
            "align_point": (titulo_x, all_bounds["min_y"] - pad - 80),
        },
    )

    # --Guardar DXF --
    abs_path = os.path.abspath(filepath)
    doc.saveas(abs_path)
    print(f"\n  Archivo DXF guardado: {abs_path}")
    print(f"  Layout: {layout_key.upper()} — {int(total_w)}mm x {int(total_h)}mm")

    # --Preview PNG --
    png_path = abs_path.replace(".dxf", ".png")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from ezdxf.addons.drawing import RenderContext, Frontend
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

        fig, ax = plt.subplots(1, 1, figsize=(20, 14), dpi=150)
        ax.set_aspect("equal")
        ax.set_facecolor("#1a1a2e")

        ctx = RenderContext(doc)
        out = MatplotlibBackend(ax)
        Frontend(ctx, out).draw_layout(msp)

        ax.set_title(
            f"Layout {layout_key.upper()} — {int(total_w)}mm x {int(total_h)}mm",
            color="white", fontsize=14, pad=10,
        )
        fig.patch.set_facecolor("#1a1a2e")
        fig.tight_layout()
        fig.savefig(png_path, dpi=150, facecolor=fig.get_facecolor())
        plt.close(fig)
        print(f"  Preview PNG guardado: {png_path}")
    except Exception as e:
        print(f"  WARN: No se pudo generar preview PNG: {e}")

    return abs_path


# --───────────────────────────────────────────
# 4b.  LAYOUT INTEGRADO CON PLANO DEL CLIENTE
# --───────────────────────────────────────────

def generar_plano_integrado(
    equipos: list[EquipoResuelto],
    plano_cliente_dxf: str,
    filepath: str = "propuesta_cocina_v1.dxf",
    layout_tipo: str = "L",
) -> tuple[str, bool]:
    """
    Genera un DXF con equipos posicionados DENTRO del plano del cliente.

    Si el analisis del plano falla, cae automaticamente al layout standalone.

    Returns:
        (ruta_dxf, plano_cliente_usado) — plano_cliente_usado=False si cayo al fallback
    """
    from features.planos.analizar import analizar_plano_cliente
    from features.planos.posicionar import EquipoPosicionado
    from features.planos.integrar import generar_dxf_catalogo

    try:
        import os as _os
        size_kb = _os.path.getsize(plano_cliente_dxf) / 1024 if _os.path.isfile(plano_cliente_dxf) else 0
        print(f"[INTEGRAR] Analizando plano del cliente: {plano_cliente_dxf} ({size_kb:.0f}KB)")
        espacio = analizar_plano_cliente(plano_cliente_dxf)
        print(f"[INTEGRAR] Plano analizado: boundary={espacio.boundary_rect}, confianza={espacio.confidence}")

        if espacio.confidence == "fallback":
            print("[WARN] Deteccion de paredes limitada, pero se integrara en el plano del cliente")

        equipos_pos = []
        for eq in equipos:
            for i in range(eq.cantidad):
                sufijo = f" #{i+1}" if eq.cantidad > 1 else ""
                equipos_pos.append(EquipoPosicionado(
                    modelo=f"{eq.modelo}{sufijo}",
                    tipo=eq.tipo,
                    ancho_mm=eq.ancho_mm,
                    fondo_mm=eq.fondo_mm,
                    alto_mm=eq.alto_mm,
                    pvp_eur=eq.pvp_eur,
                    serie=eq.serie,
                    cantidad=1,
                    zona=eq.zona,
                    x=0, y=0, rotation=0,
                    corners=None,
                    wall_side="north",
                ))

        dxf_path = generar_dxf_catalogo(equipos_pos, espacio, filepath)

        try:
            from features.documentos.pdf import generar_pdf_propuesta
            pdf_path = filepath.replace(".dxf", ".pdf")
            generar_pdf_propuesta(equipos_pos, nombre_proyecto="", filepath=pdf_path)
        except Exception as e:
            print(f"[WARN] No se pudo generar PDF: {e}")

        print(f"[INTEGRAR] Plano cliente integrado correctamente -> {dxf_path}")
        return dxf_path, True

    except Exception as e:
        import traceback
        print(f"[ERROR] Integracion de plano fallo: {e}")
        print(f"[ERROR] Trazado:")
        traceback.print_exc()
        print(f"[WARN] Usando layout standalone como fallback")
        return generar_plano(equipos, filepath, layout_tipo), False


# --───────────────────────────────────────────
# 5.  RESUMEN Y PRESUPUESTO
# --───────────────────────────────────────────

def imprimir_resumen(formulario: FormularioCliente, equipos: list[EquipoResuelto], dxf_path: str):
    """Imprime un resumen ejecutivo de la propuesta."""
    total_pvp = sum(eq.pvp_eur or 0 for eq in equipos)
    ancho_total = sum(eq.ancho_mm for eq in equipos)

    proy = formulario.proyecto
    print("\n" + "=" * 60)
    print("  RESUMEN DE PROPUESTA")
    print("=" * 60)
    print(f"  Proyecto: {proy.nombre or proy.tipo_negocio}")
    print(f"  Cliente: {proy.tipo_negocio.replace('_', ' ').title()}")
    ig = formulario.identidad_gastronomica
    if ig.identidad:
        print(f"  Identidad: {ig.identidad}")
    if ig.estructura_menu:
        print(f"  Menú: {', '.join(ig.estructura_menu)} ({ig.cantidad_platos or '?'} platos)")
    print(f"  Comensales: {proy.comensales}")
    print(f"  Energía: {formulario.energia_principal}" + (f" ({formulario.energia.tipo_gas})" if formulario.energia.tipo_gas else ""))
    print(f"  Superficie: {proy.superficie_m2 or '?'}m²")
    print(f"  Total equipos: {len(equipos)}")
    print(f"  Ancho línea mural: {ancho_total}mm ({ancho_total/1000:.2f}m)")
    print(f"  PVP estimado: €{total_pvp:,.2f}")
    if proy.presupuesto_max:
        restante = proy.presupuesto_max - total_pvp
        print(f"  Presupuesto: €{proy.presupuesto_max:,.0f} (margen: €{restante:,.2f})")
    print(f"  Archivo DXF: {dxf_path}")
    print("=" * 60)

    print("\n  Detalle de equipos:")
    print(f"  {'#':>3} {'Modelo':25s} {'Tipo':25s} {'Ancho':>6} {'Fondo':>6} {'PVP':>10} {'Serie':15s}")
    print("  " + "-" * 95)
    for i, eq in enumerate(equipos, 1):
        pvp_str = f"€{eq.pvp_eur:,.2f}" if eq.pvp_eur else "—"
        print(f"  {i:3d} {eq.modelo:25s} {eq.tipo:25s} {eq.ancho_mm:5d}mm {eq.fondo_mm:5d}mm {pvp_str:>10} {eq.serie:15s}")


# --───────────────────────────────────────────
# 6.  ORQUESTACIÓN — main()
# --───────────────────────────────────────────

