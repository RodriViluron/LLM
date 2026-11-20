/** Puente para recuperar el historial visible y el armado de una conversación (ver ../../chat/route.ts). */
export const dynamic = "force-dynamic";

const AGENTE_URL = process.env.AGENTE_URL ?? "http://localhost:8000";

export async function GET(_pedido: Request, contexto: { params: Promise<{ id: string }> }): Promise<Response> {
  const { id } = await contexto.params;
  if (!/^[A-Za-z0-9_-]{1,64}$/.test(id)) {
    return Response.json({ detail: "Identificador inválido." }, { status: 400 });
  }
  try {
    const respuesta = await fetch(`${AGENTE_URL}/conversaciones/${id}`, {
      headers: process.env.AGENTE_CLAVE ? { "X-Agente-Clave": process.env.AGENTE_CLAVE } : {},
      cache: "no-store",
    });
    if (!respuesta.ok) {
      return Response.json({ detail: "No se pudo recuperar la conversación." }, { status: 502 });
    }
    return Response.json(await respuesta.json());
  } catch {
    return Response.json({ detail: "El asistente no está disponible." }, { status: 503 });
  }
}
