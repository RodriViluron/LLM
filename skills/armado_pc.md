---
description: Procedimiento para elegir y comprar las piezas de una PC compatible dentro de un presupuesto, ajustarla y cambiarle piezas, usando las tools de armado. No es un tutorial de ensamblado físico (la tienda entrega la PC armada).
---
# Skill: armado de PC

## Regla de oro
Vos elegís **qué** producto va en **qué** lugar. La compatibilidad, los precios, el stock y el total los calcula la tienda. No hagas cuentas ni asegures que algo es compatible por tu cuenta.

## Antes de empezar
Hacé la entrevista con `siguiente_pregunta_armado`: el código decide qué preguntar y de ahí sale el perfil (gama, memoria, placa de video, segundo disco, placa escalable). No preguntes la gama ni la memoria a ciegas. Mostrá cada pregunta con `preguntar_al_usuario` y sus opciones tal cual; cuando el usuario responde, llamá otra vez a `siguiente_pregunta_armado` con `respuesta` igual a la opción elegida.
Cuando la entrevista esté completa, preguntá el **presupuesto** con las opciones de la gama del perfil y «Otro monto» (si ya lo dijo antes, no lo preguntes de nuevo). Con el perfil completo no preguntes la marca (Intel o AMD): armá con lo que pide el perfil y después el usuario puede cambiar piezas con el botón **Cambiar**. Si escribe un monto, validalo con `validar_presupuesto` (interpreta «2 palos», «20 lucas» y «$ 2.800.000») y no hagas cuentas vos.

Si el usuario nombra un juego o un programa, buscá primero sus requisitos con `buscar_especificaciones_web`. La respuesta dice qué CPU y GPU piden y si la tienda las tiene: usá primero esas piezas exactas (con su código) y, solo si no están, otras de la misma gama con `buscar_pieza_armado`.

## Procedimiento
1. `write_todos` con el plan: un item por pieza, en este orden.
2. `iniciar_configuracion` con el presupuesto validado y el perfil de la entrevista (por ejemplo «juegos 1080p»).
3. Elegí las piezas **de a una**, en este orden. El orden importa: cada pieza condiciona a las siguientes.
   1. **cpu**
   2. **cooler** (solo si la CPU no trae cooler)
   3. **motherboard**
   4. **ram**, con `cantidad` (por ejemplo, 2 módulos para doble canal)
   5. **almacenamiento**, y **almacenamiento_extra** si hace falta un segundo disco
   6. **gpu** (obligatoria si la CPU no tiene video integrado; si no, solo si el uso la necesita)
   7. **gabinete**
   8. **fuente** (solo si el gabinete no trae)
4. Para cada pieza:
   - `buscar_pieza_armado` con el `lugar`: aplica sola la gama, la memoria, el segundo disco o la placa escalable del perfil, y solo devuelve piezas compatibles con lo ya elegido. Usala en vez de `buscar_productos`.
   - Usá `precio_max` para no pasarte. Para saber cuánto destinar a cada pieza, consultá antes `consultar_caracteristicas` usando las palabras de los documentos, por ejemplo «reparto del presupuesto en gama baja» (o `media`, `alta`, `premium`) o «características para juegos en 1440p»: devuelve qué porcentaje del presupuesto se lleva cada componente con los precios de la tienda. No repartas de memoria.
   - `agregar_o_reemplazar_componente` con el `lugar` y el `codigo` elegido. Si una pieza lleva más de una unidad (por ejemplo, 2 módulos de RAM), usá `cantidad`. En la RAM, `buscar_pieza_armado` ya trae `cantidad_sugerida` para llegar a la memoria del perfil: pasala tal cual.
   - Marcá el item como `done` en los TODOs.
5. Al terminar, `obtener_configuracion` y revisá:
   - `faltan`: lugares obligatorios sin pieza.
   - `compatibilidad` y `reglas_a_revisar`.
   - `dentro_del_presupuesto`.
   - `sin_stock`: piezas elegidas que hoy no tienen stock. Avisalo y ofrecé una alternativa.

## Si se pasa del presupuesto
Llamá a `ajustar_presupuesto`. Reemplaza piezas por otras más baratas, compatibles y **de la misma gama**, con un tope de vueltas. Después explicale al usuario **qué se cedió**: cada cambio de `ajuste.cambios` (qué pieza salió, cuál entró y cuánto se ahorró).

Si aun así no entra (`dentro_del_presupuesto` en false), decilo con el motivo y ofrecé las opciones: subir el presupuesto o bajar de gama.

## Si una regla no cumple o queda sin datos
- `no_cumple`: buscá un reemplazo para una de las dos piezas en conflicto con `compatible_con` y volvé a verificar.
- `sin_datos`: **decíselo al usuario**. No digas que el armado es compatible. Ejemplo: «No puedo confirmar que la placa de video entre en el gabinete porque el gabinete no informa el largo máximo».
- Los avisos (`critica: false`: largo de la placa de video y conectores) no impiden confirmar, pero contáselos al usuario. Un `sin_datos` crítico sí impide confirmar.
- Si `buscar_productos` devuelve `sin_dato`, hay productos que quedaron afuera porque no informan el dato filtrado: avisalo.

## Cambios posteriores («cambiá la placa de video por una más potente»)
1. `obtener_configuracion` para ver el armado actual.
2. `buscar_productos` para ese lugar con `compatible_con` igual al resto de las piezas (y `precio_min` mayor al de la pieza actual si piden algo más potente).
3. `agregar_o_reemplazar_componente` en ese lugar. **No vuelvas a armar todo**: se cambia solo esa pieza.
4. Contá cómo quedó: total nuevo, compatibilidad y si sigue dentro del presupuesto.

## Al responder
- Listá cada pieza con código, nombre, precio y stock.
- Mostrá el total y el presupuesto, tal como los devuelve la tool.
- Nunca confirmes el pedido: eso lo hace el usuario con el botón **Confirmar pedido**.
