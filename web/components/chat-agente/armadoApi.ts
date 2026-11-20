/**
 * Llamadas HTTP para Cambiar y Confirmar el armado en el servicio del agente.
 * Viven dentro de `chat-agente` para que el componente siga siendo autocontenido en la tienda.
 */

import type { Armado, Producto } from "./tipos";

export class ErrorConfirmacion extends Error {
  readonly motivos: string[];
  readonly armado?: Armado;

  constructor(mensaje: string, motivos: string[] = [], armado?: Armado) {
    super(mensaje);
    this.motivos = motivos;
    this.armado = armado;
  }
}

function leerDetalle(cuerpo: unknown, respaldo: string): { mensaje: string; motivos: string[]; armado?: Armado } {
  if (cuerpo && typeof cuerpo === "object" && "detail" in cuerpo) {
    const detail = (cuerpo as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail) {
      return { mensaje: detail, motivos: [detail] };
    }
    if (detail && typeof detail === "object") {
      const d = detail as { motivos?: unknown; armado?: Armado };
      const motivos = Array.isArray(d.motivos) ? d.motivos.filter((m): m is string => typeof m === "string") : [];
      return {
        mensaje: motivos[0] ?? respaldo,
        motivos,
        armado: d.armado,
      };
    }
  }
  return { mensaje: respaldo, motivos: [] };
}

export async function pedirAlternativasArmado(
  endpoint: string,
  conversacionId: string,
  lugar: string,
): Promise<Producto[]> {
  const respuesta = await fetch(
    `${endpoint}/conversaciones/${encodeURIComponent(conversacionId)}/armado/alternativas?lugar=${encodeURIComponent(lugar)}`,
    { cache: "no-store" },
  );
  const cuerpo = (await respuesta.json().catch(() => null)) as { alternativas?: Producto[] } | null;
  if (!respuesta.ok || !cuerpo?.alternativas) {
    const { mensaje } = leerDetalle(cuerpo, "No se pudieron buscar alternativas en este momento.");
    throw new Error(mensaje);
  }
  return cuerpo.alternativas;
}

export async function cambiarPiezaArmado(
  endpoint: string,
  conversacionId: string,
  lugar: string,
  codigo: string,
): Promise<Armado> {
  const respuesta = await fetch(
    `${endpoint}/conversaciones/${encodeURIComponent(conversacionId)}/armado/cambiar`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lugar, codigo }),
    },
  );
  const cuerpo = (await respuesta.json().catch(() => null)) as { armado?: Armado } | null;
  if (!respuesta.ok || !cuerpo?.armado) {
    const { mensaje } = leerDetalle(cuerpo, "No se pudo cambiar la pieza.");
    throw new Error(mensaje);
  }
  return cuerpo.armado;
}

function nombreArchivoDe(disposicion: string | null, referencia: string | null): string {
  const match = disposicion?.match(/filename=([^;\s"]+|"[^"]+")/i);
  if (match) return match[1].replace(/^"|"$/g, "");
  return referencia ? `presupuesto-${referencia}.pdf` : "presupuesto.pdf";
}

export async function confirmarArmadoPdf(
  endpoint: string,
  conversacionId: string,
): Promise<{ blob: Blob; nombreArchivo: string; referencia: string | null }> {
  const respuesta = await fetch(
    `${endpoint}/conversaciones/${encodeURIComponent(conversacionId)}/armado/confirmar`,
    { method: "POST" },
  );
  if (!respuesta.ok) {
    const cuerpo = await respuesta.json().catch(() => null);
    const { mensaje, motivos, armado } = leerDetalle(cuerpo, "No se pudo confirmar el pedido.");
    throw new ErrorConfirmacion(mensaje, motivos, armado);
  }
  const referencia = respuesta.headers.get("X-Pedido-Referencia");
  const nombreArchivo = nombreArchivoDe(respuesta.headers.get("Content-Disposition"), referencia);
  return { blob: await respuesta.blob(), nombreArchivo, referencia };
}

export function descargarBlobPdf(blob: Blob, nombreArchivo: string): void {
  const url = URL.createObjectURL(blob);
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = nombreArchivo;
  document.body.appendChild(enlace);
  enlace.click();
  enlace.remove();
  URL.revokeObjectURL(url);
}
