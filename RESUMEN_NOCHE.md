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
