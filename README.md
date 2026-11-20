# Imagen Tool - Herramienta de Procesamiento de Imágenes por Terminal

Esta herramienta permite realizar tareas avanzadas de manipulación y conversión de imágenes (como quitar fondos o comprimir) directamente desde la línea de comandos.

## Guía de Instalación y Configuración

Sigue estos pasos para configurar el entorno virtual y tener `imagen_tool` listo para usar.

**1. Crear el Entorno Virtual:**
Asegúrate de estar en el directorio raíz del proyecto (`/home/johnd/Imágenes/CONVERT`). Ejecuta el siguiente comando para crear un entorno aislado:

```bash
python3 -m venv .venv
```

**2. Activar el Entorno:**
Debes activar el entorno virtual cada vez que vayas a trabajar con la herramienta:

```bash
source .venv/bin/activate
```
*(Verás `(.venv)` al inicio de tu prompt, indicando que está activo).*

**3. Instalar Dependencias:**
Instala todas las librerías necesarias para el funcionamiento del proyecto (incluyendo Pillow y rembg):

```bash
pip install -r requirements.txt
```

## 🛠️ Uso de la Herramienta (`imagen_tool`)

Una vez que el entorno está activo, puedes ejecutar la herramienta con:

```bash
python imagen_tool.py
```

El script te presentará un menú interactivo para elegir la operación deseada.

### Tipos de Entrada (Input)

La herramienta es flexible y acepta dos tipos de rutas:

1.  **Imagen Única:** Proporciona la ruta completa a un archivo (`/ruta/foto.jpg`).
2.  **Carpeta Completa (Batch):** Si proporcionas una ruta que termina en `/*` (ej: `/home/user/fotos/*`), el script procesará **todas** las imágenes soportadas dentro de esa carpeta.

### ⚙️ Opciones Disponibles

Al ejecutar la herramienta, selecciona una opción del menú:

#### 1️⃣ Quitar Fondo y Convertir a WebP
*   **Función:** Utiliza modelos avanzados para detectar y eliminar el fondo de la imagen.
*   **Salida:** La imagen resultante se guardará en la misma carpeta que la original con un sufijo `_sin_fondo` y formato `.webp`.

#### 2️⃣ Solo Convertir a WebP (Compresión) Recomendable 50 o 45, Conserva calidad y reduce tamaño
*   **Función:** Convierte el archivo de cualquier formato soportado a WebP.
*   **Configuración:** Se te pedirá un **Nivel de Compresión** (un número entre 1 y 100). Recuerda que:
    *   `1`: Máxima compresión (mejor reducción de tamaño, posible pérdida de calidad) ES LA OPCION POR DEFECTO.
    *   `90-100`: Menor compresión (mayor fidelidad visual, archivo más grande).

---
**Soportados:** PNG, JPG, JPEG, JFIF, BMP, GIF, TIF, TIFF, WEBP.
**Salida por defecto:** Los archivos procesados se guardarán en la misma carpeta que el original.
