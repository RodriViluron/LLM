/**
 * Contrato entre el servicio del agente y la interfaz (ver docs/GUIA_INTEGRACION.md).
 * Estos tipos describen los eventos que llegan por el flujo de POST /chat.
 */

export type Producto = {
  codigo: string;
  nombre: string;
  categoria: string | null;
  marca: string | null;
  precio: number | null;
  stock: number | null;
  imagen: string | null;
  url: string | null;
  atributos: Record<string, string | number | string[]>;
};

export type ItemPedido = { lugar: string; codigo: string; cantidad: number };

export type ReglaCompatibilidad = {
  regla: string;
  estado: "cumple" | "no_cumple" | "sin_datos";
  detalle: string;
  critica?: boolean;
};

export type Armado = {
  version: number | null;
  presupuesto: number | null;
  perfil_uso: string | null;
  componentes: { lugar: string; cantidad: number; producto: Producto }[];
  total: number;
  dentro_del_presupuesto: boolean | null;
  compatibilidad: {
    estado: "compatible" | "incompatible" | "sin_confirmar" | "sin_verificar";
    reglas: ReglaCompatibilidad[];
  };
  /** Lo que la página carga en el carrito o en «Armá tu PC» cuando el usuario confirma. */
  pedido: ItemPedido[];
  se_puede_confirmar: boolean;
  motivos_para_no_confirmar: string[];
};

export type Fuente = { titulo: string; url: string | null };

export type OpcionModelo = { valor: string; etiqueta: string };

/** Eventos del flujo. `visibilidad` dice qué hacer con cada uno: mostrar, opcional o interno. */
export type EventoAgente =
  | { tipo: "inicio"; conversacion_id: string }
  | { tipo: "estado"; visibilidad: "opcional"; paso: string; texto: string }
  | { tipo: "texto"; visibilidad: "mostrar"; texto: string }
  | { tipo: "productos"; visibilidad: "mostrar"; productos: Producto[] }
  | { tipo: "armado"; visibilidad: "mostrar"; armado: Armado | null }
  | { tipo: "pregunta"; visibilidad: "mostrar"; pregunta: string; opciones: string[] }
  | { tipo: "fuentes"; visibilidad: "mostrar"; fuentes: Fuente[] }
  | { tipo: "error"; visibilidad: "mostrar"; mensaje: string }
  | { tipo: "razonamiento"; visibilidad: "interno"; texto: string }
  | { tipo: "fin" };

/** Lo que se dibuja dentro de una respuesta del agente. */
export type Item =
  | { tipo: "texto"; texto: string }
  | { tipo: "productos"; productos: Producto[] }
  | { tipo: "armado"; armado: Armado }
  | { tipo: "pregunta"; pregunta: string; opciones: string[] }
  | { tipo: "fuentes"; fuentes: Fuente[] }
  | { tipo: "error"; mensaje: string };

export type Turno = {
  id: string;
  usuario: string;
  items: Item[];
  /** Aviso de lo que el agente está haciendo ahora. Solo existe mientras responde. */
  estado: string | null;
  enCurso: boolean;
};

export type ConversacionGuardada = {
  conversacion_id: string;
  turnos: { usuario: string; eventos: EventoAgente[] }[];
  armado: Armado | null;
};
