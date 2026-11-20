/**
 * Puente entre el navegador y el servicio del agente.
 *
 * En la tienda real este lugar lo ocupa NestJS: el navegador nunca habla directo con el agente.
 * El puente agrega la clave del servicio, reenvía solo los campos permitidos y devuelve el flujo
 * de eventos tal como llega, sin acumularlo.
 */
export const dynamic = "force-dynamic";

const AGENTE_URL = process.env.AGENTE_URL ?? "http://localhost:8000";
const MODO_DESARROLLO =
  process.env.NEXT_PUBLIC_MODO_DESARROLLO === "1" || process.env.NEXT_PUBLIC_MODO_DESARROLLO === "true";

export async function POST(pedido: Request): Promise<Response> {
  let cuerpo: { mensaje?: unknown; conversacion_id?: unknown; modelo?: unknown };
  try {
    cuerpo = await pedido.json();
  } catch {
    return Response.json({ detail: "El cuerpo tiene que ser JSON." }, { status: 400 });
  }

  const carga: { mensaje: unknown; conversacion_id: unknown; modelo?: unknown } = {
    mensaje: cuerpo.mensaje,
    conversacion_id: cuerpo.conversacion_id ?? null,
  };
  if (MODO_DESARROLLO && typeof cuerpo.modelo === "string" && cuerpo.modelo) {
    carga.modelo = cuerpo.modelo;
  }

  let respuesta: Response;
  try {
    respuesta = await fetch(`${AGENTE_URL}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(process.env.AGENTE_CLAVE ? { "X-Agente-Clave": process.env.AGENTE_CLAVE } : {}),
      },
      // En producción solo mensaje y conversacion_id: nunca `depurar`, y `modelo` solo en modo desarrollo.
      body: JSON.stringify(carga),
      cache: "no-store",
      signal: pedido.signal,
    });
  } catch {
    return Response.json({ detail: "El asistente no está disponible." }, { status: 503 });
  }

  if (!respuesta.ok || !respuesta.body) {
    const estado = respuesta.status === 400 || respuesta.status === 409 || respuesta.status === 422 ? respuesta.status : 502;
    let detail = "El asistente no pudo procesar el mensaje.";
    if (estado === 400) {
      try {
        const datos = (await respuesta.json()) as { detail?: unknown };
        if (typeof datos.detail === "string" && datos.detail) detail = datos.detail;
      } catch {
        // respuesta no JSON
      }
    }
    return Response.json({ detail }, { status: estado });
  }

  return new Response(respuesta.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      "X-Accel-Buffering": "no",
    },
  });
}
