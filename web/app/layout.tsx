import type { Metadata } from "next";
import { Inter_Tight, Space_Grotesk } from "next/font/google";
import type { ReactNode } from "react";

import "./globals.css";

// Las mismas tipografías que usa la tienda.
const sans = Inter_Tight({ subsets: ["latin"], variable: "--font-sans" });
const display = Space_Grotesk({ subsets: ["latin"], variable: "--font-display" });

export const metadata: Metadata = {
  title: "Prueba del asistente — Todo Computación",
  description: "Página de prueba del chat del asistente de compra.",
};

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <html lang="es-AR" className={`${sans.variable} ${display.variable} dark`}>
      <body>{children}</body>
    </html>
  );
}
