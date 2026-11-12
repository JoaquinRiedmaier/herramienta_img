#!/usr/bin/env python3
"""
Herramienta de terminal para imágenes:
  1) Quitar fondo + convertir a WebP
  2) Solo convertir a WebP (con compresión configurable)
La imagen resultante se guarda en la misma carpeta que la original.
Para la opción 2, se pedirá un nivel de compresión (1-100) al convertir.
Por defecto es 1 (máxima compresión).

Si la ruta termina en /* (por ejemplo /home/user/fotos/*), se procesan todas
las imágenes de esa carpeta con formatos aceptados:
png, jpg, jpeg, jfif, bmp, gif, tif, tiff, webp. Anda de lujo pa!
"""

from pathlib import Path
from PIL import Image

QUALITY = 90  # calidad WebP (1-100)
EXTENSIONES = {".png", ".jpg", ".jpeg", ".jfif", ".bmp", ".gif", ".tif", ".tiff", ".webp"}


def limpiar_ruta(texto: str) -> Path:
    """Quita comillas/espacios que se agregan al arrastrar una ruta a la terminal."""
    texto = texto.strip().replace('"', "").replace("'", "")
    return Path(texto).expanduser()


def pedir_ruta() -> tuple[Path, bool] | None:
    """Pide una ruta y devuelve (ruta, lote).

    lote es True cuando la ruta termina en /*: en ese caso ruta es la carpeta.
    """
    ruta = limpiar_ruta(input("\nRuta de la imagen (o carpeta/* para procesar todas): "))
    texto = str(ruta)
    if texto in ("", "."):
        return None

    # Modo lote: carpeta/* -> todas las imágenes de la carpeta
    if texto.endswith("/*"):
        carpeta = Path(texto[:-2] or "/")
        if not carpeta.is_dir():
            print(f"✗ No se encontró la carpeta: {carpeta}")
            return None
        return carpeta, True

    if not ruta.is_file():
        if ruta.is_dir():
            print(f"✗ '{ruta}' es una carpeta: agregá /* al final para procesar todas sus imágenes.")
        else:
            print(f"✗ No se encontró el archivo: {ruta}")
        return None
    return ruta, False


def listar_imagenes(carpeta: Path) -> list[Path]:
    """Lista (ordenada) las imágenes de la carpeta con un formato aceptado."""
    return sorted(
        p for p in carpeta.iterdir()
        if p.is_file() and p.suffix.lower() in EXTENSIONES
    )


def ruta_salida(origen: Path, sufijo: str = "") -> Path:
    destino = origen.with_name(f"{origen.stem}{sufijo}.webp")
    # Evita pisar el original si ya es .webp
    if destino == origen:
        destino = origen.with_name(f"{origen.stem}{sufijo}_nuevo.webp")
    return destino


def pedir_compresion() -> int:
    """Pide el nivel de compresión (1-100, por defecto 1 = máxima compresión)."""
    while True:
        nivel = input("Nivel de compresión (1-100, 1=máxima compresión, Enter=1 por defecto): ").strip()
        if nivel == "":
            return 1
        try:
            compression = int(nivel)
            if 1 <= compression <= 100:
                return compression
            print("✗ El valor debe estar entre 1 y 100")
        except ValueError:
            print("✗ Ingrese un número válido")


def convertir_webp(origen: Path, compression: int) -> None:
    destino = ruta_salida(origen)
    with Image.open(origen) as img:
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if "A" in img.mode or "transparency" in img.info else "RGB")
        img.save(destino, "WEBP", quality=compression, method=6)
    print(f"✓ Guardada en: {destino} (compresión: {compression})")


def quitar_fondo_y_webp(origen: Path) -> None:
    print("Procesando... (la primera vez descarga el modelo, puede tardar)")
    from rembg import remove  # import tardío: es pesado

    destino = ruta_salida(origen, "_sin_fondo")
    with Image.open(origen) as img:
        resultado = remove(img.convert("RGBA"))
    resultado.save(destino, "WEBP", quality=QUALITY, method=6)
    print(f"✓ Guardada en: {destino}")


def main() -> None:
    while True:
        print("\n=== Herramienta de imágenes ===")
        print("1) Quitar fondo y convertir a WebP")
        print("2) Solo convertir a WebP")
        print("0) Salir")
        opcion = input("Elige una opción: ").strip()

        if opcion == "0":
            print("¡Hasta luego!")
            break
        if opcion not in ("1", "2"):
            print("✗ Opción no válida.")
            continue

        pedido = pedir_ruta()
        if pedido is None:
            continue
        ruta, lote = pedido

        # El nivel de compresión se pide una sola vez, aunque sea un lote
        compression = pedir_compresion() if opcion == "2" else None

        imagenes = listar_imagenes(ruta) if lote else [ruta]
        if lote and not imagenes:
            print(f"✗ No hay imágenes con formatos aceptados en: {ruta}")
            continue

        errores = 0
        for i, origen in enumerate(imagenes, start=1):
            if lote:
                print(f"\n[{i}/{len(imagenes)}] {origen.name}")
            try:
                if opcion == "1":
                    quitar_fondo_y_webp(origen)
                else:
                    convertir_webp(origen, compression)
            except Exception as e:
                errores += 1
                print(f"✗ Error al procesar {origen.name}: {e}")

        if lote:
            print(f"\nListo: {len(imagenes) - errores} de {len(imagenes)} imágenes procesadas.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelado.")
