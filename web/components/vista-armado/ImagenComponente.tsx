/**
 * Dibujos de cada tipo de componente, para las tarjetas del armado.
 * La API de la tienda no trae imágenes: en vez de mostrar solo «CPU», se muestra un dibujo
 * representativo. Usan los colores del tema (currentColor y las variables de la página).
 */

import type { ReactElement } from "react";

const TRAZO = { fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinejoin: "round" as const };
const CUERPO = { fill: "var(--va-cuerpo)", stroke: "currentColor", strokeWidth: 2, strokeLinejoin: "round" as const };
const ACENTO = { fill: "var(--va-acento)" };
const ACENTO_SUAVE = { fill: "var(--va-acento-suave)" };

function Procesador() {
  const pines = [24, 36, 48, 60, 72, 84, 96];
  return (
    <>
      {pines.map((x) => (
        <g key={x}>
          <line x1={x} y1={10} x2={x} y2={18} {...TRAZO} />
          <line x1={x} y1={72} x2={x} y2={80} {...TRAZO} />
        </g>
      ))}
      {[27, 39, 51, 63].map((y) => (
        <g key={y}>
          <line x1={22} y1={y} x2={30} y2={y} {...TRAZO} />
          <line x1={90} y1={y} x2={98} y2={y} {...TRAZO} />
        </g>
      ))}
      <rect x={30} y={18} width={60} height={54} rx={6} {...CUERPO} />
      <rect x={44} y={30} width={32} height={30} rx={3} {...ACENTO} />
      <circle cx={37} cy={25} r={2} fill="currentColor" />
    </>
  );
}

function Cooler() {
  const aspas = [0, 72, 144, 216, 288];
  return (
    <>
      <rect x={24} y={8} width={72} height={74} rx={10} {...CUERPO} />
      <circle cx={60} cy={45} r={30} {...TRAZO} />
      {aspas.map((angulo) => (
        <path key={angulo} d="M60 45 C 64 30, 78 26, 84 34 C 76 36, 68 40, 60 45 Z"
          transform={`rotate(${angulo} 60 45)`} {...ACENTO_SUAVE} stroke="currentColor" strokeWidth={1.5} />
      ))}
      <circle cx={60} cy={45} r={7} {...ACENTO} />
      {[[30, 14], [90, 14], [30, 76], [90, 76]].map(([x, y]) => (
        <circle key={`${x}-${y}`} cx={x} cy={y} r={2} fill="currentColor" />
      ))}
    </>
  );
}

function PlacaMadre() {
  return (
    <>
      <rect x={14} y={8} width={92} height={74} rx={5} {...CUERPO} />
      <rect x={26} y={18} width={26} height={24} rx={3} {...ACENTO} />
      {[60, 66, 72, 78].map((x) => (
        <rect key={x} x={x} y={16} width={3.5} height={30} rx={1} {...ACENTO_SUAVE} stroke="currentColor" strokeWidth={1} />
      ))}
      <rect x={24} y={52} width={56} height={5} rx={1.5} {...TRAZO} />
      <rect x={24} y={64} width={56} height={5} rx={1.5} {...TRAZO} />
      <rect x={88} y={52} width={10} height={20} rx={2} {...TRAZO} />
      <circle cx={20} cy={14} r={1.8} fill="currentColor" />
      <circle cx={100} cy={76} r={1.8} fill="currentColor" />
    </>
  );
}

function Memoria() {
  return (
    <>
      <path d="M8 26 H112 V60 H66 V64 H58 V60 H8 Z" {...CUERPO} />
      {[16, 32, 48, 72, 88].map((x) => (
        <rect key={x} x={x} y={32} width={12} height={16} rx={1.5} {...ACENTO} />
      ))}
      {Array.from({ length: 22 }, (_, i) => 12 + i * 4.6).filter((x) => x < 56 || x > 68).map((x) => (
        <rect key={x} x={x} y={62} width={2.4} height={6} fill="var(--va-oro)" />
      ))}
      <circle cx={12} cy={30} r={1.6} fill="currentColor" />
    </>
  );
}

function DiscoM2() {
  return (
    <>
      <rect x={8} y={34} width={104} height={22} rx={3} {...CUERPO} />
      <path d="M106 39 a6 6 0 0 1 0 12" {...TRAZO} />
      <rect x={30} y={38} width={26} height={14} rx={1.5} {...ACENTO} />
      <rect x={62} y={38} width={26} height={14} rx={1.5} {...ACENTO} />
      <rect x={16} y={40} width={8} height={10} rx={1} {...ACENTO_SUAVE} />
      {Array.from({ length: 5 }, (_, i) => 36 + i * 3).map((y) => (
        <rect key={y} x={4} y={y} width={4} height={1.8} fill="var(--va-oro)" />
      ))}
    </>
  );
}

function SegundoDisco() {
  return (
    <>
      <rect x={22} y={10} width={76} height={70} rx={6} {...CUERPO} />
      <circle cx={60} cy={42} r={24} {...TRAZO} />
      <circle cx={60} cy={42} r={15} {...ACENTO_SUAVE} />
      <circle cx={60} cy={42} r={4} {...ACENTO} />
      <path d="M82 66 L66 46" {...TRAZO} strokeWidth={3} strokeLinecap="round" />
      {[[28, 16], [92, 16], [28, 74], [92, 74]].map(([x, y]) => (
        <circle key={`${x}-${y}`} cx={x} cy={y} r={1.8} fill="currentColor" />
      ))}
    </>
  );
}

function PlacaDeVideo() {
  return (
    <>
      <rect x={6} y={18} width={100} height={48} rx={6} {...CUERPO} />
      <path d="M106 22 H114 V70 H110" {...TRAZO} />
      {[32, 76].map((cx) => (
        <g key={cx}>
          <circle cx={cx} cy={42} r={17} {...TRAZO} />
          {[0, 90, 180, 270].map((angulo) => (
            <path key={angulo} d={`M${cx} 42 q 6 -10 14 -6`} transform={`rotate(${angulo} ${cx} 42)`}
              stroke="var(--va-acento)" strokeWidth={3} fill="none" strokeLinecap="round" />
          ))}
          <circle cx={cx} cy={42} r={4} {...ACENTO} />
        </g>
      ))}
      {Array.from({ length: 12 }, (_, i) => 24 + i * 5).map((x) => (
        <rect key={x} x={x} y={66} width={3} height={6} fill="var(--va-oro)" />
      ))}
    </>
  );
}

function Gabinete() {
  return (
    <>
      <rect x={30} y={4} width={60} height={82} rx={6} {...CUERPO} />
      <rect x={38} y={12} width={30} height={64} rx={3} {...ACENTO_SUAVE} stroke="currentColor" strokeWidth={1.5} />
      <circle cx={53} cy={30} r={8} {...TRAZO} />
      <circle cx={53} cy={56} r={8} {...TRAZO} />
      <circle cx={80} cy={14} r={3} {...ACENTO} />
      {[24, 30, 36, 42, 48, 54, 60].map((y) => (
        <line key={y} x1={76} y1={y} x2={84} y2={y} {...TRAZO} strokeWidth={1.5} />
      ))}
      <rect x={34} y={86} width={8} height={3} rx={1} fill="currentColor" />
      <rect x={78} y={86} width={8} height={3} rx={1} fill="currentColor" />
    </>
  );
}

function Fuente() {
  return (
    <>
      <rect x={14} y={14} width={92} height={62} rx={6} {...CUERPO} />
      <circle cx={46} cy={45} r={22} {...TRAZO} />
      {[-12, -6, 0, 6, 12].map((d) => (
        <line key={d} x1={46 + d} y1={25 + Math.abs(d) * 0.6} x2={46 + d} y2={65 - Math.abs(d) * 0.6} {...TRAZO} strokeWidth={1.5} />
      ))}
      <rect x={78} y={26} width={18} height={14} rx={2} {...ACENTO} />
      <rect x={82} y={30} width={3} height={6} fill="var(--va-cuerpo)" />
      <rect x={89} y={30} width={3} height={6} fill="var(--va-cuerpo)" />
      <rect x={80} y={50} width={14} height={8} rx={2} {...TRAZO} />
    </>
  );
}

function Generico() {
  return (
    <>
      <rect x={26} y={14} width={68} height={62} rx={8} {...CUERPO} />
      <path d="M44 46 h32 M60 30 v32" {...TRAZO} strokeLinecap="round" />
    </>
  );
}

const DIBUJOS: Record<string, () => ReactElement> = {
  cpu: Procesador,
  cooler: Cooler,
  motherboard: PlacaMadre,
  ram: Memoria,
  almacenamiento: DiscoM2,
  almacenamiento_extra: SegundoDisco,
  gpu: PlacaDeVideo,
  gabinete: Gabinete,
  fuente: Fuente,
};

/** Dibujo del componente que va en `lugar` (cpu, ram, gpu…). Un lugar desconocido muestra uno genérico. */
export function ImagenComponente({ lugar, titulo }: { lugar: string; titulo?: string }) {
  const Dibujo = DIBUJOS[lugar] ?? Generico;
  return (
    <svg viewBox="0 0 120 90" role="img" aria-label={titulo ?? lugar} xmlns="http://www.w3.org/2000/svg">
      <Dibujo />
    </svg>
  );
}
