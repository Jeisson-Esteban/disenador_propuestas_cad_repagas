"""
Conversor DWG -> DXF usando ODA File Converter o LibreDWG (fallback).

Uso:
    from features.planos.conversion import dwg_a_dxf
    dxf_path = dwg_a_dxf("plano_cliente.dwg")

    # O desde linea de comandos:
    python convertir_dwg.py plano_cliente.dwg
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

# Rutas conocidas de ODA File Converter en Windows
ODA_PATHS = [
    r"C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe",
    r"C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe",
    r"C:\Program Files (x86)\ODA\ODAFileConverter\ODAFileConverter.exe",
]


def _find_oda() -> str | None:
    """Encuentra el ejecutable de ODA File Converter."""
    for p in ODA_PATHS:
        if os.path.isfile(p):
            return p
    # Intentar con ezdxf addon
    try:
        from ezdxf.addons import odafc
        exe = getattr(odafc, "exe_path", None) or getattr(odafc, "_oda_fc_exe", None)
        if exe and os.path.isfile(exe):
            return exe
    except Exception:
        pass
    return None


def _find_libredwg(tool: str = "dwg2dxf") -> str | None:
    """Encuentra un ejecutable de LibreDWG (dwg2dxf o dxf2dwg)."""
    exe = shutil.which(tool)
    if exe:
        return exe
    for p in [f"/usr/bin/{tool}", f"/usr/local/bin/{tool}"]:
        if os.path.isfile(p):
            return p
    return None


def _convertir_con_oda(dwg_path: str, output_dir: str, version: str) -> str:
    """Convierte DWG a DXF usando ODA File Converter."""
    oda_exe = _find_oda()
    if not oda_exe:
        raise FileNotFoundError("ODA File Converter no disponible")

    with tempfile.TemporaryDirectory(prefix="dwg2dxf_") as tmp_input:
        tmp_output = tempfile.mkdtemp(prefix="dwg2dxf_out_")
        try:
            dwg_name = os.path.basename(dwg_path)
            shutil.copy2(dwg_path, os.path.join(tmp_input, dwg_name))

            cmd = [
                oda_exe,
                tmp_input,      # Input folder
                tmp_output,     # Output folder
                version,        # Output version
                "DXF",          # Output type
                "0",            # Recurse: 0=no
                "1",            # Audit: 1=yes
            ]

            print(f"  [ODA] Convirtiendo {dwg_name} -> DXF ({version})...")
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60,
            )

            dxf_name = Path(dwg_name).stem + ".dxf"
            dxf_tmp = os.path.join(tmp_output, dxf_name)

            if not os.path.isfile(dxf_tmp):
                stderr = result.stderr or result.stdout or "sin output"
                raise RuntimeError(f"ODA no genero el DXF. Output: {stderr}")

            dxf_final = os.path.join(output_dir, dxf_name)
            shutil.move(dxf_tmp, dxf_final)
            return dxf_final

        finally:
            shutil.rmtree(tmp_output, ignore_errors=True)


def _convertir_con_libredwg(dwg_path: str, output_dir: str) -> str:
    """Convierte DWG a DXF usando LibreDWG (dwg2dxf)."""
    dwg2dxf = _find_libredwg("dwg2dxf")
    if not dwg2dxf:
        raise FileNotFoundError("LibreDWG (dwg2dxf) no disponible")

    dwg_name = os.path.basename(dwg_path)
    dxf_name = Path(dwg_name).stem + ".dxf"
    dxf_final = os.path.join(output_dir, dxf_name)

    cmd = [dwg2dxf, "-o", dxf_final, dwg_path]
    print(f"  [LibreDWG] Convirtiendo {dwg_name} -> DXF...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    print(f"  [LibreDWG] returncode={result.returncode}")
    if result.stdout:
        print(f"  [LibreDWG] stdout: {result.stdout[:500]}")
    if result.stderr:
        print(f"  [LibreDWG] stderr: {result.stderr[:500]}")

    if not os.path.isfile(dxf_final):
        raise RuntimeError(f"LibreDWG no genero el DXF (returncode={result.returncode})")

    size_kb = os.path.getsize(dxf_final) / 1024
    if size_kb < 1:
        raise RuntimeError(f"LibreDWG genero DXF vacio ({size_kb:.2f}KB)")

    return dxf_final


def dwg_a_dxf(dwg_path: str, output_dir: str | None = None, version: str = "ACAD2018") -> str:
    """
    Convierte un archivo DWG a DXF.
    Intenta ODA File Converter primero, luego LibreDWG como fallback.

    Args:
        dwg_path: Ruta al archivo .dwg de entrada
        output_dir: Directorio de salida (default: mismo directorio que el DWG)
        version: Version DXF de salida (ACAD2010, ACAD2013, ACAD2018)

    Returns:
        Ruta absoluta del archivo DXF generado

    Raises:
        FileNotFoundError: Si el DWG no existe o no hay conversor disponible
        RuntimeError: Si la conversion falla
    """
    dwg_path = os.path.abspath(dwg_path)
    if not os.path.isfile(dwg_path):
        raise FileNotFoundError(f"Archivo DWG no encontrado: {dwg_path}")

    if output_dir is None:
        output_dir = os.path.dirname(dwg_path)
    os.makedirs(output_dir, exist_ok=True)

    # Intentar ODA primero (mejor calidad)
    try:
        dxf_final = _convertir_con_oda(dwg_path, output_dir, version)
        size_kb = os.path.getsize(dxf_final) / 1024
        print(f"  DXF generado (ODA): {dxf_final} ({size_kb:.0f}KB)")
        return dxf_final
    except FileNotFoundError:
        print("  ODA File Converter no encontrado, intentando LibreDWG...")
    except RuntimeError as e:
        print(f"  ODA fallo ({e}), intentando LibreDWG...")

    # Fallback: LibreDWG
    try:
        dxf_final = _convertir_con_libredwg(dwg_path, output_dir)
        size_kb = os.path.getsize(dxf_final) / 1024
        print(f"  DXF generado (LibreDWG): {dxf_final} ({size_kb:.0f}KB)")
        return dxf_final
    except FileNotFoundError:
        raise FileNotFoundError(
            "No hay conversor DWG disponible. "
            "Instala ODA File Converter o LibreDWG (apt install libredwg-tools)"
        )
    except RuntimeError as e:
        raise RuntimeError(f"LibreDWG tambien fallo: {e}")


def _convertir_dxf_a_dwg_con_oda(dxf_path: str, output_dir: str, version: str) -> str:
    """Convierte DXF a DWG usando ODA File Converter."""
    oda_exe = _find_oda()
    if not oda_exe:
        raise FileNotFoundError("ODA File Converter no disponible")

    with tempfile.TemporaryDirectory(prefix="dxf2dwg_") as tmp_input:
        tmp_output = tempfile.mkdtemp(prefix="dxf2dwg_out_")
        try:
            dxf_name = os.path.basename(dxf_path)
            shutil.copy2(dxf_path, os.path.join(tmp_input, dxf_name))
            cmd = [oda_exe, tmp_input, tmp_output, version, "DWG", "0", "1"]
            print(f"  [ODA] Convirtiendo {dxf_name} -> DWG ({version})...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            dwg_name = Path(dxf_name).stem + ".dwg"
            dwg_tmp = os.path.join(tmp_output, dwg_name)
            if not os.path.isfile(dwg_tmp):
                stderr = result.stderr or result.stdout or "sin output"
                raise RuntimeError(f"ODA no genero el DWG. Output: {stderr}")

            dwg_final = os.path.join(output_dir, dwg_name)
            shutil.move(dwg_tmp, dwg_final)
            return dwg_final
        finally:
            shutil.rmtree(tmp_output, ignore_errors=True)


def _convertir_dxf_a_dwg_con_libredwg(dxf_path: str, output_dir: str) -> str:
    """Convierte DXF a DWG usando LibreDWG (dxf2dwg)."""
    dxf2dwg = _find_libredwg("dxf2dwg")
    if not dxf2dwg:
        raise FileNotFoundError("LibreDWG (dxf2dwg) no disponible")

    dxf_name = os.path.basename(dxf_path)
    dwg_name = Path(dxf_name).stem + ".dwg"
    dwg_final = os.path.join(output_dir, dwg_name)

    cmd = [dxf2dwg, "-o", dwg_final, dxf_path]
    print(f"  [LibreDWG] Convirtiendo {dxf_name} -> DWG...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    print(f"  [LibreDWG] returncode={result.returncode}")
    if result.stdout:
        print(f"  [LibreDWG] stdout: {result.stdout[:500]}")
    if result.stderr:
        print(f"  [LibreDWG] stderr: {result.stderr[:500]}")

    if not os.path.isfile(dwg_final):
        raise RuntimeError(f"LibreDWG no genero el DWG (returncode={result.returncode})")

    return dwg_final


def dxf_a_dwg(dxf_path: str, output_dir: str | None = None, version: str = "ACAD2018") -> str:
    """
    Convierte un archivo DXF a DWG.
    Intenta ODA File Converter primero, luego LibreDWG como fallback.
    """
    dxf_path = os.path.abspath(dxf_path)
    if not os.path.isfile(dxf_path):
        raise FileNotFoundError(f"Archivo DXF no encontrado: {dxf_path}")

    if output_dir is None:
        output_dir = os.path.dirname(dxf_path)
    os.makedirs(output_dir, exist_ok=True)

    try:
        dwg_final = _convertir_dxf_a_dwg_con_oda(dxf_path, output_dir, version)
        size_kb = os.path.getsize(dwg_final) / 1024
        print(f"  DWG generado (ODA): {dwg_final} ({size_kb:.0f}KB)")
        return dwg_final
    except FileNotFoundError:
        print("  ODA no encontrado, intentando LibreDWG...")
    except RuntimeError as e:
        print(f"  ODA fallo ({e}), intentando LibreDWG...")

    try:
        dwg_final = _convertir_dxf_a_dwg_con_libredwg(dxf_path, output_dir)
        size_kb = os.path.getsize(dwg_final) / 1024
        print(f"  DWG generado (LibreDWG): {dwg_final} ({size_kb:.0f}KB)")
        return dwg_final
    except FileNotFoundError:
        raise FileNotFoundError(
            "No hay conversor DXF->DWG disponible. "
            "Instala ODA File Converter o libredwg-tools."
        )
    except RuntimeError as e:
        raise RuntimeError(f"LibreDWG tambien fallo: {e}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python convertir_dwg.py <archivo.dwg> [directorio_salida]")
        sys.exit(1)

    dwg = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None
    try:
        dxf = dwg_a_dxf(dwg, output_dir=out)
        print(f"\nConversión exitosa: {dxf}")
    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)
