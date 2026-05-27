"""
Genera los archivos CAD demo (librería de bloques + plano de ejemplo) a partir
de los bloques definidos en `bloque_map.json`. Se ejecuta una vez para crear
los archivos `.dxf` que viven en este mismo directorio.

Uso:
    python demo_assets/_generar_assets.py

Salidas:
    demo_assets/demo_blocks.dxf       — libreria sintetica con rectangulos
    demo_assets/demo_floor_plan.dxf   — plano de ejemplo (10x6m)
"""
import json
from pathlib import Path

import ezdxf

ROOT = Path(__file__).resolve().parent


def cargar_bloques():
    with open(ROOT / "bloque_map.json", encoding="utf-8") as f:
        data = json.load(f)
    # Filtrar claves de metadatos (las que empiezan con _)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def generar_libreria(bloques: dict, salida: Path):
    """Crea un DXF con un bloque BLOCK por cada entrada del map."""
    doc = ezdxf.new(dxfversion="R2018", setup=True)
    doc.units = 4  # mm
    blocks = doc.blocks

    for nombre_bloque, info in bloques.items():
        if nombre_bloque in blocks:
            continue
        ancho = info["ancho"]
        fondo = info["fondo"]
        blk = blocks.new(name=nombre_bloque)
        # Rectangulo del footprint
        blk.add_lwpolyline(
            [(0, 0), (ancho, 0), (ancho, fondo), (0, fondo), (0, 0)],
            dxfattribs={"layer": "0", "color": 7},
        )
        # Diagonales para que se vea que es un equipo (estilo CAD demo)
        blk.add_line((0, 0), (ancho, fondo), dxfattribs={"layer": "0", "color": 8})
        blk.add_line((0, fondo), (ancho, 0), dxfattribs={"layer": "0", "color": 8})
        # Etiqueta con el nombre del bloque centrada
        blk.add_text(
            nombre_bloque,
            dxfattribs={
                "height": min(ancho, fondo) * 0.12,
                "color": 7,
                "insert": (ancho * 0.5, fondo * 0.5),
                "halign": 1,
                "valign": 2,
            },
        )

    doc.saveas(salida)
    print(f"[OK] {salida.name}: {len(bloques)} bloques")


def generar_plano(salida: Path):
    """Crea un plano de ejemplo: rectangulo 10x6m con paredes + 1 puerta."""
    doc = ezdxf.new(dxfversion="R2018", setup=True)
    doc.units = 4  # mm
    msp = doc.modelspace()

    # Capa de muros
    doc.layers.add(name="MUROS", color=7)
    doc.layers.add(name="PUERTAS", color=4)
    doc.layers.add(name="COTAS", color=8)

    # Boundary 10m x 6m
    w, h = 10000.0, 6000.0
    # Muros (sin puerta de 1.2m centrada en el sur)
    door_w = 1200.0
    door_start = (w - door_w) / 2
    door_end = door_start + door_w

    # Norte
    msp.add_line((0, h), (w, h), dxfattribs={"layer": "MUROS"})
    # Sur (con hueco para la puerta)
    msp.add_line((0, 0), (door_start, 0), dxfattribs={"layer": "MUROS"})
    msp.add_line((door_end, 0), (w, 0), dxfattribs={"layer": "MUROS"})
    # Este
    msp.add_line((w, 0), (w, h), dxfattribs={"layer": "MUROS"})
    # Oeste
    msp.add_line((0, 0), (0, h), dxfattribs={"layer": "MUROS"})

    # Puerta (arco simple)
    msp.add_arc(
        center=(door_start, 0),
        radius=door_w,
        start_angle=0,
        end_angle=90,
        dxfattribs={"layer": "PUERTAS"},
    )

    # Cotas como texto
    msp.add_text(
        "10000",
        dxfattribs={"height": 200, "color": 8, "insert": (w / 2 - 500, -500)},
    )
    msp.add_text(
        "6000",
        dxfattribs={"height": 200, "color": 8, "insert": (-800, h / 2)},
    )
    # Etiqueta de zona
    msp.add_text(
        "COCINA",
        dxfattribs={"height": 350, "color": 1, "insert": (w / 2 - 700, h / 2)},
    )

    doc.saveas(salida)
    print(f"[OK] {salida.name}: plano {w/1000:.0f}m x {h/1000:.0f}m con puerta sur")


def main():
    bloques = cargar_bloques()
    generar_libreria(bloques, ROOT / "demo_blocks.dxf")
    generar_plano(ROOT / "demo_floor_plan.dxf")


if __name__ == "__main__":
    main()
