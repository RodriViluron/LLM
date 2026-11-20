# Prompt para la sesión nueva: corregir aprendiendo, de a poco

Copiar todo lo que sigue como primer mensaje de la sesión nueva. Este archivo se puede borrar después.

---

Seguimos con el asistente de compra de Todo Computación. Leé `CLAUDE.md`, `README.md`, `ROADMAP_APRENDIZAJE.md` y `PROBLEMAS_DETECTADOS.md` antes de hacer nada.

## Cómo quiero trabajar

Soy estudiante de 4.º año. Conozco Python, PyTorch, Transformers, LoRA, RAG y agentes a nivel de cursada, pero no tengo experiencia en LangChain, MCP, tool calling ni en armar un system prompt de un agente. Quiero **entender cada cosa a medida que la corregimos**, no solo que quede arreglada.

Reglas para esta sesión:

1. **Un problema por vez**, en el orden de abajo. No pases al siguiente hasta que el anterior esté probado y yo diga que sigamos.
2. **Antes de tocar código, explicame en criollo:** qué es esa pieza, por qué está fallando, qué opciones hay y qué recomendás. Usá el mapa de `ROADMAP_APRENDIZAJE.md` (decime a qué etapa corresponde).
3. **Proponé y esperá mi OK** antes de cambiar código, dependencias o estructura. Los cambios chicos de texto en documentos o en el prompt también me los mostrás antes.
4. **Mostrame el antes y el después** de cada cambio y cómo lo probamos (un test, un script o una prueba en el chat). Todo lo que hace el agente tiene que ser medible.
5. Al terminar cada problema, actualizá `PROBLEMAS_DETECTADOS.md` (estado y qué se hizo) y dejame una pregunta corta para chequear que lo entendí.
6. **No hagas commit** salvo que yo lo pida. Código, nombres de funciones y comentarios en español.
7. **Nunca leas ni muestres el `.env`**: tiene mi clave de Gemini y la sesión de la tienda. Si necesitás saber si una variable está cargada, comprobalo sin imprimir su valor.

## Estado actual del proyecto

- Agente conversacional con `create_agent` de LangChain, tools locales y servidor MCP `tienda-amn`, memoria en `memoria.db`, RAG con Chroma, búsqueda web con Tavily, interfaz de Streamlit (`uv run streamlit run app.py`) y servicio HTTP (`servicio.py`).
- **Selector de modelo** hecho: `local` (Ollama, `qwen3:4b`) o `gemini` (`gemini-3.8-flash`, ya probado con mi clave). Un agente por modelo con la misma memoria. Está en `model.py`, `agente.py` y `app.py`.
- Ollama tiene instalados `qwen3:4b`, `qwen2.5:7b` y `bge-m3` (embeddings).
- RAG indexado, pero **solo con `gamas.md` y `reparto_presupuesto.md`**. Los otros cinco documentos de `rag/docs/` están vacíos.
- `rag/docs/reparto_presupuesto.md` se regeneró con el catálogo real (`uv run python -m evaluacion.reparto_presupuesto --escribir-doc`). Las gamas están definidas en `rag/docs/gamas.md`.
- Catálogo real cargado en `datos/catalogo_real.sqlite` (4266 productos). **El agente todavía usa el catálogo de prueba** (`AMN_CATALOGO_DB=datos/catalogo.sqlite` en el `.env`); las reglas de compatibilidad aún no están hechas para el real.
- El panel «Armá tu PC» ahora muestra una barra de avance por pieza.
- Tests: `uv run pytest` (211 pasan, 2 salteados, tardan unos 2 minutos). Hay cambios sin commitear (problema 19).

## Los problemas, en el orden en que quiero verlos

Cada uno tiene su entrada completa en `PROBLEMAS_DETECTADOS.md`. El orden está pensado para que cada paso me enseñe algo y desbloquee el siguiente.

| Paso | Problema | Qué voy a aprender |
|---|---|---|
| 1 | **23.** El razonamiento del modelo se guarda en el historial y se reenvía en cada turno | Qué es el contexto, cómo se arma lo que lee el modelo en cada turno, qué es un middleware de `create_agent` |
| 2 | **22.** El historial desborda `MODEL_NUM_CTX` y el modelo «se olvida» de las tools | Cuánto ocupa cada parte (prompt, tools, historial), RAM vs contexto, cómo medir tokens |
| 3 | **20.** El modelo dice «agregué…» sin llamar a la tool | Tool calling: cuándo y por qué un modelo chico no llama a la tool, cómo detectarlo y medirlo |
| 4 | **1.** El filtro `gama` no encuentra nada (la tabla de CPU y GPU por gama está vacía) | Cómo la gama sale de una tabla con reglas y no del LLM; completar la tabla o inferirla por reglas |
| 5 | **2.** El agente inventa precios de ejemplo muy bajos | El system prompt: cómo se escribe una regla que un modelo chico obedezca |
| 6 | **8.** Tras buscar requisitos en la web no ubica el juego en una gama | Cómo se encadenan búsqueda web, RAG y tabla de gamas |
| 7 | **5.** El RAG devuelve fragmentos de la gama equivocada | Chunking y embeddings: cómo se parte un documento y por qué importa |
| 8 | **6.** Cinco documentos del RAG están vacíos | Qué documentación necesita el agente para poder explicar sin inventar |
| 9 | **3, 4 y 7.** Reglas de compatibilidad y datos del catálogo real | Reglas deterministas, el servidor MCP y la ingesta (plan en `SIGUIENTE_SESION.md`) |
| 10 | **12 y 13.** Selector de modelo en el servicio y disco secundario | Servicio HTTP y estado compartido |
| 11 | Resto: 9, 10, 14, 15, 16, 17, 18 y 19 | Detalles, `CLAUDE.md` actualizado, fine-tuning |

## Para empezar

Arrancá por el **paso 1** (problema 23). Primero explicame, en criollo y con un esquema simple:

1. Qué lee el modelo exactamente en cada turno (system prompt + descripción de tools + historial + lo que está escribiendo) y cuánto ocupa cada parte en mi conversación real. Medilo, no estimes.
2. Qué es `MODEL_NUM_CTX`, qué pasa cuando el historial no entra y por qué cuesta RAM.
3. Por qué el razonamiento de `qwen3:4b` llega dentro del contenido aunque `MODEL_RAZONAMIENTO=0`, y dónde se guarda.
4. Las opciones para sacarlo del historial (por ejemplo, un `before_model` de `create_agent`, o un envoltorio del modelo), con la que recomendás y por qué.

Después esperá mi OK antes de escribir código.

## Datos útiles

- Primero quiero ver el problema. Para reproducirlo hay una conversación guardada en `memoria.db`; si hace falta, armá un script chico que mida tokens por turno con `agente.saved_state` (las respuestas de Ollama traen `prompt_eval_count`).
- Comandos: `uv run streamlit run app.py`, `uv run python agente.py [--modelo gemini]`, `uv run python -m rag.ingest`, `uv run pytest`.
- Los precios de la tienda se ven solo con sesión (`AMN_API_COOKIE`); no los toques sin preguntarme.
