# Plan — Asistente de compra AMN (Grupo 10) · revisión 3

## Contexto

Hay que construir el agente de `CLAUDE.md` sin tener todavía la API ni la BD de la tienda. Dos decisiones ordenan todo el plan:

1. **El agente nunca habla con la API de la tienda:** consulta una base local (`datos/catalogo.sqlite`) y la API solo la alimenta. Así nada queda bloqueado esperando a la tienda.
2. **El proyecto sigue el patrón del ejemplo de la cátedra** (<https://github.com/fmaya02/AgenteInvestigadorVerFinal>): `create_agent`, tools con estado, memoria con `SqliteSaver`, RAG sobre Chroma, skills y UI en Streamlit. Lo nuestro se suma: servidor MCP de la tienda, armado de PC y fine-tuning.

## Estado

| Fase | Paso | Estado |
|---|---|---|
| 0 | Catálogo de prueba, búsqueda, compatibilidad, agente mínimo | Hecha. Falta el smoke con el modelo local en una máquina del grupo |
| 1 | 1. Estructura de la cátedra y `model.py` | Hecho |
| 1 | 2. Estado, memoria, TODOs y skills | Hecho |
| 1 | 3. Servidor MCP y puente | Hecho |
| 1 | 4. Armado de PC en el estado | Hecho. Falta medir con el modelo local (`evaluacion/armado.py`) |
| 2 | 5. RAG (`consultar_caracteristicas`) | Código y borradores de `rag/docs/` hechos e indexados; falta revisión con el grupo/tienda |
| 2 | 6. Búsqueda web (`buscar_especificaciones_web`) | Hecho con dominios permitidos, fuentes, caché y ubicación por código en la tabla de gamas |
| 2 | Búsqueda semántica del catálogo, cámaras, respaldo LLM | Pendiente |
| 3 | 7. `app.py` (demo Streamlit) + `servicio.py` y chat web + selector de modelo | Hecho |
| 3+ | Paso 9. Reglas para catálogo real, cantidades y segundo disco | Hecho |
| 3+ | Paso 10. Entrevista (v1 con `preguntar_al_usuario`), `validar_presupuesto` (jerga, números en palabras, «2,8M», «y medio») y cierre | En curso — código mergeado en `main`; falta la medición con el modelo local |
| 3+ | Paso 11. Recorte de contexto (`#22`), presupuesto como texto (`#31`), experimento HyDE (`#30`), RAG (`#29`) y guía Ollama (`#27`) | Hecho en `paso-11-otros-problemas`; falta prueba manual en notebook de 4 GB |
| 4–5 | Fine-tuning, evaluación e informe | Pendiente (fine-tuning queda fuera de la presentación) |

## El catálogo no depende de la tienda

```
fuente (prueba | csv | api)  ──►  mcp_tienda/ingesta: categoría + atributos (+ embeddings)  ──►  datos/catalogo.sqlite
```

Cada fuente entrega `ProductoCrudo` y pasa el mismo test de contrato (`tests/test_contrato_fuente.py`). En vivo solo se pide **precio y stock al confirmar**.

| Depende de la tienda | No depende |
|---|---|
| `mcp_tienda/ingesta/fuentes/api.py` | Todo el resto: extracción, búsqueda, reglas, MCP, RAG, web, Streamlit, fine-tuning |
| Precio/stock fresco al confirmar | |
| Destino real de «Confirmar» | |
| Re-etiquetar evaluaciones con productos reales | |

**Fecha de corte:** si al cerrar la Fase 2 no hay API ni export, el proyecto cierra en escenario B y el informe lo dice.

## Qué pedirle a la tienda

1. **Ya:** export de 50–100 productos reales (CSV/Excel). La carga desde CSV ya está (`mcp_tienda/ingesta/fuentes/export_csv.py`).
2. Documentación de la API: listado paginado, detalle por código, categorías, autenticación, límite de pedidos, entorno de prueba.
3. Campos: precio con/sin IVA, moneda, stock (¿por sucursal?), imágenes, URL, árbol de categorías.
4. Si «Armá tu PC» ya tiene atributos estructurados (si los tiene, nuestra extracción pasa a ser respaldo).
5. Qué hace «Confirmar»: carrito o aviso al vendedor.
6. BD solo si no hay API: usuario de solo lectura o dump.
7. Permiso por escrito. Datos reales y token nunca al repo.

## Qué tomamos del ejemplo de la cátedra

| De la cátedra | En nuestro proyecto |
|---|---|
| `model.py` (`get_model`, `get_embeddings`) | Igual, con proveedores locales (Ollama o LM Studio) y embeddings locales |
| `chat_lmstudio.py` | Copiado tal cual |
| `agente.py` (prompt, `create_agent`, `stream_turn`, `eventos`, `saved_turns`, conversaciones, consola) | Igual, con nuestro prompt y nuestro estado |
| `tools.py` (`Context`, estado, `_respond`, `write_todos`, `read_todos`, `load_skill`) | Igual |
| `web_search` | `buscar_especificaciones_web` (con `include_domains` y caché) |
| `search_knowledge_base` | `consultar_caracteristicas` |
| `rag/store.py`, `rag/ingest.py` | Casi iguales |
| `skills/latex.md` | El formato; la nuestra es `skills/armado_pc.md` |
| `app.py` | El chat igual, más el panel de la configuración |
| `create_pdf`, Tectonic, OpenRouter | No se usan (`Gemini` es opcional desde el selector de modelo) |

## Conceptos, en criollo

- **Estado del agente (`AgentState`).** La «mochila» de la conversación. Por defecto lleva los mensajes; la cátedra le agrega `todos` y `sources`, nosotros `configuracion`.
- **`ToolRuntime`.** Parámetro extra que LangChain le pasa a la tool y que el modelo no ve. Por ahí la tool lee la mochila (`runtime.state`), el número de turno (`runtime.context`) y el id de la llamada.
- **`Command(update={...})`.** Una tool normalmente devuelve texto. Si devuelve un `Command`, además le dice al agente «guardá esto en la mochila».
- **Checkpointer (`SqliteSaver`) y `thread_id`.** Después de cada paso el agente guarda una foto de la mochila en `memoria.db`. Cada conversación tiene su `thread_id`. Por eso el segundo turno encuentra la configuración del primero, aunque se haya cerrado el programa.
- **`artifact`.** Un `ToolMessage` tiene el texto, que lee el modelo, y el `artifact`, que no lee. Al modelo le va un resumen corto y a la pantalla los datos completos.
- **`update_state`.** Escribe en la mochila desde afuera del agente. Lo usa el botón Cambiar.
- **MCP y `langchain-mcp-adapters`.** MCP es un protocolo para que un programa aparte (el servidor) ofrezca tools. El adaptador las convierte en tools de LangChain. Separa «la tienda» de «el agente».
- **Skill y `load_skill`.** Un Markdown con instrucciones largas que el modelo pide solo cuando las necesita.
- **Streamlit.** Vuelve a ejecutar todo `app.py` en cada clic; lo que tiene que sobrevivir va en `st.session_state` o en el estado del agente.

## Fase 1 — Alinear con la cátedra y armado de PC

Un commit por paso, cada uno con la prueba que lo demuestra.

| Paso | Qué | Prueba |
|---|---|---|
| 1 | Estructura de carpetas, `model.py`, `.env`, documentación | Los tests de la Fase 0 pasan con las rutas nuevas + `tests/test_model.py` (proveedor y modelo afinado por `.env`, contexto explícito, embeddings locales) |
| 2 | `EstadoTienda`, `Context`, `_respond`, `write_todos`/`read_todos`, `load_skill`, `SqliteSaver`, conversaciones, `stream_turn`, consola | Con modelo falso: los TODOs y los mensajes siguen ahí al reabrir `memoria.db` con un agente nuevo; los eventos traen el `artifact` |
| 3 | `mcp_tienda/servidor.py` (3 tools) y `mcp_tienda/cliente.py` (puente); el agente usa el catálogo por MCP | El test levanta el servidor real y llama las 3 tools; el `artifact` trae los datos; no existe tool de confirmar |
| 4 | `armado.py`, las 4 tools de armado, `mcp_tienda/armado/gamas.py`, `skills/armado_pc.md` | Turno 1 arma; turno 2 «cambiá la placa de video» reemplaza solo la GPU, re-verifica y recalcula el total; `ajustar_presupuesto` respeta el tope |

Decisiones de diseño:

- **Servidor MCP sin estado.** La configuración vive en el agente; el servidor recibe códigos y responde.
- **Puente sincrónico.** El adaptador entrega tools asíncronas y abre un servidor nuevo en cada llamada. `mcp_tienda/cliente.py` mantiene un servidor abierto en un hilo aparte y entrega las mismas tools en versión sincrónica, con su `artifact`. Así `agente.py` y `app.py` quedan como los de la cátedra.
- **Candidatos compatibles.** `buscar_productos` acepta los códigos ya elegidos y devuelve solo lo compatible con ellos. El modelo «elige entre candidatos»; no razona la compatibilidad. Lo usa también el botón Cambiar.
- **Gama por reglas.** `gamas.py` lee la tabla de `rag/docs/tabla_cpu_gpu_por_gama.md`. Mientras la tabla esté vacía, la gama es «sin datos» y `ajustar_presupuesto` no reemplaza esas piezas y lo dice. **Es el primer documento que conviene escribir.**
- **Búsqueda:** primero todas las palabras, después cualquiera; y cuando se filtra por un atributo, se informa cuántos productos quedaron afuera por no tener el dato.
- **Nunca confirma:** no existe ninguna tool de confirmar; un test lo verifica.
- **Varias piezas en un mismo mensaje.** Si el modelo pide agregar dos piezas a la vez, las dos tools parten del mismo estado. El estado tiene un «reducer» (`armado.fusionar`) que aplica los dos cambios en vez de perder uno; la compatibilidad queda «sin verificar» hasta la siguiente lectura.
- **Al abaratar no se pierde capacidad:** CPU y GPU no cambian de gama; RAM y disco no bajan de capacidad ni cambian de tipo.

**Medición:** `evaluacion/armado.py` sobre ~20 pedidos (presupuesto + uso + gama esperada): % compatible, % dentro del presupuesto, % en la gama pedida, llamadas por armado.

**Criterio de salida:** `ajustar_presupuesto` siempre termina dentro del tope; con el LLM local, ≥ 70 % de armados compatibles y dentro del presupuesto.

**Punto de decisión:** si el modelo chico no llega a ese 70 %, se propone una tool `proponer_configuracion` (el código arma la base y el modelo ajusta). Se decide con el número en la mano.

## Fase 2 — RAG, web y búsqueda semántica

- **Paso 5 · RAG.** `rag/docs/` con los 6 documentos (encabezado con título, fecha y fuente; los escribe el grupo). `rag/ingest.py` y `rag/store.py` como los de la cátedra, con Chroma y embeddings locales (`bge-m3`). `consultar_caracteristicas` cita el archivo de origen. Prueba: ingesta sobre documentos de prueba con embeddings falsos; con embeddings reales, marcada.
- **Paso 6 · Web.** `buscar_especificaciones_web`: Tavily con `include_domains`, fuentes en el estado, caché en `datos/caches/`. La extracción a `{mínimos, recomendados: cpu, gpu, ram, almacenamiento}` la hace el LLM con salida estructurada y **el código descarta todo valor que no aparezca textual en la página**. Sin conexión y sin caché devuelve «sin datos». Prueba: Tavily simulado; real, marcada.
- **De requisitos a gama:** los modelos que nombran los requisitos se buscan en la tabla de gamas (que incluye modelos viejos como GTX 1060); si no están, «sin datos».
- **Búsqueda semántica del catálogo:** vectores en el mismo SQLite del catálogo (filtro con SQL, orden con numpy), con el mismo `get_embeddings()`. Chroma queda solo para los documentos. Se reporta Recall@5 de solo-texto, solo-embeddings e híbrida; la híbrida tiene que ganarle a solo-texto.
- **Cámaras:** `datos/esquemas/camaras.yaml` + extractor + productos. Catálogo de prueba ampliado a 300–500.
- **Respaldo LLM de la extracción:** solo para atributos que la regex dejó vacíos, validado contra el esquema y marcado con origen `llm`. Se activa solo si no agrega valores erróneos.
- **Lo externo es dato:** 3 productos con instrucciones metidas en la descripción y una página de prueba equivalente; la evaluación verifica que el agente no obedece.

**Criterio de salida** (umbrales iniciales): Recall@5 ≥ 0,80 sobre ~40 consultas; fragmento correcto ≥ 80 % y gama/perfil correctos ≥ 80 % sobre ~30 pedidos; requisitos web correctos en ≥ 12 de 15; 0 obediencias a texto inyectado. **Acá vence la fecha de corte de la API.**

## Fase 3 — Interfaz en Streamlit (paso 7)

- **Chat** igual al de la cátedra: razonamiento, cada tool en vivo, fuentes, conversaciones en la barra lateral.
- **Panel «Armá tu PC»:** tarjetas en `st.columns` (código, nombre, precio, stock, atributos), reporte de compatibilidad y total. Los datos llegan por `artifact` y por el estado.
- **Cambiar** no pasa por el LLM: muestra alternativas compatibles (`buscar_productos`) y aplica la elegida con `update_state`, usando la misma función de `armado.py` que la tool.
- **Confirmar pedido:** solo el usuario. El código vuelve a pedir precio y stock, recalcula el total y, si cambió, avisa y pide confirmar de nuevo. En escenario B guarda el pedido localmente.

**Prueba:** test automático de Streamlit con modelo falso (tarjetas, Cambiar, Confirmar) y captura de pantalla. **Criterio de salida:** eso, más el conjunto de evaluación del agente congelado.

## Fase 4 — Fine-tuning

- **Primero se congela el conjunto de evaluación** (~40 tareas de las cuatro capacidades, más pedidos vagos, casos «sin datos» y texto inyectado). Las trazas salen de pedidos distintos; un script verifica que no se repitan.
- **Trazas:** el modelo maestro resuelve conversaciones con las mismas tools. Solo se guardan las que pasan la verificación automática. El maestro es una decisión abierta.
- **Entrenamiento:** QLoRA en Colab T4, misma plantilla de chat y tools que usa el servidor local, pérdida solo sobre los turnos del asistente y filas de embedding de los tokens de tool calling entrenables (`trainable_token_indices` de PEFT).
- **Exportación con control:** merge → GGUF → misma cuantización que el base. El modelo base pasa por el mismo camino de exportación y tiene que dar lo mismo que el base original.
- **Comparación:** se cambia `MODEL_NAME` (o `get_model(nombre)`), mismo prompt, mismas tools, mismo conjunto, ≥ 3 semillas; media y desvío. Una diferencia menor al desvío no cuenta.

## Fase 5 — Evaluación e informe

Correr todo `evaluacion/` y armar el informe con las seis tablas de `CLAUDE.md`, el escenario usado (A o B), qué se re-midió con datos reales, las limitaciones y lo resuelto en cada punto de decisión.

## Trazabilidad: requisito → fase → cómo se mide

| Requisito de `CLAUDE.md` | Fase | Medición |
|---|---|---|
| Búsqueda en todo el catálogo | 0 y 2 | Recall@5 |
| Pregunta si el pedido es vago | 2 | Casos vagos: primer turno sin llamada a tools y con pregunta |
| Armado compatible y dentro del presupuesto | 1 | `evaluacion/armado.py` |
| La configuración sobrevive entre turnos | 1 | Test de dos turnos con `SqliteSaver` |
| Gama sin que la invente el LLM | 1 y 2 | Tests de `gamas.py` + gama/perfil sobre 30 pedidos |
| Interpretar el uso (web + RAG) | 2 | 15 juegos/programas contra fuente oficial |
| Explicar citando la documentación | 2 | Respuesta con llamada a `consultar_caracteristicas` y archivo citado |
| Tarjetas, Cambiar, Confirmar | 3 | Test automático de Streamlit |
| El agente nunca confirma | 1 | Test: no existe tool de confirmar |
| Lo externo es dato | 2 | Productos y página con texto inyectado |
| Sin datos no hay afirmación | 0 | Tests de reglas + casos «sin datos» en el conjunto del agente |
| Extracción evaluada a mano | 0 | Muestra retenida de 50 (la escribe el grupo) |
| Base vs. afinado | 4 | Tabla con semillas |

## Riesgos

| Riesgo | Señal | Qué hacemos |
|---|---|---|
| El modelo chico falla en tool calling o en armados largos | Fase 0/1 por debajo del criterio | Candidatos compatibles, contexto explícito, skill de armado, TODOs; si no alcanza, `proponer_configuracion` o un modelo más grande |
| La API no llega | Fecha de corte en Fase 2 | Escenario B completo |
| Las regex rinden peor con datos reales | Muestra real etiquetada | Ajustar regex; respaldo LLM solo si no agrega erróneos |
| Lento en CPU | Segundos por turno en las evaluaciones | Modelo más chico, sin razonamiento, respuestas cortas y ajustes de `docs/AJUSTES_OLLAMA.md` (KV comprimida, contexto 8192 y recorte de historial) |
| Sin conexión el día de la demo | — | Caché web precargada; todo lo demás es local |
| Colab corta la sesión | — | Checkpoints en Drive; pocas épocas; modelo de 4B o menor |

## Si no alcanza el tiempo: qué se recorta, en este orden

1. Ampliación del catálogo a 300–500 (queda en ~200 con cámaras).
2. Respaldo LLM de la extracción.
3. Búsqueda semántica del catálogo (queda texto + filtros).
4. Tercera semilla de entrenamiento (quedan las semillas de inferencia).

**No se recorta:** reglas deterministas, medición de cada componente, comparación base vs. afinado, «el usuario confirma».

## Cuando llegue la API (día D)

1. ~~Completar `mcp_tienda/ingesta/fuentes/api.py`~~ **Hecho** (11/11/2026). Falta la cookie de sesión en `.env` (`AMN_API_COOKIE`): sin sesión la API no muestra precios.
2. `uv run pytest tests/test_contrato_fuente.py` contra la API (necesita la cookie).
3. ~~Ajustar la extracción al catálogo real~~ **Hecho** para las piezas de PC: `mcp_tienda/ingesta/formato_amn.py` lee las convenciones de carga de la tienda y `uv run python -m evaluacion.calidad_catalogo` mide la cobertura y lista los productos a corregir. Falta etiquetar a mano 50 productos reales para medir la exactitud (la cobertura dice cuánto se lee, no si se lee bien).
4. `python -m mcp_tienda.ingesta.cargar --fuente api` → recalcular embeddings.
5. Re-etiquetar consultas de Recall@5 y pedidos de armado con códigos reales → correr evaluación.
6. Conectar precio/stock fresco y el destino real de «Confirmar».

## Trabajo en paralelo (contenido, no código)

Redactar los documentos de `rag/docs/` empezando por `tabla_cpu_gpu_por_gama.md`; escribir las 50 descripciones de la muestra a mano (`evaluacion/conjuntos/extraccion_manual.yaml`), las ~40 consultas de búsqueda, los ~20 pedidos de armado y la lista de 15 juegos/programas; gestionar el pedido a la tienda.

## Datos que faltan (no bloquean)

Resultado del smoke con el modelo local y en qué hardware corrió; fecha de entrega final; con qué modelo maestro cuentan para las trazas; Ollama o LM Studio como proveedor definitivo.
