# ocr-etiquetas

Extracción automática de códigos numéricos (18 dígitos, tipo SSCC/GS1) a partir de fotografías de etiquetas logísticas, usando OCR con redes neuronales ([EasyOCR](https://github.com/JaidedAI/EasyOCR)).

Pensado para lotes grandes de fotos tomadas con móvil: mala iluminación, etiquetas giradas, formato HEIC y cientos o miles de archivos que hay que procesar sin perder el trabajo si el proceso se interrumpe.

## Características

- **Tolerancia a errores del OCR.** Expresión regular flexible que acepta los caracteres que se confunden con dígitos (`O/0`, `I/1`, `S/5`, `B/8`…) y posterior normalización a dígitos.
- **Validación con dígito de control GS1.** Opción `--validar-sscc` para descartar lecturas erróneas mediante el módulo 10 del SSCC: basta un dígito mal leído para que el código se rechace.
- **Búsqueda multiángulo.** Prueba rotaciones de 0°, 90°, 180° y 270°, con ampliación y refuerzo de contraste configurables.
- **Modo rescate.** Segunda pasada agresiva (escala de grises y parámetros internos de EasyOCR forzados) para las imágenes que la pasada estándar no resuelve, registrando además el texto crudo leído para revisión manual.
- **Reanudación segura.** Los resultados se escriben en CSV incrementalmente; al relanzar el proceso se omiten los archivos ya tratados y no se generan duplicados.
- **Soporte HEIC/HEIF** además de los formatos habituales.

## Instalación

Requiere Python 3.10 o superior.

```bash
git clone https://github.com/<usuario>/ocr-etiquetas.git
cd ocr-etiquetas

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
pip install -e .                 # instala el comando `ocr-etiquetas`
```

> **GPU:** EasyOCR se apoya en PyTorch. Para acelerar por CUDA, instala la build de `torch` correspondiente a tu versión de CUDA antes de instalar las dependencias. Sin GPU, usa la opción `--cpu`.

## Uso

Procesar una carpeta completa:

```bash
ocr-etiquetas extraer ./fotos --salida resultados/codigos.csv
```

Con validación de dígito de control y sin GPU:

```bash
ocr-etiquetas extraer ./fotos -s resultados/codigos.csv --validar-sscc --cpu
```

Reanudar un lote interrumpido y reintentar solo lo que falló:

```bash
ocr-etiquetas extraer ./fotos -s resultados/codigos.csv --reintentar-fallidos
```

Pasada de rescate sobre imágenes concretas:

```bash
ocr-etiquetas rescate ./fotos -s resultados/rescate.csv -i IMG_0042.heic IMG_0117.jpg
```

También funciona sin instalar el paquete:

```bash
python -m ocr_etiquetas extraer ./fotos -s resultados/codigos.csv
```

### Opciones principales

| Opción | Descripción | Por defecto |
| --- | --- | --- |
| `--prefijo` | Prefijo conocido del código | `4260` |
| `--longitud` | Longitud total del código | `18` |
| `--validar-sscc` | Filtra por dígito de control GS1 | desactivado |
| `--angulos` | Rotaciones a probar (grados) | `0 90 180 270` |
| `--escala` | Factor de ampliación de la imagen | `2` |
| `--contraste` | Refuerzo de contraste | `1.5` |
| `--cpu` | Fuerza ejecución sin GPU | desactivado |
| `-v, --verboso` | Traza detallada | desactivado |

### Formato de salida

CSV con una fila por código detectado:

```csv
archivo,codigo,metodo,texto_ocr
IMG_0042.heic,426000123456789012,estandar,
IMG_0117.jpg,,sin_resultado,
```

La columna `metodo` distingue las lecturas estándar de las de rescate y marca los archivos sin resultado, que son los candidatos a revisión manual.

## Estructura del proyecto

```
src/ocr_etiquetas/
├── __init__.py      API pública del paquete
├── __main__.py      Punto de entrada `python -m ocr_etiquetas`
├── almacen.py       Persistencia en CSV y lógica de reanudación
├── cli.py           Interfaz de línea de comandos
├── limpieza.py      Normalización de caracteres y validación GS1
└── ocr.py           Preprocesado de imagen y extracción con EasyOCR
```

## Notas técnicas

El dígito de control del SSCC se calcula con el algoritmo módulo 10 de GS1: se ponderan los 17 primeros dígitos alternando 3 y 1, y el dígito de control es el complemento a la siguiente decena. Sirve como filtro de calidad muy eficaz frente a las confusiones típicas del OCR, aunque solo es aplicable si los códigos son realmente SSCC; por eso la validación es opcional.

## Pruebas

```bash
pip install pytest
PYTHONPATH=src pytest -q
```

## Hoja de ruta

- [x] Pruebas unitarias sobre limpieza y validación de códigos.
- [ ] Procesamiento por lotes en paralelo (multiproceso) para carpetas muy grandes.
- [ ] Detección previa de la región de la etiqueta para reducir el ruido de fondo.
- [ ] Informe resumen (tasa de acierto por método).

## Licencia

MIT — ver [LICENSE](LICENSE).

## Autor

**Sergio Antón** — Estudiante de Ingeniería Informática, Universidad de Zaragoza (España), 2026.
