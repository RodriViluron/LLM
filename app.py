"""UI de Streamlit: el chat con el recorrido del agente en vivo y el panel «Armá tu PC».

El chat es el del ejemplo de la cátedra: la lógica vive en agente.py y acá solo se dibujan los
eventos que emite. El panel muestra la configuración guardada en el estado del agente como
tarjetas, con un botón «Cambiar» por pieza y «Confirmar pedido» para el armado completo.

Los clics no pasan por el modelo: usan las mismas funciones de armado.py que las tools y escriben
el estado con update_state. Confirmar lo hace siempre el usuario; el agente no tiene cómo hacerlo.

Ejecutar con:  streamlit run app.py
"""
import json

import streamlit as st

import armado

try:
    import agente
    from mcp_tienda import cliente as modulo_cliente
except RuntimeError as e:  # por ejemplo, falta configurar algo en el .env
    st.error(str(e))
    st.stop()

PASOS_EXPANDIDOS = False   # True: razonamiento y tools quedan desplegados
ICONOS = {"pending": "⬜", "in_progress": "🔄", "done": "✅"}
ICONOS_REGLA = {"cumple": "✅", "no_cumple": "❌", "sin_datos": "❔"}
NOMBRES_LUGAR = {"cpu": "Procesador", "motherboard": "Motherboard", "ram": "Memoria RAM", "gpu": "Placa de video",
                 "almacenamiento": "Almacenamiento", "almacenamiento_extra": "Segundo disco", "fuente": "Fuente", "gabinete": "Gabinete", "cooler": "Cooler"}
ESTADOS = {"compatible": "✅ Compatible", "incompatible": "❌ Incompatible",
           "sin_confirmar": "❔ Sin confirmar", "sin_verificar": "❔ Sin verificar"}

st.set_page_config(page_title="Asistente AMN", page_icon="🖥️", layout="wide")


def pesos(valor: float | None) -> str:
    return "—" if valor is None else f"$ {valor:,.0f}".replace(",", ".")


def init_session(config) -> None:
    """Carga en session_state la conversación indicada (vacía si es nueva)."""
    st.session_state.config = config
    st.session_state.historial = agente.saved_turns(config)   # lista de (pregunta, eventos)
    st.session_state.cambiando = None                          # lugar cuya pieza se está cambiando
    st.session_state.aviso = None                              # resultado del último clic


# --- Chat: igual que el ejemplo de la cátedra, con nuestras tools --------------------

def titulo_llamada(e: dict) -> str:
    nombre, args = e["nombre"], e["args"]
    if nombre == "buscar_especificaciones_web":
        return f"🌐 Búsqueda web: «{args.get('consulta', '')}»"
    if nombre == "consultar_caracteristicas":
        return f"📚 Documentación: «{args.get('query', '')}»"
    if nombre == "write_todos":
        return "📝 Escribió la lista de TODOs"
    if nombre == "read_todos":
        return "📋 Leyó la lista de TODOs"
    if nombre == "load_skill":
        return f"📖 Skill «{args.get('nombre', '')}»"
    if nombre == "buscar_productos":
        filtros = ", ".join(f"{k}={v}" for k, v in args.items() if v not in (None, "", {}))
        return f"🔎 Buscó productos: {filtros}"
    if nombre == "obtener_producto":
        return f"📦 Producto {args.get('codigo', '')}"
    if nombre == "verificar_compatibilidad":
        return "🧩 Verificó la compatibilidad"
    if nombre == "iniciar_configuracion":
        return f"🖥️ Inició un armado (presupuesto {pesos(args.get('presupuesto'))})"
    if nombre == "agregar_o_reemplazar_componente":
        return f"➕ {NOMBRES_LUGAR.get(args.get('lugar'), args.get('lugar'))}: {args.get('codigo', '')}"
    if nombre == "ajustar_presupuesto":
        return "💸 Ajustó el armado al presupuesto"
    if nombre == "obtener_configuracion":
        return "🖥️ Leyó el armado"
    if nombre == "preguntar_al_usuario":
        return "❓ Le hizo una pregunta al usuario"
    return f"🔧 {nombre}"


def detalle_llamada(e: dict) -> None:
    """Lo que se sabe apenas el agente decide llamar a la tool (sus argumentos)."""
    if e["nombre"] == "write_todos":
        for t in e["args"].get("todos", []):
            st.markdown(f"{ICONOS.get(t['status'], '•')} {t['task']}")


def _linea_producto(p: dict) -> str:
    return f"- **{p['codigo']}** {p['nombre']} — {pesos(p['precio'])} · stock {p['stock']}"


def _error_de(r: dict) -> str | None:
    """Mensaje de error si la tool devolvió {"error": ...}."""
    try:
        datos = json.loads(r["texto"])
    except (TypeError, ValueError):
        return None
    return datos.get("error") if isinstance(datos, dict) else None


def _texto_skill(texto: str) -> tuple[str | None, str]:
    """Separa la descripción del encabezado YAML (si tiene) y el cuerpo de la skill."""
    if texto.startswith("---"):
        partes = texto.split("---", 2)
        if len(partes) == 3:
            encabezado, cuerpo = partes[1], partes[2].strip()
            descripcion = next(
                (l.removeprefix("description:").strip() for l in encabezado.splitlines() if l.startswith("description:")),
                None,
            )
            return descripcion or None, cuerpo
    return None, texto.strip()


def detalle_resultado(llamada: dict, r: dict) -> str | None:
    """Reporte de lo que devolvió la tool. Devuelve "error" si la tool falló."""
    nombre, datos = llamada["nombre"], r["datos"]
    if error := _error_de(r):
        st.warning(error)
        return "error"
    if nombre == "buscar_especificaciones_web":
        for f in datos or []:
            st.markdown(f"- [{f['title']}]({f['url']})")
        if not datos:
            st.text(r["texto"])
    elif nombre == "consultar_caracteristicas":
        for f in datos or []:
            st.markdown(f"- 📄 **{f['archivo']}**: _{f['fragmento']}…_")
        if not datos:
            st.text(r["texto"])
    elif nombre == "read_todos":
        st.text(r["texto"])
    elif nombre == "load_skill":
        texto = r.get("texto") or ""
        if texto.startswith("No existe la skill"):
            st.warning(texto)
            return "error"
        descripcion, cuerpo = _texto_skill(texto)
        st.caption("Skill cargada" + (f" — {descripcion}" if descripcion else "."))
        if cuerpo:
            st.markdown(cuerpo)
    elif nombre == "buscar_productos":
        productos = (datos or {}).get("productos", [])
        st.markdown("\n".join(_linea_producto(p) for p in productos) or "_Sin resultados._")
        for nota in (datos or {}).get("notas", []):
            st.caption(f"⚠️ {nota}")
    elif nombre == "obtener_producto":
        st.markdown(_linea_producto(datos["producto"]))
    elif nombre == "verificar_compatibilidad":
        reglas(datos["resultados"])
        st.markdown(f"**Total:** {pesos(datos['total'])}")
    elif datos and "configuracion" in datos:   # tools de armado
        config = datos["configuracion"]
        estado = (config.get("reporte") or {}).get("estado_general", "sin_verificar")
        st.markdown(f"{len(config['componentes'])} piezas · **{pesos(config['total'])}** · {ESTADOS[estado]}")
        for cambio in json.loads(r["texto"]).get("ajuste", {}).get("cambios", []):
            st.markdown(f"- {NOMBRES_LUGAR[cambio['lugar']]}: {cambio['antes']['nombre']} → "
                        f"{cambio['despues']['nombre']} (ahorra {pesos(cambio['ahorro'])})")
    return None


def opciones_del_ultimo_turno(eventos) -> list[str]:
    """Opciones de la pregunta con botones si el turno terminó con una (preguntar_al_usuario).

    La tool que pregunta termina el turno, así que su resultado es el último evento que cuenta
    (las fuentes van al final y no cuentan).
    """
    for e in reversed([e for e in eventos if e["tipo"] != "fuentes"]):
        if e["tipo"] == "resultado":
            return (e.get("datos") or {}).get("opciones") or []
        return []
    return []


def render_eventos(eventos) -> list[dict]:
    """Dibuja los eventos a medida que llegan; sirve en vivo (generador) y para el historial (lista).

    Devuelve los eventos ya dibujados, para guardarlos en el historial.
    """
    emitidos = []
    llamadas = {}   # id del tool call -> (evento de la llamada, contenedor st.status)
    for e in eventos:
        emitidos.append(e)
        tipo = e["tipo"]
        if tipo == "razonamiento":
            with st.expander("💭 Razonamiento", expanded=PASOS_EXPANDIDOS):
                # Un salto de línea por renglón y sin sangrías (que markdown tomaría por código).
                st.markdown("  \n".join(linea.strip() for linea in e["texto"].splitlines()))
        elif tipo == "texto":
            st.markdown(e["texto"])   # st.markdown renderiza el markdown del modelo
            if e.get("modelo"):
                st.caption(f"🤖 {e['modelo']}")   # qué modelo escribió esta respuesta
        elif tipo == "llamada":
            status = st.status(titulo_llamada(e), expanded=PASOS_EXPANDIDOS)   # "running" hasta el resultado
            with status:
                detalle_llamada(e)
            llamadas[e["id"]] = (e, status)
        elif tipo == "resultado":
            llamada, status = llamadas[e["id"]]
            with status:
                estado = detalle_resultado(llamada, e)
            status.update(state=estado or "complete")
            if llamada["nombre"] == "preguntar_al_usuario" and e["datos"] \
                    and e["datos"].get("opciones"):
                # La pregunta va a la vista; sus opciones son botones debajo del turno (ver opciones_del_ultimo_turno).
                st.markdown(f"**{e['datos']['pregunta']}**")
        elif tipo == "fuentes":
            with st.expander(f"Fuentes consultadas ({len(e['fuentes'])})"):
                for s in e["fuentes"]:
                    if s["url"].startswith("http"):
                        st.markdown(f"- [{s['title']}]({s['url']})")
                    else:
                        st.markdown(f"- 📄 {s['title']}")
    return emitidos


def render_sidebar() -> None:
    """Selector de modelo y manejo de conversaciones: crear una nueva o volver a una anterior."""
    actual = st.session_state.config["configurable"]["thread_id"]
    with st.sidebar:
        # Se elige por mensaje: todos los modelos comparten la memoria de la conversación.
        opciones = agente.opciones_de_modelo()
        st.selectbox("Modelo", list(opciones), format_func=opciones.get, key="modelo",
                     help="Se usa para el próximo mensaje. Gemini aparece si está configurado en el .env.")

        st.header("Conversaciones")

        # Deshabilitado si la actual todavía está vacía: no tiene sentido crear otra.
        if st.button("➕ Nueva conversación", disabled=not st.session_state.historial):
            init_session(agente.new_thread())
            st.rerun()

        for thread_id, titulo in agente.list_threads():
            if st.button(titulo, key=thread_id, disabled=thread_id == actual, use_container_width=True):
                init_session(agente.select_thread(thread_id))
                st.rerun()


# --- Panel «Armá tu PC»: dibuja la configuración guardada en el estado del agente -----

def guardar_configuracion(config: dict) -> None:
    """Escribe la configuración en el estado del agente, igual que lo haría una tool."""
    agente.get_agent().update_state(st.session_state.config, {"configuracion": config})


def reglas(resultados: list[dict]) -> None:
    for regla in resultados:
        aviso = " _(aviso: no impide confirmar)_" if regla["estado"] == "sin_datos" and not regla.get("critica", True) else ""
        st.markdown(f"{ICONOS_REGLA[regla['estado']]} {regla['detalle']}{aviso}")


def tarjeta(lugar: str, producto: dict, cantidad: int = 1) -> None:
    with st.container(border=True):
        st.caption(f"{NOMBRES_LUGAR[lugar]} · {producto['codigo']}")
        st.markdown(f"**{f'{cantidad} × ' if cantidad > 1 else ''}{producto['nombre']}**")
        stock = f"stock {producto['stock']}" if producto["stock"] > 0 else "⚠️ sin stock"
        precio = pesos(producto["precio"]) + (f" c/u · {pesos(producto['precio'] * cantidad)}" if cantidad > 1 else "")
        st.markdown(f"{precio} · {stock}")
        atributos = [f"{k.replace('_', ' ')}: {', '.join(v) if isinstance(v, list) else v}"
                     for k, v in producto["atributos"].items() if v is not None]
        if producto.get("gama"):
            atributos.append(f"gama: {producto['gama']}")
        st.caption(" · ".join(atributos) or "Sin atributos informados")
        if st.button("Cambiar", key=f"cambiar_{lugar}", use_container_width=True):
            st.session_state.cambiando = lugar
            st.session_state.aviso = None
            st.rerun()


def selector_de_alternativas(config: dict, lugar: str) -> None:
    """Alternativas compatibles con el resto del armado, debajo de la tarjeta que se está cambiando.

    Elegir una aplica el cambio sin pasar por el modelo.
    """
    with st.container(border=True):
        st.markdown(f"**Cambiar {NOMBRES_LUGAR[lugar].lower()}** — opciones compatibles con el resto:")
        opciones = armado.alternativas(config, lugar, modulo_cliente.get_cliente())
        if not opciones:
            st.info("No hay otras opciones compatibles con stock.")
        for p in opciones:
            st.markdown(f"**{p['codigo']}** {p['nombre']}  \n{pesos(p['precio'])} · stock {p['stock']}")
            if st.button(f"Elegir {p['codigo']}", key=f"elegir_{p['codigo']}", use_container_width=True):
                try:
                    nueva = armado.poner_componente(config, lugar, p["codigo"], modulo_cliente.get_cliente(),
                                                    armado.cantidad(config, lugar))
                    guardar_configuracion(nueva)
                    st.session_state.aviso = ("ok", f"{NOMBRES_LUGAR[lugar]} cambiada por {p['codigo']}.")
                except armado.ErrorArmado as e:
                    st.session_state.aviso = ("error", str(e))
                st.session_state.cambiando = None
                st.rerun()
        if st.button("Cancelar", key="cancelar_cambio", use_container_width=True):
            st.session_state.cambiando = None
            st.rerun()


def confirmar(config: dict) -> None:
    """Clic en «Confirmar pedido»: vuelve a verificar con la tienda y, si nada cambió, envía el pedido."""
    referencia = st.session_state.config["configurable"]["thread_id"]
    try:
        resultado = armado.confirmar_pedido(config, modulo_cliente.get_cliente(), armado.PedidosLocales(), referencia)
    except armado.ErrorArmado as e:
        st.session_state.aviso = ("error", str(e))
        return
    guardar_configuracion(resultado["configuracion"])
    if resultado["confirmado"]:
        st.session_state.aviso = ("ok", f"Pedido {resultado['pedido']} confirmado por {pesos(config['total'])}.")
    else:
        st.session_state.aviso = ("error", "No se confirmó el pedido. " + " · ".join(resultado["motivos"]))


def progreso(config: dict) -> None:
    """Qué piezas ya están en el armado y cuáles faltan (lo que realmente guardó el agente)."""
    elegidas = config.get("componentes") or {}
    # Las obligatorias dependen de lo elegido (fuente del gabinete, video y cooler de la CPU).
    lugares = [l for l in NOMBRES_LUGAR if l in armado.obligatorios(config) or l in elegidas]
    hechas = sum(1 for lugar in lugares if lugar in elegidas)
    st.progress(hechas / len(lugares), text=f"Armado: {hechas} de {len(lugares)} piezas")
    st.caption("  ·  ".join(f"{'✅' if l in elegidas else '⬜'} {NOMBRES_LUGAR[l]}" for l in lugares))


def render_panel() -> None:
    st.subheader("🖥️ Armá tu PC")
    config = agente.saved_state(st.session_state.config).get("configuracion")
    if st.session_state.aviso:
        tipo, mensaje = st.session_state.aviso
        (st.success if tipo == "ok" else st.error)(mensaje)
    if not config:
        st.info("Todavía no hay un armado. Pedile al asistente, por ejemplo: "
                "«Armame una PC para jugar con $1.200.000».")
        return
    if not config.get("componentes"):
        # Hay una configuración iniciada pero el agente todavía no puso ninguna pieza.
        st.markdown(f"**Presupuesto:** {pesos(config.get('presupuesto'))}"
                    + (f" · **Uso:** {config['perfil_uso']}" if config.get("perfil_uso") else ""))
        progreso(config)
        st.info("El armado está iniciado pero todavía no tiene piezas. Acá aparecen a medida que el asistente "
                "las agrega: si dice que agregó una y no se ve acá, no la agregó.")
        return
    if config.get("reporte") is None:   # quedó sin verificar (ver armado.fusionar): se verifica al mostrar
        config = armado.asegurar_verificada(config, modulo_cliente.get_cliente())
        guardar_configuracion(config)

    presupuesto, total = config.get("presupuesto"), config["total"]
    columna_total, columna_presupuesto = st.columns(2)
    excedente = None if presupuesto is None or total <= presupuesto else f"{pesos(total - presupuesto)} de más"
    columna_total.metric("Total", pesos(total), delta=excedente, delta_color="inverse")
    columna_presupuesto.metric("Presupuesto", pesos(presupuesto))
    st.markdown(f"**Compatibilidad:** {ESTADOS[config['reporte']['estado_general']]}"
                + (f" · **Uso:** {config['perfil_uso']}" if config.get("perfil_uso") else ""))
    progreso(config)

    columnas = st.columns(2)
    for i, (lugar, producto) in enumerate(config["componentes"].items()):
        with columnas[i % 2]:
            tarjeta(lugar, producto, armado.cantidad(config, lugar))
            if st.session_state.cambiando == lugar:
                selector_de_alternativas(config, lugar)

    with st.expander("Reporte de compatibilidad", expanded=config["reporte"]["estado_general"] != "compatible"):
        reglas(config["reporte"]["resultados"])

    motivos = armado.motivos_para_no_confirmar(config)
    for motivo in motivos:
        st.caption(f"⚠️ {motivo}")
    if st.button("✅ Confirmar pedido", type="primary", disabled=bool(motivos), use_container_width=True):
        confirmar(config)
        st.rerun()
    st.caption("El pedido lo confirmás vos con este botón: el asistente no puede confirmarlo.")


# --- Página ------------------------------------------------------------------------

if "config" not in st.session_state:
    init_session(agente.resume_thread())

st.title("🖥️ Asistente de compra AMN")
render_sidebar()
columna_chat, columna_panel = st.columns([3, 2], gap="large")

with columna_chat:
    # Streamlit re-ejecuta todo el script en cada interacción: se redibuja el historial guardado.
    ultimo = len(st.session_state.historial) - 1
    for i, (pregunta, eventos) in enumerate(st.session_state.historial):
        st.chat_message("user").markdown(pregunta)
        with st.chat_message("assistant"):
            render_eventos(eventos)
            if i == ultimo:   # solo la última pregunta tiene botones: las anteriores ya fueron contestadas
                for j, opcion in enumerate(opciones_del_ultimo_turno(eventos)):
                    if st.button(opcion, key=f"opcion_{i}_{j}"):
                        st.session_state.enviado = opcion   # se envía como si el usuario lo escribiera
                        st.rerun()

entrada = st.chat_input("Escribí tu consulta...")
if prompt := (st.session_state.pop("enviado", None) or entrada):
    turno = len(st.session_state.historial) + 1
    with columna_chat:
        st.chat_message("user").markdown(prompt)
        with st.chat_message("assistant"):
            try:
                with st.spinner("El asistente está trabajando..."):
                    el_agente = agente.get_agent(st.session_state.get("modelo", agente.OPCION_LOCAL))
                    eventos = render_eventos(agente.stream_turn(prompt, st.session_state.config, turno, el_agente))
            except Exception as e:  # noqa: BLE001
                st.error(agente.mensaje_de_error(e))
                st.stop()

    st.session_state.historial.append((prompt, eventos))
    st.session_state.aviso = None
    st.rerun()   # redibuja todo desde session_state (y el panel, con el estado nuevo)

with columna_panel:
    render_panel()
