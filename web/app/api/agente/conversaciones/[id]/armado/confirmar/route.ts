/** Puente para confirmar el armado y reenviar el presupuesto en PDF (o 409 con motivos). */
export const dynamic = "force-dynamic";

const AGENTE_URL = process.env.AGENTE_URL ?? "http://localhost:8000";

export async function POST(_pedido: Request, contexto: { params: Promise<{ id: string }> }): Promise<Response> {
  const { id } = await contexto.params;
  if (!/^[A-Za-z0-9_-]{1,64}$/.test(id)) {
    return Response.json({ detail: "Identificador inválido." }, { status: 400 });
  }
  try {
    const respuesta = await fetch(`${AGENTE_URL}/conversaciones/${id}/armado/confirmar`, {
      method: "POST",
      headers: process.env.AGENTE_CLAVE ? { "X-Agente-Clave": process.env.AGENTE_CLAVE } : {},
    });
    if (!respuesta.ok) {
      return Response.json(await respuesta.json(), { status: respuesta.status });
    }
    const cabeceras = new Headers({
      "Content-Type": respuesta.headers.get("Content-Type") ?? "application/pdf",
    });
    const disposicion = respuesta.headers.get("Content-Disposition");
    if (disposicion) cabeceras.set("Content-Disposition", disposicion);
    const referencia = respuesta.headers.get("X-Pedido-Referencia");
    if (referencia) cabeceras.set("X-Pedido-Referencia", referencia);
    return new Response(await respuesta.arrayBuffer(), { status: 200, headers: cabeceras });
  } catch {
    return Response.json({ detail: "El asistente no está disponible." }, { status: 503 });
  }
}
