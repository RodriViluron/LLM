"use client";

/**
 * «Armá tu PC» de la página de prueba: muestra, paso a paso, solo las piezas que eligió el asistente
 * (o que el cliente tocó en el chat). No lista el catálogo: es para ver al asistente trabajar.
 * No es parte del chat que va a la tienda; la tienda ya tiene su propio «Armá tu PC».
 */

import type { Armado, ItemPedido, Producto } from "@/components/chat-agente";

import { ImagenComponente } from "./ImagenComponente";
import estilos from "./VistaArmado.module.css";

export type Pieza = { producto: Producto; cantidad: number; origen: "asistente" | "cliente" };

/** Los pasos, en el orden de la tienda. `lugar` es el mismo nombre que usa el agente. */
export const PASOS: { lugar: string; nombre: string }[] = [
  { lugar: "cpu", nombre: "Procesador" },
  { lugar: "cooler", nombre: "Cooler" },
  { lugar: "motherboard", nombre: "Motherboard" },
  { lugar: "ram", nombre: "Memoria" },
  { lugar: "almacenamiento", nombre: "M.2" },
  { lugar: "almacenamiento_extra", nombre: "SATA" },
  { lugar: "gpu", nombre: "Placa de video" },
  { lugar: "gabinete", nombre: "Gabinete" },
  { lugar: "fuente", nombre: "Fuente" },
];

const COMPATIBILIDAD: Record<Armado["compatibilidad"]["estado"], { texto: string; tono: string }> = {
  compatible: { texto: "Compatible", tono: estilos.bien },
  incompatible: { texto: "Incompatible", tono: estilos.mal },
  sin_confirmar: { texto: "Compatibilidad sin confirmar", tono: estilos.duda },
  sin_verificar: { texto: "Sin verificar", tono: estilos.duda },
};

const pesos = new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 });
const precio = (valor: number | null) => (valor == null ? "Consultar" : pesos.format(valor));

export function VistaArmado({ piezas, armado, alQuitar, alConfirmar }: {
  piezas: Record<string, Pieza>;
  /** El último armado del asistente, para la compatibilidad y el presupuesto (los calcula el servicio). */
  armado: Armado | null;
  alQuitar: (lugar: string) => void;
  alConfirmar?: (pedido: ItemPedido[], armado: Armado) => void;
}) {
  const elegidos = PASOS.filter((paso) => piezas[paso.lugar]);
  const actual = PASOS.findIndex((paso) => !piezas[paso.lugar]);
  // El total de la vista es la suma de lo que se ve (precio por cantidad). El del asistente viene en `armado`.
  const total = elegidos.reduce((suma, { lugar }) => suma + (piezas[lugar].producto.precio ?? 0) * piezas[lugar].cantidad, 0);
  // La compatibilidad la verificó el servicio sobre el armado del asistente. Si el cliente sumó piezas
  // desde el chat, esas no pasaron por la verificación: no se dice «Compatible».
  const conPiezasDelCliente = elegidos.some(({ lugar }) => piezas[lugar].origen === "cliente");
  const compatibilidad = conPiezasDelCliente
    ? { texto: "Sin verificar: incluye piezas que elegiste en el chat", tono: estilos.duda }
    : armado ? COMPATIBILIDAD[armado.compatibilidad.estado] ?? COMPATIBILIDAD.sin_verificar : null;
  const revisionHecha = Boolean(armado?.se_puede_confirmar) && !conPiezasDelCliente;
  const excedido = armado?.presupuesto != null && total > armado.presupuesto;

  return (
    <section className={estilos.vista} aria-labelledby="titulo-armado">
      <span className={estilos.ceja}>Configuración de componentes · lo que eligió el asistente</span>
      <h2 id="titulo-armado" className={estilos.titulo}>Armá tu PC</h2>

      <ol className={estilos.pasos}>
        {[...PASOS, { lugar: "revision", nombre: "Revisión" }].map((paso, i) => {
          const hecho = paso.lugar === "revision" ? revisionHecha : Boolean(piezas[paso.lugar]);
          const enCurso = !hecho && i === (actual === -1 ? PASOS.length : actual);
          return (
            <li key={paso.lugar} className={`${estilos.paso} ${hecho ? estilos.hecho : ""} ${enCurso ? estilos.enCurso : ""}`}>
              <span className={estilos.numero}>{hecho ? "✓" : i + 1}</span>
              <span className={estilos.nombrePaso}>{paso.nombre}</span>
            </li>
          );
        })}
      </ol>

      <div className={estilos.cuerpo}>
        <div className={estilos.piezas}>
          {elegidos.length === 0 ? (
            <div className={estilos.vacio}>
              <ImagenComponente lugar="gabinete" titulo="PC sin piezas" />
              <p>Pedile al asistente que te arme una PC. Las piezas van a aparecer acá, paso a paso, a medida que las elige.</p>
            </div>
          ) : (
            elegidos.map(({ lugar, nombre }) => {
              const { producto, cantidad, origen } = piezas[lugar];
              return (
                <article key={lugar} className={estilos.tarjeta}>
                  <div className={estilos.imagen}>
                    <ImagenComponente lugar={lugar} titulo={nombre} />
                  </div>
                  <div className={estilos.datos}>
                    <div className={estilos.fila}>
                      <span className={estilos.codigo}>{producto.codigo}</span>
                      <span className={estilos.marca}>{producto.marca ?? nombre}</span>
                    </div>
                    <span className={estilos.lugar}>{nombre}</span>
                    <strong className={estilos.nombre}>{producto.nombre}</strong>
                    <span className={`${estilos.origen} ${origen === "cliente" ? estilos.cliente : ""}`}>
                      {origen === "asistente" ? "Lo eligió el asistente" : "Lo elegiste en el chat"}
                    </span>
                  </div>
                  <div className={estilos.pie}>
                    <span className={estilos.stock}>
                      <i className={producto.stock ? estilos.conStock : estilos.sinStock} />
                      {producto.stock ?? "—"}{cantidad > 1 ? ` · ${cantidad} unidades` : ""}
                    </span>
                    <span className={estilos.precio}>
                      <small>Precio</small>
                      {precio(producto.precio)}
                    </span>
                    <button type="button" className={estilos.quitar} onClick={() => alQuitar(lugar)}
                      aria-label={`Quitar ${nombre}`}>
                      Quitar
                    </button>
                  </div>
                </article>
              );
            })
          )}
        </div>

        <aside className={estilos.resumen}>
          <span className={estilos.ceja}>Tu configuración</span>
          <div className={estilos.avance}>
            <span>{elegidos.length} de {PASOS.length} pasos</span>
            <span>{PASOS.length - elegidos.length} pendientes</span>
          </div>
          <div className={estilos.barra}><i style={{ width: `${(elegidos.length / PASOS.length) * 100}%` }} /></div>
          {elegidos.length === 0 ? (
            <p className={estilos.nada}>Todavía no hay componentes.</p>
          ) : (
            <ul className={estilos.lista}>
              {elegidos.map(({ lugar, nombre }) => {
                const { producto, cantidad } = piezas[lugar];
                return (
                  <li key={lugar}>
                    <span>{nombre}{cantidad > 1 ? ` ×${cantidad}` : ""}</span>
                    <span>{precio(producto.precio != null ? producto.precio * cantidad : null)}</span>
                  </li>
                );
              })}
            </ul>
          )}
          {compatibilidad && (
            <p className={`${estilos.estado} ${compatibilidad.tono}`}>{compatibilidad.texto}</p>
          )}
          {armado && !conPiezasDelCliente && (
            <>
              {armado.compatibilidad.reglas.filter((regla) => regla.estado !== "cumple").length > 0 && (
                <ul className={estilos.reglas}>
                  {armado.compatibilidad.reglas
                    .filter((regla) => regla.estado !== "cumple")
                    .map((regla) => (
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
            </>
          )}
          <div className={estilos.total}>
            <span>Total</span>
            <strong className={excedido ? estilos.mal : undefined}>{pesos.format(total)}</strong>
          </div>
          {armado?.presupuesto != null && (
            <p className={estilos.nota}>
              Presupuesto: {precio(armado.presupuesto)}{excedido ? " — el armado lo supera" : ""}
            </p>
          )}
          {armado && !conPiezasDelCliente && alConfirmar && (
            <>
              <button type="button" className={estilos.confirmar} disabled={!armado.se_puede_confirmar}
                onClick={() => alConfirmar(armado.pedido, armado)}>
                Cargar armado
              </button>
              {!armado.se_puede_confirmar && armado.motivos_para_no_confirmar.length > 0 && (
                <p className={estilos.nota}>Falta para confirmar: {armado.motivos_para_no_confirmar.join(" · ")}</p>
              )}
            </>
          )}
        </aside>
      </div>
    </section>
  );
}
