"""
generar_pdf_propuesta.py -- Genera un PDF profesional con la propuesta de equipos.

Usa la paleta Repagas del formulario:
  - Primary:  #010069 (azul oscuro)
  - Gray-700: #374151
  - Gray-100: #f3f4f6
  - Success:  #10b981 (verde)

Zonas con colores diferenciados:
  - Coccion:       #c0392b (rojo)
  - Lavado:        #2980b9 (azul)
  - Refrigeracion: #16a085 (cyan/verde)
  - Horno:         #e67e22 (naranja)
"""

import os
from datetime import datetime

from fpdf import FPDF


# ─── Rutas de assets ─────────────────────────────────────

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
LOGO_PATH = os.path.join(_ASSETS_DIR, "logo-white.png")
FONT_DIR = os.path.join(_ASSETS_DIR, "fonts")

# ─── Paleta Repagas Concept (del manual de marca) ───────

PRIMARY = (57, 67, 183)      # #3943B7 - Azul Repagas Concept
PRIMARY_DARK = (40, 47, 128) # #282F80
PRIMARY_LIGHT = (230, 232, 245)  # #E6E8F5
WHITE = (255, 255, 255)
GRAY_50 = (249, 250, 251)
GRAY_100 = (243, 244, 246)
GRAY_200 = (229, 231, 235)
GRAY_300 = (209, 213, 219)
GRAY_500 = (107, 114, 128)
GRAY_700 = (55, 65, 81)
GRAY_800 = (31, 41, 55)
BLACK = (17, 24, 39)         # #111827

ZONA_COLORES = {
    "coccion":       PRIMARY,
    "horno":         PRIMARY,
    "lavado":        PRIMARY,
    "frio":          PRIMARY,
    "refrigeracion": PRIMARY,
}

ZONA_NOMBRES = {
    "coccion": "Coccion",
    "horno": "Coccion",
    "lavado": "Lavado",
    "frio": "Refrigeracion",
    "refrigeracion": "Refrigeracion",
}

ZONA_ORDEN = ["coccion", "horno", "lavado", "frio"]


class PropuestaPDF(FPDF):
    """PDF profesional con branding RepagasConcept."""

    def __init__(self, nombre_proyecto: str = ""):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.nombre_proyecto = nombre_proyecto
        self.set_auto_page_break(auto=True, margin=20)
        self._fonts_loaded = False
        self._load_fonts()

    def _load_fonts(self):
        """Registra Basier Square si las fuentes estan disponibles."""
        if not os.path.isdir(FONT_DIR):
            return
        try:
            self.add_font("Basier", "", os.path.join(FONT_DIR, "BasierSquare-Regular.otf"), uni=True)
            self.add_font("Basier", "B", os.path.join(FONT_DIR, "BasierSquare-Bold.otf"), uni=True)
            self.add_font("Basier", "I", os.path.join(FONT_DIR, "BasierSquare-Regular.otf"), uni=True)  # no italic file
            self._fonts_loaded = True
        except Exception:
            pass  # Fallback a Helvetica

    @property
    def _font(self) -> str:
        return "Basier" if self._fonts_loaded else "Helvetica"

    def header(self):
        # Barra superior azul Repagas (ancho adaptativo)
        self.set_fill_color(*PRIMARY)
        self.rect(0, 0, self.w, 20, "F")

        # Logo imagen si existe
        if os.path.isfile(LOGO_PATH):
            try:
                self.image(LOGO_PATH, 8, 3, h=14)
            except Exception:
                self.set_font(self._font, "B", 11)
                self.set_text_color(*WHITE)
                self.set_xy(10, 5)
                self.cell(0, 10, "RepagasConcept", align="L")
        else:
            self.set_font(self._font, "B", 11)
            self.set_text_color(*WHITE)
            self.set_xy(10, 5)
            self.cell(0, 10, "RepagasConcept", align="L")

        # Nombre proyecto a la derecha
        if self.nombre_proyecto:
            self.set_font(self._font, "B", 9)
            self.set_text_color(*WHITE)
            self.set_xy(-80, 6)
            self.cell(70, 8, self.nombre_proyecto, align="R")

        self.ln(24)

    def footer(self):
        self.set_y(-15)
        # Linea separadora
        self.set_draw_color(*GRAY_200)
        self.line(10, self.get_y(), self.w - 10, self.get_y())
        # Texto
        self.set_font(self._font, "", 7)
        self.set_text_color(*GRAY_500)
        self.cell(0, 8, f"RepagasConcept  |  Propuesta generada el {datetime.now().strftime('%d/%m/%Y')}", align="L")
        self.cell(0, 8, f"Pagina {self.page_no()}/{{nb}}", align="R")


def generar_pdf_propuesta(
    equipos: list,
    nombre_proyecto: str = "",
    filepath: str = "propuesta_equipos.pdf",
) -> str:
    """
    Genera un PDF profesional con la lista de equipos agrupados por zona.

    Args:
        equipos: Lista de objetos con atributos: modelo, tipo, zona, ancho_mm, fondo_mm,
                 alto_mm, pvp_eur, serie, cantidad
        nombre_proyecto: Nombre del proyecto para el header
        filepath: Ruta de salida del PDF

    Returns:
        Ruta absoluta del PDF generado
    """
    abs_path = os.path.abspath(filepath)
    pdf = PropuestaPDF(nombre_proyecto)
    pdf.alias_nb_pages()
    pdf.add_page()

    # ── Titulo principal ──
    pdf.set_font(pdf._font, "B", 20)
    pdf.set_text_color(*PRIMARY)
    pdf.cell(0, 12, "Propuesta de Equipamiento", align="C")
    pdf.ln(12)

    pdf.set_font(pdf._font, "", 10)
    pdf.set_text_color(*GRAY_700)
    subtitle = "Listado de equipos organizados por zona funcional"
    if nombre_proyecto:
        subtitle = f"{nombre_proyecto}  --  {subtitle}"
    pdf.cell(0, 6, subtitle, align="C")
    pdf.ln(6)
    pdf.ln(4)

    # Linea decorativa
    pdf.set_draw_color(*PRIMARY)
    pdf.set_line_width(0.8)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.set_line_width(0.2)
    pdf.ln(6)

    # ── Resumen rapido ──
    from collections import defaultdict
    equipos_por_zona: dict[str, list] = defaultdict(list)
    for ep in equipos:
        zona = getattr(ep, "zona", None) or "coccion"
        equipos_por_zona[zona].append(ep)

    total_equipos = len(equipos)
    total_zonas = len(equipos_por_zona)
    total_pvp = sum(getattr(ep, "pvp_eur", 0) or 0 for ep in equipos)

    # Cajas de resumen
    _draw_summary_boxes(pdf, total_equipos, total_zonas, total_pvp)
    pdf.ln(6)

    # ── Tabla de equipos por zona ──
    zonas_ordenadas = []
    for z in ZONA_ORDEN:
        if z in equipos_por_zona:
            zonas_ordenadas.append(z)
    for z in equipos_por_zona:
        if z not in zonas_ordenadas:
            zonas_ordenadas.append(z)

    for zona in zonas_ordenadas:
        items = equipos_por_zona[zona]
        color = ZONA_COLORES.get(zona, GRAY_700)
        nombre = ZONA_NOMBRES.get(zona, zona.upper())

        # Check space: need at least header + 1 row (about 25mm)
        if pdf.get_y() > 250:
            pdf.add_page()

        # ── Cabecera de zona ──
        _draw_zone_header(pdf, nombre, color, len(items))

        # ── Tabla ──
        _draw_equipment_table(pdf, items, color)

        pdf.ln(4)

    # ── Pagina 2: Tabla de especificaciones tipo Excel ──
    pdf.add_page("L")  # Landscape para más columnas
    _draw_spec_table(pdf, equipos, equipos_por_zona, zonas_ordenadas)

    pdf.output(abs_path)
    print(f"[PDF] Propuesta generada: {abs_path}")
    return abs_path


def _draw_summary_boxes(pdf: FPDF, total_equipos: int, total_zonas: int, total_pvp: float):
    """Dibuja 3 cajas de resumen en fila."""
    box_w = 60
    box_h = 18
    start_x = (210 - box_w * 3 - 6) / 2  # Centrado

    boxes = [
        (str(total_equipos), "Equipos", PRIMARY),
        (str(total_zonas), "Zonas", (22, 160, 133)),
    ]
    if total_pvp > 0:
        boxes.append((f"{total_pvp:,.0f} EUR", "Presupuesto est.", (230, 126, 34)))
    else:
        boxes.append(("--", "Presupuesto", GRAY_500))

    for i, (value, label, color) in enumerate(boxes):
        x = start_x + i * (box_w + 3)
        y = pdf.get_y()

        # Fondo gris claro con borde de color
        pdf.set_fill_color(*GRAY_50)
        pdf.set_draw_color(*color)
        pdf.set_line_width(0.6)
        pdf.rect(x, y, box_w, box_h, "DF")
        pdf.set_line_width(0.2)

        # Linea de acento arriba
        pdf.set_draw_color(*color)
        pdf.set_line_width(1.5)
        pdf.line(x, y, x + box_w, y)
        pdf.set_line_width(0.2)

        # Valor grande
        pdf.set_font(pdf._font, "B", 14)
        pdf.set_text_color(*color)
        pdf.set_xy(x, y + 2)
        pdf.cell(box_w, 8, value, align="C")

        # Label
        pdf.set_font(pdf._font, "", 7)
        pdf.set_text_color(*GRAY_500)
        pdf.set_xy(x, y + 10)
        pdf.cell(box_w, 6, label, align="C")

    pdf.set_y(pdf.get_y() + box_h + 2)


def _draw_zone_header(pdf: FPDF, nombre: str, color: tuple, count: int):
    """Dibuja la cabecera de una zona con barra de color."""
    y = pdf.get_y()

    # Barra de color a la izquierda
    pdf.set_fill_color(*color)
    pdf.rect(10, y, 3, 8, "F")

    # Nombre de zona
    pdf.set_font(pdf._font, "B", 12)
    pdf.set_text_color(*color)
    pdf.set_xy(16, y)
    pdf.cell(120, 8, nombre.upper())

    # Contador
    pdf.set_font(pdf._font, "", 9)
    pdf.set_text_color(*GRAY_500)
    pdf.set_xy(-50, y)
    pdf.cell(40, 8, f"{count} equipo{'s' if count != 1 else ''}", align="R")

    pdf.set_y(y + 10)


def _draw_equipment_table(pdf: FPDF, items: list, zona_color: tuple):
    """Dibuja la tabla de equipos para una zona."""
    # Header de tabla
    col_widths = [8, 72, 28, 22, 22, 38]  # #, Modelo, Dims, Cant, Serie, PVP
    headers = ["#", "Modelo / Tipo", "Dimensiones", "Cant.", "Serie", "PVP (EUR)"]

    pdf.set_fill_color(*PRIMARY)
    pdf.set_text_color(*WHITE)
    pdf.set_font(pdf._font, "B", 8)
    x = 10
    for w, h_text in zip(col_widths, headers):
        pdf.set_x(x)
        pdf.cell(w, 7, h_text, fill=True, align="C" if w < 40 else "L")
        x += w
    pdf.ln(7)

    # Filas
    pdf.set_font(pdf._font, "", 8)
    for i, ep in enumerate(items):
        # Alternar fondo
        if i % 2 == 0:
            pdf.set_fill_color(*WHITE)
        else:
            pdf.set_fill_color(*GRAY_50)

        y = pdf.get_y()
        if y > 270:
            pdf.add_page()
            # Re-dibujar header de tabla
            pdf.set_fill_color(*PRIMARY)
            pdf.set_text_color(*WHITE)
            pdf.set_font(pdf._font, "B", 8)
            x = 10
            for w, h_text in zip(col_widths, headers):
                pdf.set_x(x)
                pdf.cell(w, 7, h_text, fill=True, align="C" if w < 40 else "L")
                x += w
            pdf.ln(7)
            pdf.set_font(pdf._font, "", 8)
            if i % 2 == 0:
                pdf.set_fill_color(*WHITE)
            else:
                pdf.set_fill_color(*GRAY_50)

        row_h = 6.5
        x = 10

        # Numero
        pdf.set_text_color(*GRAY_500)
        pdf.set_x(x)
        pdf.cell(col_widths[0], row_h, str(i + 1), fill=True, align="C")
        x += col_widths[0]

        # Modelo
        modelo = getattr(ep, "modelo", str(ep))
        tipo = getattr(ep, "tipo", "")
        pdf.set_text_color(*GRAY_800)
        pdf.set_font(pdf._font, "B", 8)
        pdf.set_x(x)
        pdf.cell(col_widths[1], row_h, modelo[:35], fill=True)
        x += col_widths[1]

        # Dimensiones
        w_mm = getattr(ep, "ancho_mm", 0) or 0
        d_mm = getattr(ep, "fondo_mm", 0) or 0
        dims = f"{int(w_mm)}x{int(d_mm)}" if w_mm and d_mm else "--"
        pdf.set_font(pdf._font, "", 8)
        pdf.set_text_color(*GRAY_700)
        pdf.set_x(x)
        pdf.cell(col_widths[2], row_h, dims, fill=True, align="C")
        x += col_widths[2]

        # Cantidad
        cant = getattr(ep, "cantidad", 1) or 1
        pdf.set_x(x)
        pdf.cell(col_widths[3], row_h, str(cant), fill=True, align="C")
        x += col_widths[3]

        # Serie
        serie = getattr(ep, "serie", "") or ""
        pdf.set_x(x)
        pdf.cell(col_widths[4], row_h, serie[:10], fill=True, align="C")
        x += col_widths[4]

        # PVP
        pvp = getattr(ep, "pvp_eur", 0) or 0
        pvp_text = f"{pvp:,.0f}" if pvp else "--"
        pdf.set_text_color(*zona_color)
        pdf.set_font(pdf._font, "B", 8)
        pdf.set_x(x)
        pdf.cell(col_widths[5], row_h, pvp_text, fill=True, align="R")

        pdf.ln(row_h)

    # Linea inferior
    pdf.set_draw_color(*zona_color)
    pdf.set_line_width(0.4)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.set_line_width(0.2)


def _draw_spec_table(pdf: FPDF, equipos: list, equipos_por_zona: dict, zonas_ordenadas: list):
    """Dibuja una tabla tipo Excel con todas las especificaciones tecnicas."""
    page_w = 297  # Landscape A4 width

    # Titulo
    pdf.set_font(pdf._font, "B", 14)
    pdf.set_text_color(*PRIMARY)
    pdf.cell(0, 8, "Especificaciones Tecnicas", align="C")
    pdf.ln(10)

    # Linea decorativa
    pdf.set_draw_color(*PRIMARY)
    pdf.set_line_width(0.8)
    pdf.line(10, pdf.get_y(), page_w - 10, pdf.get_y())
    pdf.set_line_width(0.2)
    pdf.ln(4)

    # Columnas: N, Zona, Modelo, Tipo, Ancho, Fondo, Alto, Dims total, Serie, Cant, PVP, Subtotal
    col_widths = [8, 28, 52, 38, 20, 20, 20, 28, 20, 14, 26, 26]
    # Total = 300 -> no cabe. Ajusto para landscape (277mm utiles)
    # 8+28+52+38+20+20+20+28+20+14+26+26 = 300 -> reducir
    col_widths = [7, 24, 48, 34, 18, 18, 18, 26, 18, 12, 24, 24]
    # Total = 271
    headers = [
        "#", "Zona", "Modelo", "Tipo", "Ancho\n(mm)", "Fondo\n(mm)",
        "Alto\n(mm)", "Superficie\n(mm x mm)", "Serie", "Uds", "PVP\n(EUR)", "Subtotal\n(EUR)",
    ]
    start_x = (page_w - sum(col_widths)) / 2  # Centrar tabla

    row_h = 6
    header_h = 9

    # ── Header ──
    pdf.set_fill_color(*PRIMARY)
    pdf.set_text_color(*WHITE)
    pdf.set_font(pdf._font, "B", 6.5)
    x = start_x
    y_header = pdf.get_y()
    for w, h_text in zip(col_widths, headers):
        pdf.set_xy(x, y_header)
        pdf.multi_cell(w, header_h / 2, h_text, border=1, fill=True, align="C")
        x += w
    pdf.set_y(y_header + header_h)

    # ── Filas por zona ──
    num = 0
    for zona in zonas_ordenadas:
        items = equipos_por_zona[zona]
        color = ZONA_COLORES.get(zona, GRAY_700)
        nombre = ZONA_NOMBRES.get(zona, zona.upper())

        # Fila de cabecera de zona (barra de color)
        y = pdf.get_y()
        if y > 180:  # Landscape tiene ~190mm de alto util
            pdf.add_page("L")
            # Re-dibujar header
            pdf.set_fill_color(*PRIMARY)
            pdf.set_text_color(*WHITE)
            pdf.set_font(pdf._font, "B", 6.5)
            x = start_x
            y_header = pdf.get_y()
            for w, h_text in zip(col_widths, headers):
                pdf.set_xy(x, y_header)
                pdf.multi_cell(w, header_h / 2, h_text, border=1, fill=True, align="C")
                x += w
            pdf.set_y(y_header + header_h)

        # Barra de zona
        pdf.set_fill_color(*color)
        pdf.set_text_color(*WHITE)
        pdf.set_font(pdf._font, "B", 7)
        pdf.set_x(start_x)
        pdf.cell(sum(col_widths), row_h, f"  {nombre.upper()}", border=1, fill=True, align="L")
        pdf.ln(row_h)

        # Items
        zona_subtotal = 0
        for i, ep in enumerate(items):
            num += 1
            y = pdf.get_y()
            if y > 185:
                pdf.add_page("L")
                # Re-dibujar header
                pdf.set_fill_color(*PRIMARY)
                pdf.set_text_color(*WHITE)
                pdf.set_font(pdf._font, "B", 6.5)
                x = start_x
                y_header = pdf.get_y()
                for w, h_text in zip(col_widths, headers):
                    pdf.set_xy(x, y_header)
                    pdf.multi_cell(w, header_h / 2, h_text, border=1, fill=True, align="C")
                    x += w
                pdf.set_y(y_header + header_h)

            # Alternar fondo
            if i % 2 == 0:
                pdf.set_fill_color(*WHITE)
            else:
                pdf.set_fill_color(*GRAY_50)

            modelo = getattr(ep, "modelo", str(ep))
            tipo = getattr(ep, "tipo", "")
            w_mm = getattr(ep, "ancho_mm", 0) or 0
            d_mm = getattr(ep, "fondo_mm", 0) or 0
            h_mm = getattr(ep, "alto_mm", 0) or 0
            serie = getattr(ep, "serie", "") or ""
            cant = getattr(ep, "cantidad", 1) or 1
            pvp = getattr(ep, "pvp_eur", 0) or 0
            subtotal = pvp * cant
            zona_subtotal += subtotal

            # Tipo legible
            tipo_legible = tipo.replace("_", " ").title() if tipo else "--"

            # Superficie (ancho x fondo)
            sup = f"{int(w_mm)} x {int(d_mm)}" if w_mm and d_mm else "--"

            valores = [
                str(num),
                nombre[:12],
                modelo[:25],
                tipo_legible[:18],
                str(int(w_mm)) if w_mm else "--",
                str(int(d_mm)) if d_mm else "--",
                str(int(h_mm)) if h_mm else "--",
                sup,
                serie[:8] if serie else "--",
                str(cant),
                f"{pvp:,.0f}" if pvp else "--",
                f"{subtotal:,.0f}" if subtotal else "--",
            ]

            aligns = ["C", "L", "L", "L", "C", "C", "C", "C", "C", "C", "R", "R"]

            x = start_x
            pdf.set_font(pdf._font, "", 7)
            for j, (cw, val, align) in enumerate(zip(col_widths, valores, aligns)):
                # Color de texto
                if j == 2:  # Modelo en negrita
                    pdf.set_font(pdf._font, "B", 7)
                    pdf.set_text_color(*GRAY_800)
                elif j >= 10:  # PVP y Subtotal en color de zona
                    pdf.set_font(pdf._font, "B", 7)
                    pdf.set_text_color(*color)
                else:
                    pdf.set_font(pdf._font, "", 7)
                    pdf.set_text_color(*GRAY_700)

                pdf.set_x(x)
                pdf.cell(cw, row_h, val, border=1, fill=True, align=align)
                x += cw
            pdf.ln(row_h)

        # Subtotal de zona
        pdf.set_fill_color(*GRAY_100)
        pdf.set_font(pdf._font, "B", 7)
        pdf.set_text_color(*color)
        x = start_x
        # Celdas vacias hasta la columna de subtotal
        merge_w = sum(col_widths[:-1])
        pdf.set_x(x)
        pdf.cell(merge_w, row_h, f"  Subtotal {nombre}", border=1, fill=True, align="R")
        pdf.cell(col_widths[-1], row_h,
                 f"{zona_subtotal:,.0f}" if zona_subtotal else "--",
                 border=1, fill=True, align="R")
        pdf.ln(row_h)

    # ── TOTAL GENERAL ──
    pdf.set_fill_color(*PRIMARY)
    pdf.set_text_color(*WHITE)
    pdf.set_font(pdf._font, "B", 8)
    total_pvp = sum((getattr(ep, "pvp_eur", 0) or 0) * (getattr(ep, "cantidad", 1) or 1) for ep in equipos)
    merge_w = sum(col_widths[:-1])
    pdf.set_x(start_x)
    pdf.cell(merge_w, row_h + 1, "  TOTAL PRESUPUESTO", border=1, fill=True, align="R")
    pdf.cell(col_widths[-1], row_h + 1,
             f"{total_pvp:,.0f} EUR" if total_pvp else "--",
             border=1, fill=True, align="R")
    pdf.ln(row_h + 4)

    # Nota
    pdf.set_font(pdf._font, "I", 7)
    pdf.set_text_color(*GRAY_500)
    pdf.set_x(start_x)
    pdf.multi_cell(sum(col_widths), 3.5,
        "Dimensiones en milimetros (ancho x fondo x alto). "
        "PVP en EUR sin IVA. Precios orientativos sujetos a confirmacion. "
        "Superficie = espacio que ocupa el equipo en planta.",
    )


# ═══════════════════════════════════════════════════════════
#  PDF 2: PROSPECCION — Documento Q&A formato RepagasConcept
# ═══════════════════════════════════════════════════════════

def generar_pdf_prospeccion(
    formulario_data: dict,
    nombre_proyecto: str = "",
    filepath: str = "prospeccion.pdf",
) -> str:
    """
    Genera el documento de Prospeccion siguiendo el formato del PPTX oficial
    de RepagasConcept: portada + secciones numeradas (Parte Tecnica, Parte
    Operativa, Lavado, Refrigeracion) + pagina final de firma.
    """
    abs_path = os.path.abspath(filepath)
    nombre = nombre_proyecto or (formulario_data.get("proyecto") or {}).get("nombre", "")
    textos = _cargar_textos_config()
    pdf = PropuestaPDF(nombre)
    pdf.alias_nb_pages()

    # ── Portada ──
    pdf.add_page()
    pdf.ln(40)
    pdf.set_font(pdf._font, "B", 36)
    pdf.set_text_color(*PRIMARY)
    pdf.cell(0, 18, "PROSPECCION", align="C")
    pdf.ln(22)

    pdf.set_font(pdf._font, "", 14)
    pdf.set_text_color(*GRAY_700)
    pdf.cell(0, 10, nombre or "Nombre del Proyecto", align="C")
    pdf.ln(14)

    pdf.set_draw_color(*PRIMARY)
    pdf.set_line_width(1.0)
    pdf.line(70, pdf.get_y(), 140, pdf.get_y())
    pdf.set_line_width(0.2)
    pdf.ln(10)

    pdf.set_font(pdf._font, "", 10)
    pdf.set_text_color(*GRAY_500)
    intro = textos.get("prospeccion_intro") or "Documento de prospeccion - RepagasConcept"
    pdf.multi_cell(0, 5, intro, align="C")
    pdf.ln(2)
    pdf.cell(0, 6, datetime.now().strftime("%d de %B de %Y"), align="C")

    # ── Secciones Q&A ──
    secciones = [
        ("01", "PARTE TECNICA", _campos_tecnica_qa(formulario_data)),
        ("02", "PARTE OPERATIVA", _campos_operativa_qa(formulario_data)),
        ("03", "VAJILLA Y LAVADO", _campos_lavado_qa(formulario_data)),
        ("04", "REFRIGERACION Y ALMACENAJE", _campos_refrigeracion_qa(formulario_data)),
        ("05", "PERSONAL Y FORMACION", _campos_personal_qa(formulario_data)),
    ]

    for numero, titulo, preguntas in secciones:
        if not preguntas:
            continue
        pdf.add_page()
        _draw_seccion_header(pdf, numero, titulo)
        for pregunta, respuesta in preguntas:
            _draw_qa(pdf, pregunta, respuesta)

    # ── Equipos manuales (si existen) ──
    eqm = formulario_data.get("equipos_manuales", {})
    has_equipos = any(eqm.get(z) for z in ["coccion", "refrigeracion", "lavado", "horno"])
    if has_equipos:
        pdf.add_page()
        _draw_seccion_header(pdf, "06", "EQUIPOS SOLICITADOS")
        for zona in ["coccion", "horno", "refrigeracion", "lavado"]:
            items = eqm.get(zona, [])
            if not items:
                continue
            if pdf.get_y() > 250:
                pdf.add_page()
            pdf.set_font(pdf._font, "B", 11)
            pdf.set_text_color(*PRIMARY)
            pdf.set_x(14)
            pdf.cell(0, 7, ZONA_NOMBRES.get(zona, zona).upper())
            pdf.ln(8)
            for eq in items:
                if pdf.get_y() > 275:
                    pdf.add_page()
                pdf.set_font(pdf._font, "", 9)
                pdf.set_text_color(*GRAY_700)
                pdf.set_x(18)
                pdf.cell(150, 5, "- " + eq.get("nombre", "")[:80])
                pdf.set_text_color(*PRIMARY)
                pdf.cell(20, 5, "x" + str(eq.get("cantidad", 1)), align="R")
                pdf.ln(6)
            pdf.ln(3)

    # ── Pagina de firma ──
    pdf.add_page()
    pdf.ln(20)
    pdf.set_font(pdf._font, "", 10)
    pdf.set_text_color(*GRAY_700)
    cierre = textos.get("prospeccion_cierre") or (
        "Este documento sirve como punto de partida del proyecto. "
        "Incluye una radiografia tecnica y operativa que sera utilizada "
        "para ofrecer una propuesta alineada con las necesidades del proyecto."
    )
    pdf.multi_cell(0, 6, cierre)
    pdf.ln(20)

    pdf.set_font(pdf._font, "", 9)
    firma_text = textos.get("prospeccion_firma") or "Es indispensable visarlo y firmarlo para confirmar conformidad."
    pdf.multi_cell(0, 6, firma_text)
    pdf.ln(14)

    # Lineas de firma
    col_w = 85
    gap = 10
    start_x = (210 - col_w * 2 - gap) / 2

    pdf.set_x(start_x)
    pdf.set_draw_color(*GRAY_300)
    pdf.set_line_width(0.3)
    y = pdf.get_y() + 18
    pdf.line(start_x, y, start_x + col_w, y)
    pdf.line(start_x + col_w + gap, y, start_x + col_w * 2 + gap, y)

    pdf.set_xy(start_x, y + 2)
    pdf.set_font(pdf._font, "B", 9)
    pdf.set_text_color(*GRAY_700)
    pdf.cell(col_w, 5, "Receptor de Servicios", align="C")
    pdf.set_xy(start_x + col_w + gap, y + 2)
    pdf.cell(col_w, 5, "RepagasConcept", align="C")
    pdf.ln(8)

    pdf.set_font(pdf._font, "", 8)
    pdf.set_text_color(*GRAY_500)
    pdf.set_x(start_x)
    pdf.cell(col_w, 5, "Nombre y firma", align="C")
    pdf.set_xy(start_x + col_w + gap, pdf.get_y())
    pdf.cell(col_w, 5, "Nombre y firma", align="C")

    pdf.output(abs_path)
    print(f"[PDF] Prospeccion generada: {abs_path}")
    return abs_path


def _draw_seccion_header(pdf, numero: str, titulo: str):
    """Dibuja la cabecera numerada de una seccion (estilo PPTX RepagasConcept)."""
    pdf.ln(4)
    pdf.set_font(pdf._font, "B", 28)
    pdf.set_text_color(*PRIMARY)
    pdf.cell(0, 14, numero, align="L")
    pdf.ln(14)

    pdf.set_font(pdf._font, "B", 14)
    pdf.set_text_color(*PRIMARY)
    pdf.cell(0, 8, titulo)
    pdf.ln(10)

    pdf.set_draw_color(*PRIMARY)
    pdf.set_line_width(0.6)
    pdf.line(10, pdf.get_y(), 50, pdf.get_y())
    pdf.set_line_width(0.2)
    pdf.ln(6)


def _draw_qa(pdf, pregunta: str, respuesta):
    """Dibuja una pregunta y su respuesta en formato Q&A."""
    if pdf.get_y() > 260:
        pdf.add_page()

    if isinstance(respuesta, bool):
        valor_str = "Si" if respuesta else "No"
    elif isinstance(respuesta, list):
        valor_str = ", ".join(str(v) for v in respuesta) if respuesta else "-"
    elif respuesta in (None, "", []):
        valor_str = "-"
    else:
        valor_str = str(respuesta)

    pdf.set_font(pdf._font, "B", 9)
    pdf.set_text_color(*GRAY_700)
    pdf.set_x(12)
    pdf.multi_cell(186, 5, pregunta)
    pdf.ln(0.5)

    pdf.set_font(pdf._font, "", 10)
    pdf.set_text_color(*PRIMARY)
    pdf.set_x(12)
    pdf.multi_cell(186, 5.5, valor_str)
    pdf.ln(3)


def _fmt_list(v):
    if not v:
        return None
    if isinstance(v, list):
        return ", ".join(str(x) for x in v) if v else None
    return v


def _campos_tecnica_qa(data: dict) -> list:
    p = data.get("proyecto", {})
    t = data.get("parte_tecnica", {})
    desn = t.get("desniveles_suelo", {}) or {}
    accesos = t.get("dimensiones_accesos", {}) or {}

    qa = [
        ("Nombre del proyecto", p.get("nombre")),
        ("Tipo de negocio", p.get("tipo_negocio")),
        ("Concepto del negocio", p.get("concepto")),
        ("Numero de comensales por servicio", p.get("comensales")),
        ("Superficie disponible (m2)", p.get("superficie_m2")),
        ("Hay que disenar la cocina desde cero?", t.get("tipo_proyecto") == "nuevo"),
        ("Se trata de una renovacion de la cocina?", t.get("tipo_proyecto") == "renovacion"),
        ("Si es renovacion, hay que retirar la cocina antigua?", t.get("retirar_cocina_antigua")),
        ("Existe plano tecnico acotado del local?", t.get("existe_plano_tecnico")),
        ("Que medida hay desde el suelo al techo?", f"{t.get('altura_suelo_techo_m')} metros" if t.get("altura_suelo_techo_m") else None),
        ("Cual es el material de las paredes?", _fmt_list(t.get("material_paredes"))),
        ("Material del suelo?", t.get("material_suelo")),
        ("Hay desniveles en el suelo?", desn.get("existe")),
    ]
    if desn.get("existe") and desn.get("detalle"):
        qa.append(("Detalle de los desniveles", desn.get("detalle")))
    if accesos:
        for k, v in accesos.items():
            label = "Dimension " + k.replace("_", " ").replace(" m", " (m)")
            qa.append((label, v))
    return [q for q in qa if q[1] is not None]


def _campos_operativa_qa(data: dict) -> list:
    e = data.get("energia", {})
    n = data.get("necesidades_equipamiento", {})
    g = data.get("identidad_gastronomica", {})

    necesidades = []
    for zona, label in [("coccion", "Coccion"), ("refrigeracion", "Refrigeracion"),
                         ("lavado", "Lavado"), ("otros", "Otros")]:
        items = n.get(zona) or []
        if items:
            necesidades.append(f"{label}: {', '.join(items)}")

    qa = [
        ("Que necesidades de aparatos tiene el cliente?",
         "\n".join(necesidades) if necesidades else None),
        ("Tipo de energia principal?", e.get("tipo_energia")),
        ("Si es gas, que tipo de gas?", e.get("tipo_gas")),
        ("Caudal de gas disponible", e.get("caudal_gas_disponible")),
        ("Tipo de instalacion electrica?", e.get("tipo_electrico")),
        ("Potencia contratada en el local (kW)", e.get("potencia_contratada_kw")),
        ("Tiene preferencias de aparatos o colocacion?", n.get("preferencias_colocacion")),
        ("Marcas preferidas", _fmt_list(n.get("marcas_preferidas"))),
        ("Identidad de la cocina", g.get("identidad")),
        ("Tipo de cocina", g.get("tipo_cocina")),
        ("Estructura del menu", _fmt_list(g.get("estructura_menu"))),
        ("Cantidad de platos que ofrece", g.get("cantidad_platos")),
        ("Trabaja con ingredientes frescos. Cuales?", _fmt_list(g.get("ingredientes_frescos"))),
        ("Trabaja con congelados. Cuales?", _fmt_list(g.get("ingredientes_congelados"))),
        ("Trabaja con cuarta gama (pelados, cortados, envasados)?", _fmt_list(g.get("cuarta_gama"))),
        ("Trabaja con quinta gama (listos para calentar)?", _fmt_list(g.get("quinta_gama"))),
    ]
    return [q for q in qa if q[1] is not None]


def _campos_lavado_qa(data: dict) -> list:
    l = data.get("lavado", {})
    qa = [
        ("Cantidad de platos por servicio", l.get("platos")),
        ("Cantidad de vasos por servicio", l.get("vasos")),
        ("Cantidad de copas por servicio", l.get("copas")),
        ("Cantidad de cubiertos por servicio", l.get("cubiertos")),
        ("Cantidad de tazas por servicio", l.get("tazas")),
        ("Otros utensilios", _fmt_list(l.get("otros_utensilios"))),
        ("Consideraciones especiales (desagues, trampas de grasa, ventilacion)",
         _fmt_list(l.get("consideraciones"))),
    ]
    return [q for q in qa if q[1] is not None]


def _campos_refrigeracion_qa(data: dict) -> list:
    r = data.get("refrigeracion", {})
    qa = []
    gamas = [
        ("primera_gama", "Primera gama (producto fresco)"),
        ("segunda_gama", "Segunda gama (conservas)"),
        ("tercera_gama", "Tercera gama (congelados)"),
        ("cuarta_gama", "Cuarta gama (pelados, cortados)"),
        ("quinta_gama", "Quinta gama (listos para calentar)"),
    ]
    for key, label in gamas:
        gama = r.get(key, {}) or {}
        prods = gama.get("productos") or []
        if prods:
            qa.append((f"{label} - productos", ", ".join(prods)))
            kg = gama.get("kg_aproximados")
            if kg:
                qa.append((f"{label} - kilos aproximados", f"{kg} kg"))
            if key == "segunda_gama":
                qa.append(("Necesita estanterias para conservas?",
                          gama.get("necesita_estanterias")))
    return qa


def _campos_personal_qa(data: dict) -> list:
    p = data.get("personal", {})
    es = data.get("escalabilidad", {})
    f = data.get("formacion", {})
    qa = [
        ("Cuantas personas trabajan en cocina?", p.get("personas_en_cocina")),
        ("Roles del personal", _fmt_list(p.get("roles"))),
        ("Puede aumentar la carta en el futuro?", es.get("puede_ampliar_carta")),
        ("Hay espacio para anadir mas equipamiento?", es.get("espacio_mas_equipamiento")),
        ("La instalacion permitiria mas potencia o maquinaria?",
         es.get("instalacion_permite_mas_potencia")),
        ("Quiere recibir formacion sobre los aparatos?", f.get("requiere_formacion")),
        ("Equipos sobre los que necesita formacion", _fmt_list(f.get("equipos_formacion"))),
        ("Quiere visitar la fabrica antes de la propuesta?", data.get("visita_fabrica")),
    ]
    return [q for q in qa if q[1] is not None]


def _val(data: dict, *keys, default=None):
    """Accede a datos anidados."""
    d = data
    for k in keys:
        if isinstance(d, dict):
            d = d.get(k, default)
        else:
            return default
    return d


def _campos_proyecto(data: dict) -> list:
    p = data.get("proyecto", {})
    return [
        ("Nombre del proyecto", p.get("nombre")),
        ("Tipo de negocio", p.get("tipo_negocio")),
        ("Concepto", p.get("concepto")),
        ("Comensales por servicio", p.get("comensales")),
        ("Superficie (m2)", p.get("superficie_m2")),
        ("Presupuesto maximo (EUR)", p.get("presupuesto_max")),
    ]


def _campos_tecnica(data: dict) -> list:
    t = data.get("parte_tecnica", {})
    campos = [
        ("Tipo de proyecto", t.get("tipo_proyecto")),
        ("Retirar cocina antigua", t.get("retirar_cocina_antigua")),
        ("Existe plano tecnico", t.get("existe_plano_tecnico")),
        ("Altura suelo-techo (m)", t.get("altura_suelo_techo_m")),
        ("Material paredes", t.get("material_paredes")),
        ("Material suelo", t.get("material_suelo")),
    ]
    desn = t.get("desniveles_suelo", {})
    if desn:
        campos.append(("Desniveles", desn.get("existe")))
        if desn.get("detalle"):
            campos.append(("Detalle desniveles", desn.get("detalle")))
    accesos = t.get("dimensiones_accesos", {})
    if accesos:
        for k, v in accesos.items():
            label = k.replace("_", " ").replace("m", "(m)").title()
            campos.append((label, v))
    return campos


def _campos_energia(data: dict) -> list:
    e = data.get("energia", {})
    return [
        ("Tipo de energia", e.get("tipo_energia")),
        ("Tipo de gas", e.get("tipo_gas")),
        ("Caudal gas disponible", e.get("caudal_gas_disponible")),
        ("Tipo electrico", e.get("tipo_electrico")),
        ("Potencia contratada (kW)", e.get("potencia_contratada_kw")),
    ]


def _campos_equipamiento(data: dict) -> list:
    n = data.get("necesidades_equipamiento", {})
    return [
        ("Coccion", n.get("coccion")),
        ("Refrigeracion", n.get("refrigeracion")),
        ("Lavado", n.get("lavado")),
        ("Otros", n.get("otros")),
        ("Preferencias colocacion", n.get("preferencias_colocacion")),
        ("Marcas preferidas", n.get("marcas_preferidas")),
    ]


def _campos_gastronomica(data: dict) -> list:
    g = data.get("identidad_gastronomica", {})
    return [
        ("Identidad cocina", g.get("identidad")),
        ("Tipo de cocina", g.get("tipo_cocina")),
        ("Estructura menu", g.get("estructura_menu")),
        ("Cantidad de platos", g.get("cantidad_platos")),
        ("Ingredientes frescos", g.get("ingredientes_frescos")),
        ("Ingredientes congelados", g.get("ingredientes_congelados")),
    ]


def _campos_lavado(data: dict) -> list:
    l = data.get("lavado", {})
    return [
        ("Platos/servicio", l.get("platos")),
        ("Vasos/servicio", l.get("vasos")),
        ("Copas/servicio", l.get("copas")),
        ("Cubiertos/servicio", l.get("cubiertos")),
        ("Tazas/servicio", l.get("tazas")),
    ]


def _campos_refrigeracion(data: dict) -> list:
    r = data.get("refrigeracion", {})
    campos = []
    for gama, nombre in [("primera_gama", "1a Gama (frescos)"), ("segunda_gama", "2a Gama (conservas)"),
                         ("tercera_gama", "3a Gama (congelados)"), ("cuarta_gama", "4a Gama"),
                         ("quinta_gama", "5a Gama")]:
        g = r.get(gama, {})
        prods = g.get("productos", [])
        if prods:
            campos.append((nombre, prods))
            kg = g.get("kg_aproximados")
            if kg:
                campos.append((f"  Kg aproximados", kg))
    return campos


def _campos_personal(data: dict) -> list:
    p = data.get("personal", {})
    e = data.get("escalabilidad", {})
    f = data.get("formacion", {})
    return [
        ("Personas en cocina", p.get("personas_en_cocina")),
        ("Roles", p.get("roles")),
        ("Puede ampliar carta", e.get("puede_ampliar_carta")),
        ("Espacio para mas equipos", e.get("espacio_mas_equipamiento")),
        ("Instalacion permite mas potencia", e.get("instalacion_permite_mas_potencia")),
        ("Requiere formacion", f.get("requiere_formacion")),
        ("Visita fabrica", data.get("visita_fabrica")),
    ]


# ═══════════════════════════════════════════════════════════
#  PDF 3: PRESUPUESTO — Documento comercial para el cliente
# ═══════════════════════════════════════════════════════════

IVA_PORCENT = 21.0


def _cargar_textos_config() -> dict:
    """Carga textos personalizables desde la BD (tabla textos_config). Tolera fallos."""
    try:
        from core.database import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT clave, valor FROM textos_config")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return {r[0]: r[1] for r in rows}
    except Exception:
        return {}


def _modelo_en_lista(modelo: str, lista) -> bool:
    """Match case-insensitive (exacto o por prefijo) de modelo contra una lista."""
    if not lista:
        return False
    if modelo in lista:
        return True
    modelo_up = modelo.upper().strip()
    for clave in lista:
        clave_up = str(clave).upper().strip()
        if modelo_up == clave_up or modelo_up.startswith(clave_up):
            return True
    return False


def _resolver_descuento_modelo(
    modelo: str,
    individuales: dict,
    general: float,
    sin_descuento: list | None = None,
) -> float:
    """
    Devuelve el descuento (%) a aplicar a un modelo.
      - Si modelo esta en sin_descuento -> 0
      - Si esta en individuales -> ese %
      - Si no, descuento general
    Match case-insensitive (exacto o por prefijo) tanto para individuales
    como para sin_descuento.
    """
    if _modelo_en_lista(modelo, sin_descuento):
        return 0.0
    if not individuales:
        return general
    if modelo in individuales:
        return float(individuales[modelo] or 0)
    modelo_up = modelo.upper().strip()
    for clave, valor in individuales.items():
        clave_up = str(clave).upper().strip()
        if modelo_up == clave_up or modelo_up.startswith(clave_up):
            return float(valor or 0)
    return general


def generar_pdf_presupuesto(
    equipos: list,
    nombre_proyecto: str = "",
    datos_cliente: dict | None = None,
    filepath: str = "presupuesto.pdf",
    descuento_general: float = 0.0,
    descuentos_individuales: dict | None = None,
    sin_descuento: list | None = None,
) -> str:
    """
    Genera un presupuesto comercial para enviar al cliente.
    Incluye: datos del proyecto, tabla de equipos, descuentos, IVA y total.

    Args:
        descuento_general: porcentaje (0-100) de descuento aplicado por defecto.
        descuentos_individuales: dict {modelo: porcentaje} que sobrescribe el
            descuento general para los modelos especificados (match por prefijo).
        sin_descuento: lista de modelos a los que NO se aplica ningun descuento
            (ni el general ni el individual). Match por prefijo case-insensitive.
    """
    descuentos_individuales = descuentos_individuales or {}
    sin_descuento = sin_descuento or []
    abs_path = os.path.abspath(filepath)
    textos = _cargar_textos_config()
    try:
        iva_porcent = float(textos.get("presupuesto_iva_porcent") or IVA_PORCENT)
    except ValueError:
        iva_porcent = IVA_PORCENT
    try:
        validez_dias = int(textos.get("presupuesto_validez_dias") or 30)
    except ValueError:
        validez_dias = 30

    pdf = PropuestaPDF(nombre_proyecto)
    pdf.alias_nb_pages()
    pdf.add_page()

    # ── Titulo ──
    pdf.set_font(pdf._font, "B", 20)
    pdf.set_text_color(*PRIMARY)
    pdf.cell(0, 12, "Presupuesto", align="C")
    pdf.ln(14)

    # ── Datos del proyecto ──
    if datos_cliente:
        proy = datos_cliente.get("proyecto", {})
        filas_info = [
            ("Cliente / Proyecto", proy.get("nombre", "")),
            ("Tipo de negocio", (proy.get("tipo_negocio") or "").replace("_", " ").title()),
            ("Comensales", proy.get("comensales", "")),
            ("Fecha", datetime.now().strftime("%d/%m/%Y")),
        ]

        pdf.set_fill_color(*GRAY_50)
        pdf.set_draw_color(*GRAY_200)
        for label, valor in filas_info:
            pdf.set_font(pdf._font, "B", 9)
            pdf.set_text_color(*GRAY_500)
            pdf.set_x(12)
            pdf.cell(45, 6, label, border="B")
            pdf.set_font(pdf._font, "", 10)
            pdf.set_text_color(*GRAY_800)
            pdf.cell(0, 6, str(valor), border="B")
            pdf.ln(6.5)
        pdf.ln(6)
    else:
        pdf.set_font(pdf._font, "", 10)
        pdf.set_text_color(*GRAY_500)
        pdf.cell(0, 6, f"Fecha: {datetime.now().strftime('%d/%m/%Y')}")
        pdf.ln(10)

    # Linea
    pdf.set_draw_color(*PRIMARY)
    pdf.set_line_width(0.6)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.set_line_width(0.2)
    pdf.ln(6)

    # ── Tabla de equipos (horno se agrupa dentro de coccion) ──
    from collections import defaultdict
    _MERGE = {"horno": "coccion", "refrigeracion": "frio"}
    equipos_por_zona: dict[str, list] = defaultdict(list)
    for ep in equipos:
        zona = getattr(ep, "zona", None) or "coccion"
        zona = _MERGE.get(zona, zona)
        equipos_por_zona[zona].append(ep)

    zonas_ordenadas = [z for z in ["coccion", "lavado", "frio"] if z in equipos_por_zona]
    for z in equipos_por_zona:
        if z not in zonas_ordenadas:
            zonas_ordenadas.append(z)

    # Header tabla (con columna Dto si hay descuento general, individuales o exclusiones)
    mostrar_dto = descuento_general > 0 or bool(descuentos_individuales) or bool(sin_descuento)
    if mostrar_dto:
        col_w = [8, 75, 22, 14, 25, 18, 28]  # #, Desc, Dims, Uds, PVP, Dto%, Subtotal
        headers = ["#", "Descripcion", "Dimensiones", "Uds", "PVP Unit.", "Dto %", "Subtotal"]
    else:
        col_w = [8, 85, 25, 18, 27, 27]
        headers = ["#", "Descripcion", "Dimensiones", "Uds", "PVP Unit.", "Subtotal"]

    pdf.set_fill_color(*PRIMARY)
    pdf.set_text_color(*WHITE)
    pdf.set_font(pdf._font, "B", 8)
    x = 10
    for w, h_text in zip(col_w, headers):
        pdf.set_x(x)
        pdf.cell(w, 7, h_text, fill=True, align="C" if w < 40 else "L")
        x += w
    pdf.ln(7)

    num = 0
    gran_total = 0.0

    for zona in zonas_ordenadas:
        items = equipos_por_zona[zona]
        color = ZONA_COLORES.get(zona, GRAY_700)
        nombre_zona = ZONA_NOMBRES.get(zona, zona.upper())

        if pdf.get_y() > 250:
            pdf.add_page()
            # Re-header
            pdf.set_fill_color(*PRIMARY)
            pdf.set_text_color(*WHITE)
            pdf.set_font(pdf._font, "B", 8)
            x = 10
            for w, h_text in zip(col_w, headers):
                pdf.set_x(x)
                pdf.cell(w, 7, h_text, fill=True, align="C" if w < 40 else "L")
                x += w
            pdf.ln(7)

        # Barra de zona
        pdf.set_fill_color(*color)
        pdf.set_text_color(*WHITE)
        pdf.set_font(pdf._font, "B", 8)
        pdf.set_x(10)
        pdf.cell(sum(col_w), 6, f"  {nombre_zona.upper()}", fill=True)
        pdf.ln(6)

        zona_total = 0.0
        for i, ep in enumerate(items):
            num += 1
            if pdf.get_y() > 268:
                pdf.add_page()

            if i % 2 == 0:
                pdf.set_fill_color(*WHITE)
            else:
                pdf.set_fill_color(*GRAY_50)

            modelo = getattr(ep, "modelo", str(ep))
            w_mm = getattr(ep, "ancho_mm", 0) or 0
            d_mm = getattr(ep, "fondo_mm", 0) or 0
            cant = getattr(ep, "cantidad", 1) or 1
            pvp = getattr(ep, "pvp_eur", 0) or 0
            # sin_descuento -> 0; individuales sobrescribe general (match prefijo case-insensitive)
            dto_aplicado = _resolver_descuento_modelo(
                modelo, descuentos_individuales, descuento_general, sin_descuento
            )
            pvp_con_dto = pvp * (1 - dto_aplicado / 100) if mostrar_dto else pvp
            subtotal = pvp_con_dto * cant
            zona_total += subtotal

            dims = f"{int(w_mm)}x{int(d_mm)}" if w_mm and d_mm else ""

            x = 10
            row_h = 6

            pdf.set_font(pdf._font, "", 8)
            pdf.set_text_color(*GRAY_500)
            pdf.set_x(x)
            pdf.cell(col_w[0], row_h, str(num), fill=True, align="C")
            x += col_w[0]

            pdf.set_font(pdf._font, "B", 8)
            pdf.set_text_color(*GRAY_800)
            pdf.set_x(x)
            pdf.cell(col_w[1], row_h, modelo[:42], fill=True)
            x += col_w[1]

            pdf.set_font(pdf._font, "", 8)
            pdf.set_text_color(*GRAY_700)
            pdf.set_x(x)
            pdf.cell(col_w[2], row_h, dims, fill=True, align="C")
            x += col_w[2]

            pdf.set_x(x)
            pdf.cell(col_w[3], row_h, str(cant), fill=True, align="C")
            x += col_w[3]

            pdf.set_text_color(*GRAY_700)
            pdf.set_x(x)
            pdf.cell(col_w[4], row_h, f"{pvp:,.2f}" if pvp else "--", fill=True, align="R")
            x += col_w[4]

            if mostrar_dto:
                pdf.set_text_color(*color)
                pdf.set_x(x)
                pdf.cell(col_w[5], row_h, f"{dto_aplicado:.1f}%" if dto_aplicado else "--", fill=True, align="C")
                x += col_w[5]

            pdf.set_font(pdf._font, "B", 8)
            pdf.set_text_color(*color)
            pdf.set_x(x)
            pdf.cell(col_w[-1], row_h, f"{subtotal:,.2f}" if subtotal else "--", fill=True, align="R")
            pdf.ln(row_h)

        # Subtotal zona
        gran_total += zona_total
        pdf.set_fill_color(*GRAY_100)
        pdf.set_font(pdf._font, "B", 8)
        pdf.set_text_color(*color)
        merge_w = sum(col_w[:-1])
        pdf.set_x(10)
        pdf.cell(merge_w, 6, f"  Subtotal {nombre_zona}", fill=True, align="R")
        pdf.cell(col_w[-1], 6, f"{zona_total:,.2f} EUR" if zona_total else "--", fill=True, align="R")
        pdf.ln(7)

    # ── Totales finales ──
    if pdf.get_y() > 245:
        pdf.add_page()

    pdf.ln(2)
    total_w = sum(col_w)
    label_w = total_w - 40
    val_w = 40

    # Base imponible
    pdf.set_font(pdf._font, "", 9)
    pdf.set_text_color(*GRAY_700)
    pdf.set_x(10)
    pdf.cell(label_w, 7, "Base imponible", align="R")
    pdf.set_font(pdf._font, "B", 9)
    pdf.cell(val_w, 7, f"{gran_total:,.2f} EUR", align="R")
    pdf.ln(7)

    # IVA
    iva = gran_total * iva_porcent / 100
    pdf.set_font(pdf._font, "", 9)
    pdf.set_text_color(*GRAY_700)
    pdf.set_x(10)
    pdf.cell(label_w, 7, f"IVA ({iva_porcent:.0f}%)", align="R")
    pdf.set_font(pdf._font, "B", 9)
    pdf.cell(val_w, 7, f"{iva:,.2f} EUR", align="R")
    pdf.ln(8)

    # Total
    pdf.set_draw_color(*PRIMARY)
    pdf.set_line_width(0.8)
    pdf.line(120, pdf.get_y(), 200, pdf.get_y())
    pdf.set_line_width(0.2)
    pdf.ln(2)

    total_con_iva = gran_total + iva
    pdf.set_fill_color(*PRIMARY)
    pdf.set_text_color(*WHITE)
    pdf.set_font(pdf._font, "B", 12)
    pdf.set_x(10)
    pdf.cell(label_w, 10, "TOTAL (IVA incluido)", fill=True, align="R")
    pdf.cell(val_w, 10, f"{total_con_iva:,.2f} EUR", fill=True, align="R")
    pdf.ln(14)

    # Nota legal (configurable desde admin -> textos_config)
    pdf.set_font(pdf._font, "I", 7)
    pdf.set_text_color(*GRAY_500)
    intro = textos.get("presupuesto_intro") or "Presupuesto orientativo. Precios en EUR sin incluir transporte ni instalacion salvo indicacion contraria."
    condiciones = textos.get("presupuesto_condiciones") or (
        f"Validez: {validez_dias} dias desde la fecha de emision. "
        "Condiciones de pago: 50% a la confirmacion del pedido, 50% a la entrega. "
        "Plazo de entrega estimado: consultar."
    )
    pdf.multi_cell(0, 3.5, intro + " " + condiciones)

    pdf.output(abs_path)
    print(f"[PDF] Presupuesto generado: {abs_path}")
    return abs_path


# ─── CLI ─────────────────────────────────────────────────

if __name__ == "__main__":
    # Demo con equipos de prueba
    from features.planos.posicionar import EquipoPosicionado

    # (modelo, tipo, zona, ancho, fondo, alto, pvp, serie)
    tipos = [
        ("J-6-2", "fregadero", "coccion", 508, 393, 300, 0, ""),
        ("CG-720/M POW", "cocina_gas", "coccion", 400, 750, 900, 2500, "750"),
        ("FTG-71/M POW", "fry_top_gas", "coccion", 400, 750, 900, 1800, "750"),
        ("BARG-71/M PRO", "barbacoa", "coccion", 400, 847, 900, 2200, "750"),
        ("SMPG-225", "mesa_refrigerada", "lavado", 2242, 725, 850, 1500, "700"),
        ("SALIDA_700", "mesa_salida", "lavado", 700, 750, 850, 400, "700"),
        ("ARMARIO_1_700", "armario_conservacion", "lavado", 740, 733, 2100, 800, "700"),
        ("GS-83", "grifo", "lavado", 377, 747, 1200, 350, ""),
        ("LAVAVAJILLAS", "lavavajillas", "lavado", 599, 772, 1445, 3200, ""),
        ("B-2000", "botellero", "lavado", 2000, 550, 850, 900, ""),
        ("ARMARIO 1", "armario_conservacion", "frio", 740, 911, 2100, 1200, "700"),
        ("ARMARIO 2", "armario_congelacion", "frio", 740, 911, 2100, 1400, "700"),
    ]

    equipos = []
    for modelo, tipo, zona, w, d, h, pvp, serie in tipos:
        equipos.append(EquipoPosicionado(
            modelo=modelo, tipo=tipo, zona=zona,
            ancho_mm=w, fondo_mm=d, alto_mm=h,
            pvp_eur=pvp, serie=serie, cantidad=1,
            x=0, y=0, rotation=0, corners=None, wall_side="north",
        ))

    out = generar_pdf_propuesta(
        equipos,
        nombre_proyecto="Demo Bar",
        filepath="output/demo_PROPUESTA.pdf",
    )
    print(f"PDF: {out}")
