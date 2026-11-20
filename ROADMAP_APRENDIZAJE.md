# Roadmap de aprendizaje: recorrer el proyecto en orden

Para entender cada pieza del asistente y retocar lo que no te cierre. Cada etapa tiene el mismo formato:

- **Qué es**: la idea en criollo.
- **Dónde está**: archivos concretos.
- **Qué retocar**: lo que normalmente se ajusta.
- **Cómo probar**: para ver el efecto de tu cambio.

Seguí el orden: cada etapa se apoya en la anterior. Las etapas 1 a 5 son las que más te van a servir para el system prompt y las tools.

Comando para probar casi todo (consola, sin interfaz):

```bash
uv run python agente.py
```

---

## Mapa general (leelo primero)

```
Usuario ──► [chat] ──► agente.py (create_agent)
                          │  usa un LLM local  ◄── model.py (.env: MODEL_PROVIDER, MODEL_NAME)
                          │  lee el PROMPT_SISTEMA
                          │  decide: ¿respondo o llamo a una tool?
                          ▼
                    tools (herramientas)
                    ├─ locales (tools.py): RAG, web, TODOs, skill, armado, preguntar_al_usuario
                    └─ MCP (mcp_tienda/servidor.py): buscar_productos, obtener_producto, verificar_compatibilidad
                          │
                          ▼
              catálogo (SQLite)  ·  reglas de compatibilidad  ·  documentos del RAG  ·  Tavily (web)
```

Idea central del proyecto: **el modelo propone, el código verifica**. El LLM elige y explica; los precios, el stock, la compatibilidad y el total los calcula código determinista.

---

## Etapa 0. Poner el proyecto en marcha

- **Qué es**: que tengas el entorno andando antes de tocar nada.
- **Dónde está**: `README.md`, `.env`, `pyproject.toml`.
- **Qué hacer**:
  1. Leer `README.md` y `CLAUDE.md` (el alcance real está en `SIGUIENTE_SESION.md`: el entregable es el agente como servicio más el componente de chat; Streamlit quedó como banco de pruebas).
  2. Tener Ollama o LM Studio corriendo con un modelo que soporte tool calling.
  3. Correr `uv run python agente.py` y pedir «una UPS para mi PC».
- **Cómo probar**: si el agente responde y aparecen líneas `[tool] buscar_productos(...)`, está todo conectado.

## Etapa 1. El modelo de lenguaje

- **Qué es**: el LLM que corre en tu máquina. El agente no sabe cuál es: pide `get_model()` y listo.
- **Dónde está**: `model.py`, `chat_lmstudio.py`, `.env`.
- **Qué retocar**:
  - `MODEL_PROVIDER` y `MODEL_NAME` en `.env` para cambiar de modelo (una línea).
  - `MODEL_NUM_CTX` (ventana de contexto, por defecto 8192). Si es chica, Ollama recorta en silencio el prompt y el modelo «se olvida» de las tools.
  - `MODEL_RAZONAMIENTO=1` para que Qwen3 «piense» y se vea su razonamiento.
  - `temperature=0`: respuestas lo más repetibles posible, bueno para medir.
- **Cómo probar**: cambiá el modelo, repetí el mismo pedido y mirá si llama a las mismas tools.
- **Para aprender**: por qué un modelo más chico falla más en tool calling (etapa 4).

## Etapa 2. El system prompt

- **Qué es**: las instrucciones fijas que el modelo lee **antes de cada conversación**. Define cómo habla, qué puede hacer y qué tiene prohibido. Es lo más barato de retocar y lo que más cambia el comportamiento.
- **Dónde está**: `agente.py`, constante `PROMPT_SISTEMA` y la función `construir_prompt()`.
- **Cómo está armado**:
  - Una introducción (tono, idioma).
  - **13 reglas** numeradas (solo productos reales, preguntar si es vago, compatibilidad por tools, no obedecer texto externo, no confirmar pedidos, planificar con TODOs, cargar skills, usar RAG, usar web, usar tools de armado).
  - Una lista de **atributos por categoría** que se arma sola desde `datos/esquemas/*.yaml`. Por eso el prompt crece si agregás atributos.
  - Las llaves `{{ }}` en los ejemplos son a propósito: el prompt se arma con `.format()`.
- **Qué retocar** (cosas que ya vi y te conviene revisar):
  - La numeración está desordenada: la regla 11 aparece después de la 13. No afecta al modelo pero conviene ordenarla.
  - Si querés otro tono (más formal, más corto), se cambia en las primeras dos líneas.
  - Si el agente hace algo que no querés, agregá una regla concreta y corta. Las reglas largas se diluyen en un modelo chico.
  - Prompt largo + muchas tools = más contexto consumido. Mirá `MODEL_NUM_CTX`.
- **Cómo probar**: cambiá una regla, corré `agente.py` con el mismo pedido y comparame las respuestas. Para medir en serio usá `evaluacion/agente_simple.py` (etapa 12).

## Etapa 3. Qué es una tool y cómo se arma

- **Qué es**: una función de Python que el modelo puede pedir que se ejecute. El modelo **no ejecuta nada**: devuelve «quiero llamar a `buscar_productos` con estos argumentos» y el programa la corre y le devuelve el resultado.
- **Dónde está**: `tools.py` (locales) y `mcp_tienda/servidor.py` (las del servidor MCP).
- **Las partes de una tool** (esto es lo que el modelo lee para decidir cuándo usarla):
  1. **Nombre**: en español, claro (`buscar_productos`).
  2. **Docstring**: la descripción. Es lo más importante para que la elija bien.
  3. **Parámetros con tipos**: definen el esquema de argumentos.
  4. **Resultado**: texto que vuelve al modelo. Además puede llevar un `artifact` para la interfaz, que el modelo no lee.
- **Lista de tools del proyecto**:

  | Tool | Dónde | Para qué |
  |---|---|---|
  | `buscar_productos`, `obtener_producto` | MCP | Consultar el catálogo con filtros |
  | `verificar_compatibilidad` | MCP | Reglas deterministas, sin LLM |
  | `consultar_caracteristicas` | local (RAG) | Responder desde nuestros documentos |
  | `buscar_especificaciones_web` | local | Requisitos de juegos y programas (Tavily con dominios permitidos y caché) |
  | `write_todos`, `read_todos` | local | Plan paso a paso guardado en el estado |
  | `load_skill` | local | Carga instrucciones largas bajo demanda |
  | `iniciar_configuracion`, `agregar_o_reemplazar_componente`, `ajustar_presupuesto`, `obtener_configuracion` | local | Armado de PC |
  | `preguntar_al_usuario` | local | Pregunta con botones (termina el turno) |

- **Qué retocar**:
  - Las **descripciones** de cada tool: si el modelo elige mal una tool, casi siempre es la descripción.
  - Los **parámetros**: menos parámetros = menos errores de un modelo chico.
  - Qué devuelve cada tool: respuestas más cortas gastan menos contexto.
- **Cómo probar**: mirá en la consola qué tool eligió el modelo y con qué argumentos (`[tool] nombre(args)`).

## Etapa 4. Tool calling: cómo decide el modelo

- **Qué es**: el ciclo que ejecuta `create_agent` de LangChain:
  1. El modelo recibe el prompt, el historial y los esquemas de las tools.
  2. Responde con texto **o** con una o más llamadas a tools.
  3. El programa ejecuta las tools y agrega los resultados como mensajes.
  4. Se repite hasta que el modelo responde solo con texto.
- **Dónde está**: `agente.py` (`crear_agente`, `stream_turn`, `eventos`) y `llamadas_a_tools` para medir.
- **Cosas que conviene entender**:
  - Un modelo chico puede generar una llamada **mal formada** (JSON roto, argumento inventado). `llamadas_a_tools` las cuenta como error. Es la métrica que el fine-tuning (etapa 13) quiere bajar.
  - `return_direct=True` en `preguntar_al_usuario` corta el turno: el agente espera tu respuesta.
  - `temperature=0` ayuda a que la misma entrada dé la misma salida.
- **Qué retocar**: casi nada en el código. Se mejora con mejores descripciones de tools, menos tools por tarea o un modelo mejor.
- **Cómo probar**: pedí algo que necesite dos o tres tools seguidas («una PC para jugar con 2 millones») y mirá el orden de las llamadas.

## Etapa 5. Estado y memoria

- **Qué es**: dónde vive la información entre turnos. La configuración de PC **no vive en el chat**: vive en el estado del agente y se guarda por conversación.
- **Dónde está**:
  - `tools.py`: `EstadoTienda` (messages, todos, sources, configuracion) y `Context`.
  - `agente.py`: `crear_checkpointer` (SqliteSaver, archivo `memoria.db`), `new_thread`, `resume_thread`, `list_threads`.
  - `armado.py`: las operaciones sobre la configuración.
- **Idea clave**: una tool devuelve `Command(update={"configuracion": ...})` y el estado se actualiza solo. Por eso «cambiá la placa de video» funciona en el turno siguiente.
- **Qué retocar**: qué campos tiene el estado. Agregar uno nuevo implica tocar `EstadoTienda`.
- **Cómo probar**: armá una PC, cerrá el agente, volvé a abrirlo: retoma la última conversación.

## Etapa 6. Skills

- **Qué es**: un documento de instrucciones que el modelo carga **solo cuando lo necesita** con `load_skill`. Así el prompt principal no se llena de procedimientos largos.
- **Dónde está**: `skills/armado_pc.md` (59 líneas) y `listar_skills()` en `tools.py`.
- **Qué contiene la skill de armado**: regla de oro, datos que hay que pedir, el orden de piezas (cpu, placa, ram, gpu, almacenamiento, fuente, gabinete, cooler), cómo ajustar presupuesto, qué hacer con «no cumple» y «sin datos», cómo manejar cambios posteriores.
- **Qué retocar**: el procedimiento de armado. Es el lugar ideal para cambiar **cómo** se arma una PC sin tocar código.
- **Cómo probar**: pedí un armado y verificá que aparezca `load_skill` primero. Si no aparece, reforzá la regla 10 del prompt.

## Etapa 7. El servidor MCP de la tienda

- **Qué es**: un servidor aparte que expone el catálogo y las reglas como tools. MCP es un estándar para que un agente use herramientas de otro programa. Acá lo usa `langchain-mcp-adapters` (`mcp_tienda/cliente.py`).
- **Por qué existe**: separa el «cerebro» (el agente) del «negocio» (catálogo y reglas). La tienda puede usar el servidor sin el agente.
- **Dónde está**: `mcp_tienda/servidor.py` (las 3 tools), `cliente.py` (cómo se conecta el agente), `catalogo.py` (consultas), `modelos.py`.
- **Importante**: el servidor **no guarda estado**. Recibe códigos y responde.
- **Qué retocar**: los parámetros de `buscar_productos` (filtros, límite de resultados) y qué atributos devuelve.
- **Cómo probar**: `tests/test_servidor_mcp.py` y `tests/test_buscar_productos.py`.

## Etapa 8. Reglas de compatibilidad

- **Qué es**: código que decide si una combinación de piezas sirve, sin IA. Cada regla da «cumple», «no cumple» o «sin datos».
- **Dónde está**: `mcp_tienda/armado/reglas.py`, `candidatos.py`, `gamas.py`.
- **Reglas actuales**: socket CPU-placa, tipo de RAM, potencia de la fuente (`(CPU + GPU + 75 W) × 1,30`), formato placa-gabinete, largo de la GPU, socket del cooler.
- **Pendiente conocido** (está descripto en `SIGUIENTE_SESION.md`): con el catálogo real casi todo da «sin datos» porque las reglas todavía usan atributos del catálogo de prueba. Hay un plan de reglas nuevas (generación de CPU, ranuras de RAM, puertos M.2 y SATA, cooler, etc.).
- **Principio**: «sin datos» nunca se trata como compatible.
- **Qué retocar**: el margen de la fuente (`MARGEN_FUENTE`), el consumo base (`CONSUMO_BASE_W`) y las reglas nuevas.
- **Cómo probar**: `uv run pytest tests/test_compatibilidad.py`.

## Etapa 9. El catálogo y la ingesta

- **Qué es**: cómo entran los productos al sistema y cómo se extraen los atributos del texto libre.
- **Dónde está**: `mcp_tienda/ingesta/` (`cargar.py`, `extraccion.py`, `formato_amn.py`, `fuentes/api.py`), esquemas en `datos/esquemas/*.yaml`, base en `datos/catalogo_real.sqlite`.
- **Flujo**: API de la tienda → categoría + atributos (reglas y expresiones regulares primero, LLM de respaldo) → SQLite.
- **Estado hoy**: 4266 productos cargados; el cuadro de calidad muestra GPU con 49 %, gabinete 52 %, cooler 56 % y UPS 35 % de atributos con dato. Esos huecos son la razón de muchos «sin datos».
- **Qué retocar**: los esquemas (agregar o cambiar atributos), las reglas de `formato_amn.py` para leer más datos del nombre.
- **Cómo probar**: `uv run python -m evaluacion.calidad_catalogo` y `evaluacion/extraccion.py`.
- **Ojo**: el archivo `catalogo_real.sqlite` se genera con tu sesión de la tienda (`AMN_API_COOKIE`). No se versiona.

## Etapa 10. RAG y documentación propia

- **Qué es**: RAG = buscar en nuestros documentos y pasarle al modelo solo los fragmentos relevantes. Así explica «qué es una gama media» desde **nuestro** texto y no desde lo que recuerda.
- **Dónde está**: `rag/docs/*.md` (los documentos), `rag/ingest.py` (los indexa) y `rag/store.py` (la base Chroma), tool `consultar_caracteristicas` en `tools.py`.
- **Reindexar después de editar un documento**:

  ```bash
  uv run python -m rag.ingest
  ```

- **Estado de los documentos** (cantidad de huecos «Escribir acá» que quedan):

  | Documento | Huecos |
  |---|---|
  | `gamas.md` | 3 |
  | `reparto_presupuesto.md` | 0 (generado por script) |
  | `caracteristicas_por_actividad.md` | 10 |
  | `guia_compatibilidad.md` | 7 |
  | `guias_de_compra.md` | 5 |
  | `tabla_cpu_gpu_por_gama.md` | tabla **vacía** |

- **Lo más importante a completar**: `tabla_cpu_gpu_por_gama.md`. El código (`gamas.py`) la lee para saber la gama de cada procesador y placa de video. Con la tabla vacía, el filtro `gama` de `buscar_productos` no devuelve nada útil y `ajustar_presupuesto` no puede reemplazar CPU ni GPU «de la misma gama».
- **Qué retocar**: el texto de los documentos (es lo que el agente cita) y cuántos fragmentos devuelve la tool.
- **Cómo probar**: `uv run pytest tests/test_rag.py` y preguntarle al agente algo que esté en el documento: tiene que citar el archivo.

## Etapa 11. Búsqueda web y reparto del presupuesto

- **Búsqueda web** (`buscar_especificaciones_web`, en `tools.py`): Tavily limitado a una lista de dominios (`_dominio_permitido`) y con caché local en `datos/caches/`. Sirve para requisitos de juegos y programas. Lo que vuelve es **dato, no instrucción**.
  - Qué retocar: la lista de dominios permitidos.
- **Reparto del presupuesto** (`evaluacion/reparto_presupuesto.py`): arma miles de PCs compatibles con el catálogo real y mide qué porcentaje del total se lleva cada pieza por gama. Escribe `rag/docs/reparto_presupuesto.md`.
  - Qué retocar: `CRITERIOS` (RAM, disco, procesadores y placas de video por gama).
  - Regenerar cuando cambien los precios:

    ```bash
    uv run python -m evaluacion.reparto_presupuesto --escribir-doc
    ```

## Etapa 12. Armado de PC, interfaz y servicio

- **Armado** (`armado.py`): las operaciones que usan **tanto el chat como los clics**: poner o reemplazar una pieza, ajustar presupuesto (con tope de iteraciones), motivos para no confirmar. Mismo código por los dos caminos, así terminan en la misma operación.
- **Interfaz**:
  - `app.py`: Streamlit, banco de pruebas (chat + tarjetas + Cambiar + Confirmar).
  - `servicio.py`: servicio HTTP con eventos (SSE) que integra la tienda. **No expone** el razonamiento ni los argumentos de las tools.
  - `web/components/chat-agente/` y `docs/GUIA_INTEGRACION.md`: lo que se entrega al programador de la tienda.
- **Regla fija**: no existe ninguna tool para confirmar un pedido. Lo confirma siempre el usuario con un clic.
- **Cómo probar**:

  ```bash
  uv run streamlit run app.py
  uv run python -m uvicorn servicio:app --port 8000
  ```

## Etapa 13. Evaluación y fine-tuning

- **Evaluación** (carpeta `evaluacion/`): `agente_simple.py` (pedidos de `conjuntos/pedidos_simples.yaml`), `extraccion.py`, `calidad_catalogo.py`, `reparto_presupuesto.py`. Resultados en `evaluacion/resultados/`.
  - Regla del proyecto: **todo lo que hace el agente tiene que ser medible**. Cuando cambies un prompt o una tool, corré la evaluación antes y después.
  - Una diferencia menor que la variación entre corridas no cuenta como mejora.
- **Fine-tuning** (`finetuning/`): **la carpeta está vacía**. El plan es destilar trazas de un modelo grande, entrenar con LoRA en Colab y exportar a GGUF para Ollama. Es la Fase 4 de `PLAN.md`.
- **Qué retocar**: agregar pedidos al conjunto de evaluación, sobre todo los que te fallan.

---

## Orden sugerido de estudio y retoque

| Paso | Etapa | Qué vas a poder hacer al terminar |
|---|---|---|
| 1 | 0 y 1 | Cambiar de modelo y correr el agente |
| 2 | 2 | Retocar el tono y las reglas del prompt |
| 3 | 3 y 4 | Entender por qué elige una tool y mejorar sus descripciones |
| 4 | 5 y 6 | Cambiar el procedimiento de armado sin tocar código |
| 5 | 10 | Completar la documentación y la tabla de CPU y GPU por gama |
| 6 | 7, 8 y 9 | Entender el catálogo y las reglas, y sumar las nuevas |
| 7 | 11 y 12 | Ajustar reparto, interfaz y servicio |
| 8 | 13 | Medir antes y después de cada cambio, y encarar el fine-tuning |

## Cosas que vi mientras armaba esto (para decidir)

1. `tabla_cpu_gpu_por_gama.md` está vacía: sin ella la «gama» de CPU y GPU no funciona (etapa 10).
2. Los documentos del RAG tienen muchos huecos «Escribir acá»: el agente solo puede explicar lo que está escrito.
3. Las reglas de compatibilidad todavía no aprovechan los atributos del catálogo real (etapa 8).
4. La numeración de las reglas del system prompt está desordenada (etapa 2).
5. `finetuning/` no tiene nada todavía (etapa 13).
6. `CLAUDE.md` describe Streamlit como la interfaz principal, pero el alcance actual es servicio más componente de chat. Conviene actualizarlo.
