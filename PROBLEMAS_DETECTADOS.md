# Problemas detectados

Lista viva de lo que se va notando mal en el asistente, para corregirlo después en orden. Cada punto tiene un estado:

- `[ ]` pendiente
- `[~]` en curso o resuelto a medias
- `[x]` resuelto

**Cómo agregar uno nuevo:** copiá una entrada, poné el próximo número y completá: *Qué se vio* (lo que viste en pantalla), *Causa* (si la sabés o la sospechás), *Dónde* (archivo) e *Idea de arreglo*. Gravedad: **alta** (el agente falla o miente), **media** (funciona peor de lo esperado), **baja** (detalle).

Última actualización: 2026-11-20 (paso 13; cerrados 4, 9, 14, 15, 25, 29, 30 y 31; decidido el 34).

---

## Resumen

| N.º | Problema | Gravedad | Estado |
|---|---|---|---|
| 1 | El filtro `gama` no encuentra nada («21 productos no están en la tabla de gamas») | alta | `[x]` |
| 2 | El agente inventa precios de ejemplo muy bajos al pedir el presupuesto | alta | `[x]` |
| 3 | Las reglas de compatibilidad dan «sin datos» con el catálogo real | alta | `[x]` |
| 4 | Faltan datos en el catálogo real (GPU, gabinete, cooler, UPS, cables) | media | `[x]` |
| 5 | El RAG devuelve fragmentos de la gama equivocada | media | `[x]` |
| 6 | Cinco documentos del RAG están vacíos | media | `[x]` |
| 7 | El agente usa el catálogo de prueba por defecto | media | `[x]` |
| 8 | Tras buscar requisitos en la web no ubica el juego en una gama | media | `[x]` |
| 9 | El razonamiento del modelo local sale en inglés | baja | `[x]` |
| 10 | El detalle de «Skill armado_pc» se ve vacío en la interfaz | baja | `[x]` |
| 11 | Gemini devuelve 503 («alta demanda») y se mostraba el error crudo | media | `[x]` |
| 12 | Falta el selector de modelo en el servicio y en el chat web | media | `[x]` |
| 13 | El disco secundario (SSD 2,5" o HDD) solo está en la documentación | media | `[x]` |
| 14 | Los precios máximos de `gamas.md` están en pesos y sin cotización | baja | `[x]` |
| 15 | `gamas.md` tiene secciones y datos sin completar | baja | `[x]` |
| 16 | Reglas del system prompt mal numeradas | baja | `[x]` |
| 17 | `CLAUDE.md` describe un alcance viejo (Streamlit como interfaz principal) | baja | `[x]` |
| 18 | La carpeta `finetuning/` está vacía (queda para después de la presentación) | baja | `[ ]` |
| 19 | Los cambios de esta etapa están sin commitear | baja | `[x]` |
| 20 | El modelo dice «agregué el procesador» sin llamar a la tool | alta | `[x]` |
| 21 | El panel «Armá tu PC» no mostraba el avance del armado | media | `[x]` |
| 22 | La conversación no entra en el contexto del modelo: se «olvida» de la conversación vieja | alta | `[~]` |
| 23 | El razonamiento del modelo se guarda en el historial y se reenvía en cada turno | alta | `[x]` |
| 24 | El modelo escribe la llamada a una tool como texto JSON en vez de ejecutarla | media | `[x]` |
| 25 | 29 modelos de CPU y GPU sin gama: decisiones pendientes del grupo | media | `[x]` |
| 26 | El asistente pregunta la gama en vez de deducirla del uso | alta | `[~]` |
| 27 | Ajustes de Ollama / llama.cpp para que el modelo ande más liviano | media | `[ ]` |
| 28 | El razonamiento de `qwen3:4b` no se puede acotar | media | `[ ]` |
| 29 | Las consultas que escribe el modelo para el RAG no se parecen a los documentos | media | `[x]` |
| 30 | Experimento: RAG solo contra RAG con documento hipotético (HyDE) | media | `[x]` |
| 31 | El presupuesto que escribe el usuario no se valida | media | `[x]` |
| 32 | Ante preguntas de explicación el agente no consulta la documentación y repregunta | alta | `[x]` |
| 33 | El armado puede ofrecer piezas de plataformas viejas (socket 775, DDR3) | media | `[x]` |
| 34 | El chat web no tiene Cambiar ni Confirmar pedido (decisión del grupo) | media | `[~]` |

---

## 1. El filtro `gama` no encuentra nada

- **Estado:** `[ ]` · **Gravedad:** alta
- **Qué se vio:** el agente llamó a `buscar_productos` con `categoria=cpu, gama=media, precio_max=400000, texto=intel i5` y devolvió «Sin resultados». Debajo: «21 productos no están en la tabla de gamas: no se sabe su gama».
- **Causa:** `gama` **no es un atributo del catálogo**: ningún producto trae un campo «gama». El código la deduce buscando el modelo del procesador o de la placa de video en `rag/docs/tabla_cpu_gpu_por_gama.md`, y esa tabla está **vacía** (0 filas). Por eso cualquier filtro por gama excluye todo. Además `ajustar_presupuesto` no puede reemplazar CPU ni GPU «de la misma gama», porque no sabe cuál es.
- **Dónde:** `mcp_tienda/armado/gamas.py` (`clasificar_gama`, lee la tabla), `rag/docs/tabla_cpu_gpu_por_gama.md`, filtro `gama` en `mcp_tienda/servidor.py` (`buscar_productos`).
- **Idea de arreglo** (hay dos caminos, se pueden combinar):
  1. **Completar la tabla** con los modelos reales del catálogo (86 procesadores y 27 placas de video). Es lo que pide el diseño: la gama sale de una tabla y de reglas, no del modelo de lenguaje.
  2. **Inferir la gama por reglas** cuando el modelo no está en la tabla, usando señales del catálogo: línea del procesador (i3 / i5 / i7 / i9, Ryzen 3 / 5 / 7 / 9), generación, consumo (`consumo_max_w`), precio relativo dentro de su categoría, y para placas de video la VRAM y la serie. Tiene que ser determinista y devolver «sin datos» solo cuando de verdad no alcanza.
  3. Cuando un producto no tenga gama, que el filtro **no lo descarte en silencio**: hoy el aviso aparece pero la búsqueda ya devolvió vacío.
- **Estado:** `[x]` (2026-11-19).
- **Medido antes:** tabla con 0 filas, gama «sin datos» en 0 de 86 CPU y 0 de 27 GPU del catálogo real. Además: (a) la tabla no reconocía los nombres pegados de la tienda («RTX5060TI», «GTX1650»); (b) el código solo conocía tres gamas (faltaba premium); (c) el filtro descartaba en silencio.
- **Solución aplicada:**
  - `mcp_tienda/armado/tabla_gamas.py`: los criterios de `gamas.md` en código (`CRITERIOS_GAMA`: línea de procesador + socket, y modelos de placa de video por gama) y un generador que escribe `rag/docs/tabla_cpu_gpu_por_gama.md` (`uv run python -m mcp_tienda.armado.tabla_gamas --escribir-doc`). Asigna solo lo que dicen los criterios; lo demás va a «Pendientes de decidir». La sección «Agregados y correcciones a mano» se conserva al regenerar y manda sobre lo generado. `evaluacion/reparto_presupuesto.py` usa los mismos criterios.
  - `gamas.py`: normalizador que entiende «RTX5060TI» = «RTX 5060 Ti» sin confundir «5600» con «5600G»; cuarta gama `premium`; si un modelo se repite, manda la última fila.
  - `buscar_productos`: acepta `gama=premium`; si ninguno cumple la gama, los productos sin gama vuelven aparte en `productos_sin_gama` con la nota «no los presentes como de gama X».
- **Resultado:** gama asignada a 65 de 86 CPU y 13 de 27 GPU (78 de 113). `buscar_productos(cpu, gama=media, texto="intel i5", precio_max=400000)` pasó de 0 a 3 resultados (10400F, 12400F, 14400F). Pedido nuevo de punta a punta con Ollama («gama media, Intel, 3.000.000»), 3 semillas: en 2 encontró los i5 reales y preguntó cuál, con precios de la tool; en 1 escribió la llamada a una tool como texto (problema 24).
- **Prueba:** `tests/test_tabla_gamas.py` (19 tests). RAG reindexado.
- **Pendiente:** las 29 decisiones de gama (problema 25).
- **Nota:** el `precio_max=400000` que eligió el modelo es razonable (el procesador de gama media pesa cerca del 13 % de unos $ 2.762.000), pero salió de su criterio. Conviene que el límite salga del reparto del presupuesto.
- **Segunda causa, encontrada el 2026-11-20:** la gama no está en la base y el servidor la filtra después de buscar, pero traía solo los 50 productos más baratos de la categoría. Si había más de 50, las piezas caras nunca entraban: en el catálogo real, `buscar_productos(cpu, gama=premium)` daba 0 aunque la tienda tiene un Core Ultra 9 285K con stock. Ahora, cuando filtra después de buscar (gama o compatibilidad), trae todos los candidatos (`LIMITE_MAXIMO` en `mcp_tienda/catalogo.py`); el modelo sigue viendo como mucho 20. Con el catálogo real: CPU premium 1, alta 11; GPU alta 4, media 7. Test: `test_el_filtro_de_gama_encuentra_piezas_caras_aunque_haya_muchas_baratas` en `tests/test_servidor_mcp.py`.
- **Vacíos que siguen siendo datos, no errores:** no hay GPU de gama baja (esa gama no lleva placa de video) ni GPU premium con stock, y 12 de las 23 GPU con stock no tienen gama en la tabla (problema 25).

## 2. El agente inventa precios de ejemplo

- **Estado:** `[ ]` · **Gravedad:** alta
- **Qué se vio:** al preguntar el presupuesto, el agente dijo «Ej: $20.000, $30.000». En la tienda una PC cuesta millones.
- **Causa:** el ejemplo no está escrito en el proyecto: lo inventó `qwen3:4b` porque el prompt no le da una escala de precios.
- **Dónde:** `PROMPT_SISTEMA` en `agente.py`; `skills/armado_pc.md` (dice solo «Presupuesto en pesos»).
- **Idea de arreglo:**
  - Agregar una regla al prompt: no dar ejemplos de precio inventados; usar solo las referencias por gama (totales típicos de `reparto_presupuesto.md`).
  - Hacer la pregunta del presupuesto con `preguntar_al_usuario` y opciones por gama (botones), así no hay que escribir ejemplos.
  - Repetir la escala en la skill de armado.
- **Ojo:** si los precios se escriben a mano en el prompt quedan viejos cuando cambian. Lo ideal es que se tomen del último `reparto_presupuesto.md`.
- **Estado:** `[x]` (2026-11-19).
- **Medido antes** (2 pedidos sin presupuesto × 5 semillas, Ollama, ventana 8192): **9 de 10** corridas ofrecieron montos inventados («5000 / 8000 / 10000», «Menos de $ 20.000», «$500-$1000»), entre 20 y 500 veces menos que la escala real ($ 998.000 a $ 8.800.000). Ninguna consultó el reparto. Causa: el modelo pregunta el presupuesto antes de buscar nada, sin ningún dato de precios en el contexto, y `preguntar_al_usuario` le pide opciones.
- **Solución aplicada:**
  - **Escala en el prompt, generada del reparto** (`escala_de_presupuesto` y `bloque_de_presupuesto` en `agente.py`): bloque «Presupuesto de referencia» con el total típico y el rango de cada gama, leído de `rag/docs/reparto_presupuesto.md`. Al regenerar el reparto, el prompt cambia solo.
  - **Regla 15:** preguntar el presupuesto con las cuatro gamas como opciones, copiadas tal cual; no inventar montos; si preguntan cuánto sale, responder con esos totales.
  - **Métrica** `montos_sin_respaldo` (también en `evaluacion/afirmaciones_sin_tool.py`): montos mostrados al usuario, en el texto o en los botones, que no salieron de una tool, del usuario ni de la escala.
- **Resultado:** **0 de 10** corridas con montos inventados. Todas preguntaron por gama o respondieron con los totales de referencia. El system prompt pasó de 1.379 a 1.750 tokens desde el inicio de la sesión (incluye la regla 14 del problema 20).
- **Relacionado:** esto cubre los montos que **inventa el agente**. Los que **escribe el usuario** («tengo $ 20.000», «2 palos») se validan en el problema 31.
- **Detalle a mejorar:** a veces copia la línea entera como botón («Gama baja (cerca de $ 1.000.000): entre $ 919.000 y $ 1.119.000»), que queda largo, y otras pone solo «Gama baja».
- **Prueba:** `tests/test_montos.py` (6 tests).

## 3. Las reglas de compatibilidad dan «sin datos» con el catálogo real

- **Estado:** `[ ]` · **Gravedad:** alta
- **Qué se vio:** con el catálogo real casi todas las reglas devuelven «sin datos». Está descripto en `SIGUIENTE_SESION.md`.
- **Causa:** las reglas de `reglas.py` se hicieron para el catálogo de prueba. Por ejemplo, la de la fuente usa `gpu.consumo_w`, que el catálogo real no trae. Los atributos nuevos que sí hay (`generacion`, `ranuras_ram`, `ranuras_m2`, `puertos_sata`, `fuente_recomendada_w`, `incluye_cooler`, etc.) todavía no se usan.
- **Dónde:** `mcp_tienda/armado/reglas.py`, `mcp_tienda/armado/candidatos.py`, `mcp_tienda/modelos.py`.
- **Idea de arreglo:** el plan de reglas nuevas ya está en `SIGUIENTE_SESION.md` (generación de CPU y placa, formato del módulo de RAM, ranuras de RAM, puertos M.2 y SATA, potencia del cooler, fuente rehecha, etc.), con cantidades y segundo disco. Hay que aprobarlo antes de implementar.
- **Estado:** `[x]` (2026-11-19, paso 9).
- **Medido antes** (`uv run python -m evaluacion.reglas_catalogo`, catálogo real, 2000 armados al azar con piezas en stock, semillas 0 y 1; línea de base en `evaluacion/resultados/reglas_catalogo_antes.json`):
  - `potencia_fuente` **59-61 % sin datos** (usaba `gpu.consumo_w`, que el catálogo real no trae en ninguna placa); `largo_gpu_gabinete` **100 % sin datos**.
  - **33 de 33 fuentes** dejaban **0 placas de video** candidatas: `candidatos.py` filtraba por `consumo_w__max` y en SQL `NULL <= 360` no es verdadero.
  - **57 % de los armados se podían confirmar con una falla física** que ninguna regla miraba: RAM SODIMM o ECC 27 %, CPU sin cooler 14 %, sin video 10 %, fuente corta 5 %, cooler corto 2 %, generación 1 %. Confirmar solo frenaba con «no cumple»: un «sin datos» pasaba.
- **Solución aplicada:**
  - **Reglas** (`mcp_tienda/armado/reglas.py`): nuevas `generacion_cpu_placa`, `modulo_ram` (DIMM), `ranuras_ram`, `puertos_almacenamiento` (M.2 y SATA; un disco «M.2 SATA» da «sin datos»), `video`, `cooler`, `potencia_cooler` y `conectores_gpu`. `potencia_fuente` rehecha: la fuente es la elegida o la del gabinete, y hace falta lo más exigente entre `(consumo máximo de la CPU + consumo de la GPU si se conoce + 75 W) × 1,3` y la fuente que recomienda el fabricante de la GPU. El consumo de la CPU es `consumo_max_w` (si falta, `tdp_w`).
  - **Críticas y avisos:** cada resultado trae `critica`. «Sin datos» en una crítica impide confirmar; en un aviso (`REGLAS_AVISO`: largo y conectores de la GPU) no, pero aparece en `avisos`. «No cumple» bloquea siempre.
  - **Piezas obligatorias según lo elegido** (`lugares_obligatorios`): la fuente no hace falta si el gabinete trae una; la GPU sí si la CPU no tiene video; el cooler sí si la CPU no lo trae. La usan las reglas, Confirmar, el resumen para el modelo y la barra de progreso de la app.
  - **Candidatos** (`candidatos.py`): sin filtro por `consumo_w`; filtros por generación, DIMM, módulos y ranuras, conexión libre del disco, potencia del cooler, fuente recomendada y potencia mínima (misma cuenta que la regla). Además `buscar_productos` con `compatible_con` pasa cada candidato por las reglas y descarta los que dan «no cumple»: el filtro y la regla nunca se contradicen.
  - **Catálogo de prueba:** campo `atributos_declarados` en `ProductoCrudo` (dato estructurado que manda sobre lo leído del texto), cargado desde `declarados` de `semillas.yaml` y deducido por el generador.
  - **Medición fija:** `evaluacion/reglas_catalogo.py` (cobertura, simulación, falsos compatibles con la misma decisión que el botón Confirmar, candidatos de GPU).
- **Resultado** (catálogo real recargado, semillas 0 y 1, con cantidades y segundo disco): **0 armados confirmables con una falla física**; `potencia_fuente` sin datos 10 % (las 4 GPUs sin fuente recomendada); **0 de 33 fuentes** dejan sin placas de video. Se pueden confirmar el 19-20 % de los armados al azar (antes 83 %, la mayoría con fallas).
- **Prueba:** `tests/test_compatibilidad.py` (43), `tests/test_servidor_mcp.py` (filtros, cantidades), `tests/test_armado.py` (cantidades y segundo disco), `tests/test_guia_compatibilidad.py` (3). Suite: 329 pasan, 1 se saltea.
- **Resultado con el agente (paso 9g):** `AMN_CATALOGO_DB=datos/catalogo_real.sqlite uv run python -m evaluacion.armado_punta_a_punta --semillas 1 2 3` (`qwen3:4b`, ventana 8192, temperatura 0,6 con semilla fija; hasta 4 turnos, contestando «elegí vos y seguí» si pregunta). 3 pedidos × 3 semillas:

  | Pedido | Completas y confirmables | Detalle |
  |---|---|---|
  | Fortnite 1080p, $ 2.800.000, Intel | 0 / 3 | 2 corridas escribieron la llamada a `iniciar_configuracion` como texto JSON (problema 24); 1 armó 5 piezas pero eligió una GT 1030 porque filtró GPUs por `consumo_w`, que el catálogo no trae |
  | Oficina, $ 1.000.000 | 1 / 3 | 1 se cortó con 2 piezas; 1 eligió un Celeron 775 con placa 775 (problema 33): las reglas dieron «sin datos» y bloquearon Confirmar |
  | Edición de video 4K con dos discos, $ 5.500.000 | 2 / 3 | 1 usó `almacenamiento_extra`; 1 se cortó con 4 piezas |

  - **Lo que hace el código, anduvo:** 0 armados confirmables con fallas, 0 afirmaciones de acción sin tool (el middleware corrigió 1), 9 códigos inventados frenados por el control de códigos vistos (`RTX3060`, `GTX1650`, `ATX123`…). Los 3 armados completos son compatibles y entran en el presupuesto.
  - **Lo que falla es cómo busca el modelo:** 30 llamadas con error en 150 (10 atributos que no existen, como `tipo_ram` en RAM o `capacidad_tb`; 9 códigos no buscados), **nunca usó `compatible_con`** (así no actúan los filtros por reglas de los candidatos) y nunca puso cantidad en la RAM. Promedio: 16,7 llamadas y 5,7 minutos por corrida.
  - **Qué sigue (paso 10):** el perfil de uso convertido en filtros por código (problema 26), para que el modelo no arme los filtros a mano; problema 24 (llamadas escritas como texto) y 33 (plataformas viejas).

## 4. Faltan datos en el catálogo real

- **Estado:** `[ ]` · **Gravedad:** media
- **Qué se vio:** en la carga de 4266 productos, atributos con dato: GPU 49 %, gabinete 52 %, cooler 56 %, cables 67 %, UPS 35 %. Almacenamiento 100 %, RAM 98 %, motherboard 96 %, fuente 93 %, CPU 92 %.
- **Causa:** el texto de la tienda no siempre trae el dato, o `formato_amn.py` no lo sabe leer.
- **Dónde:** `mcp_tienda/ingesta/formato_amn.py`, `mcp_tienda/ingesta/extraccion.py`, `datos/esquemas/*.yaml`; reporte con `uv run python -m evaluacion.calidad_catalogo`.
- **Idea de arreglo:** mirar qué productos de GPU, gabinete, cooler y UPS quedaron sin dato y ampliar las reglas de lectura. Lo que no se pueda leer del texto se puede pedir a la tienda como campo estructurado (propuestas en `docs/MEJORAS_API_ARMADO_PC.md`).
- **Estado:** `[~]` (2026-11-19, paso 9).
- **Hecho:** los sockets y memorias viejas (LGA775 a 1156, AM1, AM3, FM2, DDR2, DDR3) se guardan con `valores_fuera_del_armado` en el esquema (no se listan en el prompt). Antes quedaban en nulo y las reglas daban «sin datos» en vez de «no cumple». Catálogo recargado: atributos con dato en CPU 92 → 94 %, motherboard 96 → 99 %, RAM 98 → 100 %; precios y stock iguales.
- **Lo que sigue faltando** (productos con stock): `gpu.consumo_w` y `largo_mm` 0 %, `gabinete.largo_max_gpu_mm` 0 %, `gpu.fuente_recomendada_w` 83 % (faltan GT 210, Quadro P620 y dos RX 550), `gpu.conectores_energia` 52 %, `cooler.potencia_enfriamiento_w` 80 %, `cooler.sockets` 89 %. Son los «sin datos» que quedan en las reglas. Se pueden pedir a la tienda como campos estructurados.
- **Cerrado como aceptado (2026-11-20):** el grupo acepta el problema. Los datos que faltan no están en el texto de la tienda y no se pueden leer por código; los tiene que cargar TodoComputación como campos estructurados (`docs/MEJORAS_API_ARMADO_PC.md`). Mientras tanto, las reglas devuelven «sin datos» y el asistente lo avisa.

## 5. El RAG devuelve fragmentos de la gama equivocada

- **Estado:** `[ ]` · **Gravedad:** media
- **Qué se vio:**
  - «Qué disco usa la gama alta» trajo el reparto de la gama **media**.
  - Buscar «gama media juegos reparto de presupuesto tabla cpu gpu» trajo las **cuatro** gamas, incluida premium.
- **Causa:** los fragmentos (chunks) son largos y mezclan varias gamas y varios componentes; el modelo de embeddings no distingue bien «media» de «alta» dentro de un texto grande.
- **Dónde:** `rag/ingest.py` (tamaño de fragmento), estructura de `rag/docs/gamas.md` y `rag/docs/reparto_presupuesto.md`.
- **Idea de arreglo:** partir los documentos con un subtítulo por gama y componente («Gama alta: disco») para que cada fragmento hable de una sola cosa; achicar el tamaño de fragmento; y medir con las ~30 consultas de evaluación del RAG que pide el proyecto.
- **Estado:** `[x]` (2026-11-19).
- **Causa medida:** el splitter cortaba cada 1000 caracteres sin respetar secciones: «Reparto en gama baja» terminaba con la gama media, «Gama alta» arrastraba premium, y 7 de los 10 fragmentos de la tabla eran filas sueltas sin título.
- **Solución aplicada:**
  - **A.** `rag/ingest.py` corta por sección de Markdown (`MarkdownHeaderTextSplitter`, y subdivide solo si una sección es muy larga). Cada fragmento empieza con «documento › sección › subsección» y lleva en la metadata `gama` (de su título; «general» si no nombra una sola). El generador de la tabla escribe una subsección por componente y gama («Procesadores de gama media»).
  - **C.** `rag/consulta.py`: si la consulta nombra una sola gama, la búsqueda filtra por esa gama y completa con los generales (por código; si la base es vieja, busca sin filtro).
  - **D.** Si la consulta nombra un CPU o una GPU, la primera respuesta es su fila de la tabla, buscada por código con `clasificar_gama` (o «sin datos»).
  - **E.** Conjunto de 30 consultas en `evaluacion/conjuntos/rag_consultas.yaml` y `uv run python -m evaluacion.rag` (con `--solo-vectores` mide la búsqueda por parecido sola).
- **Resultado** (30 consultas, `bge-m3`): acierto@1 **40 % → 73 %**, acierto@4 **70 % → 100 %**, fragmentos de otra gama **85 % → 9 %**. Solo el corte por sección (A) da 67 % / 97 % / 43 %; el filtro y la búsqueda exacta suman el resto.
- **Lo que queda:** las 8 consultas que no aciertan primero son preguntas de `gamas.md` («cuánta RAM tiene la gama media») que traen primero el reparto de esa misma gama («Gama media, memoria ram: 23 %»); el fragmento correcto está segundo o tercero. Además `gamas.md` tiene campos vacíos (problema 15): lo que no está escrito no se puede recuperar.
- **Prueba:** `tests/test_rag_secciones.py` (10 tests). RAG reindexado (28 fragmentos).

## 6. Cinco documentos del RAG están vacíos

- **Estado:** `[ ]` · **Gravedad:** media
- **Qué se vio:** al indexar: «Sin contenido todavía: `caracteristicas_por_actividad.md`, `guia_compatibilidad.md`, `guias_de_compra.md`, `tabla_cpu_gpu_por_gama.md`, `tutorial_armado_pc.md`».
- **Causa:** son plantillas con comentarios «Escribir acá». Cantidad de huecos: 10, 7, 5, 2 y 11.
- **Efecto:** el agente no puede explicar actividades, compatibilidad, tutorial ni guías de compra; la regla del prompt le prohíbe explicar desde su conocimiento general.
- **Idea de arreglo:** completar los documentos (el contenido lo define el grupo con la tienda) y reindexar con `uv run python -m rag.ingest`.
- **Estado:** `[~]` (2026-11-19): 2 de 3 documentos escritos, como borradores. Falta `guia_compatibilidad.md` (paso 9). El tutorial de armado se borró: el agente se acotó a elegir y comprar (la tienda entrega la PC armada).
- **Medido antes** (4 preguntas de explicación × 2 semillas, Ollama): **0 de 8** respuestas salieron de la documentación correcta. «¿Cómo armo una PC paso a paso?» lo entendió como comprar; «¿Qué UPS necesito?» preguntó la gama de la PC; «¿Cómo sé si un procesador es compatible?» explicó de memoria citando archivos que no lo dicen.
- **Hecho (8a):**
  - `datos/entrevista_armado.yaml` (**borrador para revisar**): 8 perfiles de uso (uso → gama, RAM, placa de video, qué pesa más) y la guía de preguntas de la entrevista (problema 26). Es la única fuente de «uso → gama».
  - `mcp_tienda/armado/perfiles.py` genera la sección «Perfiles de uso» del documento desde ese archivo (`uv run python -m mcp_tienda.armado.perfiles --escribir-doc`), con una subsección por perfil y la gama en el título (así el RAG la filtra).
  - `rag/docs/caracteristicas_por_actividad.md` escrito (borrador): oficina, juegos 1080p/1440p/4K, diseño, edición, programación, streaming y cómo se eligen placa madre, fuente y cooler por necesidad.
  - 9 consultas nuevas en `evaluacion/conjuntos/rag_consultas.yaml` (39 en total; `debe` acepta alternativas).
- **Resultado:** las 9 consultas de actividades traen el fragmento correcto entre los 4 (9/9) y primero en 9/9. Total: acierto@1 77 %, acierto@4 97 %, otra gama 14 % (39 consultas). «¿Qué importa en una PC para jugar en 1440p?» ahora se responde desde el documento (2/2). Pruebas: `tests/test_perfiles.py` (4).
- **Para revisar con el grupo:** las gamas de cada perfil; diseño gráfico va en gama media pero con 32 GB, cuando `gamas.md` dice 16 GB para la media; juegos en 4K con 64 GB.
- **Hecho (8b):** `guias_de_compra.md` (UPS: VA contra W, margen y autonomía; cables; cámaras; almacenamiento; monitores y periféricos), como borrador y con vocabulario de usuario, como pidió el profesor (problema 29). También se escribió un tutorial de armado, que después se borró por el cambio de alcance. Evaluación del RAG sin el tutorial (45 consultas): acierto@1 78 %, acierto@4 98 %, otra gama 12 %.
- **Falta:** `guia_compatibilidad.md`, que tiene que coincidir con las reglas nuevas del paso 9 (8c).
- **Hecho (8c, 2026-11-19):** `rag/docs/guia_compatibilidad.md` (borrador): cómo se revisa, socket y generación, RAM (tipo, DIMM, ranuras), discos (M.2 y SATA), video integrado, cooler, fuente y gabinete. La sección «Números que usa el verificador» la genera `uv run python -m mcp_tienda.armado.guia_compatibilidad --escribir-doc` desde las constantes de `reglas.py`; un test comprueba que el documento esté al día y que la lista de reglas críticas y avisos coincida con el código. 7 consultas nuevas en `rag_consultas.yaml`: 5/7 traen primero la guía y 7/7 entre las 4 primeras. Total (52 consultas): acierto@1 77 %, acierto@4 98 %, otra gama 11 %.
- **Estado:** `[x]`. Los tres documentos escritos siguen siendo borradores para revisar con el grupo.
- **Lo que no se arregla con documentos:** el agente no siempre consulta la documentación antes de responder (problema 32).
- **Efecto secundario:** «la gama baja lleva placa de video?» ahora trae primero el perfil generado («sin placa de video») en vez de `gamas.md`; la respuesta es la misma, pero cuenta como fallo en la evaluación.

## 7. El agente usa el catálogo de prueba por defecto

- **Estado:** `[ ]` · **Gravedad:** media
- **Qué se vio:** el `.env` tiene `AMN_FUENTE_CATALOGO=prueba` y `AMN_CATALOGO_DB=datos/catalogo.sqlite`. Los armados salen con productos y precios de prueba, no con los de la tienda.
- **Causa:** el catálogo real (`datos/catalogo_real.sqlite`, 4266 productos) existe pero no es el que lee el agente.
- **Dónde:** `.env` (`AMN_CATALOGO_DB`).
- **Idea de arreglo:** apuntar a `datos/catalogo_real.sqlite` cuando las reglas nuevas (problema 3) estén hechas. Hasta entonces el de prueba permite ver armados completos.
- **Estado:** `[x]` (2026-11-19). El `.env` ya apunta al catálogo real y las reglas nuevas andan con él (problema 3). El valor por defecto del código sigue siendo `datos/catalogo.sqlite` (prueba) a propósito: es lo que usan los tests y quien clone el repo sin sesión de la tienda.

## 8. Tras buscar requisitos en la web no ubica el juego en una gama

- **Estado:** `[ ]` · **Gravedad:** media
- **Qué se vio:** pidió God of War, buscó los requisitos en la web y después le preguntó el presupuesto al usuario sin decir en qué gama cae el juego.
- **Causa:** depende del problema 1 (tabla de CPU y GPU vacía): no hay con qué ubicar los requisitos del juego. La regla 13 del prompt le pide ubicarlos con `consultar_caracteristicas`.
- **Idea de arreglo:** completar la tabla (incluidos modelos viejos que aparecen en los requisitos: GTX 1060, Core i5-4460, Ryzen 5 1600) y medir con ~15 juegos, como pide la evaluación.
- **Estado:** `[x]` el mecanismo (2026-11-19). Los datos dependen del problema 25.
- **Medido antes** (God of War Ragnarök, resultado web desde la caché, Ollama, 5 semillas): 5/5 buscaron los requisitos, **0/5 consultaron el RAG** y **0/5 ubicaron el juego en una gama**; todas preguntaron la gama. Además la tabla no conoce ninguno de los 10 modelos que piden los requisitos (GTX 1060, RX 5500 XT, Arc A750, i5-4670K, Ryzen 3 1200, RTX 2060 Super, RX 5700, Arc A770, i5-8600, Ryzen 5 3600).
- **Solución aplicada** (todo por código; el modelo no tiene que encadenar tools):
  - `mcp_tienda/armado/requisitos.py`: `leer_requisitos` lee los CPU y GPU de los resultados web y los separa en mínimos y recomendados (solo cuenta modelos en líneas que hablan de CPU o GPU, y decide la sección por votos entre sitios); `ubicar_requisitos` los ubica con la tabla (por componente alcanza una alternativa; por sección manda el más exigente; la gama sugerida es la de los recomendados).
  - `buscar_especificaciones_web` agrega «Gama sugerida: …» (o «sin datos» con los modelos que faltan) a su respuesta y la guarda en el estado (`requisitos`).
  - `preguntar_al_usuario`: si se pregunta la gama, el código pone primero y marca la opción sugerida («— la que piden los requisitos»); si no hay datos, antepone «No pude ubicar estos requisitos en una gama: sus modelos (…) no están en la tabla de referencia».
  - Reglas 13 y 15 del prompt ajustadas como refuerzo.
- **Resultado** (5 semillas): con una tabla de prueba que conoce esos modelos, **5/5** propusieron la gama media (2 en el texto, 3 con el botón marcado por el código). Con la tabla real, **5/5** explicaron que los requisitos no están en la tabla antes de preguntar. 0 gamas inventadas en todos los casos. Los 10 modelos del resultado real se leen bien.
- **Prueba:** `tests/test_requisitos.py` (19 tests).
- **Cambio de criterio (2026-11-20):** la regla 13 solo pasaba la gama, así que el modelo buscaba cualquier pieza de esa gama y nunca la CPU o GPU que pedía el juego. Ahora, por código, `buscar_especificaciones_web` busca en la tienda cada CPU y GPU de los requisitos recomendados (o de los mínimos, si no hay recomendados): `buscar_en_catalogo` y `texto_de_catalogo` en `requisitos.py`, con `mismo_modelo` en `gamas.py` (la RTX 4060 no se confunde con la 4060 Ti). Si la pieza está con stock, el modelo recibe su código y la usa; solo si no está, busca otra de la misma gama con `buscar_pieza_armado`. Regla 13 y `skills/armado_pc.md` actualizadas. Tests: 11 más en `tests/test_requisitos.py`.
- **Arreglado de paso:** `buscar_pieza_armado` no estaba en `TOOLS_QUE_MUESTRAN_CODIGOS`, así que el control de códigos del problema 20 rechazaba la pieza que la propia tool acababa de encontrar. Ahora cuenta. Test en `tests/test_entrevista_tools.py`.
- **Revisión de seguridad (2026-11-20):** `buscar_especificaciones_web` no cuenta como tool que muestra códigos, porque su respuesta trae texto de la web y una página podría nombrar un código del catálogo (en el real los códigos son modelos, como `12400F`). Las piezas que encontró el código quedan en el estado (`requisitos.codigos_en_tienda`) y solo esas se aceptan. El bloque del catálogo va como dato, sin órdenes (las da la regla 13), y se buscan a lo sumo 3 modelos por componente (`MODELOS_A_BUSCAR`). Tests en `tests/test_requisitos.py`.
- **Pendiente:** cargar en la tabla los modelos viejos que piden los juegos (problema 25) y medir con ~15 juegos, como pide la evaluación.

## 9. El razonamiento del modelo local sale en inglés

- **Estado:** `[ ]` · **Gravedad:** baja
- **Qué se vio:** el bloque «Razonamiento» de `qwen3:4b` está escrito en inglés («Yes, that should get the necessary specs from the web…»), aunque la respuesta final sale en español.
- **Causa:** Qwen3 piensa en inglés por defecto. El prompt le pide hablar en español rioplatense, pero eso solo afecta la respuesta.
- **Idea de arreglo:** agregar al prompt «Pensá y respondé siempre en español», o aceptar que el razonamiento es interno (el servicio para la tienda no lo expone). Con `MODEL_RAZONAMIENTO=0` no se muestra.
- **Agregado sin medir (2026-11-20, #9):** se sumó «Pensá y razoná siempre en español, nunca en inglés.» al encabezado de `PROMPT_SISTEMA` en `agente.py`. Falta probarlo a mano con el modelo local (`qwen3:4b`).
- **Cerrado por decisión (2026-11-20):** el razonamiento queda en inglés, que es como Qwen3 razona mejor. Se quitó la línea «Pensá y razoná siempre en español» del prompt. La respuesta al usuario sigue en español y el chat web de la tienda no muestra el razonamiento.

## 10. El detalle de «Skill armado_pc» se ve vacío

- **Estado:** `[x]` · **Gravedad:** baja
- **Qué se vio:** en el chat, el bloque «📖 Skill «armado_pc»» se abre y no muestra nada adentro.
- **Dónde:** `detalle_resultado` / `render_eventos` en `app.py`.
- **Idea de arreglo:** mostrar el texto de la skill (o su descripción) al expandirlo, o un aviso corto de «Skill cargada». A confirmar que sea solo de la interfaz y que el modelo sí reciba el contenido.

## 11. Gemini devuelve 503 («alta demanda»)

- **Estado:** `[x]` · **Gravedad:** media
- **Qué se vio:** `El asistente falló: 503 UNAVAILABLE ... high demand`, en crudo, a mitad de un turno.
- **Causa:** saturación temporal de Google; es común en el plan gratis.
- **Solución aplicada:** 4 reintentos automáticos en `model.py` y mensaje claro en `agente.py` («El modelo está saturado… reenviá el mensaje»). La conversación queda guardada hasta donde llegó.
- **Pendiente relacionado:** `gemini-2.5-flash` ya no está disponible para cuentas nuevas; se usa `gemini-3.8-flash`. Si Google lo cambia, hay que actualizar `GEMINI_MODEL` en el `.env`.

## 12. Falta el selector de modelo en el servicio y en el chat web

- **Estado:** `[x]` · **Gravedad:** media
- **Qué se vio:** el selector (local o Gemini) funciona en Streamlit y en la consola, pero no en `servicio.py` ni en `web/components/chat-agente/`.
- **Idea de arreglo:** campo opcional `modelo` en `POST /chat`, limitado por una lista de permitidos (`AGENTE_MODELOS_PERMITIDOS`, por defecto solo `local`) para que un cliente de la tienda no gaste tu cuota de Gemini. Selector en el componente web solo en modo desarrollo. Actualizar `docs/GUIA_INTEGRACION.md`.
- **Pendiente de probar:** cambiar de modelo a mitad de un armado con la API real (los tests usan modelos falsos).

## 13. El disco secundario solo está en la documentación

- **Estado:** `[x]` (2026-11-20) · **Gravedad:** media
- **Qué se vio:** `gamas.md` dice que la gama alta y la premium llevan un SSD 2,5" o HDD como disco secundario, pero el armado solo admite un disco por lugar y el reparto del presupuesto no lo cuenta.
- **Dónde:** `armado.py`, `mcp_tienda/modelos.py`, `evaluacion/reparto_presupuesto.py`.
- **Idea de arreglo:** el lugar opcional `almacenamiento_extra` con cantidades, ya propuesto en `SIGUIENTE_SESION.md`. La parte del generador que elige un SSD SATA en gama baja no tiene test.
- **Hecho:** lugar `almacenamiento_extra` (categoría almacenamiento) y `cantidades` en la configuración (1 a 4, solo RAM y discos). El total es precio × cantidad; lo calcula el servidor MCP. `agregar_o_reemplazar_componente` acepta `cantidad`; `buscar_productos` y `verificar_compatibilidad` aceptan `cantidades` (y `para_lugar`). Reglas `ranuras_ram` y `puertos_almacenamiento`. El servicio, la app y el chat web muestran la cantidad. La skill pide RAM con cantidad y el segundo disco si hace falta.
- **Hecho en el reparto (paso 10, 2026-11-19):** `evaluacion/reparto_presupuesto.py` arma el disco secundario (SSD SATA o HDD de 1 a 2 TB) en gama alta y premium, y solo si la placa tiene un puerto SATA libre. Medido sin regenerar el documento: alta pasa de $ 5.320.000 a $ 5.799.000 de total típico, y premium de $ 8.800.000 a $ 9.324.000. Test en `tests/test_reparto_presupuesto.py` (4 pasan).
- **Cerrado (2026-11-20):** `rag/docs/reparto_presupuesto.md` regenerado con los nuevos valores de alta y premium y base del RAG (`chroma.sqlite3`) reindexada. Los módulos de RAM del reparto quedan como nota aparte (la RAM va como un solo kit).

## 14. Los precios máximos de `gamas.md` están en pesos y sin cotización

- **Estado:** `[ ]` · **Gravedad:** baja
- **Qué se vio:** los precios máximos quedaron en pesos (baja $ 1.120.000, media $ 3.040.000, alta $ 5.780.000, premium más de $ 5.780.000). Originalmente estaban en dólares y no eran consistentes entre gamas.
- **Causa:** el catálogo no trae cotización del dólar.
- **Idea de arreglo:** definir la cotización de referencia (o el dato del precio en dólares que usa la tienda: `inbdprice`, `margenadie`, `dolar`, ver `docs/MEJORAS_API_ARMADO_PC.md`) y mostrar las dos monedas. Los valores son el techo del rango habitual del reparto del 2026-11-13: hay que recalcularlos cada vez que se regenera.
- **Cerrado (2026-11-20):** los valores de `gamas.md` pasaron a dólares con la cotización de referencia de $ 1.576 por dólar (2026-11-20), con el equivalente en pesos al lado: baja USD 710, media USD 1.930, alta USD 3.670, premium más de USD 3.670 (típico USD 5.580). La escala que usa el asistente para comparar presupuestos sigue en pesos (reparto). Si cambia el dólar, hay que actualizar la cotización del documento y reindexar.

## 15. `gamas.md` tiene secciones y datos sin completar

- **Estado:** `[ ]` · **Gravedad:** baja
- **Qué falta:**
  - La sección «Cómo se decide la gama de un equipo» está vacía.
  - La fecha del encabezado dice «(completar al escribir…)».
  - Quedan tres comentarios «Escribir acá».
  - Los largos de placa de video (330, 360, 400 mm) y los chipsets los puse de criterio general, no salen del catálogo.
  - El precio máximo de gama baja (originalmente USD 500) fue una estimación mía.
- **Idea de arreglo:** completar la sección, la fecha y cotejar largos y chipsets con piezas reales de la tienda.
- **Cerrado (2026-11-20):** completados la fecha, la placa madre, la placa de video, la fuente, el gabinete y el cooler de cada gama, el «para qué alcanza» de cada una y la sección «Cómo se decide la gama de un equipo». Las piezas de ejemplo salen del catálogo con stock (chipsets B760, H610, A620, B650, B850, B860, Z890, X870; placas de video GT 1030 a RTX 5070). Reindexar con `uv run python -m rag.ingest`.

## 16. Reglas del system prompt mal numeradas

- **Estado:** `[x]` (2026-11-20) · **Gravedad:** baja
- **Qué se vio:** en `PROMPT_SISTEMA` la regla 11 aparece después de la 13.
- **Dónde:** `agente.py`.
- **Solución aplicada:** reglas numeradas del `1` al `17` en orden en `PROMPT_SISTEMA` (y regla 17 realineada con la versión 1 de `siguiente_pregunta_armado`). Test en `tests/test_explicaciones_rag.py`.

## 17. `CLAUDE.md` describe un alcance viejo

- **Estado:** `[x]` · **Gravedad:** baja
- **Qué se vio:** `CLAUDE.md` presenta Streamlit como la interfaz principal. El alcance real, según `SIGUIENTE_SESION.md`, es el agente como servicio (`servicio.py`) más el componente de chat y la guía de integración; Streamlit quedó como banco de pruebas. `CLAUDE.md` tampoco menciona el selector de modelo ni la categoría «premium».
- **Idea de arreglo:** actualizar `CLAUDE.md` y `README.md`.
- **Hecho en parte (2026-11-19):** `CLAUDE.md` ya refleja el alcance acotado: el agente ayuda a elegir y comprar (armar una PC a medida y recomendar productos); no hay tutorial de ensamblado porque la tienda entrega la PC armada; queda fuera todo lo que no sea elegir productos de la tienda. Falta lo de Streamlit contra el servicio, el selector de modelo y la gama premium.

## 18. La carpeta `finetuning/` está vacía

- **Estado:** `[ ]` · **Gravedad:** media
- **Qué falta:** generación de trazas con un modelo maestro, notebook de LoRA, exportación a GGUF y la comparación del modelo base contra el afinado (Fase 4 de `PLAN.md`).
- **Nota:** con el selector, Gemini puede servir como modelo maestro para las trazas.
- **Decisión (2026-11-19):** no entra para la presentación del proyecto. Queda al final de la lista, sin hacer, como mejora futura (incluido el mini fine-tuning para formular consultas al RAG del problema 29).

## 19. Los cambios de esta etapa están sin commitear

- **Estado:** `[x]` (2026-11-20) · **Gravedad:** baja
- **Resuelto:** los cambios de esta etapa y del paso 10 ya están commiteados y mergeados en `main` (el cierre de detalles quedó en la rama `paso-10-cierre`).
- **Nota:** el `.env` no se versiona (tiene la clave de Gemini y la sesión de la tienda).

## 20. El modelo dice «agregué el procesador» sin llamar a la tool

- **Estado:** `[x]` (2026-11-19) · **Gravedad:** alta
- **Qué se vio:** el agente respondió «¡Listo! Agregué el procesador Intel i5-12400F» y, al preguntarle dónde, «en la sección procesador». En la conversación guardada no hay ninguna llamada a `agregar_o_reemplazar_componente`: el armado tiene `componentes = {}`. Es una afirmación inventada.
- **Causa:** hay dos. (a) `buscar_productos` devolvió cero resultados por el problema 1. (b) Lo más probable: el historial desbordó el contexto del modelo (problemas 22 y 23), así que `qwen3:4b` perdió de vista las tools y «actuó» en texto en vez de ejecutarlas. Va contra el principio «sin datos no hay afirmación».
- **Segundo caso (mismo patrón):** ante «vamos con la gráfica para jugar», el razonamiento concluye «hay que llamar a `buscar_productos` con estos parámetros» y la respuesta final es «¡Listo! Buscando tarjetas gráficas… 🔍», **sin llamada a la tool** (`tool_calls` vacío y sin llamadas inválidas). Además el razonamiento repite tres veces la misma conclusión.
- **Dónde:** `PROMPT_SISTEMA` en `agente.py`; tools de armado en `tools.py`.
- **Idea de arreglo:**
  - Regla en el prompt: nunca digas que agregaste, cambiaste o quitaste una pieza si no llamaste a la tool en este turno; el panel «Armá tu PC» muestra lo que realmente quedó.
  - Un control en código: si la respuesta dice «agregué…» y no hubo llamada a la tool de armado en el turno, avisarlo o reintentar.
  - Medirlo en la evaluación del agente: afirmaciones de acción sin llamada a tool.
- **Relacionado:** se agravó por el problema 1; al arreglar el filtro de gama, el modelo recibe candidatos reales.
- **Causa medida:** las dos búsquedas de CPU devolvieron 0 productos (problema 1); el modelo inventó «i5-12400F» sin código y después «lo agregó» en texto. Repitiendo esos turnos con Ollama (5 semillas): con el historial crudo llamó a la tool en 3 de 10 corridas; con la limpieza del problema 23, en 9 de 10. Al llamar a la tool sin candidatos, pasaba códigos inventados con el formato del catálogo (`CPU001`, `CPU002`, `CPU12400F`).
- **Solución aplicada:**
  - **Métrica** `afirmaciones_sin_respaldo` / `accion_sin_respaldo` en `agente.py` y `uv run python -m evaluacion.afirmaciones_sin_tool` (detalle en `evaluacion/resultados/afirmaciones_sin_tool.json`). Línea de base en `memoria.db`: 3 en 34 turnos (8,8 %).
  - **Middleware** `sin_acciones_inventadas` (`wrap_model_call`): si la respuesta final afirma una acción sin tool en el turno, le pide una sola vez que llame a la tool o corrija. El aviso no se guarda.
  - **Regla 14** del prompt: no anunciar acciones sin llamar a la tool; si la búsqueda no devolvió nada, decirlo sin nombrar productos, códigos ni precios.
  - **Control de códigos** en `agregar_o_reemplazar_componente` (`codigo_visto` en `tools.py`): solo acepta códigos que aparecieron en un resultado de búsqueda o del armado, en un mensaje del usuario o en el armado actual. `obtener_producto` no cuenta, para que no sirva para «lavar» un código inventado.
- **Resultado** (turnos enteros con todo aplicado, ventana 8192, 5 semillas por turno): **0 afirmaciones sin tool** y **0 piezas agregadas con códigos que no salieron de una búsqueda**. El control frenó los códigos inventados (`CPU001`, `CPU002`) y en una corrida el modelo buscó y agregó el `12400F` real. El middleware reintentó 3 veces. En 2 de 10 corridas el turno no terminó dentro de 16 pasos (el modelo da vueltas buscando sin candidatos: problema 1).
- **Pruebas:** `tests/test_acciones_sin_tool.py` (14) y `tests/test_codigos_vistos.py` (4). Los guiones de `test_armado`, `test_app` y `test_servicio` ahora buscan antes de agregar.
- **Ojo:** el `.env` ya apunta al catálogo real (ver problema 7). Ahí los códigos son modelos como `12400F`, que un modelo de lenguaje puede adivinar desde su conocimiento general; por eso el control de códigos importa más con el catálogo real.

## 21. El panel «Armá tu PC» no mostraba el avance del armado

- **Estado:** `[x]` · **Gravedad:** media
- **Qué se vio:** con el armado iniciado pero sin piezas, el panel decía solo «Todavía no hay un armado».
- **Solución aplicada:** `app.py` ahora muestra una barra de progreso («Armado: N de 8 piezas») y la lista de piezas con ✅ o ⬜, desde que se inicia la configuración. Con piezas puestas aparece arriba de las tarjetas.

## 22. La conversación no entra en el contexto del modelo

- **Estado:** `[~]` en pausa: depende de la máquina (notebook con 4 GB de VRAM o escritorio con 8 GB) y se decide con el grupo. · **Gravedad:** alta
- **Causa corregida (2026-11-19):** cuando no entra, Ollama conserva el system prompt y las tools, y descarta los mensajes más viejos (medido: en el último turno de `99c1a78e` leyó solo los últimos 9 mensajes). Lo que se pierde es la conversación vieja (pedido original, skill, preferencias), no las tools.
- **Medido tras el problema 23:** el historial limpio crece sin tope (≈ 5.000 tokens en `99c1a78e`, ≈ 7.900 en `4ab40d12`); con 8192 quedan unos 3.000 para el historial (parte fija 3.147 + reserva de ≈ 2.000 para lo que genera). Memoria de video de `qwen3:4b` con 8192: 3,9 GB con caché f16, 3,3 GB con `OLLAMA_KV_CACHE_TYPE=q8_0` (y `OLLAMA_FLASH_ATTENTION=1`). Con 32768 en 8 GB se vuelca a la CPU y genera 8 veces más lento.
- **Solución implementada (2026-11-20, #22):** middleware `historial_en_contexto` (`wrap_model_call`) con `recortar_historial_para_el_modelo` y `resumir_resultado_tool` en `agente.py`. Presupuesto calculado desde `MODEL_NUM_CTX` (`TOKENS_FIJOS=3150`, `TOKENS_RESERVA_RESPUESTA=2000` → `3.042` tokens para el historial en `8192`). Estimación por caracteres (`3,0` caracteres/token + `12` tokens/mensaje, sumando el JSON de `tool_calls`), calibrada contra las conversaciones reales de `#22` y `#23`. Actúa sobre una copia del historial limpio (sin modificar el estado guardado ni `memoria.db`), nunca toca los `HumanMessage` ni el turno actual (incluidos los reintentos `[Aviso del sistema]`), y prioriza resumir resultados de tools viejos por código **sin usar `[cleared]`**: `buscar_especificaciones_web` conserva consulta, gama sugerida y URLs; `consultar_caracteristicas` conserva los archivos fuente del RAG y fila de tabla; `buscar_productos`/`buscar_pieza_armado`/armado conservan códigos y nombres sin atributos; `load_skill` resume la carga previa (respaldo final: acortar respuestas de AI viejas si aún excede).
- **Medido sin modelo local sobre `memoria.db` (`MODEL_NUM_CTX=8192`, historial tras `limpiar_historial_para_el_modelo`):**
  - `99c1a78e` (31 mensajes): historial `5.255 → 2.729` tokens (`total ~8.405 → ~5.879` con parte fija), entra en el presupuesto de `3.042` resumiendo 2 tools viejas (`buscar_especificaciones_web` `4.290 → 452` chars con URLs y `load_skill` `3.789 → 46` chars).
  - `4ab40d12` (75 mensajes): historial `8.504 → 4.845` tokens (`total ~11.654 → ~7.995`, −43 % resumiendo 26 mensajes viejos), baja de `8.192` totales aunque sin margen completo de reserva por la cantidad de mensajes de usuario conservados.
- **Pruebas:** `tests/test_recorte_historial.py` (3 tests con modelo falso). Prueba manual con el modelo local pendiente a cargo del usuario.
- **Opciones a decidir:** recorte de resultados viejos de tools (`ContextEditingMiddleware` + `ClearToolUsesEdit`, con presupuesto calculado desde `MODEL_NUM_CTX`), aviso de desborde, ventana según la máquina y modelo sin razonamiento (`qwen3:4b-instruct-2507`).
- **Conflicto con una corrección del profesor:** lo que el agente busca (web o RAG) tiene que quedar en el contexto **con su fuente**, para usarlo y citarlo después. `ClearToolUsesEdit` reemplaza los resultados viejos por `[cleared]` y eso lo rompe. Si se elige recortar, el recorte tiene que dejar un resumen corto con la fuente en lugar del resultado (por ejemplo «[búsqueda web de God of War: gama sugerida media; fuentes: technical.city, store.steampowered.com]»). Hoy, sin recorte, los resultados sí quedan en el historial con su fuente.
- **Más parámetros que pidió el profesor:** cuantización del modelo, capas en la GPU (`num_gpu`) y `keep_alive` → problema 27. El tope de razonamiento → problema 28.
- **Qué se vio:** medido sobre la conversación guardada: el historial tiene 31 mensajes y unos 59.700 caracteres (≈ 17.000 tokens). `MODEL_NUM_CTX` está en 8192. Ollama recorta en silencio lo que no entra, empezando por lo más viejo, que es donde están el system prompt y las definiciones de las tools. El comentario de `model.py` ya advierte de esto: «el modelo se olvida de las tools».
- **Efecto:** el modelo contesta en texto («Buscando…») en vez de llamar a la tool, inventa acciones (problema 20) y repite el razonamiento.
- **Dónde:** `MODEL_NUM_CTX` en `.env`; `model.py` (`ChatOllama`); resultados largos de `load_skill`, `consultar_caracteristicas` y `buscar_especificaciones_web` que quedan en el historial.
- **Idea de arreglo:**
  - Subir `MODEL_NUM_CTX` (por ejemplo 16384 o 32768). Cuesta memoria y velocidad: probar según la máquina.
  - Quitar el razonamiento del historial (problema 23). Es lo que más pesa: ≈ 47.000 de los 59.700 caracteres son texto de los mensajes del modelo.
  - Acortar o resumir los resultados de las tools viejas (skill, RAG, web) cuando ya se usaron.
  - Probar otro modelo local: `qwen2.5:7b` ya está instalado, no «piensa» y suele llamar mejor a las tools. O Gemini desde el selector.
  - Medir: cantidad de tokens del prompt por turno (la respuesta de Ollama trae `prompt_eval_count`).

## 23. El razonamiento del modelo se guarda en el historial

- **Estado:** `[x]` · **Gravedad:** alta
- **Qué se vio:** con `MODEL_RAZONAMIENTO=0` el modelo igual «piensa» y ese texto llega dentro del contenido del mensaje («Okay, the user wants to proceed…»). Se guarda en `memoria.db` y se reenvía completo en cada turno. `separar_razonamiento` en `agente.py` solo lo oculta en pantalla; no lo saca de lo que lee el modelo.
- **Causa:** `qwen3:4b` no respeta el apagado del razonamiento en este entorno; la bandera `reasoning=False` no alcanza.
- **Dónde:** `agente.py` (`separar_razonamiento`, `eventos`), `model.py`.
- **Idea de arreglo:** antes de cada llamada al modelo, limpiar el contenido de los mensajes anteriores del modelo con `separar_razonamiento` (un `before_model` de `create_agent` o un envoltorio del modelo). Sin tocar lo que se muestra en la interfaz. Con eso baja mucho el tamaño del historial (problema 22) y el modelo deja de imitar su propio razonamiento.
- **Relacionado:** el razonamiento en inglés (problema 9) y las afirmaciones sin tool (problema 20).
- **Causa confirmada (2026-11-19):** el `qwen3:4b` de Ollama es la variante que piensa siempre (`ollama show qwen3:4b`: `thinking`, `default true`) y su plantilla abre `<think>` sola al final del pedido. Con `reasoning=False` Ollama no separa el razonamiento: llega en el texto como «lo que pensó</think>respuesta» (con cierre, sin apertura). A veces el modelo llama a la tool sin cerrar el `</think>`.
- **Medición** (conversación `99c1a78e`, último turno, tokens contados por Ollama): system prompt 1.379, 13 tools 1.768, historial 15.203, de los cuales **10.098 eran razonamiento viejo**. Pedido total: 18.350 tokens para una ventana de 8.192.
- **Solución aplicada:** middleware `sin_razonamiento_viejo` (`wrap_model_call`) en `agente.py`, con la función `limpiar_historial_para_el_modelo`. Antes de cada llamada al modelo arma una **copia** del historial: los mensajes del modelo con llamadas a tools quedan sin texto y las respuestas finales quedan solo con la respuesta. El estado y `memoria.db` no cambian, así que la interfaz sigue mostrando el razonamiento. El contenido en bloques (Gemini) no se toca.
- **Resultado:** el mismo pedido bajó de 18.350 a **8.252 tokens** (−55 %). Sigue sin entrar en 8.192: en un turno real Ollama leyó 6.587 tokens, o sea que todavía descarta mensajes viejos. Eso se encara en el problema 22.
- **Prueba:** `tests/test_limpieza_historial.py` (5 tests; sin el middleware, el test de punta a punta falla).

## 24. El modelo escribe la llamada a una tool como texto JSON

- **Estado:** `[x]` (2026-11-20) · **Gravedad:** media
- **Qué se vio:** en una prueba con Ollama (pedido de gama media, semilla 2), después de `load_skill` la respuesta final fue un JSON con la lista de TODOs (`{"todos": [{"task": "Elegir CPU…"}]}`) escrito como texto, en vez de una llamada a `write_todos`. El turno terminó sin armar nada.
- **Causa probable:** `qwen3:4b` no siempre respeta el formato `<tool_call>…</tool_call>` de su plantilla; escribe el contenido de la llamada «suelto». Es justo lo que el fine-tuning (Fase 4) quiere bajar.
- **Solución aplicada:**
  - Detector `llamada_como_texto` y métrica `llamadas_como_texto` en `agente.py`; además `llamadas_a_tools` ahora las cuenta con `error=True`.
  - Middleware `sin_llamadas_como_texto` (`wrap_model_call`) en `agente.py`: si la respuesta final es un JSON de llamada a tool, pide una sola vez invocarla mediante tool calling sin guardar el JSON descartado.
- **Prueba:** `tests/test_llamadas_como_texto.py` (16 tests con modelo falso).
- **Pendiente de medir:** impacto con el modelo local en la evaluación punta a punta.
- **Medido (2026-11-20, paso 10 cierre):** en `evaluacion/resultados/armado_con_entrevista_paso10_cierre.json` (`qwen3:4b`, `MODEL_NUM_CTX=8192`, Ollama `0.40.16`, catálogo real, 9 corridas) hubo **0** llamadas escritas como texto JSON detectadas (`0` errores de este tipo en `llamadas_a_tools` y `0` reintentos disparados por el middleware; antes en `v1` también `0/9`, aunque en Oficina semilla 3 quedó en `respuesta_final` un borrador de pensamiento sin cerrar `</think>` mencionando `<tool_call>` pero el texto final al usuario fue vacío/no JSON).

## 25. Modelos de CPU y GPU sin gama: decisiones del grupo

- **Estado:** `[ ]` · **Gravedad:** media
- **Qué falta:** la tabla generada deja 29 modelos en «Pendientes de decidir» (lista completa en `rag/docs/tabla_cpu_gpu_por_gama.md`):
  - Core Ultra 5 y Ultra 7 (9 productos): `gamas.md` no los menciona.
  - RTX 5070: los criterios la ponen en alta **y** en premium.
  - GT 210, GT 710, GT 1030, RX 550, Quadro P620: la gama baja «no lleva placa de video», pero se venden.
  - RX 6600 y RTX 3080 Ti: no están en ningún criterio.
  - Procesadores viejos (socket 775, 1155, 1156, 1151) y el Xeon 5416S.
- **Cómo se resuelve:** decidirlo con la tienda y escribir las filas en la sección «Agregados y correcciones a mano» del documento (o ampliar `CRITERIOS_GAMA` y `gamas.md`), regenerar y reindexar. Sumar también modelos viejos de requisitos de juegos (GTX 1060, Core i5-4460, Ryzen 5 1600) para el problema 8.
- **Cerrado (2026-11-20):** filas agregadas en la sección manual de `tabla_cpu_gpu_por_gama.md`: Ultra 5 media, Ultra 7 alta, RTX 5070 alta, RTX 3080 Ti alta, RX 6600 media, GT 210 / GT 710 / GT 1030 / RX 550 / Quadro P620 baja. Quedan sin gama a propósito los procesadores de plataformas viejas (775, 1155, 1156, 1151), que no entran al armado (problema 33), y el Xeon 5416S (servidor). También se sumaron unos 80 modelos de requisitos de juegos (GTX 1060, RTX 2060, Core i5-4460, Ryzen 5 1600…) con la gama más baja de la tienda que los iguala o supera, para que menos juegos den «sin datos» (problema 8). `tabla_gamas.py` ya no lista como pendiente lo que se decidió a mano.

## 26. El asistente pregunta la gama en vez de deducirla del uso

- **Estado:** `[~]` (2026-11-19, paso 10, en curso) · **Gravedad:** alta
- **Qué se vio:** ante «¿Qué PC necesito para editar video?» el agente pregunta «¿en qué gama querés la PC?» (2 de 2 corridas). Para alguien que no sabe de técnica, la gama no dice nada. La regla 15 (problema 2) empuja a preguntarla.
- **Idea de arreglo (acordada con el grupo el 2026-11-19):**
  - La gama sale de lo que cuenta el usuario: para qué la usa, qué juegos o programas, en qué monitor, si la va a mejorar.
  - Entrevista corta con botones, en términos de uso (no «¿cuánta RAM?» sino «¿usás muchos programas a la vez?»). Las preguntas y lo que implica cada respuesta están en `datos/entrevista_armado.yaml`.
  - Una tool `siguiente_pregunta_armado` (por código) lee lo respondido del estado y devuelve la próxima pregunta o el perfil final (gama, RAM, si lleva placa de video, disco, placa escalable). Salta lo que el usuario ya dijo en su mensaje.
  - El perfil se convierte en filtros por código para las tools de armado. Placa madre, fuente y cooler se eligen por reglas (necesitan las reglas nuevas del paso 9: ranuras de RAM y M.2, consumo).
  - El presupuesto se pregunta después, con opciones calculadas para la gama del perfil («lo habitual es cerca de $ 2.800.000»).
  - El usuario que sabe puede elegir piezas («¿querés elegir vos alguna pieza?»).
- **Hecho y con tests (paso 10):**
  - `mcp_tienda/armado/entrevista.py`: recorre `datos/entrevista_armado.yaml` y devuelve la pregunta siguiente con sus opciones exactas, o el perfil. Rechaza las respuestas que no son opción. Del perfil salen los filtros (`filtros_del_perfil`): gama para CPU y GPU, memoria mínima, segundo disco y placa escalable.
  - Tool `siguiente_pregunta_armado` (versión 1, vigente): devuelve la pregunta y sus opciones; el modelo la muestra con `preguntar_al_usuario` (regla 17). Después del perfil, el modelo pregunta el presupuesto con las opciones de la gama y «Otro monto». Si el usuario escribe otra cosa, el modelo la contesta en texto y repite la pregunta.
  - Tool `buscar_pieza_armado`: busca las piezas ya filtradas por el perfil y por lo elegido.
  - Gama de la guía: la pregunta del gabinete se sacó del flujo (no cambia ningún filtro).
  - Hallazgo de la prueba: el modelo pidió la siguiente pregunta dos veces en un mismo paso y LangGraph rechazó el turno. Ahora el estado junta las respuestas (test).
- **Corregido en la revisión (2026-11-20):** el perfil de juegos en 4K pide 64 GB y se buscaba un solo producto de 64 GB (no hay ninguno en el catálogo real). Ahora `filtros_del_perfil` cubre la memoria con hasta 2 unidades (`UNIDADES_MAX_RAM`) y `buscar_pieza_armado` devuelve `cantidad_sugerida` calculada por código (`cantidad_de_ram` en `mcp_tienda/armado/entrevista.py`). Tests en `tests/test_entrevista.py` y `tests/test_entrevista_tools.py`.
- **Medido con el modelo local** (`evaluacion/armado_con_entrevista.py`, 3 pedidos × 3 semillas, `qwen3:4b`). Versión 1, con botones desde `preguntar_al_usuario`: entrevista completa en 6 de 9 corridas, perfil correcto en 6 de 9, 4 preguntas de gama fuera de la entrevista, 0 armados completos. Versión 2, con botones desde la tool: entrevista completa en 0 de 9; el modelo llamaba a la tool con argumentos inventados (`pregunta`, `opciones`) y repetía la misma pregunta. **Decisión (2026-11-20): se vuelve a la versión 1**, que es la que tuvo datos buenos.
- **Visto en la prueba de un pedido (versión 1):** la entrevista llegó al perfil correcto y el modelo no preguntó la gama al principio. Después de la pregunta de mejora dejó la entrevista y preguntó la gama por su cuenta: la regla 17 no alcanza para un modelo de 4B. Eso motivó la versión 2, que no funcionó (ver arriba).
- **Medido (2026-11-20, paso 10 cierre):** (`qwen3:4b`, `MODEL_NUM_CTX=8192`, Ollama `0.40.16`, `datos/catalogo_real.sqlite`, commit `9360b43` con `57f6c4f`; guardado en `armado_con_entrevista_paso10_cierre.json`). **Empeoró claramente frente a `armado_con_entrevista_v1.json`:** entrevista completa `6/9 → 1/9` (Fortnite `1/3 → 0/3`, Oficina `2/3 → 0/3`, Edición 4K `3/3 → 1/3`), perfil correcto `6/9 → 1/9`, preguntas de gama fuera de la entrevista `4 → 19` (Fortnite `2 → 13`, Oficina `2 → 6`, Edición 4K `0 → 0`), armados completos `0/9 → 0/9`, compatibles `0/9 → 0/9`, dentro del presupuesto `8/9 → 5/9`, llamadas con error `19 → 15` (sobre `143 → 138` llamadas totales), tiempo promedio `4,2 → 4,7` min/corrida. Causa principal vista en las trazas: en Fortnite `buscar_especificaciones_web` devolvió requisitos sin match en la tabla y el modelo preguntó la gama en bucle ignorando la entrevista; en Oficina/4K llamó a `siguiente_pregunta_armado` con argumentos inventados (`perfil`, `completa`, `pregunta`, `opciones`) o inventó preguntas de RAM/resolución fuera de la entrevista hasta agotar los 8 turnos.
- **Solución aplicada (2026-11-20, paso 12, entrevista conducida por código):**
  - **Middleware `entrevista_por_codigo` (`agente.py`, primero en `crear_agente`):** cuando el usuario pide armar una PC al inicio (`pide_armar_pc`) o responde exactamente una de las opciones de `pendiente`, el código ejecuta `siguiente_pregunta_armado` → `preguntar_al_usuario` en 2 pasos sin llamar al modelo (`0` llamadas al LLM por botón/opción), conservando el estado en `memoria.db` mediante `Command(update=...)`. Si escribe texto libre fuera de opción, el modelo responde normalmente; al completarse la entrevista, inyecta un aviso con el perfil y la gama (y frena repreguntas de gama o presupuesto ya conocido).
  - **Tolerancia en `siguiente_pregunta_armado` (`tools.py`):** esquema Pydantic `_ArgsSiguientePregunta` con `extra="ignore"` para ignorar argumentos inventados por modelos chicos (`perfil`, `completa`, `pregunta`, `opciones`).
  - **Presupuesto del primer mensaje (`mcp_tienda/armado/montos.py` + `tools.py`):** `extraer_presupuesto_mensaje` limpia resoluciones (`1080p`, `4K`) y tokens de hardware antes de llamar a `interpretar_monto`, guarda el presupuesto válido en el estado (`_merge_entrevista`) y el aviso al terminar la entrevista prohíbe volver a preguntarlo (si es ambiguo o está en dólares, sí se pregunta).
  - **Sin preguntar gama ante `sin datos`:** ajustados regla 13 (`agente.py`), `texto_de_gama` (`mcp_tienda/armado/requisitos.py`) y `aviso_sin_datos` (`tools.py`) para continuar la entrevista o usar la gama del perfil sin preguntar gama.
  - **Pruebas:** nueva suite `tests/test_entrevista_por_codigo.py` (9 tests con modelo falso) + 33 suites completas ejecutadas de a una (`479 passed, 0 failed`).
- **Medido (2026-11-20, paso 12):** `uv run python -m evaluacion.armado_con_entrevista --semillas 1` (`qwen3:4b`, `MODEL_NUM_CTX=8192`, Ollama `0.40.16`, `datos/catalogo_real.sqlite`; guardado en `evaluacion/resultados/armado_con_entrevista_paso12.json`, manteniendo `TURNOS_MAXIMOS=8`):

  | Métrica | Paso 10 cierre (9 corridas) | Paso 10 cierre (semilla 1) | Paso 12 (semilla 1) |
  |---|---|---|---|
  | Entrevista completa | `1/9` | `0/3` | **`3/3`** |
  | Perfil correcto | `1/9` | `0/3` | **`3/3`** |
  | Preguntas de gama fuera de entrevista | `19` | `9` | **`0`** |
  | Armados completos | `0/9` | `0/3` | **`2/3`** |
  | Compatibles (`se_pueden_confirmar`) | `0/9` | `0/3` | **`2/3`** |
  | Dentro del presupuesto | `5/9` | `1/3` | **`3/3`** |
  | Llamadas con error | `15` | `5` | **`3`** |
  | Afirmaciones sin tool | `0` | `0` | **`0`** |
  | Tiempo promedio | `4,7 min` | `4,1 min` | **`3,1 min`** |

  - **Turnos por etapa y trazas:** Fortnite completó las 6 preguntas en turnos 1–6 y armó las 7 piezas compatibles en el turno 7 (`$ 1.677.300 <= $ 2.800.000`, `confirmar=True`, `0` errores; turno 8 cerró tras `"¿Quieres confirmar?"`). Edición 4K completó las 5 preguntas en turnos 1–5 y armó 6 piezas obligatorias compatibles en el turno 6 (`$ 2.050.200 <= $ 5.500.000`, `confirmar=True`, `3` errores iniciales frenados por `codigo_visto`), aunque sin agregar GPU dedicada, segundo disco ni `cantidad=2` en RAM (puso 16 GB en lugar de 32 GB). Oficina completó las 4 preguntas en turnos 1–4, inició configuración con `$ 1.000.000` y buscó CPU en el turno 5, pero preguntó `"¿Prefieres Intel o AMD?"` (el usuario simulado no responde preferencias de marca y cerró en 5 turnos sin piezas). Queda pendiente tu prueba manual en la app antes de cambiar el estado a `[x]`.
- **Solución aplicada (2026-11-20, paso 13, armado completo controlado por código):**
  - **`piezas_faltantes` y `texto_piezas_faltantes` (`mcp_tienda/armado/entrevista.py`):** cálculo determinista de lo que exige el perfil más las piezas ya elegidas (`cpu`, `cooler` si la CPU no trae, `motherboard`, `ram` verificando `capacidad_gb * cantidad >= perfil["ram_gb"]`, `almacenamiento`, `almacenamiento_extra` si `segundo_disco`, `gpu` si `perfil["gpu"]` o si la CPU no tiene video integrado, `gabinete`, `fuente` si el gabinete no trae). Sin asumir si falta un atributo (`sin datos`).
  - **RAM automática (`tools.py`):** si `agregar_o_reemplazar_componente` recibe `lugar="ram"` sin `cantidad` habiendo perfil, calcula `cantidad_de_ram(perfil, capacidad)` (ej. `2` unidades de 16 GB para 32 GB) o devuelve error pidiendo un módulo más grande si supera 2 unidades. `buscar_pieza_armado(lugar="gpu")` también permite buscar GPU cuando la CPU no tiene video integrado aunque el perfil tenga `gpu=False`.
  - **Estado del perfil en tools (`tools.py`):** `agregar_o_reemplazar_componente` y `obtener_configuracion` agregan el dato `"estado_perfil"` (`"Faltan: …"` / `"Armado completo según el perfil."`) solo en el texto JSON para el modelo, nunca en `artifact`.
  - **Middleware `armado_completo` (`agente.py`, después de `entrevista_por_codigo`):** ante perfil + configuración iniciada + `piezas_faltantes` no vacía, si el modelo frena en texto final o pregunta algo distinto del presupuesto (`¿Intel o AMD?`), reintenta UNA sola vez con `[Aviso del sistema]` pidiendo elegir de `buscar_pieza_armado` y recordar preferencias previas (`Intel`/`AMD`) si hubo, sin preguntar marca y sin bloquear preguntas del presupuesto ni casos de presupuesto insuficiente. También actualizado `skills/armado_pc.md` y regla 11.
  - **Métricas y pruebas:** agregadas métricas `cumple_perfil`, `ram_total_gb`, `tiene_gpu`, `tiene_segundo_disco`, `turnos_entrevista` y `turnos_armado` en `evaluacion/armado_con_entrevista.py` (`TURNOS_MAXIMOS=8` sin cambios); nueva suite `tests/test_armado_completo.py` (`9 passed`) y 34 suites completas (`490 passed, 0 failed`, cubriendo también `b71b853`).
- **Medido (2026-11-20, paso 13):** `uv run python -m evaluacion.armado_con_entrevista --semillas 1` (`qwen3:4b`, `MODEL_NUM_CTX=8192`, Ollama `0.40.16`, `datos/catalogo_real.sqlite`; guardado en `evaluacion/resultados/armado_con_entrevista_paso13.json`):

  | Métrica (semilla 1, 3 corridas) | Paso 12 | Paso 13 |
  |---|---|---|
  | Entrevista completa | `3/3` | **`3/3`** |
  | Perfil correcto | `3/3` | **`3/3`** |
  | Preguntas de gama fuera de entrevista | `0` | **`0`** |
  | Armados completos | `2/3` | **`2/3`** |
  | Cumplen el perfil completo | `1/3` *(Fortnite)* | **`2/3`** *(Oficina + Edición 4K)* |
  | Compatibles (`se_pueden_confirmar`) | `2/3` | **`2/3`** |
  | Dentro del presupuesto | `3/3` | **`3/3`** |
  | Llamadas con error | `3` | **`0`** |
  | Afirmaciones sin tool | `0` | **`0`** |
  | Tiempo promedio | `3,1 min` | `5,0 min` |

  - **Detalle por pedido:**
    - **Oficina (`0 → 1`):** `8` turnos (`4` entrevista + `4` armado), **`6` piezas compatibles**, `cumple_perfil=True`, `ram_total_gb=8`, `tiene_gpu=False`, `confirmar=True`, `$ 705.200 <= $ 1.000.000`, `0` errores (`220,6 s`). El middleware `armado_completo` evitó que preguntara marca y lo llevó a armar todas las piezas.
    - **Edición de video 4K (`parcial → completo según perfil`):** `7` turnos (`5` entrevista + `2` armado), **`8` piezas compatibles**, **`cumple_perfil=True`** (**`ram_total_gb=32` automática**, **`tiene_gpu=True`**, **`tiene_segundo_disco=True`**), `confirmar=True`, `$ 3.461.550 <= $ 5.500.000`, `0` errores (`358,4 s`). *(Nota menor en texto final: el modelo sugirió subir a 32 GB aunque el armado ya quedó guardado con `cantidad=2` = 32 GB.)*
    - **Fortnite 1080p (`1 → 0` por búsqueda de placa sin agregar CPU):** `7` turnos (`6` entrevista + `1` armado), `0` piezas, `18` llamadas (`0` error, `317,2 s`). Buscó CPU (`12400F`) y enseguida buscó motherboard con `texto="LGA1700"` (`0` resultados porque el catálogo escribe `"1700"`) en vez de agregar primero la CPU para que `compatible_con` filtre la placa madre automáticamente; tras los reintentos de `armado_completo`, cerró con texto sin usar tools. Sigue pendiente tu prueba manual antes de cerrar `#26`.
- **Medido (2026-11-20, paso 14, sobre `d2436a1` que corrigió Fortnite y con el agregado de `#34`):** `uv run python -m evaluacion.armado_con_entrevista --semillas 1` (`qwen3:4b`, `MODEL_NUM_CTX=8192`, Ollama `0.40.16`, `datos/catalogo_real.sqlite`; guardado en `evaluacion/resultados/armado_con_entrevista_paso14.json`, manteniendo `TURNOS_MAXIMOS=8`):

  | Métrica (semilla 1, 3 corridas) | Paso 13 | Paso 14 |
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

  - **Detalle por pedido:**
    - **Fortnite 1080p (`0 → 1` completo):** `7` turnos (`6` entrevista + `1` armado), **`7` piezas compatibles** (`10400F`, `H47MDS`, `832BLK` ×2, `6G3050`, `M2P128`, `VORTNE`, `TR-600`), **`cumple_perfil=True`**, `ram_total_gb=16`, `tiene_gpu=True`, `tiene_segundo_disco=False`, `confirmar=True`, **`$ 1.678.300 <= $ 2.800.000`**, `28` llamadas (`0` error, `242,8 s`).
    - **Oficina (`1` completo en menos turnos):** `5` turnos (`4` entrevista + `1` armado), **`6` piezas compatibles** (`IG5900`, `H47MDS`, `832BLK`, `240GMX`, `VORTNE`, `ATX500`), **`cumple_perfil=True`**, `ram_total_gb=8`, `tiene_gpu=False`, `tiene_segundo_disco=False`, `confirmar=True`, **`$ 695.700 <= $ 1.000.000`**, `22` llamadas (`0` error, `172,5 s`).
    - **Edición de video 4K (`1` completo con cooler):** `8` turnos (`5` entrevista + `3` armado), **`9` piezas compatibles** (`R570TY`, `G550MK`, `HKD432` ×2, `38TI3F`, `M256HI`, `WDB1TB`, `AMDPER`, `VORTNE`, `CM850G`), **`cumple_perfil=True`**, **`ram_total_gb=32`**, **`tiene_gpu=True`**, **`tiene_segundo_disco=True`**, `confirmar=True`, **`$ 3.555.500 <= $ 5.500.000`**, `30` llamadas (`0` error, `341,5 s`).
  - Queda en `[~]` hasta tu prueba manual de punta a punta en la app.

## 27. Ajustes de Ollama / llama.cpp para que el modelo ande más liviano

- **Estado:** `[ ]` · **Gravedad:** media · **Origen:** corrección del profesor (2026-11-19).
- **Qué pide:** Ollama y LM Studio usan por debajo llama.cpp, así que sus parámetros se parecen y lo aprendido en uno sirve en el otro. Investigar qué se puede ajustar para que el modelo ande más liviano, **revisando en la documentación de la versión instalada cuáles existen** antes de apoyarse en ellas.
- **Ya medido (problema 22, Ollama 0.40.16, RTX 5060 Ti 8 GB):**
  - Tamaño de contexto (`MODEL_NUM_CTX`): con caché f16, 8192 → 3,9 GB, 16384 → 5,1 GB, 32768 → 7,9 GB y se vuelca a la CPU (genera 8 veces más lento).
  - Caché de contexto comprimida (`OLLAMA_KV_CACHE_TYPE`) con flash attention (`OLLAMA_FLASH_ATTENTION=1`): 8192 → 3,3 GB con `q8_0` y 3,0 GB con `q4_0`, a la misma velocidad. Las dos variables existen en esta versión: aparecen en el `server config` del log y funcionaron.
- **Falta medir:**
  - Cuantización del modelo: hoy `qwen3:4b` es Q4_K_M (2,5 GB). Comparar con otras (por ejemplo Q8_0) en memoria, velocidad y calidad (evaluación del agente).
  - Capas en la GPU (`num_gpu`): cuántas entran en 4 GB de VRAM y cuánto se pierde al mandar el resto a la CPU.
  - Tiempo que el modelo queda cargado (`keep_alive`, `OLLAMA_KEEP_ALIVE`): carga en frío medida entre 2 y 6 s; decidir un valor para la demo.
- **Entregable:** una tabla «parámetro · dónde se configura en Ollama y en LM Studio · existe en nuestra versión · efecto medido», para elegir la configuración de la notebook (4 GB) y del escritorio (8 GB). Relacionado: problema 22.
- **Documentado (2026-11-20, #27):** tabla Ollama / LM Studio y recomendaciones en [docs/AJUSTES_OLLAMA.md](docs/AJUSTES_OLLAMA.md), distinguiendo lo ya **medido** (`#22`, `#27`, `#28`: `MODEL_NUM_CTX` 8192/16384/32768, `OLLAMA_KV_CACHE_TYPE` + `OLLAMA_FLASH_ATTENTION=1`, carga en frío 2–6 s, tope de razonamiento en `qwen3:4b`) de lo que quedó como **recomendación sin medir** para la notebook de 4 GB (`OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0` o `q4_0`, `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_KEEP_ALIVE=-1`, embeddings en CPU creando variante `bge-m3-cpu` con `PARAMETER num_gpu 0`, y verificar con `ollama ps` que diga `100% GPU`). Queda pendiente (requiere permiso para descargar ~4,3 GB) medir cuantización `Q8_0` con `ollama pull qwen3:4b-q8_0`.

## 28. El razonamiento de `qwen3:4b` no se puede acotar

- **Estado:** `[ ]` · **Gravedad:** media · **Origen:** corrección del profesor («reasoning budget»; comprobar si Ollama deja pasar el parámetro).
- **Medido (2026-11-19, Ollama 0.40.16, temperatura 0, misma pregunta):**

  | Forma de acotar | Tokens generados | Resultado |
  |---|---|---|
  | `think=true` | 1.391 | razona aparte, responde bien |
  | `think=false` (lo de hoy) | 1.670 | **razona igual**, mezclado en el texto (problema 23) |
  | `think="low"` / `"high"` | 1.670 / 1.670 | Ollama los acepta, pero **no cambian nada** con este modelo |
  | `/no_think` en el prompt | 1.158 | **razona igual** (esta variante de Qwen3 piensa siempre) |
  | «Pensá en no más de 3 frases» | 1.328 | casi no cambia |
  | `num_predict=300` (cortar) | 300 | corta en medio del razonamiento: **respuesta vacía** |

- **Conclusión:** con `qwen3:4b` no hay tope de razonamiento. Lo que piensa ocupa contexto (mediana de 800 tokens por llamada, problema 22) y tiempo.
- **Idea de arreglo:** comparar con la variante de Qwen3 4B que no razona (`qwen3:4b-instruct-2507`, mismo tamaño) sobre la evaluación del agente: tool calling, afirmaciones sin tool, montos, tiempo por turno. Si rinde parecido, es la forma efectiva de acotar. Ojo: cambia el modelo base del fine-tuning (problema 18). Relacionado: problemas 9, 22 y 23.

## 29. Las consultas que escribe el modelo para el RAG no se parecen a los documentos

- **Estado:** `[~]` (2026-11-20) · **Gravedad:** media · **Origen:** corrección del profesor (similitud semántica).
- **Qué pasa:** la búsqueda del RAG es por parecido de significado. Si el modelo escribe la consulta con palabras distintas a las de los documentos, vuelven fragmentos que no son los correctos.
- **Hecho:** se agregaron ejemplos de consulta con el vocabulario de los documentos (`reparto del presupuesto en gama media`, `qué es una gama media`, `características para juegos en 1440p`, `guía de compatibilidad procesador y motherboard`, `UPS cómo dimensionarla`, `cables cuál sirve para conectar notebook al monitor`, `cámaras de seguridad cómo elegir`) en `consultar_caracteristicas` (`tools.py`) y en `skills/armado_pc.md`. Cubierto en `tests/test_explicaciones_rag.py`.
- **Qué falta:** registrar las consultas reales que genera el modelo local y medir el RAG (`evaluacion/rag.py`) sobre ellas.
- **Medido (2026-11-20, paso 10 cierre):** `evaluacion/rag.py` (52 consultas, `bge-m3`): `acierto@1` `77 % → 69 %` (`0.769 → 0.692`, 40/52 → 36/52), `acierto@4` `98 % → 94 %` (`0.981 → 0.942`, 51/52 → 49/52), fragmentos con otra gama `11 % → 11 %` (`0.106 → 0.106`). **Empeoró respecto a la línea de base** porque `reparto_presupuesto.md` se regeneró con los valores actualizados del disco secundario (en gama alta la RAM pasó de 25 % a 23 % y en premium el procesador de 16 % a 15 %) y 2 consultas de porcentajes de `rag_consultas.yaml` siguen esperando los porcentajes anteriores (`Gama premium, procesador: 16 %` y `Gama alta, memoria ram: 25 %`), además de 2 consultas que bajaron de `acierto@1` al cambiar el orden en `reparto_presupuesto.md` / `gamas.md`.
- **Actualizado `rag_consultas.yaml` (2026-11-20, `uv run python -m evaluacion.rag`, #29):** `acierto@1` `69 % → 73 %` (`0.692 → 0.731`, 36/52 → 38/52), `acierto@4` `94 % → 98 %` (`0.942 → 0.981`, 49/52 → 51/52), fragmentos con otra gama `11 % → 11 %` (`0.106 → 0.106`). Se corrigieron solo las 2 consultas con porcentajes viejos (`16 % → 15 %` para procesador en premium y `25 % → 23 %` para RAM en alta). Las otras 2 consultas que bajaron de `acierto@1` respecto al 77 % previo siguen 2.ª (`acierto@4 = True`): en «qué disco lleva una PC de gama media», al agregarse `- Gama media, disco secundario (ssd 2,5" o hdd): 0 %` en `reparto_presupuesto.md`, ese fragmento pasó a repetir «disco»/«ssd» y superó por densidad semántica a `gamas.md` (que tiene campos vacíos); en «cuánto cuesta una PC de gama premium», al alargarse la lista de porcentajes de `reparto_presupuesto.md`, perdió peso la frase inicial de precio frente al fragmento más corto de `gamas.md` (`Valor: más de $ 5.780.000…`). Arreglo propuesto por código (en `rag/consulta.py`, sin tocar documentación a mano): desempate leve por intención (priorizar `reparto_presupuesto.md` cuando la consulta pregunta costo/porcentaje/presupuesto/reparto, y `gamas.md` ante consultas de componentes de una gama sin pedido de precio/porcentaje) o fusión híbrida vector + BM25 (RRF).
- **Desempate por intención implementado (2026-11-20, #29):** agregado `_ordenar_por_intencion` en `rag/consulta.py` (prioriza `reparto_presupuesto.md` ante preguntas de costo/porcentaje/presupuesto y `gamas.md` ante consultas de componentes de una gama entre los fragmentos recuperados), cubierto con `tests/test_rag_secciones.py`. Falta volver a correr `uv run python -m evaluacion.rag` con Ollama (`bge-m3`) para medir el impacto real sobre las 52 consultas.
- **Principio que ya seguimos y hay que mantener:** pocos documentos en el RAG, solo prosa. Los datos (gamas, reparto, perfiles, modelos de CPU y GPU) se resuelven por código (problemas 1, 5 y 8), para que la similitud semántica no tenga que distinguir entre muchos textos parecidos.
- **Cerrado (2026-11-20):** con el reordenamiento por intención (`rag/consulta.py`) el acierto@1 pasó de 73 % a 92 % y el acierto@4 a 98 %. Lo que queda es opcional.

## 30. Experimento: RAG solo contra RAG con documento hipotético (HyDE)

- **Estado:** `[ ]` · **Gravedad:** media · **Origen:** corrección del profesor («hay que probarlo»; sirve para la presentación).
- **Qué es:** el modelo primero escribe una respuesta hipotética a la pregunta, y se busca con esa respuesta en vez de con la pregunta corta. Como se parece más a los documentos reales, suele recuperar mejor.
- **Cómo medirlo:** las mismas 39 consultas de `evaluacion/conjuntos/rag_consultas.yaml`, con `evaluacion/rag.py` en tres variantes: solo vectores, búsqueda actual (filtro por gama y búsqueda exacta) y búsqueda actual con documento hipotético. Métricas: acierto@1, acierto@4, fragmentos de otra gama y **tiempo extra** (HyDE suma una llamada al modelo, unos 10 s con `qwen3:4b`).
- **Ojo:** el documento hipotético lo escribe el modelo y puede inventar; solo se usa para buscar, nunca se le muestra al usuario ni se cita.
- **Medido (2026-11-20, 52 consultas de `evaluacion/conjuntos/rag_consultas.yaml`, `bge-m3` + `qwen3:4b`, 1 pasada por variante):** comandos `uv run python -m evaluacion.rag --solo-vectores`, `uv run python -m evaluacion.rag` y `uv run python -m evaluacion.rag --hyde`. Tests rápidos en `tests/test_rag_hyde.py` (5 tests).

  | Variante | acierto@1 | acierto@4 | Otra gama | Tiempo promedio / consulta | Resultado |
  |---|---|---|---|---|---|
  | Solo vectores (`--solo-vectores`) | 69 % (36/52) | 98 % (51/52) | 31 % | 0,11 s | `evaluacion/resultados/rag_solo_vectores.json` |
  | Búsqueda actual (gama + tabla) | 73 % (38/52) | 98 % (51/52) | 11 % | 0,06 s | `evaluacion/resultados/rag.json` |
  | Búsqueda actual + HyDE (`--hyde`) | 67 % (35/52) | 100 % (52/52) | 13 % | 13,22 s | `evaluacion/resultados/rag_hyde.json` |

- **Conclusión:** No conviene activarlo en el asistente: aunque HyDE llevó `acierto@4` a `100 %` (52/52), bajó `acierto@1` (`73 % → 67 %`) porque su prosa genérica desplazó a `reparto_presupuesto.md` en preguntas de precios/porcentajes y sumó **+13,16 s por consulta** (`687,4 s` totales). La búsqueda actual con filtro por gama y tabla exacta ya alcanza `98 %` en `0,06 s` con menor mezcla de gamas (`11 %`).
- **Cerrado (2026-11-20):** el experimento se hizo y HyDE no conviene: acierto@1 67 % (contra 92 % sin HyDE) y 13 s más por consulta. Se queda el RAG solo.

## 31. El presupuesto que escribe el usuario no se valida

- **Estado:** `[~]` (2026-11-19, paso 10) · **Gravedad:** media · **Origen:** corrección del profesor (reforzar con una tool que verifique).
- **Hecho:** `mcp_tienda/armado/montos.py`. `interpretar_monto` pasa el texto a pesos: «2 palos», «2,5 millones», «20 lucas», «mil», «800k», «$ 2.800.000». Los dólares no se convierten (no hay cotización). Un número chico sin unidad («20») es ambiguo y se pregunta. `evaluar_presupuesto` compara con la escala del reparto y dice qué gama entra o cuánto hace falta como mínimo. Tool `validar_presupuesto` para el modelo, y la entrevista lo usa para el presupuesto. Tests en `tests/test_montos_usuario.py` (18) y `tests/test_entrevista_tools.py`.
- **Corregido en la revisión (2026-11-20):** «dos millones» daba $ 1.000.000 (se ignoraba el número en palabras); «2,8M», «1 millon» (singular) y «un palo y medio» no se entendían, y «entre 1 y 2 millones» tomaba el primero. Ahora se leen los números en palabras justo antes de la unidad, «millón» en singular, la «M» pegada al número y «y medio»; dos montos distintos son ambiguos y se pregunta. Tests en `tests/test_montos_usuario.py` (32).
- **Arreglo en `iniciar_configuracion` (2026-11-20, #31):** ahora acepta `presupuesto` como número o texto (`resolver_presupuesto` en `tools.py`, delegando en `mcp_tienda/armado/montos.interpretar_monto`). Si el texto es un rango o monto ambiguo, está en dólares o no tiene monto, devuelve un error claro indicando qué preguntarle al usuario y no pisa la configuración ni adivina. Tests nuevos en `tests/test_montos_usuario.py` (número, `None`, `"2 palos"`, `"Gama media ($ 2.800.000)"`, rango ambiguo, dólares y texto sin monto).
- **Falta:** medirlo con `montos_sin_respaldo` en la medición de la entrevista.
- **Medido (2026-11-20, paso 10 cierre):** en las 9 corridas de `armado_con_entrevista_paso10_cierre.json`, el modelo nunca llamó a `validar_presupuesto` (`0` llamadas); el usuario del script usó montos explícitos (`2.800.000`, `un millón`, `5.500.000`). En 1 corrida (Fortnite semilla 2), en lugar de llamar a `validar_presupuesto` o a la entrevista, el modelo inventó rangos en `preguntar_al_usuario` (`$ 2.400.000`, `$ 3.600.000`, `$ 3.200.000`: 3 llamadas con montos sin respaldo) y luego pasó el string `"Gama media (2.800.000 - 3.200.000 pesos)"` como `presupuesto` a `iniciar_configuracion` (1 error de tipo numérico); en las otras 5 corridas que llegaron a `iniciar_configuracion` pasó el monto correcto (`2800000`, `1000000`, `5500000`), y en las 3 restantes no inició armado (`presupuesto=None`). No hubo errores de interpretación de `validar_presupuesto` porque no fue invocada.
- **Qué pasa:** el problema 2 cubre los montos que **inventa el agente**. Si el **usuario** escribe un monto que no alcanza para una PC («tengo $ 20.000») o uno ambiguo («20 lucas», «2 palos»), nadie lo verifica.
- **Idea de arreglo (por código):** una tool, o un paso de la entrevista del problema 26, lee el monto que escribió el usuario, lo interpreta («2 palos» → $ 2.000.000) y lo compara con la escala del reparto. Si no alcanza para la gama más baja, responde «con ese monto no alcanza para una PC completa; lo mínimo es cerca de $ 919.000», con alternativas (subir el presupuesto o buscar solo una pieza). Si alcanza, devuelve la gama que entra en ese monto.
- **Prueba:** tests con montos reales, cortos, con «mil», «lucas», «palos» y en dólares; medir con la métrica `montos_sin_respaldo` que el agente no responda con montos inventados.
- **Cerrado (2026-11-20):** `validar_presupuesto` e `interpretar_monto` entienden jerga, números en palabras, «2,8M», «y medio» y dos montos ambiguos; el monto del primer mensaje lo toma el código (paso 12). Los dólares no se convierten.

## 32. Ante preguntas de explicación el agente no consulta la documentación y repregunta

- **Estado:** `[x]` (2026-11-20) · **Gravedad:** alta
- **Qué se vio** (2026-11-19, con los documentos ya escritos; Ollama, 2 semillas por pregunta):
  - «¿Cómo armo una PC paso a paso?»: 2/2 cargaron la skill `armado_pc` (que es para elegir piezas y comprar) y preguntaron «¿para qué la vas a usar?». No consultaron el tutorial. «Armar» quiere decir comprar y ensamblar, y el modelo elige comprar.
  - «¿Qué UPS necesito para mi PC?»: 2/2 consultaron el RAG y trajeron la guía de compra, pero preguntaron «¿para qué usás la PC?» en vez de «qué equipos vas a conectar», que es lo que dice la guía.
  - «¿Qué cable uso para conectar la notebook al monitor?»: 2/2 no consultaron el RAG y le devolvieron al usuario la misma pregunta.
- **Cambio de alcance (2026-11-19):** se agregó la regla 16 (el agente solo ayuda a elegir y comprar; si preguntan cómo ensamblar, la tienda la entrega armada; lo que no tiene que ver con la tienda se declina).
- **Solución aplicada (2026-11-20):**
  - En `skills/armado_pc.md` se aclaró en `description:` que es para elegir y comprar piezas (no ensamblado físico).
  - En `tools.py` (`consultar_caracteristicas`) se sumaron las cuatro gamas, ejemplos de consulta y la pauta explícita de consultar antes de responder o repreguntar.
  - En `agente.py`, detector `tema_de_explicacion` y middleware `consultar_documentacion_antes` (`wrap_model_call`): ante preguntas de explicación o guía de compra sin consulta previa al RAG en el turno, pide una vez llamar a `consultar_caracteristicas` antes de responder o usar `preguntar_al_usuario` (sin dejar `tool_calls` abiertos).
- **Prueba:** `tests/test_explicaciones_rag.py` (16 tests con modelo falso y base Chroma temporal).
- **Pendiente de medir:** corrida con el modelo local sobre las preguntas de explicación y guía de compra.

## 33. El armado puede ofrecer piezas de plataformas viejas

- **Estado:** `[x]` (2026-11-20) · **Gravedad:** media · **Detectado:** 2026-11-19, al recargar el catálogo (paso 9).
- **Qué pasa:** la ingesta marca las piezas que el armado no usa (`fuera_del_armado` en `formato_amn.Lectura`: socket 775/1151/1155, DDR3, SODIMM), pero esa marca **no se guarda en la base**. `buscar_productos` las devuelve igual y, como ordena por precio, un Celeron 775 sale primero al buscar procesadores. El filtro de gama las excluye (no tienen gama), pero una búsqueda sin gama no.
- **Solución aplicada:** `FILTROS_DEL_ARMADO` en `mcp_tienda/servidor.py` restringe `cpu`, `motherboard` (`socket__en: SOCKETS_ARMADO`) y `ram` (`formato_modulo: DIMM`, `tipo__en: ["DDR4", "DDR5"]`) cuando la búsqueda es para armado (`para_lugar` o `compatible_con`, derivando la categoría desde `para_lugar` si hace falta). En búsquedas comunes sin armado siguen saliendo piezas viejas o SODIMM.
- **Prueba:** `tests/test_servidor_mcp.py` (18 tests, incluidos `test_la_busqueda_para_el_armado_no_ofrece_plataformas_viejas` y `test_plataformas_viejas_quedan_fuera_del_armado_pero_salen_en_busqueda_comun`).

## 34. El chat web no tiene Cambiar ni Confirmar pedido

- **Estado:** `[x]` (solucionado 2026-11-20, paso 14) · **Gravedad:** media
- **Qué se vio:** `servicio.py` solo expone `/chat`, `/conversaciones/{id}` y `/salud`; `CLAUDE.md` dice que las tarjetas tienen botón **Cambiar** y que la configuración entera tiene **Confirmar pedido**. En Streamlit (`app.py`) sí existen usando `armado.alternativas`, `armado.poner_componente` y `armado.confirmar_pedido`.
- **Dónde:** `servicio.py`, `presupuesto_pdf.py`, `web/`, `app.py`, `docs/GUIA_INTEGRACION.md`, `CLAUDE.md`.
- **Idea de arreglo:** agregar endpoints en `servicio.py` que usen las mismas funciones de `armado.py`, o dejarlo a la integración de la tienda cuando el usuario carga el armado en «Armá tu PC» o el carrito (`onConfirmarArmado`).
- **Decisión del grupo (2026-11-20):** **Confirmar** genera un PDF con el presupuesto de la PC confirmada. **Cambiar** reemplaza un producto por otro compatible en el carrito que se está armando.
- **Solución aplicada (2026-11-20, paso 14):**
  - **Generación de PDF (`presupuesto_pdf.py` con `fpdf2==2.9.0`):** agrega `datos_del_presupuesto` y `pdf_del_presupuesto` (`presupuesto-<referencia>.pdf`) con fecha, número de referencia, perfil, presupuesto, tabla de componentes elegidos con precio y cantidad, total, estado de compatibilidad y notas sin datos, manteniendo texto seguro para fuente estándar Latin-1.
  - **Endpoints sin LLM (`servicio.py`):** agrega `GET /conversaciones/{conversacion_id}/armado/alternativas`, `POST /conversaciones/{conversacion_id}/armado/cambiar` (`PedidoCambiar`) y `POST /conversaciones/{conversacion_id}/armado/confirmar` (devuelve `application/pdf` con `Content-Disposition: attachment; filename=presupuesto-<referencia>.pdf` y cabecera `X-Pedido-Referencia`, o `409` con `detail.motivos` si faltan piezas o hay incompatibilidades). Todos verifican `verificar_clave`, escriben estado con `update_state` sin pasar por el modelo y no exponen ninguna tool nueva del agente.
  - **Chat web (`web/`):** agregadas rutas proxy `/api/agente/conversaciones/[id]/armado/{alternativas,cambiar,confirmar}/route.ts`, cliente `armadoApi.ts`, selector inline de alternativas compatibles en **Cambiar** dentro de `VistaArmado` y botón **Confirmar pedido** con descarga directa del PDF e indicador de pedido confirmado (se limpia con aviso si se modifica alguna pieza luego de confirmar), conectado en `ChatAgente`, `useChatAgente` y `web/app/page.tsx`.
  - **Streamlit (`app.py`) y documentación (`docs/GUIA_INTEGRACION.md`, `CLAUDE.md`):** `confirmar()` en Streamlit genera el mismo PDF y muestra `st.download_button("📄 Descargar presupuesto (PDF)")`; actualizadas guía de integración (endpoints y puente NestJS) y documentación del proyecto.
  - **Verificación:** `npm --prefix web run typecheck` y `npm --prefix web run build` OK (`0` errores); 35 suites Python sin Ollama (`uv run pytest -q -m "not ollama and not embeddings and not tavily" tests/<archivo>.py` de a una): `503 passed, 0 failed` (`3 deselected`, `1 skipped`), incluyendo `test_presupuesto_pdf.py` (`1 passed`), `test_servicio.py` (`21 passed`), `test_app.py` (`10 passed`), `test_app_botones.py` (`4 passed`) y `test_web.py` (`8 passed, 1 deselected`).

## Cosas que **no** son problemas (para no volver a investigarlas)

- La clave de Gemini no empieza con `AIza` y aun así funciona: es válida.
- `gemini-2.5-flash` devuelve 404 «no longer available to new users»: es de Google, no un error del proyecto.
- `ollama list` mostraba solo modelos de chat al principio; ya se instaló `bge-m3` y el RAG se reindexó (solo `gamas.md` y `reparto_presupuesto.md` tienen contenido).
