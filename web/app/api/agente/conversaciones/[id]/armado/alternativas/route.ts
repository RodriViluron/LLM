/** Puente para pedir alternativas compatibles de una pieza del armado. */
export const dynamic = "force-dynamic";

const AGENTE_URL = process.env.AGENTE_URL ?? "http://localhost:8000";

export async function GET(pedido: Request, contexto: { params: Promise<{ id: string }> }): Promise<Response> {
  const { id } = await contexto.params;
  if (!/^[A-Za-z0-9_-]{1,64}$/.test(id)) {
    return Response.json({ detail: "Identificador inválido." }, { status: 400 });
  }
  const lugar = new URL(pedido.url).searchParams.get("lugar") ?? "";
  try {
    const respuesta = await fetch(
      `${AGENTE_URL}/conversaciones/${id}/armado/alternativas?lugar=${encodeURIComponent(lugar)}`,
      {
        headers: process.env.AGENTE_CLAVE ? { "X-Agente-Clave": process.env.AGENTE_CLAVE } : {},
        cache: "no-store",
      },
    );
    return Response.json(await respuesta.json(), { status: respuesta.status });
  } catch {
    return Response.json({ detail: "El asistente no está disponible." }, { status: 503 });
  }
}
