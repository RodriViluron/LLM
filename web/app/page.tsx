"use client";

/**
 * Página de prueba: una maqueta mínima de la tienda para ver el chat en su lugar.
 * Lo único que va a la tienda real es <ChatAgente /> (carpeta components/chat-agente).
 * La vista «Armá tu PC» (components/vista-armado) es solo para mostrar al asistente trabajando.
 */

import { useCallback, useRef, useState } from "react";

import { ChatAgente, type Armado, type ItemPedido, type Producto } from "@/components/chat-agente";
import { PASOS, type Pieza, VistaArmado } from "@/components/vista-armado/VistaArmado";

const LUGARES = new Set(PASOS.map((paso) => paso.lugar));

/**
 * En qué paso va un producto que tocó el cliente. Los discos se ubican por su tipo: NVMe o M.2 van
 * al paso «M.2»; SSD SATA o HDD, al «SATA» (segundo disco). Sin dato, al M.2 si está libre.
 * Lo que no es una pieza de PC (una UPS, un cable) no entra en el armado.
 */
function lugarDelProducto(producto: Producto, piezas: Record<string, Pieza>): string | null {
  const categoria = producto.categoria ?? "";
  if (categoria !== "almacenamiento") return LUGARES.has(categoria) ? categoria : null;
  const tipo = String(producto.atributos.tipo ?? "").toUpperCase();
  const conexion = String(producto.atributos.conexion ?? "").toUpperCase();
  if (tipo === "NVME" || tipo.startsWith("M.2") || conexion === "M.2") return "almacenamiento";
  if (tipo === "SSD SATA" || tipo === "HDD" || conexion === "SATA") return "almacenamiento_extra";
  const principal = piezas.almacenamiento;
  return !principal || principal.producto.codigo === producto.codigo ? "almacenamiento" : "almacenamiento_extra";
}

export default function Pagina() {
  const [recibido, setRecibido] = useState<unknown>(null);
  const [piezas, setPiezas] = useState<Record<string, Pieza>>({});
  const [armado, setArmado] = useState<Armado | null>(null);
  const armadoAnterior = useRef<Armado | null>(null);

  const alternarTema = () => document.documentElement.classList.toggle("dark");

  // En la tienda real, acá se carga el armado en «Armá tu PC» o en el carrito, con la sesión del usuario.
  const alConfirmarArmado = (pedido: ItemPedido[], armadoConfirmado: Armado) =>
    setRecibido({ accion: "cargar armado", pedido, total: armadoConfirmado.total });

  // En la tienda real, acá se navega a la página del producto. En la prueba, además, la pieza
  // ocupa su paso en «Armá tu PC» (si es una pieza de PC).
  const alVerProducto = (producto: Producto) => {
    setRecibido({ accion: "ver producto", codigo: producto.codigo });
    setPiezas((actuales) => {
      const lugar = lugarDelProducto(producto, actuales);
      return lugar ? { ...actuales, [lugar]: { producto, cantidad: 1, origen: "cliente" } } : actuales;
    });
  };

  // El armado del asistente cambió: entra lo que él puso o cambió. Lo que el cliente eligió en otros
  // pasos se mantiene; si el asistente cambia una pieza, gana el cambio (lo último que pasó).
  const alCambiarArmado = useCallback((nuevo: Armado | null) => {
    const previo = armadoAnterior.current;
    armadoAnterior.current = nuevo;
    setArmado(nuevo);
    if (!nuevo) {
      setPiezas({}); // conversación nueva
      return;
    }
    setPiezas((actuales) => {
      const siguiente = { ...actuales };
      for (const { lugar, cantidad, producto } of nuevo.componentes) {
        const antes = previo?.componentes.find((c) => c.lugar === lugar);
        if (!antes || antes.producto.codigo !== producto.codigo || antes.cantidad !== cantidad) {
          siguiente[lugar] = { producto, cantidad, origen: "asistente" };
        }
      }
      for (const lugar of Object.keys(siguiente)) {
        const quitada = !nuevo.componentes.some((c) => c.lugar === lugar);
        if (quitada && siguiente[lugar].origen === "asistente") delete siguiente[lugar];
      }
      return siguiente;
    });
  }, []);

  const quitar = (lugar: string) =>
    setPiezas((actuales) => {
      const { [lugar]: _quitada, ...resto } = actuales;
      return resto;
    });

  return (
    <>
      <header className="barra">
        <a href="#" className="marca">
          <span>todo</span>
          <br />
          <span>computación</span>
        </a>
        <nav>
          <a href="#">Catálogo</a>
          <a href="#armado">Armá tu PC</a>
          <a href="#">Marcas</a>
        </nav>
        <span className="espacio" />
        <button type="button" className="boton-tema" onClick={alternarTema}>
          Cambiar tema
        </button>
      </header>

      <main className="contenido">
        <span className="etiqueta">Página de prueba</span>
        <h1>Asistente de compra</h1>
        <p>
          Esta página es una maqueta para probar el chat. Abrilo con el botón de abajo a la derecha y pedile, por
          ejemplo, que te arme una PC: las piezas que elige aparecen abajo, paso a paso. Lo que la página recibe cuando
          tocás un producto o cargás un armado aparece al final.
        </p>

        <div id="armado">
          <VistaArmado piezas={piezas} armado={armado} alQuitar={quitar} />
        </div>

        <section className="recibido">
          <h2>Lo que recibe la página</h2>
          <p>El asistente no confirma nada: entrega los códigos y la página decide qué hacer con ellos.</p>
          <pre>{recibido ? JSON.stringify(recibido, null, 2) : "Todavía nada."}</pre>
        </section>
      </main>

      <ChatAgente endpoint="/api/agente" onConfirmarArmado={alConfirmarArmado} onVerProducto={alVerProducto}
        onArmado={alCambiarArmado} />
    </>
  );
}
