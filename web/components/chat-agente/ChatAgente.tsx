"use client";

/**
 * Chat del asistente de compra: botón flotante abajo a la derecha + panel de conversación.
 *
 * Es lo único que hay que llevar a la tienda: esta carpeta no depende de nada más que de React.
 * Toma los colores de las variables CSS de la página (--brand-blue, --surface, --foreground...),
 * así que acompaña el tema claro u oscuro sin tocar nada. Ver docs/GUIA_INTEGRACION.md.
 */

import { type FormEvent, type KeyboardEvent, type ReactNode, useEffect, useId, useMemo, useRef, useState } from "react";

import estilos from "./ChatAgente.module.css";
import {
  ErrorConfirmacion,
  cambiarPiezaArmado,
  confirmarArmadoPdf,
  descargarBlobPdf,
  pedirAlternativasArmado,
} from "./armadoApi";
import type { Armado, Fuente, Item, ItemPedido, OpcionModelo, Producto, Turno } from "./tipos";
import { useChatAgente } from "./useChatAgente";

const MODO_DESARROLLO_ENV =
  typeof process !== "undefined" &&
  (process.env.NEXT_PUBLIC_MODO_DESARROLLO === "1" || process.env.NEXT_PUBLIC_MODO_DESARROLLO === "true");

const MODELOS_POR_DEFECTO: OpcionModelo[] = [
  { valor: "local", etiqueta: "Local" },
  { valor: "gemini", etiqueta: "Gemini" },
];

export type PropsChatAgente = {
  /** Ruta del backend que hace de puente con el agente. Tiene que exponer /chat y /conversaciones/:id. */
  endpoint?: string;
  titulo?: string;
  subtitulo?: string;
  /** Pedidos de ejemplo que se ofrecen cuando el chat está vacío. */
  sugerencias?: string[];
  /** Muestra el aviso de lo que el agente está haciendo («Pensando…», «Buscando productos…», «Buscando en internet…»). */
  mostrarEstados?: boolean;
  /** Texto del botón confirmar del armado (por defecto «Confirmar pedido»). */
  textoConfirmar?: string;
  /** Callback opcional cuando se confirma un pedido (recibe pedido y armado además de descargar el PDF). */
  onConfirmarArmado?: (pedido: ItemPedido[], armado: Armado) => void;
  /** El usuario tocó un producto: la página decide adónde lo lleva. */
  onVerProducto?: (producto: Producto) => void;
  /**
   * El armado de la conversación cambió (el agente puso o cambió una pieza, se recuperó la
   * conversación o se empezó una nueva: en ese caso llega `null`). Sirve para que la página
   * muestre el armado en vivo, por ejemplo en «Armá tu PC». No confirma nada.
   */
  onArmado?: (armado: Armado | null) => void;
  /** Avisa a la página qué `conversacion_id` está activo (para sincronizar Cambiar/Confirmar externos). */
  onConversacionId?: (conversacionId: string | null) => void;
  /** Armado actualizado desde fuera del componente (p. ej. al cambiar una pieza desde «Armá tu PC»). */
  armadoExterno?: Armado | null;
  abiertoInicial?: boolean;
  /** Solo desarrollo: muestra el selector de modelo (por defecto según NEXT_PUBLIC_MODO_DESARROLLO). En producción no aparece. */
  modoDesarrollo?: boolean;
  /** Opciones del selector de modelo cuando `modoDesarrollo` está activo. */
  modelos?: OpcionModelo[];
};

const SUGERENCIAS = [
  "Armame una PC para jugar en 1080p",
  "Necesito un cable HDMI de 2 metros",
  "¿Qué es una PC de gama media?",
];

const LUGARES: Record<string, string> = {
  cpu: "Procesador",
  cooler: "Cooler",
  motherboard: "Placa madre",
  ram: "Memoria",
  almacenamiento: "Disco",
  almacenamiento_extra: "Segundo disco",
  gpu: "Placa de video",
  gabinete: "Gabinete",
  fuente: "Fuente",
};

const COMPATIBILIDAD: Record<Armado["compatibilidad"]["estado"], { texto: string; tono: string }> = {
  compatible: { texto: "Compatible", tono: estilos.bien },
  incompatible: { texto: "Incompatible", tono: estilos.mal },
  sin_confirmar: { texto: "Compatibilidad sin confirmar", tono: estilos.duda },
  sin_verificar: { texto: "Sin verificar", tono: estilos.duda },
};

const pesos = new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 });

function precio(valor: number | null): string {
  return valor == null ? "Consultar" : pesos.format(valor);
}

// --- Íconos -------------------------------------------------------------------------------

function Icono({ children, tamano = 20 }: { children: ReactNode; tamano?: number }) {
  return (
    <svg width={tamano} height={tamano} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {children}
    </svg>
  );
}

const IconoChat = () => (
  <Icono tamano={24}>
    <path d="M20 11.5a7.5 7.5 0 0 1-11.2 6.5L4 19.5l1.5-4.3A7.5 7.5 0 1 1 20 11.5Z" />
    <path d="M12.5 8.2l.8 1.9 1.9.8-1.9.8-.8 1.9-.8-1.9-1.9-.8 1.9-.8.8-1.9Z" fill="currentColor" stroke="none" />
  </Icono>
);
const IconoCerrar = () => <Icono><path d="M6 6l12 12M18 6 6 18" /></Icono>;
const IconoEnviar = () => <Icono><path d="M12 19V5M5.5 11.5 12 5l6.5 6.5" /></Icono>;
const IconoDetener = () => <Icono><rect x="7" y="7" width="10" height="10" rx="1.5" fill="currentColor" stroke="none" /></Icono>;
const IconoNueva = () => <Icono tamano={18}><path d="M12 5v14M5 12h14" /></Icono>;

// --- Texto del agente: markdown mínimo, sin HTML crudo --------------------------------------

function enLinea(texto: string): ReactNode[] {
  const partes = texto.split(/(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|`[^`]+`|\[[^\]]+\]\(https?:\/\/[^\s)]+\))/g);
  return partes.filter(Boolean).map((parte, i) => {
    if (parte.startsWith("**")) return <strong key={i}>{parte.slice(2, -2)}</strong>;
    if (parte.startsWith("*")) return <em key={i}>{parte.slice(1, -1)}</em>;
    if (parte.startsWith("`")) return <code key={i}>{parte.slice(1, -1)}</code>;
    const enlace = /^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/.exec(parte);
    if (enlace) {
      return <a key={i} href={enlace[2]} target="_blank" rel="noopener noreferrer">{enlace[1]}</a>;
    }
    return parte;
  });
}

const ES_FILA_TABLA = /^\|.+\|$/;
const ES_SEPARADOR_TABLA = /^\|(\s*:?-{3,}:?\s*\|)+\s*$/;

function separarCeldas(linea: string): string[] {
  return linea
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((celda) => celda.trim());
}

function TextoAgente({ texto }: { texto: string }) {
  const bloques: ReactNode[] = [];
  let parrafo: string[] = [];
  let lista: { ordenada: boolean; items: string[] } | null = null;

  const cerrar = () => {
    if (parrafo.length) {
      const lineas = parrafo;
      bloques.push(
        <p key={bloques.length}>
          {lineas.map((linea, i) => (
            <span key={i}>{enLinea(linea)}{i < lineas.length - 1 && <br />}</span>
          ))}
        </p>,
      );
      parrafo = [];
    }
    if (lista) {
      const Etiqueta = lista.ordenada ? "ol" : "ul";
      bloques.push(
        <Etiqueta key={bloques.length}>
          {lista.items.map((item, i) => <li key={i}>{enLinea(item)}</li>)}
        </Etiqueta>,
      );
      lista = null;
    }
  };

  const crudas = texto.split("\n");
  for (let idx = 0; idx < crudas.length; idx++) {
    const linea = crudas[idx].trim();
    if (ES_FILA_TABLA.test(linea) && idx + 1 < crudas.length && ES_SEPARADOR_TABLA.test(crudas[idx + 1].trim())) {
      cerrar();
      const encabezados = separarCeldas(linea);
      const filas: string[][] = [];
      idx += 2;
      while (idx < crudas.length && ES_FILA_TABLA.test(crudas[idx].trim())) {
        filas.push(separarCeldas(crudas[idx].trim()));
        idx++;
      }
      idx--;
      bloques.push(
        <div key={bloques.length} className={estilos.tablaEnvuelta}>
          <table className={estilos.tabla}>
            <thead>
              <tr>{encabezados.map((celda, j) => <th key={j}>{enLinea(celda)}</th>)}</tr>
            </thead>
            <tbody>
              {filas.map((fila, r) => (
                <tr key={r}>{encabezados.map((_, j) => <td key={j}>{enLinea(fila[j] ?? "")}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }
    const vineta = /^[-*•]\s+(.*)$/.exec(linea);
    const numerada = /^\d+[.)]\s+(.*)$/.exec(linea);
    const titulo = /^#{1,6}\s+(.*)$/.exec(linea);
    if (!linea) {
      cerrar();
    } else if (vineta || numerada) {
      const ordenada = Boolean(numerada);
      if (parrafo.length || (lista && lista.ordenada !== ordenada)) cerrar();
      lista ??= { ordenada, items: [] };
      lista.items.push((vineta ?? numerada)![1]);
    } else if (titulo) {
      cerrar();
      bloques.push(<p key={bloques.length}><strong>{enLinea(titulo[1])}</strong></p>);
    } else {
      if (lista) cerrar();
      parrafo.push(linea);
    }
  }
  cerrar();
  return <div className={estilos.texto}>{bloques}</div>;
}

// --- Piezas de una respuesta ----------------------------------------------------------------

function Atributos({ atributos }: { atributos: Producto["atributos"] }) {
  const visibles = Object.entries(atributos).slice(0, 3);
  if (!visibles.length) return null;
  return (
    <span className={estilos.atributos}>
      {visibles.map(([clave, valor]) => (
        <span key={clave} className={estilos.atributo}>
          {clave.replace(/_/g, " ")}: {Array.isArray(valor) ? valor.join(", ") : String(valor)}
        </span>
      ))}
    </span>
  );
}

function TarjetaProducto({ producto, alTocar }: { producto: Producto; alTocar?: (producto: Producto) => void }) {
  const sinStock = producto.stock != null && producto.stock <= 0;
  const contenido = (
    <>
      <span className={estilos.miniatura}>
        {producto.imagen
          ? <img src={producto.imagen} alt="" loading="lazy" />
          : <span aria-hidden="true">{(producto.categoria ?? "?").slice(0, 3).toUpperCase()}</span>}
      </span>
      <span className={estilos.datosProducto}>
        <span className={estilos.nombreProducto}>{producto.nombre}</span>
        <span className={estilos.codigo}>{producto.codigo}{producto.marca ? ` · ${producto.marca}` : ""}</span>
        <Atributos atributos={producto.atributos} />
      </span>
      <span className={estilos.precioProducto}>
        <strong>{precio(producto.precio)}</strong>
        <span className={sinStock ? estilos.mal : estilos.bien}>{sinStock ? "Sin stock" : "En stock"}</span>
      </span>
    </>
  );
  return alTocar
    ? <button type="button" className={estilos.producto} onClick={() => alTocar(producto)}>{contenido}</button>
    : <div className={estilos.producto}>{contenido}</div>;
}

function ListaProductos({ productos, alTocar }: {
  productos: Producto[]; alTocar?: (producto: Producto) => void;
}) {
  const [todos, setTodos] = useState(false);
  const visibles = todos ? productos : productos.slice(0, 4);
  return (
    <div className={estilos.bloque}>
      {visibles.map((producto) => <TarjetaProducto key={producto.codigo} producto={producto} alTocar={alTocar} />)}
      {productos.length > visibles.length && (
        <button type="button" className={estilos.enlace} onClick={() => setTodos(true)}>
          Ver {productos.length - visibles.length} más
        </button>
      )}
    </div>
  );
}

function TarjetaArmado({
  armado,
  vigente,
  textoConfirmar,
  endpoint,
  conversacionId,
  bloqueado,
  alConfirmar,
  alActualizarArmado,
}: {
  armado: Armado;
  vigente: boolean;
  textoConfirmar: string;
  endpoint: string;
  conversacionId: string | null;
  bloqueado: boolean;
  alConfirmar?: (pedido: ItemPedido[], armado: Armado) => void;
  alActualizarArmado: (armado: Armado) => void;
}) {
  const [editandoLugar, setEditandoLugar] = useState<string | null>(null);
  const [cargandoAlt, setCargandoAlt] = useState(false);
  const [alternativas, setAlternativas] = useState<Producto[]>([]);
  const [estadoAccion, setEstadoAccion] = useState<string | null>(null);
  const [errorAccion, setErrorAccion] = useState<string | null>(null);
  const [motivosConfirmar, setMotivosConfirmar] = useState<string[]>([]);
  const [avisoOk, setAvisoOk] = useState<string | null>(null);

  useEffect(() => {
    setEditandoLugar(null);
    setAlternativas([]);
    setErrorAccion(null);
    setMotivosConfirmar([]);
  }, [armado.version]);

  const abrirCambiar = async (lugar: string) => {
    if (!conversacionId) return;
    if (editandoLugar === lugar) {
      setEditandoLugar(null);
      setAlternativas([]);
      return;
    }
    setEditandoLugar(lugar);
    setCargandoAlt(true);
    setErrorAccion(null);
    setAvisoOk(null);
    try {
      setAlternativas(await pedirAlternativasArmado(endpoint, conversacionId, lugar));
    } catch (e) {
      setErrorAccion(e instanceof Error ? e.message : "No se pudieron buscar alternativas.");
      setEditandoLugar(null);
    } finally {
      setCargandoAlt(false);
    }
  };

  const elegirAlternativa = async (lugar: string, codigo: string) => {
    if (!conversacionId) return;
    setEstadoAccion("Cambiando pieza…");
    setErrorAccion(null);
    setAvisoOk(null);
    setMotivosConfirmar([]);
    try {
      const actualizado = await cambiarPiezaArmado(endpoint, conversacionId, lugar, codigo);
      alActualizarArmado(actualizado);
      setEditandoLugar(null);
      setAlternativas([]);
    } catch (e) {
      setErrorAccion(e instanceof Error ? e.message : "No se pudo cambiar la pieza.");
    } finally {
      setEstadoAccion(null);
    }
  };

  const confirmarPedido = async () => {
    if (!conversacionId) {
      alConfirmar?.(armado.pedido, armado);
      return;
    }
    setEstadoAccion("Generando presupuesto…");
    setErrorAccion(null);
    setAvisoOk(null);
    setMotivosConfirmar([]);
    try {
      const { blob, nombreArchivo, referencia } = await confirmarArmadoPdf(endpoint, conversacionId);
      descargarBlobPdf(blob, nombreArchivo);
      setAvisoOk(referencia ? `Presupuesto ${referencia} descargado.` : "Presupuesto descargado.");
      alConfirmar?.(armado.pedido, armado);
    } catch (e) {
      if (e instanceof ErrorConfirmacion) {
        if (e.armado) alActualizarArmado(e.armado);
        setMotivosConfirmar(e.motivos.length ? e.motivos : [e.message]);
      } else {
        setErrorAccion(e instanceof Error ? e.message : "No se pudo confirmar el pedido.");
      }
    } finally {
      setEstadoAccion(null);
    }
  };

  const compatibilidad = COMPATIBILIDAD[armado.compatibilidad.estado] ?? COMPATIBILIDAD.sin_verificar;
  const pendientes = armado.compatibilidad.reglas.filter((regla) => regla.estado !== "cumple");
  const excedido = armado.dentro_del_presupuesto === false;
  const ocupado = bloqueado || Boolean(estadoAccion);
  const puedeAccionar = vigente && Boolean(conversacionId);
  const mostrarConfirmar = vigente && (Boolean(conversacionId) || Boolean(alConfirmar));

  return (
    <div className={estilos.armado}>
      <div className={estilos.armadoCabecera}>
        <strong>Tu armado{armado.perfil_uso ? ` · ${armado.perfil_uso}` : ""}</strong>
        <span className={`${estilos.insignia} ${compatibilidad.tono}`}>{compatibilidad.texto}</span>
      </div>
      {armado.componentes.length === 0 && <p className={estilos.nota}>Todavía no tiene piezas.</p>}
      <ul className={estilos.piezas}>
        {armado.componentes.map(({ lugar, cantidad, producto }) => (
          <li key={lugar}>
            <div className={estilos.filaPieza}>
              <span className={estilos.lugar}>{LUGARES[lugar] ?? lugar}</span>
              <span className={estilos.nombrePieza}>
                {cantidad > 1 ? `${cantidad} × ` : ""}{producto.nombre}
                <span className={estilos.codigo}>
                  {producto.codigo}
                  {cantidad > 1 && producto.precio != null ? ` · ${cantidad} × ${precio(producto.precio)}` : ""}
                </span>
              </span>
              <span className={estilos.precioYAccion}>
                <span className={estilos.precioPieza}>
                  {precio(producto.precio != null ? producto.precio * cantidad : null)}
                </span>
                {puedeAccionar && (
                  <button type="button" className={estilos.cambiar} disabled={ocupado}
                    onClick={() => void abrirCambiar(lugar)}>
                    {editandoLugar === lugar ? "Cerrar" : "Cambiar"}
                  </button>
                )}
              </span>
            </div>
            {puedeAccionar && editandoLugar === lugar && (
              <div className={estilos.selector}>
                {cargandoAlt ? (
                  <p className={estilos.nota}>Buscando opciones…</p>
                ) : alternativas.length === 0 ? (
                  <p className={estilos.nota}>No hay otras opciones compatibles con stock.</p>
                ) : (
                  alternativas.map((alt) => (
                    <button key={alt.codigo} type="button" className={estilos.opcionCambio} disabled={ocupado}
                      onClick={() => void elegirAlternativa(lugar, alt.codigo)}>
                      <span className={estilos.opcionNombre}>{alt.nombre}</span>
                      <span className={estilos.opcionMeta}>
                        {precio(alt.precio)} · {alt.stock != null && alt.stock > 0 ? `stock ${alt.stock}` : "sin stock"}
                      </span>
                    </button>
                  ))
                )}
              </div>
            )}
          </li>
        ))}
      </ul>
      <div className={estilos.total}>
        <span>Total</span>
        <strong className={excedido ? estilos.mal : undefined}>{precio(armado.total)}</strong>
      </div>
      {armado.presupuesto != null && (
        <p className={estilos.nota}>
          Presupuesto: {precio(armado.presupuesto)}{excedido ? " — el armado lo supera" : ""}
        </p>
      )}
      {pendientes.length > 0 && (
        <ul className={estilos.reglas}>
          {pendientes.map((regla) => (
            <li key={regla.regla} className={regla.estado === "no_cumple" ? estilos.mal : estilos.duda}>
              {regla.estado === "no_cumple"
                ? "No es compatible: "
                : regla.critica === false
                  ? "Aviso: "
                  : "Sin datos: "}
              {regla.detalle}
            </li>
          ))}
        </ul>
      )}
      {estadoAccion && (
        <p className={estilos.estado}>
          <span className={estilos.puntos} aria-hidden="true"><i /><i /><i /></span>
          {estadoAccion}
        </p>
      )}
      {errorAccion && <p className={`${estilos.nota} ${estilos.mal}`} role="alert">{errorAccion}</p>}
      {avisoOk && <p className={`${estilos.nota} ${estilos.bien}`}>{avisoOk}</p>}
      {motivosConfirmar.length > 0 && (
        <p className={`${estilos.nota} ${estilos.mal}`} role="alert">
          No se pudo confirmar: {motivosConfirmar.join(" · ")}
        </p>
      )}
      {mostrarConfirmar && (
        <>
          <button type="button" className={estilos.confirmar}
            disabled={!armado.se_puede_confirmar || ocupado}
            onClick={() => void confirmarPedido()}>
            {textoConfirmar}
          </button>
          {!armado.se_puede_confirmar && armado.motivos_para_no_confirmar.length > 0 && (
            <p className={estilos.nota}>Todavía no se puede confirmar: {armado.motivos_para_no_confirmar.join(" · ")}</p>
          )}
        </>
      )}
    </div>
  );
}

function Fuentes({ fuentes }: { fuentes: Fuente[] }) {
  return (
    <details className={estilos.fuentes}>
      <summary>Fuentes consultadas ({fuentes.length})</summary>
      <ul>
        {fuentes.map((fuente, i) => (
          <li key={i}>
            {fuente.url
              ? <a href={fuente.url} target="_blank" rel="noopener noreferrer">{fuente.titulo}</a>
              : fuente.titulo}
          </li>
        ))}
      </ul>
    </details>
  );
}

// --- Componente ---------------------------------------------------------------------------

export function ChatAgente({
  endpoint = "/api/agente",
  titulo = "Asistente de compra",
  subtitulo = "Todo Computación",
  sugerencias = SUGERENCIAS,
  mostrarEstados = true,
  textoConfirmar = "Confirmar pedido",
  onConfirmarArmado,
  onVerProducto,
  onArmado,
  onConversacionId,
  armadoExterno,
  abiertoInicial = false,
  modoDesarrollo = MODO_DESARROLLO_ENV,
  modelos = MODELOS_POR_DEFECTO,
}: PropsChatAgente) {
  const [abierto, setAbierto] = useState(abiertoInicial);
  const [borrador, setBorrador] = useState("");
  const [modelo, setModelo] = useState(modelos[0]?.valor ?? "local");
  const {
    turnos,
    armadoGuardado,
    conversacionId,
    respondiendo,
    recuperando,
    enviar,
    detener,
    recuperar,
    nuevaConversacion,
    actualizarArmado,
  } = useChatAgente(endpoint);
  const idPanel = useId();
  const idModelo = useId();
  const lista = useRef<HTMLDivElement>(null);
  const entrada = useRef<HTMLTextAreaElement>(null);
  const boton = useRef<HTMLButtonElement>(null);
  const pegadoAbajo = useRef(true);

  // El armado vigente es el último que mandó el agente (o el recuperado del servidor).
  const armadoActual = useMemo(() => {
    for (let t = turnos.length - 1; t >= 0; t--) {
      const item = [...turnos[t].items].reverse().find((i) => i.tipo === "armado");
      if (item?.tipo === "armado") return item.armado;
    }
    return armadoGuardado;
  }, [turnos, armadoGuardado]);
  const avisarArmado = useRef(onArmado);
  avisarArmado.current = onArmado;
  useEffect(() => {
    avisarArmado.current?.(armadoActual);
  }, [armadoActual]);

  const avisarConversacion = useRef(onConversacionId);
  avisarConversacion.current = onConversacionId;
  useEffect(() => {
    avisarConversacion.current?.(conversacionId);
  }, [conversacionId]);

  useEffect(() => {
    if (!armadoExterno) return;
    if ((armadoExterno.version ?? 0) > (armadoActual?.version ?? 0)) {
      actualizarArmado(armadoExterno);
    }
  }, [armadoExterno, armadoActual?.version, actualizarArmado]);

  useEffect(() => {
    if (!abierto) return;
    pegadoAbajo.current = true;
    void recuperar();
    entrada.current?.focus();
  }, [abierto, recuperar]);

  // Con cada novedad, baja solo si el usuario no desplazó el historial hacia arriba.
  useEffect(() => {
    if (pegadoAbajo.current) lista.current?.scrollTo({ top: lista.current.scrollHeight });
  }, [turnos, abierto]);

  const cerrar = () => {
    setAbierto(false);
    boton.current?.focus();
  };

  const mandar = (texto: string) => {
    pegadoAbajo.current = true;
    void enviar(texto, modoDesarrollo ? modelo : undefined);
    setBorrador("");
    if (entrada.current) entrada.current.style.height = "auto";
  };

  const alEnviar = (evento: FormEvent) => {
    evento.preventDefault();
    mandar(borrador);
  };

  const alTeclear = (evento: KeyboardEvent<HTMLTextAreaElement>) => {
    if (evento.key === "Enter" && !evento.shiftKey && !evento.nativeEvent.isComposing) {
      evento.preventDefault();
      if (!respondiendo) mandar(borrador);
    }
  };

  const ultimo = turnos[turnos.length - 1];
  // Solo el armado más reciente se puede cargar: los anteriores quedaron viejos.
  const turnoDelArmado = [...turnos].reverse().find((turno) => turno.items.some((item) => item.tipo === "armado"))?.id;

  const dibujar = (turno: Turno, item: Item, i: number) => {
    switch (item.tipo) {
      case "texto":
        return <TextoAgente key={i} texto={item.texto} />;
      case "productos":
        return <ListaProductos key={i} productos={item.productos} alTocar={onVerProducto} />;
      case "armado":
        return (
          <TarjetaArmado
            key={i}
            armado={item.armado}
            vigente={turno.id === turnoDelArmado}
            textoConfirmar={textoConfirmar}
            endpoint={endpoint}
            conversacionId={conversacionId}
            bloqueado={respondiendo}
            alConfirmar={onConfirmarArmado}
            alActualizarArmado={actualizarArmado}
          />
        );
      case "pregunta": {
        const sePuedeResponder = turno === ultimo && !respondiendo;
        return (
          <div key={i} className={estilos.pregunta}>
            <p>{item.pregunta}</p>
            <div className={estilos.opciones}>
              {item.opciones.map((opcion) => (
                <button key={opcion} type="button" disabled={!sePuedeResponder} onClick={() => mandar(opcion)}>
                  {opcion}
                </button>
              ))}
            </div>
          </div>
        );
      }
      case "fuentes":
        return <Fuentes key={i} fuentes={item.fuentes} />;
      case "error": {
        const puedeReintentar = turno === ultimo && !respondiendo;
        return (
          <div key={i} className={estilos.bloqueError}>
            <p className={estilos.error} role="alert">{item.mensaje}</p>
            {puedeReintentar && (
              <button type="button" className={estilos.enlace} onClick={() => mandar(turno.usuario)}>
                Reintentar
              </button>
            )}
          </div>
        );
      }
    }
  };

  return (
    <div className={estilos.raiz} onKeyDown={(evento) => evento.key === "Escape" && abierto && cerrar()}>
      {abierto && (
        <section id={idPanel} className={estilos.panel} role="dialog" aria-label={titulo}>
          <header className={estilos.cabecera}>
            <span className={estilos.avatar} aria-hidden="true"><IconoChat /></span>
            <span className={estilos.titulos}>
              <strong>{titulo}</strong>
              <span>{subtitulo}</span>
            </span>
            <button type="button" className={estilos.accion} onClick={nuevaConversacion} disabled={!turnos.length}
              title="Empezar una conversación nueva" aria-label="Empezar una conversación nueva">
              <IconoNueva />
            </button>
            <button type="button" className={estilos.accion} onClick={cerrar} title="Cerrar" aria-label="Cerrar el chat">
              <IconoCerrar />
            </button>
          </header>

          {modoDesarrollo && modelos.length > 0 && (
            <div className={estilos.barraDesarrollo}>
              <label htmlFor={idModelo}>Modelo (desarrollo)</label>
              <select id={idModelo} value={modelo} onChange={(evento) => setModelo(evento.target.value)}
                disabled={respondiendo}>
                {modelos.map((opcion) => (
                  <option key={opcion.valor} value={opcion.valor}>{opcion.etiqueta}</option>
                ))}
              </select>
            </div>
          )}

          <div
            ref={lista}
            className={estilos.mensajes}
            aria-live="polite"
            onScroll={(evento) => {
              const el = evento.currentTarget;
              pegadoAbajo.current = el.scrollHeight - el.scrollTop - el.clientHeight < 96;
            }}
          >
            {turnos.length === 0 && (
              <div className={estilos.bienvenida}>
                <p className={estilos.saludo}>¡Hola! Soy el asistente de Todo Computación.</p>
                <p>
                  Te ayudo a encontrar productos y a armar una PC compatible con tu presupuesto.
                  {recuperando ? " Recuperando tu conversación…" : ""}
                </p>
                <div className={estilos.sugerencias}>
                  {sugerencias.map((sugerencia) => (
                    <button key={sugerencia} type="button" onClick={() => mandar(sugerencia)} disabled={respondiendo}>
                      {sugerencia}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {turnos.map((turno) => (
              <div key={turno.id} className={estilos.turno}>
                <p className={estilos.usuario}>{turno.usuario}</p>
                <div className={estilos.agente}>
                  {turno.items.map((item, i) => dibujar(turno, item, i))}
                  {turno.enCurso && (
                    <p className={estilos.estado}>
                      <span className={estilos.puntos} aria-hidden="true"><i /><i /><i /></span>
                      {mostrarEstados ? (turno.estado ?? "Escribiendo…") : "Escribiendo…"}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>

          <form className={estilos.redactor} onSubmit={alEnviar}>
            <textarea ref={entrada} rows={1} value={borrador} maxLength={2000}
              placeholder="Escribí tu consulta…" aria-label="Mensaje para el asistente"
              onChange={(evento) => {
                setBorrador(evento.target.value);
                evento.target.style.height = "auto";
                evento.target.style.height = `${Math.min(evento.target.scrollHeight, 120)}px`;
              }}
              onKeyDown={alTeclear} />
            {respondiendo ? (
              <button type="button" className={estilos.enviar} onClick={detener} aria-label="Detener la respuesta"
                title="Detener">
                <IconoDetener />
              </button>
            ) : (
              <button type="submit" className={estilos.enviar} disabled={!borrador.trim()} aria-label="Enviar"
                title="Enviar">
                <IconoEnviar />
              </button>
            )}
          </form>
          <p className={estilos.pie}>El asistente puede equivocarse. Precio y stock se confirman al cargar el pedido.</p>
        </section>
      )}

      <button ref={boton} type="button" className={`${estilos.boton} ${abierto ? estilos.botonAbierto : ""}`}
        onClick={() => (abierto ? cerrar() : setAbierto(true))}
        aria-expanded={abierto} aria-controls={abierto ? idPanel : undefined}
        aria-label={abierto ? "Cerrar el asistente" : "Abrir el asistente de compra"}>
        <span className={estilos.botonIcono}>{abierto ? <IconoCerrar /> : <IconoChat />}</span>
        {!abierto && <span className={estilos.botonTexto}>¿Te ayudo?</span>}
        {!abierto && <span className={estilos.punto} aria-hidden="true" />}
      </button>
    </div>
  );
}
