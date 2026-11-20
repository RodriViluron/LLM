# Resumen de la noche (2026-11-20)

Trabajo realizado sin supervisión en la rama **`paso-11-otros-problemas`** (partiendo de `main` `90e8bef`). No se hicieron `git push`, `git merge`, descargas de modelos (`ollama pull`), cambios en `.env`, cambios en `web/` ni modificaciones en la entrevista del armado (`#26`), y ningún problema se marcó como `[x]` en `PROBLEMAS_DETECTADOS.md`.

---

## Commits de la noche

- `2a68a86` — Registrar mediciones del cierre del paso 10 en `PROBLEMAS_DETECTADOS.md`
- `75356a1` — Parte A (`#29`): actualizar porcentajes esperados del RAG tras incluir disco secundario
- `9152eb5` — Parte B (`#30`): agregar experimento HyDE en `evaluacion/rag.py` y medir contra RAG actual
- `44f46ae` — Parte C (`#31`): aceptar presupuesto como texto en `iniciar_configuracion` y validarlo con `interpretar_monto`
- `0a979d0` — Parte F (`#22`): recortar resultados de tools viejos conservando fuentes para 8192 tokens
- `9d8ecf8` — Parte D (`#27`): documentar ajustes de Ollama y recomendación para notebook de 4 GB

---

## Resultado de las 32 suites de tests

Comando ejecutado una vez por archivo (`uv run pytest -q -m "not ollama and not embeddings and not tavily" tests/<archivo>.py`): **464 tests pasaron, 0 fallaron** (`3 deselected` por los marcadores `ollama`/`embeddings`/`tavily` y `1 skipped` preexistente en `test_contrato_fuente.py`).

| Suite | Resultado | Suite | Resultado |
|---|---|---|---|
| `test_acciones_sin_tool.py` | 14 passed | `test_limpieza_historial.py` | 5 passed |
| `test_agente.py` | 2 passed, 1 deselected | `test_llamadas_como_texto.py` | 16 passed |
| `test_app.py` | 10 passed (81.80s) | `test_model.py` | 11 passed |
| `test_app_botones.py` | 3 passed | `test_montos.py` | 6 passed |
| `test_armado.py` | 22 passed | `test_montos_usuario.py` | 38 passed |
| `test_buscar_productos.py` | 11 passed | `test_perfiles.py` | 4 passed |
| `test_codigos_vistos.py` | 4 passed | `test_rag.py` | 9 passed, 1 deselected |
| `test_compatibilidad.py` | 43 passed | `test_rag_hyde.py` | 5 passed |
| `test_contrato_fuente.py` | 11 passed, 1 skipped | `test_rag_secciones.py` | 10 passed |
| `test_entrevista.py` | 22 passed | `test_recorte_historial.py` | 3 passed |
| `test_entrevista_tools.py` | 12 passed | `test_reparto_presupuesto.py` | 4 passed |
| `test_estado_memoria.py` | 10 passed | `test_requisitos.py` | 32 passed |
| `test_explicaciones_rag.py` | 16 passed | `test_servicio.py` | 17 passed |
| `test_extraccion.py` | 29 passed | `test_servidor_mcp.py` | 20 passed |
| `test_formato_amn.py` | 45 passed | `test_tabla_gamas.py` | 19 passed |
| `test_guia_compatibilidad.py` | 3 passed | `test_web.py` | 8 passed, 1 deselected |

---

## Tabla del experimento HyDE (`#30`)

Medido antes del cambio de plan sobre las 52 consultas de `evaluacion/conjuntos/rag_consultas.yaml` (`bge-m3` + `qwen3:4b`, 1 pasada por variante):

| Variante | acierto@1 | acierto@4 | Otra gama | Tiempo promedio / consulta | Resultado |
|---|---|---|---|---|---|
| `--solo-vectores` | 69 % (36/52) | 98 % (51/52) | 31 % | 0,11 s | `evaluacion/resultados/rag_solo_vectores.json` |
| Búsqueda actual (gama + tabla) | 73 % (38/52) | 98 % (51/52) | 11 % | 0,06 s | `evaluacion/resultados/rag.json` |
| Búsqueda actual + `--hyde` | 67 % (35/52) | 100 % (52/52) | 13 % | 13,22 s | `evaluacion/resultados/rag_hyde.json` |

**Conclusión:** No conviene activarlo en el agente. Si bien `--hyde` llevó `acierto@4` a `100 %` (52/52), bajó `acierto@1` (`73 % → 67 %`) porque su prosa genérica desplazó a `reparto_presupuesto.md` en consultas de porcentajes/precios y sumó **+13,16 s por consulta** (`687,4 s` totales frente a `3,06 s` de la búsqueda actual).

---

## Qué quedó pendiente o bloqueado y por qué

- **Prueba real de la Parte F (`#22`) con `qwen3:4b`:** se midió en Python offline sobre `memoria.db` (`99c1a78e`: `5.255 → 2.729` tokens, total `~8.405 → ~5.879`; `4ab40d12`: `8.504 → 4.845` tokens, total `~11.654 → ~7.995`), pero no se corrió con el modelo real por el cambio de plan.
- **Medición de `num_gpu`, `OLLAMA_NUM_PARALLEL`, `keep_alive` y cuantización `Q8_0` (`#27`):** no se ejecutaron mediciones nuevas por el cambio de plan. Para comparar `Q4_K_M` contra `Q8_0` hace falta permiso para descargar `qwen3:4b-q8_0` (`ollama pull qwen3:4b-q8_0`, ~4,3 GB). `docs/AJUSTES_OLLAMA.md` deja marcado qué valores están medidos y cuáles son recomendaciones sin medir.
- **Arreglo en código del orden `gamas.md` / `reparto_presupuesto.md` (`#29`):** solo quedó propuesto en `#29` (no se tocó `rag/consulta.py` para no alterar la comparación de `#30`).
- **Corrida `uv run python -m evaluacion.armado_con_entrevista --semillas 1`:** omitida por el cambio de plan urgente.
- **Entrevista (`#26`), decisiones del grupo/tienda y cambio de estados a `[x]`:** sin tocar para que los revises y decidas vos (`#14`, `#15`, `#18`, `#25`, `#34` y cierre de `#22`, `#29`, `#30`, `#31`).

---

## Qué tenés que probar a mano a la mañana

1. **Ajustes en la notebook de 4 GB de VRAM (`docs/AJUSTES_OLLAMA.md`):**
   - Configurar `.env` y el servidor Ollama con `MODEL_NUM_CTX=8192`, `OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0` (o `q4_0` si no entra), `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_KEEP_ALIVE=-1`.
   - Crear la variante de embeddings en CPU (`Modelfile` con `FROM bge-m3` y `PARAMETER num_gpu 0` → `ollama create bge-m3-cpu -f Modelfile`) y poner `EMBEDDINGS_MODEL=bge-m3-cpu`.
   - Con el asistente en uso, correr `ollama ps` y verificar que `qwen3:4b` figure en **`100% GPU`**.
2. **Parte F (`#22`) con el modelo real (la prioridad más importante):**
   - Abrir Streamlit (`uv run streamlit run app.py`) con `MODEL_NUM_CTX=8192`.
   - Iniciar una conversación larga de varios turnos: pedir una PC para un juego (ej. *God of War*, que dispare `buscar_especificaciones_web`), preguntar por una gama o presupuesto (`consultar_caracteristicas`) y hacer un par de búsquedas de piezas (`buscar_productos` / `buscar_pieza_armado`).
   - En un turno posterior, preguntarle de qué páginas o documentos sacó los requisitos del juego y la gama, y comprobar que el modelo sigue citando las fuentes reales (conservadas en el resumen recortado) mientras en pantalla/historial completo (`memoria.db`) siguen los resultados enteros.
3. **Parte C (`#31`):**
   - Probar en el chat un monto en jerga («tengo 2 palos») y un rango ambiguo («entre 2.800.000 y 3.200.000 pesos») y confirmar que `iniciar_configuracion` acepta «2 palos» como `$ 2.000.000` y pide aclaración sin adivinar ante el rango.
4. **Entrevista (`#26`) y razonamiento en español (`#9`):**
   - Probar el flujo de armado por entrevista y mirar el desplegable de «Razonamiento» en Streamlit (con `MODEL_RAZONAMIENTO=1` o el razonamiento interno) para ver si con la línea agregada en `PROMPT_SISTEMA` ya piensa en español o sigue en inglés.

---

## Revisión propia (`git diff main..paso-11-otros-problemas`)

Al revisar todo el diff contra `main` se encontraron y corrigieron cuatro detalles menores:

1. **Respaldo de fuentes cuando `artifact == []` (`agente.py`, `_resumir_web` y `_resumir_rag`):** si `mensaje.artifact` llegaba como lista vacía o sin URLs/archivos, no caía al regex sobre `mensaje.text`. Se corrigió para hacer respaldo por texto cuando de `artifact` no sale ninguna fuente, y se agregó un test específico para ambos casos en `tests/test_recorte_historial.py`.
2. **Nombres en inglés en el código nuevo (`agente.py` y `tests/test_recorte_historial.py`):** renombrados `match_gama` → `coincidencia_gama`, `match` → `coincidencia`, `items` → `elementos`, `slot`/`prod` → `lugar`/`producto`, `payload` → `datos`, y `"por request"` → `"por pedido"` en `docs/AJUSTES_OLLAMA.md`.
3. **Comentario desactualizado en `crear_agente` (`agente.py`):** el comentario sobre el orden de middlewares mencionaba solo `sin_acciones_inventadas` y `sin_razonamiento_viejo`; se actualizó para incluir `historial_en_contexto`. También se pulió el comentario de `_BaseLarga` en `tests/test_recorte_historial.py`.
4. **`import math` dentro de función (`tools.py`):** movido desde `resolver_presupuesto` al encabezado de imports del módulo.

Tests verificados tras las correcciones: `tests/test_recorte_historial.py` (`3 passed`) y `tests/test_montos_usuario.py` (`38 passed`).

---

## Mejoras adicionales (interfaz web, modelo/agente y RAG)

Commits agregados luego de la revisión y actualización de documentación (`4e944cf`, `f72bb67`, `1696155`):

- `1696155` — Parte E (`#9`, sin medir): instrucción en `PROMPT_SISTEMA` (`agente.py`) pidiendo razonar en español (falta probar a mano con `qwen3:4b`).
- `6ab61b7` — **Bloque 1 (interfaz web, servicio y Streamlit):**
  - `tools.py` + `servicio.py`: `buscar_pieza_armado` ahora pasa `artifact=datos` y `_resultado_publico` emite eventos `productos`, mostrando tarjetas también en el chat web y en Streamlit durante la entrevista.
  - `app.py`: `pesos()` soporta presupuesto en texto (`"2 palos"`) sin fallar, y se sumaron títulos/detalles en Streamlit para `buscar_pieza_armado` y `validar_presupuesto`.
  - `web/components/chat-agente/`: soporte de `critica` en reglas (`tipos.ts`), subtotales por `cantidad` en `TarjetaArmado`, distinción de avisos no críticos (`Aviso:` vs `Sin datos:`), tablas Markdown en `TextoAgente`, scroll inteligente (`pegadoAbajo`), botón **Reintentar** ante un error del último turno, conservación del `armadoGuardado` al reabrir conversaciones y aviso discreto al detener una respuesta vacía (`useChatAgente.ts`).
  - `web/components/vista-armado/` y `web/app/page.tsx`: paso «Revisión» conectado a `armado.se_puede_confirmar`, subtotales por cantidad, detalle de reglas no cumplidas/avisos y botón **Cargar armado** también en la vista de prueba.
- `17aaf60` — **Bloque 2 (modelo local y middlewares):**
  - `agente.py`: middleware `sin_respuesta_vacia` que pide una vez texto visible si `qwen3:4b` devuelve vacío o `<think>` sin cerrar (sin guardar el intento descartado en `memoria.db`).
  - `model.py` + `docs/AJUSTES_OLLAMA.md`: soporte opcional de `MODEL_KEEP_ALIVE` y `MODEL_NUM_GPU` desde `.env` en `ChatOllama`.
- `f0c6ad6` — **Bloque 3 (desempate por intención en el RAG, `#29`):**
  - `rag/consulta.py`: `_ordenar_por_intencion` prioriza `reparto_presupuesto.md` ante consultas de costo/porcentaje/presupuesto y `gamas.md` ante consultas de componentes de una gama entre los fragmentos recuperados (falta re-correr `uv run python -m evaluacion.rag` para medir con `bge-m3`).

### Verificación final completa (tras Bloque 3)

- **32 suites de Python (`uv run pytest -q -m "not ollama and not embeddings and not tavily" tests/<archivo>.py`):** **470 passed, 0 failed** (`3 deselected` por marcadores, `1 skipped` en `test_contrato_fuente.py`). Incluyen los nuevos tests en `test_servicio.py` (`18`), `test_app_botones.py` (`4`), `test_limpieza_historial.py` (`7`), `test_model.py` (`12`) y `test_rag_secciones.py` (`11`).
- **Web (`npm --prefix web run typecheck` y `npm --prefix web run build`):** ambos pasaron sin errores (`tsc --noEmit` y `next build` compilado y exportado con éxito).

---

## Paso 12: entrevista conducida por código (`#26`)

Trabajo realizado sin supervisión en la rama **`paso-12-entrevista-por-codigo`** (partiendo de `paso-11-otros-problemas` `d9e0d1d`), sin modificar `web/`, `.env`, `TURNOS_MAXIMOS=8` ni pasar el estado de `#26` a `[x]`.

### Commits del paso 12

- `9470f49` — Paso 12 (`#26`): conducir la entrevista del armado por código sin pasar opciones por el modelo (`agente.py`, `tools.py`, `mcp_tienda/armado/montos.py`, `mcp_tienda/armado/requisitos.py`, `tests/test_entrevista_por_codigo.py` y ajustes en tests previos).
- Commit siguiente de cierre — Guardar `evaluacion/resultados/armado_con_entrevista_paso12.json` y actualizar `PROBLEMAS_DETECTADOS.md` y `RESUMEN_NOCHE.md`.

### Suites de tests (paso 12)

- **33 suites completas de Python (`uv run pytest -q -m "not ollama and not embeddings and not tavily" tests/<archivo>.py` de a una):** **479 passed, 0 failed** (`3 deselected`, `1 skipped` en `test_contrato_fuente.py`).
- **Suite nueva `tests/test_entrevista_por_codigo.py`:** `9 passed` (avance con 0 llamadas al modelo falso, texto libre no registra opción, entrevista completa guarda perfil y avisa al modelo, argumentos inventados ignorados, presupuesto en frases con `1080p`/`4K` y detección de ambiguo, requisitos `sin datos` sin preguntar gama).
- **Suites clave verificadas:** `test_entrevista_tools.py` (`12 passed`), `test_entrevista.py` (`22 passed`), `test_servicio.py` (`18 passed`), `test_app_botones.py` (`4 passed`), `test_requisitos.py` (`32 passed`), `test_model.py` (`12 passed`).

### Medición única (`evaluacion/resultados/armado_con_entrevista_paso12.json`)

Corrida `uv run python -m evaluacion.armado_con_entrevista --semillas 1` (`qwen3:4b`, `MODEL_NUM_CTX=8192`, Ollama `0.40.16`, `datos/catalogo_real.sqlite`):

| Métrica | Paso 10 cierre (9 corridas) | Paso 10 cierre (semilla 1) | Paso 12 (semilla 1) |
|---|---|---|---|
| Entrevista completa | `1/9` | `0/3` | **`3/3`** |
| Perfil correcto | `1/9` | `0/3` | **`3/3`** |
| Preguntas de gama fuera de entrevista | `19` | `9` | **`0`** |
| Armados completos | `0/9` | `0/3` | **`2/3`** |
| Compatibles | `0/9` | `0/3` | **`2/3`** |
| Se pueden confirmar | `0/9` | `0/3` | **`2/3`** |
| Dentro del presupuesto | `5/9` | `1/3` | **`3/3`** |
| Con críticas sin datos | `0/9` | `0/3` | **`0/3`** |
| Afirmaciones sin tool | `0` | `0` | **`0`** |
| Llamadas promedio | `15,3` | `14,3` | **`22,7`** |
| Llamadas con error | `15` | `5` | **`3`** |
| Tiempo promedio | `4,7 min` | `4,1 min` | **`3,1 min`** |

**Turnos por etapa (`TURNOS_MAXIMOS=8`):**
- **Fortnite 1080p** (`Tengo 2.800.000 y prefiero Intel`): 8 turnos totales — 6 preguntas de entrevista (turnos 1–6), armado completo y compatible de 7 piezas en turno 7 (`$ 1.677.300 <= $ 2.800.000`, `confirmar=True`, `0` errores) y cierre en turno 8 (`208,4 s`).
- **Oficina** (`Tengo un millón`): 5 turnos totales — 4 preguntas de entrevista (turnos 1–4); en turno 5 inició configuración con `$ 1.000.000` y buscó `cpu`, pero preguntó `"¿Prefieres Intel o AMD?"` (el simulador no responde preferencia de marca y cerró sin agregar piezas, `0` errores, `34,7 s`).
- **Edición de video 4K** (`Tengo 5.500.000`): 8 turnos totales — 5 preguntas de entrevista (turnos 1–5), armado compatible y confirmable de 6 piezas obligatorias en turno 6 (`$ 2.050.200 <= $ 5.500.000`, `confirmar=True`, `3` errores iniciales de códigos inventados frenados por `codigo_visto`) y cierre en turnos 7–8 (`313,7 s`). *Observación:* eligió CPU con video integrado (`R7870G`), por lo que quedó `confirmar=True`, pero omitió GPU dedicada, segundo disco (`almacenamiento_extra`) y `cantidad=2` en RAM (puso 16 GB en lugar de 32 GB).

### Qué probar a mano en la app (paso 12)

1. **Entrevista con botones de punta a punta:** pedir «Armame una PC para jugar Fortnite en 1080p. Tengo 2.800.000 y prefiero Intel», hacer clic en todas las opciones y comprobar que avanza sin demoras en cada botón, arma al final con Intel y **no vuelve a preguntar gama ni presupuesto**.
2. **Pregunta fuera de opción en mitad de la entrevista:** ante una pregunta con botones (p. ej. monitor), escribir texto libre («¿Qué diferencia hay entre 1080p y 1440p?»), comprobar que el asistente responde la duda y permite seguir la entrevista.
3. **Monto ambiguo o en dólares:** probar «Quiero armar una PC entre 1 y 2 millones» (o en dólares) y confirmar que completa la entrevista y luego pregunta cuál presupuesto usar sin adivinar.
4. **Edición de video / 4K:** verificar en una conversación interactiva si al terminar la entrevista agrega GPU dedicada, `cantidad=2` en RAM (32 GB) y segundo disco, o si conviene reforzarlo en el aviso del perfil o skill.

---

## Paso 13: armado completo controlado por código (`#26`, parte 2)

Trabajo realizado sin supervisión en la rama **`paso-13-armado-completo`** (partiendo de `paso-12-entrevista-por-codigo` `b71b853`), sin modificar `web/`, `.env`, `TURNOS_MAXIMOS=8` ni pasar el estado de `#26` a `[x]`.

### Commits del paso 13

- `e82ec61` — Paso 13 (`#26`): controlar por código las piezas que exige el perfil y evitar que pregunte marca (`mcp_tienda/armado/entrevista.py`, `tools.py`, `agente.py`, `skills/armado_pc.md`, `evaluacion/armado_con_entrevista.py`, `tests/test_armado_completo.py` y ajustes mínimos en tests previos).
- Commit siguiente de cierre — Documentar medición y cierre en `PROBLEMAS_DETECTADOS.md` y `RESUMEN_NOCHE.md`.

### Suites de tests (paso 13)

- **34 suites completas de Python (`uv run pytest -q -m "not ollama and not embeddings and not tavily" tests/<archivo>.py` de a una, cubriendo también `b71b853`):** **490 passed, 0 failed** (`3 deselected`, `1 skipped` en `test_contrato_fuente.py`).
- **Suite nueva `tests/test_armado_completo.py`:** `9 passed` (`piezas_faltantes`, GPU si falta o sin video integrado, RAM automática con `cantidad=2` y rechazo si supera 2 módulos, `estado_perfil` solo en texto y no en `artifact`, reintento único de `armado_completo` recordando preferencia, sin bloquear presupuesto ni presupuesto insuficiente, regla 11 y skill).
- **Suites focalizadas verificadas:** `test_entrevista_por_codigo.py` (`11 passed`), `test_entrevista_tools.py` (`12 passed`), `test_armado.py` (`22 passed`), `test_servicio.py` (`18 passed`), `test_app_botones.py` (`4 passed`), `test_model.py` (`12 passed`), `test_explicaciones_rag.py` (`16 passed`).

### Medición única (`evaluacion/resultados/armado_con_entrevista_paso13.json`)

Corrida `uv run python -m evaluacion.armado_con_entrevista --semillas 1` (`qwen3:4b`, `MODEL_NUM_CTX=8192`, Ollama `0.40.16`, `datos/catalogo_real.sqlite`):

| Métrica (semilla 1, 3 corridas) | Paso 12 | Paso 13 |
|---|---|---|
| Entrevista completa | `3/3` | **`3/3`** |
| Perfil correcto | `3/3` | **`3/3`** |
| Preguntas de gama fuera de entrevista | `0` | **`0`** |
| Armados completos | `2/3` | **`2/3`** |
| Cumplen el perfil completo | `1/3` *(solo Fortnite)* | **`2/3`** *(Oficina + Edición 4K)* |
| Compatibles (`se_pueden_confirmar`) | `2/3` | **`2/3`** |
| Dentro del presupuesto | `3/3` | **`3/3`** |
| Con críticas sin datos | `0/3` | **`0/3`** |
| Afirmaciones sin tool | `0` | **`0`** |
| Llamadas promedio | `22,7` | `22,7` |
| Llamadas con error | `3` | **`0`** |
| Tiempo promedio | `3,1 min` | `5,0 min` |

**Turnos por etapa (`TURNOS_MAXIMOS=8`) y piezas del perfil:**
- **Oficina (`Tengo un millón`, `oficina`):** `8` turnos (`4` entrevista + `4` armado) — **`6` piezas**, `faltan=[]`, **`cumple_perfil=True`**, `ram_total_gb=8`, `tiene_gpu=False` (CPU con integrado `IG5900`), `tiene_segundo_disco=False`, `compatible`, `confirmar=True`, `$ 705.200 <= $ 1.000.000`, `22` llamadas (`0` error), `220,6 s`. Superó el bloqueo de `"¿Prefieres Intel o AMD?"` del paso 12.
- **Edición de video 4K (`Tengo 5.500.000`, `edicion_video`):** `7` turnos (`5` entrevista + `2` armado) — **`8` piezas**, `faltan=[]`, **`cumple_perfil=True`**, **`ram_total_gb=32`** (`162X8G` ×2 automática), **`tiene_gpu=True`** (`56TI3F`), **`tiene_segundo_disco=True`** (`WDB1TB`), `compatible`, `confirmar=True`, `$ 3.461.550 <= $ 5.500.000`, `28` llamadas (`0` error), `358,4 s`.
- **Fortnite 1080p (`Tengo 2.800.000 y prefiero Intel`, `juegos_1080p`):** `7` turnos (`6` entrevista + `1` armado) — `0` piezas, `cumple_perfil=False`, `18` llamadas (`0` error), `317,2 s`. Buscó CPU (`12400F`) y enseguida buscó `motherboard` con `texto="LGA1700"` (`0` resultados porque el catálogo usa `"1700"`) en lugar de agregar primero la CPU para activar `compatible_con`, agotando el turno en texto sin agregar componentes.

### Qué probar a mano en la app (paso 13)

1. **Oficina sin preferencia de marca:** pedir «Necesito una PC para oficina: planillas y mail. Tengo un millón», responder los botones y verificar que arma las **6 piezas compatibles** sin frenar a preguntar Intel o AMD.
2. **Edición 4K completo según perfil:** pedir «Quiero una PC para editar video en 4K, con un disco rápido y otro grande. Tengo 5.500.000», responder los botones y comprobar en el panel derecho que quedan cargados **RAM ×2 (32 GB)**, **GPU dedicada** y **segundo disco (almacenamiento_extra)** dentro del presupuesto.
3. **Fortnite 1080p con preferencia Intel:** probar «Armame una PC para jugar Fortnite en 1080p. Tengo 2.800.000 y prefiero Intel» y verificar si agrega el procesador Intel primero y luego la motherboard compatible (o si vuelve a buscar `"LGA1700"` por texto).
4. **Botón Cambiar después del armado:** tras armar sin preguntar marca, probar cambiar procesador o gabinete desde el botón **Cambiar** del panel derecho.

---

## Paso 14: Cambiar y Confirmar pedido con PDF en el chat web (`#34`) y medición (`#26`)

Trabajo realizado sin supervisión en la rama **`paso-14-cambiar-confirmar`** (partiendo de `paso-13-armado-completo` `d2436a1`), sin tocar `rag/docs/`, tabla de gamas, `sin_socket`, `piezas_faltantes`, `TURNOS_MAXIMOS=8` ni `.env`.

### Commits del paso 14

- `65eca6e` — Paso 14 (`#34`): endpoints Cambiar/Confirmar, presupuesto en PDF con `fpdf2` y descarga en Streamlit (`pyproject.toml`, `uv.lock`, `presupuesto_pdf.py`, `servicio.py`, `app.py`, `tests/test_presupuesto_pdf.py`, `tests/test_servicio.py`, `tests/test_app.py`).
- `6d38f66` — Paso 14 (`#34`): botones **Cambiar** y **Confirmar pedido** con PDF en el chat web y docs (`web/app/api/agente/conversaciones/[id]/armado/{alternativas,cambiar,confirmar}/route.ts`, `web/components/chat-agente/`, `web/components/vista-armado/`, `web/app/page.tsx`, `docs/GUIA_INTEGRACION.md`, `CLAUDE.md`).
- Commit siguiente de cierre — Registrar cierre de `#34`, medición `#26` y resumen en `PROBLEMAS_DETECTADOS.md` y `RESUMEN_NOCHE.md`.

### Suites de tests y build web (paso 14)

- **Web (`web/`):** `npm --prefix web run typecheck` y `npm --prefix web run build` — **OK** (sin errores; compiladas las 3 nuevas rutas API `/api/agente/conversaciones/[id]/armado/{alternativas,cambiar,confirmar}`).
- **35 suites completas de Python (`uv run pytest -q -m "not ollama and not embeddings and not tavily" tests/<archivo>.py` de a una):** **503 passed, 0 failed** (`3 deselected`, `1 skipped` en `test_contrato_fuente.py`).
- **Suites nuevas / modificadas en este paso:** `test_presupuesto_pdf.py` (`1 passed`), `test_servicio.py` (`21 passed`), `test_app.py` (`10 passed`), `test_armado_completo.py` (`18 passed`, incluye tests de `d2436a1`), `test_web.py` (`8 passed, 1 deselected`), `test_app_botones.py` (`4 passed`).

### Medición única (`evaluacion/resultados/armado_con_entrevista_paso14.json`)

Corrida `uv run python -m evaluacion.armado_con_entrevista --semillas 1` (`qwen3:4b`, `MODEL_NUM_CTX=8192`, Ollama `0.40.16`, `datos/catalogo_real.sqlite`):

| Métrica (semilla 1, 3 corridas) | Paso 13 | Paso 14 *(sobre `d2436a1`)* |
|---|---|---|
| Entrevista completa | `3/3` | **`3/3`** |
| Perfil correcto | `3/3` | **`3/3`** |
| Preguntas de gama fuera de entrevista | `0` | **`0`** |
| Armados completos | `2/3` | **`3/3`** |
| Cumplen el perfil completo | `2/3` | **`3/3`** |
| Compatibles (`se_pueden_confirmar`) | `2/3` | **`3/3`** |
| Dentro del presupuesto | `3/3` | **`3/3`** |
| Con críticas sin datos | `0/3` | **`0/3`** |
| Afirmaciones sin tool | `0` | **`0`** |
| Llamadas promedio | `22,7` | `26,7` |
| Llamadas con error | `0` | **`0`** |
| Tiempo promedio | `5,0 min` | **`4,2 min`** |

**Turnos por etapa (`TURNOS_MAXIMOS=8`) y detalle por corrida:**
- **Fortnite 1080p (`Tengo 2.800.000 y prefiero Intel`, `juegos_1080p`):** `7` turnos (`6` entrevista + `1` armado) — **`7` piezas**, `faltan=[]`, **`cumple_perfil=True`**, `ram_total_gb=16` (`832BLK` ×2), `tiene_gpu=True` (`6G3050`), `tiene_segundo_disco=False`, `compatible`, `confirmar=True`, **`$ 1.678.300 <= $ 2.800.000`**, `28` llamadas (`0` error), `242,8 s`. El arreglo de `d2436a1` permitió agregar la CPU Intel `10400F` y luego la motherboard compatible `H47MDS` sin quedar bloqueado en `"LGA1700"`.
- **Oficina (`Tengo un millón`, `oficina`):** `5` turnos (`4` entrevista + `1` armado) — **`6` piezas**, `faltan=[]`, **`cumple_perfil=True`**, `ram_total_gb=8`, `tiene_gpu=False`, `tiene_segundo_disco=False`, `compatible`, `confirmar=True`, **`$ 695.700 <= $ 1.000.000`**, `22` llamadas (`0` error), `172,5 s`.
- **Edición de video 4K (`Tengo 5.500.000`, `edicion_video`):** `8` turnos (`5` entrevista + `3` armado) — **`9` piezas** (incluye cooler `AMDPER`), `faltan=[]`, **`cumple_perfil=True`**, **`ram_total_gb=32`** (`HKD432` ×2), **`tiene_gpu=True`** (`38TI3F`), **`tiene_segundo_disco=True`** (`WDB1TB`), `compatible`, `confirmar=True`, **`$ 3.555.500 <= $ 5.500.000`**, `30` llamadas (`0` error), `341,5 s`.

### Qué probar a mano en la app (paso 14)

1. **Armado completo y botón Cambiar en el chat web (`#34`):** pedir una PC (por ejemplo Fortnite 1080p con `$ 2.800.000`), responder los botones, esperar las tarjetas del panel derecho, hacer clic en **Cambiar** en una pieza (ej. almacenamiento o gabinete), elegir una alternativa compatible y comprobar que actualiza el componente y el total al instante sin consultar al modelo.
2. **Botón Confirmar pedido y descarga de PDF (`#34`):** con el armado completo, hacer clic en **Confirmar pedido** y verificar que descarga `presupuesto-<referencia>.pdf` con la tabla de componentes, precios, total, compatibilidad y notas sin datos; luego probar **Cambiar** otra pieza y verificar que se limpia el estado de confirmación anterior.
3. **Intento de confirmar incompleto y descarga en Streamlit (`#34` / `#26`):** comprobar que con armado incompleto o incompatible el backend devuelve `409` con motivos claros (en la UI el botón queda deshabilitado cuando faltan piezas o hay error de compatibilidad) y probar también **Confirmar pedido** → **Descargar presupuesto (PDF)** en Streamlit.
