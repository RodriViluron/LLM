# Ajustes de Ollama y LM Studio (problema 27)

Referencia práctica para decidir la configuración de **notebook (4 GB de VRAM)** para la presentación y **escritorio (8 GB de VRAM)**.  
Versión revisada en el proyecto: **Ollama `0.40.16`** con el modelo **`qwen3:4b`** (`Q4_K_M`, 2,5 GB) y embeddings **`bge-m3`** (1,2 GB), medido en **NVIDIA GeForce RTX 5060 Ti (8 GB)** en las pruebas `#22`, `#27` y `#28`.

> Se distingue explícitamente qué valores fueron **medidos** en el hardware de prueba y cuáles quedan como **recomendación sin medir**.

---

## Tabla comparativa de parámetros

| Parámetro | Dónde se configura en Ollama | Dónde se configura en LM Studio | Existe en Ollama 0.40.16 | Estado | Efecto medido / Nota |
|---|---|---|---|---|---|
| Tamaño de contexto (`num_ctx`) | `MODEL_NUM_CTX` en `.env` (`ChatOllama(num_ctx=...)`) o `OLLAMA_CONTEXT_LENGTH` en el servidor | *Context Length* al cargar el modelo | Sí | **Medido** (`#22`/`#27`, caché `f16`) | `8192 → 3,9 GB` VRAM; `16384 → 5,1 GB` VRAM; `32768 → 7,9 GB` VRAM (en 8 GB se vuelca a CPU y genera **8× más lento**). |
| Caché KV comprimida + Flash Attention | Variables de entorno del servidor: `OLLAMA_KV_CACHE_TYPE` y `OLLAMA_FLASH_ATTENTION=1` | *K/V Cache Quantization* (`Q8_0`/`Q4_0`), *Flash Attention* y *Offload KV Cache to GPU* | Sí (verificado en `ollama serve --help` y `server config`) | **Medido** (`#22`/`#27`, en `8192`) | Con `OLLAMA_FLASH_ATTENTION=1`: `f16` `3,9 GB` → `q8_0` `3,3 GB` → `q4_0` `3,0 GB` VRAM, a la misma velocidad. |
| Control / tope de razonamiento | `MODEL_RAZONAMIENTO` en `.env` (`ChatOllama(reasoning=...)`), `/no_think`, `num_predict` | Opciones de *Reasoning* y *Max Tokens* | Sí (Ollama acepta el parámetro) | **Medido** (`#28`, temp. `0`, misma pregunta) | Ninguno acota a `qwen3:4b`: `think=true` `1.391` tok; `think=false` `1.670` tok (razona igual dentro del texto); `think="low"/"high"` `1.670`/`1.670` tok; `/no_think` `1.158` tok; `num_predict=300` corta a los 300 tok dejando respuesta vacía. Alternativa sin medir: `qwen3:4b-instruct-2507`. |
| Permanencia en memoria (`keep_alive`) | `OLLAMA_KEEP_ALIVE` en el servidor o `MODEL_KEEP_ALIVE` en `.env` (lo pasa `model.py`) | *Model TTL* / *Idle Timeouts* del servidor | Sí (`ollama serve --help`) | **Parcialmente medido** (`#27`) | La **carga en frío** se midió entre **2 y 6 s** (`#27`). Mantenerlo indefinidamente con `OLLAMA_KEEP_ALIVE=-1` (o `MODEL_KEEP_ALIVE=-1`) es **recomendación sin medir**. |
| Pedidos en paralelo | Variable de entorno `OLLAMA_NUM_PARALLEL` | *Max Concurrent Predictions* + *Unified KV Cache* | Sí (`ollama serve --help`) | **Sin medir** | Cada slot paralelo reserva su propia caché KV en VRAM; para 4 GB conviene fijar `1`. |
| Capas en GPU (`num_gpu`) | `MODEL_NUM_GPU` en `.env` (lo pasa `model.py`) o `PARAMETER num_gpu N` en `Modelfile` | Slider *GPU Offload* al cargar el modelo | Sí | **Sin medir** | En 4 GB, conviene dejar el LLM 100 % en GPU y mover el modelo de embeddings (`bge-m3`) a CPU (`PARAMETER num_gpu 0`) para que no compitan por la VRAM. |
| Cuantización del modelo | Etiqueta del modelo al descargar (ej. `qwen3:4b` = `Q4_K_M`, vs `qwen3:4b-q8_0`) | Selección del archivo GGUF al descargar | Sí | **Sin medir** | Hoy usamos `Q4_K_M` (2,5 GB). Probar `Q8_0` (~4,3 GB) queda **pendiente de descarga** (`ollama pull qwen3:4b-q8_0`, no ejecutado; no entra completo en 4 GB). |

---

## Recomendación concreta para la notebook de 4 GB de VRAM

En 4 GB de VRAM el margen es muy justo: `qwen3:4b` en `Q4_K_M` con ventana `8192` ocupa **3,3 GB** con caché `q8_0` (**3,0 GB** con `q4_0`), medido en `#22`/`#27`. Además, el recorte automático del historial en `agente.py` (`historial_en_contexto`, `#22`) permite trabajar con `MODEL_NUM_CTX=8192` sin perder fuentes ni desbordar la ventana.

### 1. Variables de entorno del proyecto (`.env`) y servidor Ollama

- **Medido (`#22` y `#27`):**
  ```env
  MODEL_NUM_CTX=8192
  OLLAMA_FLASH_ATTENTION=1
  OLLAMA_KV_CACHE_TYPE=q8_0
  ```
  *(Si en la notebook Windows + escritorio/navegador consumen demasiada VRAM y el modelo no entra en GPU, bajar a `OLLAMA_KV_CACHE_TYPE=q4_0`, medido en **3,0 GB** en lugar de **3,3 GB**.)*

- **Recomendación sin medir (ajustes de servidor Ollama antes de iniciar la demo):**
  ```env
  OLLAMA_NUM_PARALLEL=1
  OLLAMA_KEEP_ALIVE=-1
  ```
  - `OLLAMA_NUM_PARALLEL=1` evita multiplicar la caché KV por pedidos simultáneos.
  - `OLLAMA_KEEP_ALIVE=-1` mantiene el modelo cargado en VRAM durante toda la presentación y evita la carga en frío medida de 2 a 6 s.

### 2. Mover los embeddings (`bge-m3`) a CPU *(recomendación sin medir)*

`bge-m3` pesa ~1,2 GB: si queda cargado en VRAM junto con `qwen3:4b` (3,0–3,3 GB), supera los 4 GB y obliga a descargar/volcar capas del chat a CPU. Se recomienda crear una variante en CPU mediante `Modelfile`:

```text
FROM bge-m3
PARAMETER num_gpu 0
```

Crear la variante y configurarla en `.env` (sin modificar código):

```powershell
ollama create bge-m3-cpu -f Modelfile
```

```env
EMBEDDINGS_MODEL=bge-m3-cpu
```

### 3. Verificación antes de presentar *(recomendación sin medir)*

Con el chat en marcha (después de hacer una consulta normal), correr en consola:

```powershell
ollama ps
```

Confirmar que la fila de `qwen3:4b` indique **`100% GPU`** en la columna de procesador (si dice algo de CPU, pasar `OLLAMA_KV_CACHE_TYPE` de `q8_0` a `q4_0`, reiniciar Ollama y cerrar pestañas pesadas/aplicaciones que usen aceleración gráfica).

---

## Referencia para escritorio de 8 GB de VRAM

- Con 8 GB entran juntos `qwen3:4b` y `bge-m3` en GPU con margen.
- Se puede usar `MODEL_NUM_CTX=8192` o subir a `16384` (**5,1 GB** medidos con `f16`; menos con `OLLAMA_KV_CACHE_TYPE=q8_0` + `OLLAMA_FLASH_ATTENTION=1`).
- **No** usar `32768` en 8 GB: medido en `#22` en **7,9 GB**, donde vuelca a CPU y genera **8× más lento**.
