#!/usr/bin/env python3
"""
separar_bandas.py
-----------------
Separa una imagen satelital GeoTIFF multibanda en archivos TIF individuales,
uno por banda, conservando la georreferenciación y los metadatos GeoTIFF.

Nombre de salida: <nombre_original>_<BANDA>.tif
Ejemplo:  SENTINEL2_POST_misiones.tif  →  SENTINEL2_POST_misiones_B4.tif

MODO DE SALIDA (variable MODO):
  'float32'  → valores originales de reflectancia (0.0–1.0)
               Solo legible en QGIS/GDAL. NO abre en GNOME ni visores comunes.
  'uint16'   → escala a 0–10000 (estándar Sentinel-2 L2A)
               Abre en QGIS. Algunos visores avanzados.
  'uint8'    → escala a 0–255, normalizado por percentil
               Abre en GNOME, Zed, Eye of GNOME, cualquier visor. ✔

Uso:
    python3 separar_bandas.py                    # usa las variables definidas abajo
    python3 separar_bandas.py mi_imagen.tif      # pasa la ruta como argumento

Requiere: tifffile, numpy (venv) + libtiff.so del sistema.
"""

import sys
import os
import struct
import ctypes
import xml.etree.ElementTree as ET
import numpy as np
import tifffile

# ─────────────────────────────────────────────────────────────
# ▶  CONFIGURACIÓN: ajustá estas variables según tus necesidades
# ─────────────────────────────────────────────────────────────
IMAGEN = "SENTINEL2_POST_misiones.tif"

# Modo de salida: 'uint8' | 'uint16' | 'float32'
# uint8  → abre en cualquier visor (GNOME, Zed, etc.)  ← recomendado para visualizar
# uint16 → estándar Sentinel-2, solo visores GIS (QGIS, etc.)
# float32→ valores originales de reflectancia, solo GIS/científico
MODO = "uint16"

# Percentil de recorte para normalización (solo aplica a uint8 y uint16)
# 2/98 elimina extremos y mejora el contraste visual
PERCENTIL_MIN = 2
PERCENTIL_MAX = 98
# ─────────────────────────────────────────────────────────────

if len(sys.argv) > 1:
    IMAGEN = sys.argv[1]
if len(sys.argv) > 2:
    MODO = sys.argv[2]

IMAGEN = os.path.abspath(IMAGEN)

# ── Colores ANSI ──────────────────────────────
RESET  = "\033[0m"; BOLD   = "\033[1m"; CYAN  = "\033[96m"
GREEN  = "\033[92m"; YELLOW = "\033[93m"; RED  = "\033[91m"
DIM    = "\033[2m"
CHECK  = f"{GREEN}✔{RESET}"; CROSS = f"{RED}✘{RESET}"
ARROW  = f"{CYAN}→{RESET}"

def ok(msg):   print(f"  {CHECK} {msg}")
def warn(msg): print(f"  {YELLOW}⚠  {msg}{RESET}")
def err(msg):  print(f"  {CROSS} {RED}{msg}{RESET}")
def titulo(t):
    print(f"\n{BOLD}{CYAN}{'─'*58}{RESET}")
    print(f"{BOLD}{CYAN}  {t}{RESET}")
    print(f"{BOLD}{CYAN}{'─'*58}{RESET}")

print(f"\n{BOLD}{'═'*60}{RESET}")
print(f"{BOLD}  🛰  SEPARADOR DE BANDAS — GeoTIFF Multibanda{RESET}")
print(f"{BOLD}{'═'*60}{RESET}")

if MODO not in ("float32", "uint16", "uint8"):
    err(f"MODO inválido: '{MODO}'. Usá 'float32', 'uint16' o 'uint8'.")
    sys.exit(1)

# ── Verificar archivo ─────────────────────────
if not os.path.exists(IMAGEN):
    err(f"Archivo no encontrado: {IMAGEN}")
    sys.exit(1)

dir_salida  = os.path.dirname(IMAGEN)
nombre_base = os.path.splitext(os.path.basename(IMAGEN))[0]

titulo("📂  ARCHIVO DE ENTRADA")
print(f"  {DIM}Ruta:{RESET}             {IMAGEN}")
print(f"  {DIM}Carpeta de salida:{RESET} {dir_salida}")
print(f"  {DIM}Tamaño:{RESET}           {os.path.getsize(IMAGEN) / (1024**2):.1f} MB")
print(f"  {DIM}Modo de salida:{RESET}   {BOLD}{MODO}{RESET}", end="")
if MODO == "uint8":
    print(f"  {GREEN}← abre en GNOME, Zed, cualquier visor{RESET}")
elif MODO == "uint16":
    print(f"  {YELLOW}← solo visores GIS (QGIS, etc.){RESET}")
else:
    print(f"  {YELLOW}← solo aplicaciones científicas/GIS{RESET}")

# ── libtiff vía ctypes ────────────────────────
try:
    _lib = ctypes.CDLL("libtiff.so.6")
except OSError:
    err("No se encontró libtiff.so.6. Instalá con: sudo pacman -S libtiff")
    sys.exit(1)

_lib.TIFFOpen.restype             = ctypes.c_void_p
_lib.TIFFOpen.argtypes            = [ctypes.c_char_p, ctypes.c_char_p]
_lib.TIFFClose.restype            = ctypes.c_void_p
_lib.TIFFClose.argtypes           = [ctypes.c_void_p]
_lib.TIFFNumberOfTiles.restype    = ctypes.c_uint32
_lib.TIFFNumberOfTiles.argtypes   = [ctypes.c_void_p]
_lib.TIFFTileSize.restype         = ctypes.c_int64
_lib.TIFFTileSize.argtypes        = [ctypes.c_void_p]
_lib.TIFFReadEncodedTile.restype  = ctypes.c_int64
_lib.TIFFReadEncodedTile.argtypes = [ctypes.c_void_p, ctypes.c_uint32,
                                      ctypes.c_void_p, ctypes.c_int64]

# ── Leer metadatos con tifffile ───────────────
titulo("📖  LEYENDO METADATOS")

tif_meta = tifffile.TiffFile(IMAGEN)
p0       = tif_meta.pages[0]
tags     = p0.tags

n_bandas = tags[277].value if 277 in tags else 1
ancho    = tags[256].value
alto     = tags[257].value
tile_w   = tags[322].value if 322 in tags else ancho
tile_h   = tags[323].value if 323 in tags else alto
src_dtype = p0.dtype

tiles_x = -(-ancho // tile_w)
tiles_y = -(-alto  // tile_h)

print(f"  {DIM}Dimensiones:{RESET}  {ancho} × {alto} píxeles")
print(f"  {DIM}Bandas:{RESET}       {n_bandas}")
print(f"  {DIM}Tile size:{RESET}    {tile_w} × {tile_h} px ({tiles_x}×{tiles_y} = {tiles_x*tiles_y} tiles)")
print(f"  {DIM}Tipo original:{RESET} {src_dtype}")

# Nombres de bandas
nombres_bandas = []
tag_gdal = tags.get(42112)
if tag_gdal:
    try:
        root = ET.fromstring(tag_gdal.value)
        for item in root.findall("Item"):
            if item.get("role") == "description":
                nombres_bandas.append(item.text)
    except ET.ParseError:
        pass
if len(nombres_bandas) != n_bandas:
    warn("Nombres de bandas no encontrados. Usando 'Band_N'.")
    nombres_bandas = [f"Band_{i+1}" for i in range(n_bandas)]
else:
    print(f"  {DIM}Bandas:{RESET}       {', '.join(nombres_bandas)}")

# Tags GeoTIFF
tag_pixel_scale = tags.get(33550)
tag_tiepoint    = tags.get(33922)
tag_geodir      = tags.get(34735)
tag_geodbl      = tags.get(34736)
tag_geoasc      = tags.get(34737)
tag_nodata      = tags.get(42113)

def _build_extratags(nombre_banda: str, nodata_val=None) -> list:
    xml = (
        f'<GDALMetadata>\n'
        f'  <Item name="DESCRIPTION" sample="0" role="description">{nombre_banda}</Item>\n'
    )
    if nodata_val is not None:
        xml += f'  <Item name="NODATA">{nodata_val}</Item>\n'
    xml += '</GDALMetadata>'
    extra = []
    if tag_pixel_scale:
        v = tag_pixel_scale.value
        extra.append((33550, 12, len(v), struct.pack(f"<{len(v)}d", *v), True))
    if tag_tiepoint:
        v = tag_tiepoint.value
        extra.append((33922, 12, len(v), struct.pack(f"<{len(v)}d", *v), True))
    if tag_geodir:
        v = tag_geodir.value
        extra.append((34735, 3,  len(v), struct.pack(f"<{len(v)}H", *v), True))
    if tag_geodbl:
        v = tag_geodbl.value
        extra.append((34736, 12, len(v), struct.pack(f"<{len(v)}d", *v), True))
    if tag_geoasc:
        v = tag_geoasc.value.encode("ascii")
        extra.append((34737, 2, len(v), v, True))
    extra.append((42112, 2, len(xml), xml.encode("utf-8"), True))
    return extra

# ── Cargar imagen completa con libtiff ────────
titulo("💾  CARGANDO IMAGEN VÍA libtiff (C nativo)")

tif_c   = _lib.TIFFOpen(IMAGEN.encode(), b"r")
n_tiles = _lib.TIFFNumberOfTiles(tif_c)
tile_sz = _lib.TIFFTileSize(tif_c)

print(f"  Tiles: {n_tiles}  |  Bytes/tile (sin compresión): {tile_sz:,}")

buf     = (ctypes.c_uint8 * tile_sz)()
imagen  = np.zeros((n_bandas, alto, ancho), dtype=np.float32)

tile_idx = 0
for ty in range(tiles_y):
    y0 = ty * tile_h
    py = min(tile_h, alto - y0)
    for tx in range(tiles_x):
        x0 = tx * tile_w
        px = min(tile_w, ancho - x0)
        _lib.TIFFReadEncodedTile(tif_c, tile_idx, buf, tile_sz)
        tile_arr = np.frombuffer(buf, dtype=np.float32).reshape(tile_h, tile_w, n_bandas)
        imagen[:, y0:y0+py, x0:x0+px] = np.moveaxis(tile_arr[:py, :px, :], -1, 0)
        tile_idx += 1

_lib.TIFFClose(tif_c)
print(f"  Imagen en RAM: {imagen.shape}  |  dtype: {imagen.dtype}")

# ── Calcular percentiles para normalización ───
if MODO in ("uint8", "uint16"):
    titulo(f"📊  CALCULANDO PERCENTILES (p{PERCENTIL_MIN}–p{PERCENTIL_MAX}) POR BANDA")
    pmin_por_banda = []
    pmax_por_banda = []
    for i, nb in enumerate(nombres_bandas):
        banda = imagen[i]
        valid = banda[banda > 0]
        if len(valid) == 0:
            pmin_por_banda.append(0.0)
            pmax_por_banda.append(1.0)
        else:
            p_lo = float(np.percentile(valid, PERCENTIL_MIN))
            p_hi = float(np.percentile(valid, PERCENTIL_MAX))
            pmin_por_banda.append(p_lo)
            pmax_por_banda.append(p_hi)
        print(f"  {nb:<6} p{PERCENTIL_MIN}={pmin_por_banda[-1]:.4f}  p{PERCENTIL_MAX}={pmax_por_banda[-1]:.4f}")

# ── Función de conversión ─────────────────────
def _convertir(banda_f32: np.ndarray, idx: int):
    """Convierte una banda float32 al tipo de salida elegido."""
    if MODO == "float32":
        return banda_f32, np.float32, None

    lo = pmin_por_banda[idx]
    hi = pmax_por_banda[idx]
    if hi <= lo:
        hi = lo + 1e-6

    # Reemplazar NaN/inf antes de normalizar
    banda_f32 = np.nan_to_num(banda_f32, nan=0.0, posinf=hi, neginf=0.0)

    # Recortar y normalizar a [0, 1]
    normalizado = np.clip((banda_f32 - lo) / (hi - lo), 0.0, 1.0)

    if MODO == "uint16":
        # Escala a 0–10000 (estándar Sentinel-2 L2A)
        out = (normalizado * 10000).astype(np.uint16)
        return out, np.uint16, 0
    else:  # uint8
        out = (normalizado * 255).astype(np.uint8)
        return out, np.uint8, 0

# ── Separar y guardar bandas ──────────────────
titulo(f"✂️  GENERANDO {n_bandas} ARCHIVOS TIF ({MODO})")
print()

archivos_ok  = []
archivos_err = []

for i, nombre_banda in enumerate(nombres_bandas):
    nombre_salida = f"{nombre_base}_{nombre_banda}.tif"
    ruta_salida   = os.path.join(dir_salida, nombre_salida)

    print(f"  {ARROW} {BOLD}{nombre_banda:<5}{RESET}", end="  ", flush=True)

    try:
        banda_conv, out_dtype, nodata_val = _convertir(imagen[i], i)

        # Parámetros de escritura según tipo
        photometric = "minisblack"
        tifffile.imwrite(
            ruta_salida,
            banda_conv,
            photometric=photometric,
            compression="deflate",
            compressionargs={"level": 6},
            tile=(256, 256),
            extratags=_build_extratags(nombre_banda, nodata_val),
        )

        size_mb = os.path.getsize(ruta_salida) / (1024**2)
        print(f"{CHECK}  {DIM}{size_mb:.1f} MB{RESET}  {DIM}{nombre_salida}{RESET}")
        archivos_ok.append(ruta_salida)

    except Exception as e:
        print(f"{CROSS} {RED}{e}{RESET}")
        archivos_err.append(nombre_banda)

# ── Resumen ───────────────────────────────────
titulo("📊  RESUMEN")
print(f"  Bandas generadas:  {BOLD}{GREEN}{len(archivos_ok)}{RESET} de {n_bandas}")
if archivos_err:
    warn(f"Bandas con error: {', '.join(archivos_err)}")

total_mb = sum(os.path.getsize(f) / (1024**2) for f in archivos_ok)
print(f"  Espacio total:     {total_mb:.1f} MB")
print(f"  Formato de salida: {BOLD}{MODO}{RESET}")
print(f"  Carpeta:           {dir_salida}")

if MODO == "uint8":
    print(f"\n  {GREEN}✔ Los archivos abren en GNOME Loupe, Eye of GNOME, Zed y cualquier visor.{RESET}")
elif MODO == "uint16":
    print(f"\n  {YELLOW}⚠ uint16: compatible con QGIS/GDAL. Puede no abrir en visores básicos.{RESET}")
else:
    print(f"\n  {YELLOW}⚠ float32: solo para aplicaciones GIS/científicas (QGIS, Python, etc.).{RESET}")

print(f"\n{BOLD}{'═'*60}{RESET}")
print(f"{BOLD}{GREEN}  ✔  Separación completada.{RESET}")
print(f"{BOLD}{'═'*60}{RESET}\n")
