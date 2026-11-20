#!/usr/bin/env python3
"""
leer_metadatos.py
-----------------
Lee y muestra los metadatos de una imagen satelital GeoTIFF (Sentinel-2 u otras),
con énfasis en ubicación geográfica y fecha de adquisición.

Uso:
    python3 leer_metadatos.py                    # usa la variable IMAGEN definida abajo
    python3 leer_metadatos.py mi_imagen.tif      # o pasa la ruta como argumento

Requiere: tifffile, numpy (ya instalados en el venv)
"""

import sys
import os
import re
import struct
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

# ─────────────────────────────────────────────
# ▶  VARIABLE PRINCIPAL: cambia aquí la imagen
# ─────────────────────────────────────────────
IMAGEN = "SENTINEL2_PRE_patagonia.tif"
# ─────────────────────────────────────────────

# Permite sobrescribir con argumento de línea de comandos
if len(sys.argv) > 1:
    IMAGEN = sys.argv[1]

IMAGEN = os.path.abspath(IMAGEN)

# ── Colores ANSI ──────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
MAGENTA= "\033[95m"
RED    = "\033[91m"
DIM    = "\033[2m"

def titulo(texto):
    ancho = 60
    print(f"\n{BOLD}{CYAN}{'─'*ancho}{RESET}")
    print(f"{BOLD}{CYAN}  {texto}{RESET}")
    print(f"{BOLD}{CYAN}{'─'*ancho}{RESET}")

def fila(etiqueta, valor, color=GREEN):
    print(f"  {DIM}{etiqueta:<30}{RESET} {color}{valor}{RESET}")

def aviso(texto):
    print(f"  {YELLOW}⚠  {texto}{RESET}")

# ── GeoKeys ───────────────────────────────────
MODELO_TIPO = {1: "Proyectado (UTM/otros)", 2: "Geográfico (lat/lon)", 3: "Geocéntrico"}
RASTER_TIPO = {1: "PixelIsArea", 2: "PixelIsPoint"}

# ── Funciones auxiliares ──────────────────────

def latlon_a_dms(grados, eje="lat"):
    """Convierte grados decimales a grados°minutos'segundos\" con cardinal."""
    cardinal_pos = "N" if eje == "lat" else "E"
    cardinal_neg = "S" if eje == "lat" else "O"
    cardinal = cardinal_pos if grados >= 0 else cardinal_neg
    grados = abs(grados)
    d = int(grados)
    m = int((grados - d) * 60)
    s = ((grados - d) * 60 - m) * 60
    return f"{d}°{m:02d}'{s:05.2f}\" {cardinal}"

def coordenadas_a_lugar(lon, lat):
    """Nombre aproximado de región según bounding box de Argentina/Sudamérica."""
    # Provincias/regiones argentinas por bbox aproximado
    regiones = [
        # (lat_min, lat_max, lon_min, lon_max, nombre)
        (-27.5, -25.5, -57.0, -53.0, "Misiones, Argentina"),
        (-28.5, -26.0, -59.0, -57.0, "Corrientes, Argentina"),
        (-34.7, -33.5, -59.0, -57.5, "Buenos Aires (Gran BA), Argentina"),
        (-39.0, -33.5, -63.5, -56.5, "Buenos Aires (provincia), Argentina"),
        (-32.0, -27.5, -69.5, -64.0, "Córdoba / La Rioja, Argentina"),
        (-55.0, -17.0, -82.0, -34.0, "Sudamérica"),
    ]
    for lat_min, lat_max, lon_min, lon_max, nombre in regiones:
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            return nombre
    return "Desconocida (fuera de Sudamérica o región no mapeada)"

def buscar_fechas_en_string(texto):
    """Busca patrones de fecha en texto libre."""
    patrones = [
        (r"\b(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})", "ISO 8601 completa"),
        (r"\b(\d{4})-(\d{2})-(\d{2})\b",                        "ISO 8601 fecha"),
        (r"\b(\d{8})T(\d{6})\b",                                 "compacta YYYYMMDDTHHMMSS"),
        (r"\b(\d{8})\b",                                         "compacta YYYYMMDD"),
    ]
    encontradas = []
    for patron, tipo in patrones:
        for m in re.finditer(patron, texto):
            encontradas.append((tipo, m.group()))
    return encontradas

def parsear_fecha(s):
    """Intenta parsear una cadena de fecha en varios formatos."""
    formatos = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y:%m:%d %H:%M:%S",
        "%Y-%m-%d",
        "%Y%m%dT%H%M%S",
        "%Y%m%d",
    ]
    for fmt in formatos:
        try:
            return datetime.strptime(s.strip()[:len(fmt)], fmt)
        except (ValueError, IndexError):
            pass
    return None

# ═══════════════════════════════════════════════════════════
#  INICIO
# ═══════════════════════════════════════════════════════════

print(f"\n{BOLD}{'═'*62}{RESET}")
print(f"{BOLD}  🛰  LECTOR DE METADATOS DE IMAGEN SATELITAL{RESET}")
print(f"{BOLD}{'═'*62}{RESET}")

# ── 0. Verificar archivo ──────────────────────
if not os.path.exists(IMAGEN):
    print(f"\n{RED}✗ Archivo no encontrado: {IMAGEN}{RESET}\n")
    sys.exit(1)

try:
    import tifffile
    import numpy as np
except ImportError as e:
    print(f"\n{RED}✗ Dependencia faltante: {e}{RESET}")
    print("  Instalá con: ./bin/pip install tifffile numpy\n")
    sys.exit(1)

# ── 1. Info básica del archivo ────────────────
titulo("📁  ARCHIVO")
st = os.stat(IMAGEN)
fila("Ruta",         IMAGEN)
fila("Nombre",       os.path.basename(IMAGEN))
fila("Tamaño",       f"{st.st_size / (1024**2):.1f} MB  ({st.st_size:,} bytes)")
fila("Modificado",   datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S (hora local)"))

# ── 2. Abrir con tifffile ─────────────────────
tif = tifffile.TiffFile(IMAGEN)
p0  = tif.pages[0]
tags = p0.tags

titulo("🖼  CARACTERÍSTICAS DE LA IMAGEN")
fila("Ancho (píxeles)",    str(tags[256].value) if 256 in tags else "—")
fila("Alto  (píxeles)",    str(tags[257].value) if 257 in tags else "—")
fila("Bandas espectrales", str(tags[277].value) if 277 in tags else "—")
fila("Bits por muestra",   str(tags[258].value) if 258 in tags else "—")

compresion_map = {1:"Sin compresión", 5:"LZW", 6:"JPEG (antiguo)", 7:"JPEG",
                  8:"Deflate/ZIP", 32773:"PackBits", 34925:"LZMA", 50000:"ZSTD"}
comp = tags[259].value if 259 in tags else 1
fila("Compresión",         compresion_map.get(comp, f"Código {comp}"))
fila("Páginas/niveles",    str(len(tif.pages)))

# Formato de muestra
sf_map = {1:"uint", 2:"int", 3:"float32", 6:"float_complejo"}
sf = tags[339].value[0].value if 339 in tags else 1
formato_legible = {1:"Entero sin signo (uint)", 2:"Entero con signo (int)",
                   3:"Punto flotante 32-bit (float32)"}.get(sf, f"Código {sf}")
fila("Tipo de dato",       formato_legible)

# Nombre de bandas desde GDAL_METADATA
bandas_nombres = []
tag_gdal = tags.get(42112)
if tag_gdal:
    xml_str = tag_gdal.value
    try:
        root = ET.fromstring(xml_str)
        for item in root.findall("Item"):
            if item.get("role") == "description":
                bandas_nombres.append(item.text)
    except ET.ParseError:
        pass
if bandas_nombres:
    fila("Bandas (nombres)", ", ".join(bandas_nombres))

# ── 3. Sistema de referencia y coordenadas ────
titulo("📌  UBICACIÓN GEOGRÁFICA")

geo_meta = tif.geotiff_metadata if hasattr(tif, "geotiff_metadata") and tif.geotiff_metadata else {}

# Tipo de modelo
model_type = None
if "GTModelTypeGeoKey" in geo_meta:
    mt = geo_meta["GTModelTypeGeoKey"]
    model_type = mt.value if hasattr(mt, "value") else mt
    nombre_modelo = MODELO_TIPO.get(model_type, str(mt))
    fila("Tipo de modelo",    nombre_modelo)

# CRS
crs_code = None
if "GeographicTypeGeoKey" in geo_meta:
    crs = geo_meta["GeographicTypeGeoKey"]
    crs_code = crs.value if hasattr(crs, "value") else crs
    fila("CRS / Datum",       f"EPSG:{crs_code}  ({geo_meta.get('GeogCitationGeoKey', '')})")
elif "ProjectedCSTypeGeoKey" in geo_meta:
    crs = geo_meta["ProjectedCSTypeGeoKey"]
    crs_code = crs.value if hasattr(crs, "value") else crs
    fila("CRS proyectado",    f"EPSG:{crs_code}")

if "GeogSemiMajorAxisGeoKey" in geo_meta:
    fila("Semi-eje mayor",    f"{geo_meta['GeogSemiMajorAxisGeoKey']:.3f} m (WGS-84)")

# Píxel y tiepoint → bounding box
scale   = geo_meta.get("ModelPixelScale")    # [dx, dy, 0]
tiept   = geo_meta.get("ModelTiepoint")      # [i,j,k, lon,lat,0]

if scale and tiept and len(tiept) >= 6:
    dx, dy = scale[0], scale[1]
    lon0 = tiept[3]   # lon de la esquina superior izquierda
    lat0 = tiept[4]   # lat de la esquina superior izquierda
    ncols = tags[256].value if 256 in tags else 0
    nrows = tags[257].value if 257 in tags else 0

    lon_min = lon0
    lon_max = lon0 + ncols * dx
    lat_max = lat0
    lat_min = lat0 - nrows * dy

    lon_centro = (lon_min + lon_max) / 2
    lat_centro = (lat_min + lat_max) / 2

    print()
    fila("Esquina NO (sup-izq)", f"{latlon_a_dms(lat_max, 'lat')}  {latlon_a_dms(lon_min, 'lon')}")
    fila("Esquina NE (sup-der)", f"{latlon_a_dms(lat_max, 'lat')}  {latlon_a_dms(lon_max, 'lon')}")
    fila("Esquina SO (inf-izq)", f"{latlon_a_dms(lat_min, 'lat')}  {latlon_a_dms(lon_min, 'lon')}")
    fila("Esquina SE (inf-der)", f"{latlon_a_dms(lat_min, 'lat')}  {latlon_a_dms(lon_max, 'lon')}")
    print()
    fila("Centro (lat, lon)",    f"{lat_centro:.6f}°,  {lon_centro:.6f}°")
    fila("Centro DMS",           f"{latlon_a_dms(lat_centro, 'lat')}  {latlon_a_dms(lon_centro, 'lon')}")
    print()
    fila("Lat rango",            f"{lat_min:.6f}° → {lat_max:.6f}°  ({abs(lat_max-lat_min)*111:.1f} km aprox.)")
    fila("Lon rango",            f"{lon_min:.6f}° → {lon_max:.6f}°  ({abs(lon_max-lon_min)*111*abs(np.cos(np.radians(lat_centro))):.1f} km aprox.)")
    fila("Resolución espacial",  f"{dy * 111_000:.1f} m/píxel aprox. (N-S)")

    region = coordenadas_a_lugar(lon_centro, lat_centro)
    fila("Región estimada",      region, color=MAGENTA)

    # Link Google Maps
    maps_url = f"https://www.google.com/maps/@{lat_centro:.5f},{lon_centro:.5f},9z"
    fila("Ver en Google Maps",   maps_url, color=CYAN)
else:
    aviso("No se encontró GeoTransform (tiepoint + pixelscale). La imagen puede no estar georreferenciada.")

# ── 4. Fecha de adquisición ───────────────────
titulo("📅  FECHA DE ADQUISICIÓN SATELITAL")

fechas_encontradas = []

# 4a. Tag TIFF DateTime (306)
dt_tag = tags.get(306)
if dt_tag:
    f = parsear_fecha(str(dt_tag.value))
    if f:
        fechas_encontradas.append(("Tag TIFF DateTime", f))

# 4b. GDAL_METADATA XML
if tag_gdal:
    xml_str = tag_gdal.value
    hits = buscar_fechas_en_string(xml_str)
    for tipo, s in hits:
        f = parsear_fecha(s)
        if f:
            fechas_encontradas.append((f"GDAL XML ({tipo})", f))

# 4c. ImageDescription (270)
img_desc = tags.get(270)
if img_desc:
    hits = buscar_fechas_en_string(str(img_desc.value))
    for tipo, s in hits:
        f = parsear_fecha(s)
        if f:
            fechas_encontradas.append((f"ImageDescription ({tipo})", f))

# 4d. Nombre del archivo
hits = buscar_fechas_en_string(os.path.basename(IMAGEN))
for tipo, s in hits:
    f = parsear_fecha(s)
    if f and f.year > 1990:
        fechas_encontradas.append((f"Nombre de archivo ({tipo})", f))

# 4e. Buscar en todos los tags de texto
for tag in tags.values():
    if tag.code in (256, 257, 258, 259, 277, 324, 325):  # skip large numeric tags
        continue
    try:
        val_str = str(tag.value)
        if len(val_str) > 1000:
            continue
        hits = buscar_fechas_en_string(val_str)
        for tipo, s in hits:
            f = parsear_fecha(s)
            if f and f.year > 1990:
                key = f"Tag {tag.code} ({tag.name}) — {tipo}"
                # Evitar duplicados
                if not any(x[1] == f for x in fechas_encontradas):
                    fechas_encontradas.append((key, f))
    except Exception:
        pass

if fechas_encontradas:
    for fuente, f in fechas_encontradas:
        fila(fuente, f.strftime("%Y-%m-%d  %H:%M:%S  UTC") + f"  →  {f.strftime('%d de %B de %Y')}", color=YELLOW)
else:
    aviso("No se encontró fecha de adquisición en los metadatos embebidos.")
    aviso("El nombre del archivo ('POST') sugiere imagen post-evento.")
    aviso("Revisá el nombre original del producto Sentinel-2 (ej. S2A_MSIL2A_20230815...)")
    aviso("o el archivo MTD_MSIL2A.xml de la carpeta .SAFE original.")

# 4f. Info del archivo (fecha de creación/modificación del archivo)
print()
fila("Archivo creado/mod.",
     datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
     color=DIM)
aviso("(Fecha del archivo en disco — NO es la fecha de captura satelital)")

# ── 5. Resumen técnico ────────────────────────
titulo("🔧  RESUMEN TÉCNICO")
fila("Sensor",         "Sentinel-2 (inferido por bandas B1–B12)")
fila("Tipo producto",  "POST-evento (inferido del nombre)")
fila("Formato",        "GeoTIFF / Cloud-Optimized GeoTIFF (COG)")
fila("Proyección",     "WGS 84 — EPSG:4326 (geográfico)")
fila("Mosaico/tiles",  f"Tiles internos de {tags[322].value if 322 in tags else '?'}×{tags[323].value if 323 in tags else '?'} píxeles")

print(f"\n{BOLD}{'═'*62}{RESET}\n")
