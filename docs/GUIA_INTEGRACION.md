# Guía de integración del asistente de compra

**Para:** quien mantiene la tienda (Next.js) y la API (NestJS) de Todo Computación.
**Qué entregamos:** un servicio (el agente) y un componente de React (el chat). Nada más.
**Qué hace la tienda:** un puente en NestJS y montar el componente en el layout.

## 1. Cómo encaja

```
Navegador (Next.js)                 NestJS                         Servicio del agente (Python)
┌──────────────────┐   POST /api/agente/chat   ┌────────────┐   POST /chat    ┌───────────────────┐
│  <ChatAgente />  │ ────────────────────────► │   puente   │ ──────────────► │ agente + catálogo  │
│                  │ ◄──── flujo de eventos ── │            │ ◄── eventos ─── │ propio + reglas    │
└──────────────────┘                           └────────────┘                 └───────────────────┘
   dibuja eventos                         sesión, clave, límites                 solo lee; nunca confirma
```

Tres reglas que ordenan todo:

1. **El navegador nunca habla directo con el agente.** Siempre pasa por NestJS, que agrega la clave del servicio y aplica sus límites.
2. **El agente solo lee.** No crea carritos, no toca «Armá tu PC» y no envía pedidos. Devuelve códigos y cantidades.
3. **Confirmar es del usuario.** El chat tiene un botón «Cargar en Armá tu PC»; al tocarlo, el componente le avisa a la página y la página hace la carga con la sesión del usuario.

## 2. El servicio del agente

Se levanta aparte (ver sección 7). Expone tres rutas:

| Ruta | Para qué |
|---|---|
| `POST /chat` | Un turno de conversación. Responde un flujo `text/event-stream` |
| `GET /conversaciones/{id}` | Historial visible y armado actual, para reabrir el chat |
| `GET /salud` | Prueba de vida. Responde `{"estado": "ok"}` |

La documentación interactiva queda en `/docs` del servicio (la genera FastAPI).

### `POST /chat`

```jsonc
// Pedido
{
  "mensaje": "Armame una PC para jugar en 1080p, hasta 1.200.000",   // 1 a 2000 caracteres
  "conversacion_id": "c0ffee12",   // opcional; letras, números, - y _; hasta 64
  "modelo": "local"                // opcional; por defecto "local", validado contra AGENTE_MODELOS_PERMITIDOS
}
```

- Si no se manda `conversacion_id`, el servicio crea uno y lo devuelve en el primer evento.
- Si no se manda `modelo`, el servicio usa `"local"`. Los modelos aceptados se definen en la variable de entorno `AGENTE_MODELOS_PERMITIDOS` (por defecto solo `"local"`, para que un cliente en producción no consuma cuota de API de Gemini). Además, el modelo tiene que estar configurado en el `.env` del servicio (`opciones_de_modelo()` en `model.py`).
- **El servicio guarda la conversación.** NestJS no tiene que mandar el historial: alcanza con el identificador. Todos los modelos comparten la misma memoria, así que se puede cambiar de modelo entre mensajes en una misma conversación.
- Cabecera `X-Agente-Clave`: obligatoria si el servicio se levantó con `AGENTE_CLAVE`.

| Respuesta | Cuándo |
|---|---|
| `200` + flujo de eventos | Siempre que el pedido sea válido. Los errores del agente llegan como evento `error`, no como estado HTTP |
| `400` | `modelo` no está en `AGENTE_MODELOS_PERMITIDOS` o no está configurado en el servidor (el turno no se ejecuta) |
| `401` | Falta la clave o es incorrecta |
| `409` | Esa conversación ya tiene una respuesta en curso |
| `422` | Mensaje vacío, demasiado largo, `modelo` vacío o identificador inválido |

### `GET /conversaciones/{id}`

```jsonc
{
  "conversacion_id": "c0ffee12",
  "turnos": [
    { "usuario": "Armame una PC…", "eventos": [ /* los mismos eventos que emitió /chat */ ] }
  ],
  "armado": { /* el armado actual, o null */ }
}
```

Una conversación que no existe devuelve `turnos: []` y `armado: null` (no es un error).

## 3. Los eventos: qué mostrar y qué no

Cada evento llega como un bloque `event: <tipo>` + `data: <JSON>`. El JSON repite el `tipo` y trae un campo `visibilidad`:

| `visibilidad` | Qué hacer |
|---|---|
| `mostrar` | Se dibuja siempre |
| `opcional` | Ayuda a que la espera no parezca un cuelgue. Se puede mostrar o no |
| `interno` | **No se muestra nunca al cliente.** Solo llega en modo de depuración |

| Evento | Visibilidad | Contenido | Cómo se dibuja |
|---|---|---|---|
| `inicio` | — | `conversacion_id` | No se dibuja. Guardar el identificador para el próximo mensaje |
| `estado` | opcional | `texto` («Buscando productos…»), `paso` | Un renglón temporal con animación. Se reemplaza con cada `estado` nuevo. Mientras el agente piensa entre un paso y otro, el renglón vuelve a «Pensando…» |
| `texto` | mostrar | `texto` (markdown simple) | Párrafo del asistente. Puede haber varios por turno |
| `productos` | mostrar | `productos[]` | Tarjetas: nombre, código, precio, stock |
| `armado` | mostrar | `armado` | Tarjeta del armado. **Llega varias veces por turno** (una por pieza): mostrar solo la última |
| `pregunta` | mostrar | `pregunta`, `opciones[]` | La pregunta y un botón por opción. Tocar una opción la envía como mensaje del usuario |
| `fuentes` | mostrar | `fuentes[]` (`titulo`, `url`) | Lista plegada de enlaces |
| `error` | mostrar | `mensaje` | Aviso. El mensaje ya está escrito para el cliente |
| `razonamiento` | interno | `texto` | **No mostrar.** No llega en producción (ver abajo) |
| `fin` | — | — | Fin del turno: volver a habilitar el envío |

Un cliente tiene que **ignorar los tipos que no conoce**: así se pueden agregar eventos sin romper la tienda.

### Lo que el servicio no envía

Esto no hay que filtrarlo del lado de la tienda: directamente no sale del servicio.

| Qué | Por qué |
|---|---|
| El razonamiento del modelo | Es un borrador interno, a veces en inglés y a veces equivocado. Algunos modelos lo dejan mezclado con la respuesta: el servicio lo separa antes de emitir `texto` |
| Los argumentos de cada herramienta | Son detalles técnicos (`{"categoria": "cpu", "atributos": {...}}`). El evento `estado` solo dice qué está haciendo |
| El texto crudo que devuelven las herramientas | Está escrito para el modelo. Lo que le sirve al cliente llega como `productos` o `armado` |
| La lista de pasos que el agente se arma para trabajar | Es su organización interna |
| La descripción interna del catálogo (`hdesc`) | Tiene notas para el vendedor. El agente la usa para leer datos técnicos, pero no la guarda ni la muestra |

El razonamiento solo se emite si el servicio se levanta con `AGENTE_DEPURAR=1` **y** el pedido trae `"depurar": true`. El puente no tiene que reenviar ese campo: en la tienda no se usa.

### Preguntas del asistente

El asistente pregunta de dos maneras:

- **En el texto**, como cualquier persona («¿Para qué la vas a usar?»). Es un evento `texto` común; el usuario contesta escribiendo.
- **Con opciones**, cuando las respuestas se pueden listar. Llega un evento `pregunta` y el turno termina ahí:

```jsonc
{ "tipo": "pregunta", "visibilidad": "mostrar", "pregunta": "¿Intel o AMD?", "opciones": ["Intel", "AMD"] }
```

Reglas para dibujarla:

- Un botón por opción. Al tocarlo se manda **el texto de la opción** como un mensaje normal del usuario (`POST /chat`).
- El usuario también puede ignorar los botones y escribir otra cosa.
- Los botones valen solo mientras la pregunta sea lo último de la conversación. En el historial se muestran deshabilitados.

**La entrevista del armado** usa esta misma forma de evento. Para armar una PC el asistente hace unas 6 preguntas en términos de uso («¿Para qué la vas a usar?», «¿Solés tener muchos programas abiertos?»). Cada pregunta llega como un evento `pregunta` con sus opciones, y el turno termina ahí, igual que las demás.

- Después de la entrevista, el asistente pregunta el presupuesto con un botón por gama («Gama baja (cerca de $ 1.000.000)») y «Otro monto».
- Al elegir «Otro monto», el asistente pide el monto en texto libre. Acepta «2 palos», «20 lucas», «mil» o «$ 2.800.000»; los dólares no se convierten (no hay cotización).
- Si el usuario escribe algo que no es una opción (una pregunta, por ejemplo), el asistente lo contesta en texto y después repite la pregunta con sus botones.
- Los botones de la entrevista y el texto libre dan el mismo resultado: el asistente interpreta lo que llega como mensaje del usuario.

### El armado

```jsonc
{
  "tipo": "armado", "visibilidad": "mostrar",
  "armado": {
    "version": 7,
    "presupuesto": 1200000,
    "perfil_uso": "juegos 1080p",
    "componentes": [
      { "lugar": "cpu", "cantidad": 1,
        "producto": { "codigo": "RY5500", "nombre": "CPU AMD RYZEN 5 5500 S/VID AM4", "categoria": "cpu",
                      "marca": "AMD", "precio": 149950, "stock": 4, "imagen": "https://…", "url": null,
                      "atributos": { "socket": "AM4", "generacion": "3" } } }
    ],
    "total": 1013000,
    "dentro_del_presupuesto": true,
    "compatibilidad": {
      "estado": "sin_confirmar",          // compatible | incompatible | sin_confirmar | sin_verificar
      "reglas": [
        { "regla": "socket_cpu_placa", "estado": "cumple", "detalle": "CPU y placa usan AM4" },
        { "regla": "potencia_fuente", "estado": "sin_datos", "detalle": "2F5050 no informa 'consumo_w'" }
      ]
    },
    "pedido": [ { "lugar": "cpu", "codigo": "RY5500", "cantidad": 1 } ],
    "se_puede_confirmar": false,
    "motivos_para_no_confirmar": ["Faltan piezas: motherboard, ram, almacenamiento, fuente, gabinete"]
  }
}
```

| Campo | Cómo usarlo |
|---|---|
| `componentes` | Lo que se muestra. `lugar` es `cpu`, `cooler`, `motherboard`, `ram`, `almacenamiento`, `gpu`, `gabinete` o `fuente` |
| `total`, `presupuesto` | Los calcula el servicio. La interfaz no suma |
| `compatibilidad.estado` | La insignia del armado. `sin_confirmar` quiere decir que alguna regla no tuvo datos: **no es lo mismo que compatible** |
| `compatibilidad.reglas` | Mostrar las que no están en `cumple`, con su `detalle` |
| `pedido` | **Lo que la tienda carga** en «Armá tu PC» o en el carrito: `codigo` es el SKU |
| `se_puede_confirmar` | Si es `false`, el botón de cargar va deshabilitado y se muestran los `motivos_para_no_confirmar` |

La compatibilidad, los precios y el total los calcula el servicio con reglas fijas. El modelo de lenguaje no decide ninguna de esas tres cosas.

## 4. El puente en NestJS

Es un controlador que reenvía el pedido y devuelve el flujo sin acumularlo. Lo que tiene que hacer:

| Tarea | Detalle |
|---|---|
| Reenviar solo dos campos en producción | `mensaje` y `conversacion_id`. Nunca `depurar`; `modelo` solo en desarrollo si se habilita `AGENTE_MODELOS_PERMITIDOS` |
| Agregar la clave | Cabecera `X-Agente-Clave` con el valor de `AGENTE_CLAVE` |
| Atar la conversación al usuario | Ver «De quién es la conversación» |
| Limitar el uso | Mensajes por minuto por usuario o por IP. Cada turno usa un modelo de lenguaje: es caro |
| No acumular la respuesta | Devolver el cuerpo tal como llega y desactivar el buffer del proxy (`X-Accel-Buffering: no`, sin compresión para `text/event-stream`) |
| Cortar si el cliente se va | Si el navegador cierra la conexión, cerrar también la del servicio: el agente deja de trabajar |

Esqueleto (NestJS con Express):

```ts
@Controller('agente')
export class AgenteController {
  @Post('chat')
  async chat(@Body() cuerpo: ChatAgenteDto, @Req() pedido: Request, @Res() respuesta: Response) {
    const corte = new AbortController();
    pedido.on('close', () => corte.abort());          // el usuario cerró el chat o recargó la página

    const delAgente = await fetch(`${process.env.AGENTE_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Agente-Clave': process.env.AGENTE_CLAVE ?? '' },
      body: JSON.stringify({ mensaje: cuerpo.mensaje, conversacion_id: cuerpo.conversacion_id ?? null }),
      signal: corte.signal,
    });
    if (!delAgente.ok || !delAgente.body) {
      throw new HttpException('El asistente no está disponible.', delAgente.status === 409 ? 409 : 502);
    }

    respuesta.status(200).set({
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      'X-Accel-Buffering': 'no',
    });
    respuesta.flushHeaders();
    for await (const trozo of delAgente.body) respuesta.write(trozo);   // sin acumular
    respuesta.end();
  }

  @Get('conversaciones/:id')
  async conversacion(@Param('id') id: string) {
    const delAgente = await fetch(`${process.env.AGENTE_URL}/conversaciones/${encodeURIComponent(id)}`, {
      headers: { 'X-Agente-Clave': process.env.AGENTE_CLAVE ?? '' },
    });
    return delAgente.json();
  }
}
```

El mismo puente, hecho con rutas de Next para la página de prueba, está en `web/app/api/agente/`. Sirve de referencia, pero en la tienda va en NestJS.

### De quién es la conversación

El servicio no sabe de usuarios: quien conoce un `conversacion_id` puede leer esa conversación. Por eso el identificador lo controla el puente:

- **Con sesión iniciada:** guardar `conversacion_id` asociado al usuario y rechazar los que no sean suyos.
- **Sin sesión:** generar el identificador en el servidor (aleatorio, largo) y guardarlo en una cookie `httpOnly`, en vez de aceptar el que mande el navegador.

El componente de prueba guarda el identificador en `localStorage` porque no hay usuarios; en la tienda conviene cualquiera de las dos opciones de arriba.

### Precios y sesión

El asistente trabaja con su propia copia del catálogo, que sincroniza una vez por día. Hoy la tienda muestra precios solo con sesión iniciada. Hay que decidir qué pasa con un visitante sin sesión:

| Opción | Qué implica |
|---|---|
| El chat solo aparece con sesión iniciada | Lo más simple. El puente exige sesión |
| El chat aparece siempre, sin precios para visitantes | El puente tiene que quitar `precio`, `total` y `presupuesto` de los eventos `productos` y `armado` antes de reenviarlos |

Recomendamos la primera para empezar: armar una PC según un presupuesto no tiene sentido sin precios.

## 5. El componente del chat

Es la carpeta `web/components/chat-agente/`. No depende de nada más que de React: no usa Tailwind ni librerías de componentes.

| Archivo | Qué tiene |
|---|---|
| `ChatAgente.tsx` | El botón flotante y el panel |
| `ChatAgente.module.css` | Los estilos |
| `useChatAgente.ts` | La lógica: enviar, leer el flujo, recuperar el historial |
| `tipos.ts` | Los tipos del contrato (eventos, producto, armado) |
| `index.ts` | Lo que se exporta |

Uso, en el layout de la tienda:

```tsx
import { ChatAgente } from "@/components/chat-agente";

<ChatAgente
  endpoint="/api/agente"
  onConfirmarArmado={(pedido, armado) => cargarEnArmaTuPc(pedido)}
  onVerProducto={(producto) => router.push(`/productos/${producto.codigo}`)}
/>
```

Es un componente de cliente (`"use client"`). Si el layout es de servidor, alcanza con importarlo: las funciones que se le pasan tienen que venir de un componente de cliente.

| Propiedad | Por defecto | Para qué |
|---|---|---|
| `endpoint` | `/api/agente` | Ruta del puente. Tiene que exponer `/chat` y `/conversaciones/:id` |
| `onConfirmarArmado` | — | El usuario tocó «Cargar en Armá tu PC». Recibe `pedido` (SKU y cantidades) y el `armado` completo. **Sin esta función el botón no aparece** |
| `onVerProducto` | — | El usuario tocó una tarjeta de producto. Sin esta función las tarjetas no son clicables |
| `onArmado` | — | El armado de la conversación cambió: el agente puso o cambió una pieza, se recuperó la conversación o se empezó una nueva (llega `null`). Sirve para mostrar el armado en vivo, por ejemplo en «Armá tu PC». No confirma nada. La página de prueba lo usa en `components/vista-armado/` |
| `titulo`, `subtitulo` | «Asistente de compra», «Todo Computación» | Cabecera del panel |
| `sugerencias` | tres ejemplos | Pedidos de ejemplo con el chat vacío |
| `mostrarEstados` | `true` | Con `false`, en vez de «Buscando productos…» muestra solo «Escribiendo…» |
| `textoConfirmar` | «Cargar en Armá tu PC» | Texto del botón del armado |
| `abiertoInicial` | `false` | Arranca con el panel abierto |
| `modoDesarrollo` | Según `NEXT_PUBLIC_MODO_DESARROLLO` (`1` o `true`) | Solo desarrollo: muestra el selector de modelo y envía `modelo` en `POST /chat`. En producción no aparece |
| `modelos` | `Local` y `Gemini` | Opciones del selector cuando `modoDesarrollo` está activo |

### Colores y tipografía

El chat toma los colores de las variables CSS que la tienda ya define. No hay que configurar nada para que acompañe el tema claro y el oscuro.

| Variable de la tienda | Qué pinta en el chat |
|---|---|
| `--brand-blue`, `--brand-blue-hover`, `--brand-blue-light` | Botón flotante, mensajes del usuario, botones y enlaces |
| `--brand-green` | El punto del botón y los textos «En stock» y «Compatible» |
| `--surface`, `--muted` | Fondo del panel y de las tarjetas |
| `--foreground`, `--muted-foreground` | Textos |
| `--border` | Bordes |
| `--destructive` | Errores e incompatibilidades |
| `--font-display` | Títulos (si existe; si no, hereda la del cuerpo) |

Para cambiar un color solo en el chat, definir la variable `--ca-*` correspondiente (están todas al comienzo de `ChatAgente.module.css`). La tipografía del cuerpo se hereda de la página.

### Cargar el armado en la tienda

`onConfirmarArmado` recibe esto:

```jsonc
[
  { "lugar": "cpu",         "codigo": "RY5500", "cantidad": 1 },
  { "lugar": "motherboard", "codigo": "A52DV2", "cantidad": 1 },
  { "lugar": "ram",         "codigo": "162X8G", "cantidad": 1 }
]
```

Con la API actual hay dos caminos:

| Destino | Cómo | Observación |
|---|---|---|
| Carrito | `POST /api/cart/:cartId/items` por cada ítem (`productId` se resuelve por SKU) | Es el camino corto. Pierde la revisión paso a paso |
| «Armá tu PC» | `POST /api/pc-builder/builds` y un `PUT …/steps/:step` por pieza, en el orden que exige el builder | El orden es `cpu → cooler → motherboard → memory → m2_storage → sata_storage → gpu → case → power_supply` |

Correspondencia entre nuestros lugares y los pasos del builder:

| `lugar` | Paso del builder |
|---|---|
| `cpu` | `cpu` |
| `cooler` | `cooler` (si no viene, `POST …/steps/cooler/skip`) |
| `motherboard` | `motherboard` |
| `ram` | `PUT …/memory-target` y después `memory` |
| `almacenamiento` | `m2_storage` o `sata_storage`, según el producto |
| `gpu` | `gpu` (si no viene, `POST …/steps/gpu/skip`) |
| `gabinete` | `case` |
| `fuente` | `power_supply` |

Si el builder rechaza un paso (`409`), mostrar su mensaje: quiere decir que sus reglas y las del asistente no coinciden en ese producto. Los casos conocidos están en `docs/MEJORAS_API_ARMADO_PC.md`. La propuesta P13 de ese documento (cargar un armado completo en una llamada) reemplazaría toda esta secuencia.

**Siempre revalidar al cargar.** El asistente trabaja con una copia del catálogo de ese día; precio y stock los confirma la tienda en el momento.

## 6. Errores y casos límite

| Situación | Qué llega | Qué mostrar |
|---|---|---|
| El modelo falla o tarda demasiado | Evento `error` con un mensaje para el cliente | El mensaje, y dejar reintentar |
| El servicio está caído | El puente no puede conectar | «El asistente no está disponible». El resto de la tienda sigue funcionando |
| El usuario manda otro mensaje antes de que termine | `409` | Deshabilitar el envío mientras hay una respuesta en curso (el componente ya lo hace) |
| El usuario cierra el chat a mitad de una respuesta | El puente corta la conexión | Nada. Lo ya conversado queda guardado |
| Un armado no se puede confirmar | `se_puede_confirmar: false` | Botón deshabilitado y los motivos |
| Una regla no tuvo datos | `estado: "sin_datos"` en la regla | «Sin datos: …». No presentarlo como compatible |

**Tiempos de respuesta.** Con un modelo chico corriendo en una PC sin placa de video dedicada, un turno puede tardar más de un minuto. El evento `estado` existe para eso. Los tiempos de espera del proxy tienen que permitir conexiones largas (varios minutos) en la ruta del chat.

## 7. Puesta en marcha

Servicio del agente:

```bash
uv run python -m uvicorn servicio:app --port 8000
```

| Variable | Para qué |
|---|---|
| `AGENTE_CLAVE` | Clave que tiene que mandar el puente en `X-Agente-Clave`. Definirla siempre fuera de la máquina de desarrollo |
| `AGENTE_DEPURAR` | `1` permite pedir el razonamiento. Solo en desarrollo |
| `AGENTE_MODELOS_PERMITIDOS` | Lista separada por comas de modelos aceptados en `POST /chat` (por ejemplo `local,gemini`). Por defecto solo `local` |
| `MODEL_PROVIDER`, `MODEL_NAME` | Qué modelo local de lenguaje usa (ver `.env.example`) |
| `GOOGLE_API_KEY`, `GEMINI_MODEL` | Opcionales: habilitan la opción `gemini` si además figura en `AGENTE_MODELOS_PERMITIDOS` |
| `AMN_CATALOGO_DB` | Qué copia del catálogo usa |

Página de prueba (necesita Node.js):

```bash
cd web
npm install
npm run dev
```

Con `AGENTE_URL` en `web/.env.local` apuntando al servicio (y opcionalmente `NEXT_PUBLIC_MODO_DESARROLLO=1` para mostrar el selector de modelo en desarrollo). La página de prueba es una maqueta: lo único que se lleva a la tienda es la carpeta `components/chat-agente`.

El servicio guarda las conversaciones en un archivo local (`memoria.db`) y atiende de a un turno por conversación. Para la demostración alcanza; con mucho tráfico habría que pasar ese almacenamiento a una base compartida.

## 8. Lista de verificación

- [ ] El navegador llama al puente de NestJS, nunca al servicio.
- [ ] El puente manda `X-Agente-Clave` y no reenvía `depurar`.
- [ ] El `conversacion_id` está atado al usuario o a una cookie del servidor.
- [ ] Hay un límite de mensajes por usuario.
- [ ] El flujo llega evento por evento (sin buffer ni compresión en el proxy).
- [ ] Se ignoran los tipos de evento desconocidos y todo lo marcado `interno`.
- [ ] De cada turno se muestra solo el último `armado`.
- [ ] El botón de cargar respeta `se_puede_confirmar` y muestra los motivos.
- [ ] `sin_confirmar` y `sin_datos` no se presentan como «compatible».
- [ ] Al cargar el armado, la tienda vuelve a validar precio y stock.
