/** Puente para reemplazar una pieza en el armado actual de la conversación. */
export const dynamic = "force-dynamic";

const AGENTE_URL = process.env.AGENTE_URL ?? "http://localhost:8000";

export async function POST(pedido: Request, contexto: { params: Promise<{ id: string }> }): Promise<Response> {
  const { id } = await contexto.params;
  if (!/^[A-Za-z0-9_-]{1,64}$/.test(id)) {
    return Response.json({ detail: "Identificador inválido." }, { status: 400 });
  }
  let cuerpo: unknown;
  try {
    cuerpo = await pedido.json();
  } catch {
    return Response.json({ detail: "Pedido inválido." }, { status: 400 });
  }
  try {
    const respuesta = await fetch(`${AGENTE_URL}/conversaciones/${id}/armado/cambiar`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(process.env.AGENTE_CLAVE ? { "X-Agente-Clave": process.env.AGENTE_CLAVE } : {}),
      },
      body: JSON.stringify(cuerpo),
    });
    return Response.json(await respuesta.json(), { status: respuesta.status });
  } catch {
    return Response.json({ detail: "El asistente no está disponible." }, { status: 503 });
  }
}
