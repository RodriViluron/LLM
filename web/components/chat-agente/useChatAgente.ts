"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type { Armado, ConversacionGuardada, EventoAgente, Item, Turno } from "./tipos";

const CLAVE_CONVERSACION = "chat-agente:conversacion";

/**
 * Suma un evento a lo que ya se dibujó de una respuesta.
 * Acá está la regla de qué se muestra: lo que no tiene un caso se ignora (razonamiento,
 * tipos nuevos que el servicio agregue más adelante, cualquier evento marcado como interno).
 */
export function aplicarEvento(items: Item[], evento: EventoAgente): Item[] {
  if ("visibilidad" in evento && evento.visibilidad === "interno") return items;
  switch (evento.tipo) {
    case "texto":
      return [...items, { tipo: "texto", texto: evento.texto }];
    case "productos":
      return [...items, { tipo: "productos", productos: evento.productos }];
    case "armado": {
      // En un mismo turno el armado cambia varias veces (una por pieza): se muestra solo el último.
      const sinArmado = items.filter((item) => item.tipo !== "armado");
      return evento.armado ? [...sinArmado, { tipo: "armado", armado: evento.armado }] : sinArmado;
    }
    case "pregunta":
      return [...items, { tipo: "pregunta", pregunta: evento.pregunta, opciones: evento.opciones }];
    case "fuentes":
      return evento.fuentes.length ? [...items, { tipo: "fuentes", fuentes: evento.fuentes }] : items;
    case "error":
      return [...items, { tipo: "error", mensaje: evento.mensaje }];
    default:
      return items;
  }
}

/** Lee un flujo text/event-stream y entrega cada evento ya interpretado. */
async function* leerEventos(cuerpo: ReadableStream<Uint8Array>): AsyncGenerator<EventoAgente> {
  const lector = cuerpo.getReader();
  const decodificador = new TextDecoder();
  let pendiente = "";
  for (;;) {
    const { done, value } = await lector.read();
    if (done) break;
    pendiente += decodificador.decode(value, { stream: true });
    let corte = pendiente.indexOf("\n\n");
    while (corte >= 0) {
      const bloque = pendiente.slice(0, corte);
      pendiente = pendiente.slice(corte + 2);
      const datos = bloque
        .split("\n")
        .filter((linea) => linea.startsWith("data:"))
        .map((linea) => linea.slice(5).trim())
        .join("\n");
      if (datos) {
        try {
          yield JSON.parse(datos) as EventoAgente;
        } catch {
          // Un bloque que no se entiende no corta la conversación.
        }
      }
      corte = pendiente.indexOf("\n\n");
    }
  }
}

function nuevoId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function leerConversacionGuardada(): string | null {
  try {
    return window.localStorage.getItem(CLAVE_CONVERSACION);
  } catch {
    return null; // navegación privada o almacenamiento bloqueado
  }
}

function guardarConversacion(id: string | null): void {
  try {
    if (id) window.localStorage.setItem(CLAVE_CONVERSACION, id);
    else window.localStorage.removeItem(CLAVE_CONVERSACION);
  } catch {
    // sin almacenamiento, la conversación dura lo que dure la página
  }
}

const ERROR_DE_RED = "No pude conectarme con el asistente. Revisá tu conexión y probá de nuevo.";

export function useChatAgente(endpoint: string) {
  const [turnos, setTurnos] = useState<Turno[]>([]);
  const [armadoGuardado, setArmadoGuardado] = useState<Armado | null>(null);
  const [respondiendo, setRespondiendo] = useState(false);
  const [recuperando, setRecuperando] = useState(false);
  const conversacion = useRef<string | null>(null);
  const corte = useRef<AbortController | null>(null);
  const recuperada = useRef(false);

  const actualizarUltimo = useCallback((cambio: (turno: Turno) => Turno) => {
    setTurnos((actuales) => {
      if (!actuales.length) return actuales;
      const copia = actuales.slice();
      copia[copia.length - 1] = cambio(copia[copia.length - 1]);
      return copia;
    });
  }, []);

  /** Al abrir el chat por primera vez, trae lo que ya se había conversado. */
  const recuperar = useCallback(async () => {
    if (recuperada.current) return;
    recuperada.current = true;
    const id = leerConversacionGuardada();
    if (!id) return;
    conversacion.current = id;
    setRecuperando(true);
    try {
      const respuesta = await fetch(`${endpoint}/conversaciones/${encodeURIComponent(id)}`, { cache: "no-store" });
      if (!respuesta.ok) return;
      const guardada = (await respuesta.json()) as ConversacionGuardada;
      setArmadoGuardado((previo) => previo ?? guardada.armado ?? null);
      setTurnos((actuales) =>
        actuales.length
          ? actuales
          : guardada.turnos.map((turno) => ({
              id: nuevoId(),
              usuario: turno.usuario,
              items: turno.eventos.reduce(aplicarEvento, [] as Item[]),
              estado: null,
              enCurso: false,
            })),
      );
    } catch {
      // Si no se puede recuperar, se empieza con el chat vacío.
    } finally {
      setRecuperando(false);
    }
  }, [endpoint]);

  const enviar = useCallback(
    async (mensaje: string, modelo?: string) => {
      const texto = mensaje.trim();
      if (!texto || respondiendo) return;
      setRespondiendo(true);
      setTurnos((actuales) => [...actuales, { id: nuevoId(), usuario: texto, items: [], estado: "Pensando…", enCurso: true }]);
      const control = new AbortController();
      corte.current = control;
      try {
        const cuerpo: { mensaje: string; conversacion_id: string | null; modelo?: string } = {
          mensaje: texto,
          conversacion_id: conversacion.current,
        };
        if (modelo) cuerpo.modelo = modelo;
        const respuesta = await fetch(`${endpoint}/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(cuerpo),
          signal: control.signal,
        });
        if (!respuesta.ok || !respuesta.body) {
          let detalle: string | null = null;
          if (respuesta.status === 400) {
            try {
              const cuerpoError = (await respuesta.json()) as { detail?: unknown };
              if (typeof cuerpoError.detail === "string" && cuerpoError.detail) detalle = cuerpoError.detail;
            } catch {
              // respuesta no JSON
            }
          }
          const aviso =
            detalle ??
            (respuesta.status === 409
              ? "Todavía estoy respondiendo el mensaje anterior. Esperá un momento."
              : "El asistente no está disponible en este momento. Probá de nuevo en un rato.");
          actualizarUltimo((turno) => ({ ...turno, items: [...turno.items, { tipo: "error", mensaje: aviso }] }));
          return;
        }
        for await (const evento of leerEventos(respuesta.body)) {
          if (evento.tipo === "inicio") {
            conversacion.current = evento.conversacion_id;
            guardarConversacion(evento.conversacion_id);
          } else if (evento.tipo === "estado") {
            actualizarUltimo((turno) => ({ ...turno, estado: evento.texto }));
          } else if (evento.tipo !== "fin") {
            if (evento.tipo === "armado") setArmadoGuardado(null);
            // Después de cada resultado el agente vuelve a pensar: el estado vuelve a «Pensando…» hasta el próximo paso.
            actualizarUltimo((turno) => ({ ...turno, estado: "Pensando…", items: aplicarEvento(turno.items, evento) }));
          }
        }
      } catch (error) {
        const cancelado = error instanceof DOMException && error.name === "AbortError";
        if (cancelado) {
          actualizarUltimo((turno) =>
            turno.items.length ? turno : { ...turno, items: [{ tipo: "texto", texto: "Respuesta detenida." }] },
          );
        } else {
          actualizarUltimo((turno) => ({ ...turno, items: [...turno.items, { tipo: "error", mensaje: ERROR_DE_RED }] }));
        }
      } finally {
        actualizarUltimo((turno) => ({ ...turno, estado: null, enCurso: false }));
        corte.current = null;
        setRespondiendo(false);
      }
    },
    [actualizarUltimo, endpoint, respondiendo],
  );

  const detener = useCallback(() => corte.current?.abort(), []);

  const nuevaConversacion = useCallback(() => {
    corte.current?.abort();
    conversacion.current = null;
    guardarConversacion(null);
    setArmadoGuardado(null);
    setTurnos([]);
  }, []);

  useEffect(() => () => corte.current?.abort(), []);

  return { turnos, armadoGuardado, respondiendo, recuperando, enviar, detener, recuperar, nuevaConversacion };
}
