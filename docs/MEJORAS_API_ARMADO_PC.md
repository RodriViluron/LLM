# Mejoras propuestas a la API de la tienda — Armado de PC y catálogo

**Para:** quien mantiene la API (NestJS) y la tienda (Next.js) de tienda.amn.com.ar.
**De:** Grupo 10 — Asistente de compra (proyecto integrador, UTN FRM).
**Fecha:** 11/11/2026.

Este documento compara **lo que hoy dice el manual de la API** con **lo que proponemos cambiar**, a partir de lo que encontramos al conectar el asistente con el catálogo real. No pide reescribir nada: la mayoría son cambios chicos en cómo se leen los datos, más una propuesta de fondo (sección 4).

## 1. De dónde sale cada afirmación

| Fuente | Qué es | Cómo la usamos |
|---|---|---|
| `DEVELOPER_API_MANUAL.md` (cambios hasta el 11/11/2026) | El contrato de la API | Columna «Hoy» de las tablas |
| `3PC.PRG` | El algoritmo de armado en Visual FoxPro. El manual lo nombra como «fuente de verdad funcional» de los pasos | Para saber cómo se lee cada dato |
| Bajada de `GET /api/products` del 11/11/2026 | 4.263 productos, 509 piezas de PC | Casos concretos, con SKU |

**Qué pudimos probar y qué no.** Los endpoints públicos los consultamos de verdad (solo lectura, sin sesión). Los de `/api/pc-builder` piden sesión (`401 AUTH_REQUIRED`) y **no los probamos**: lo que decimos del builder sale del manual y del PRG. Donde escribimos «si el builder replica el PRG…», es para que lo verifiquen ustedes con el SKU que damos.

### Quién corrige qué

Los datos nacen en el sistema de la empresa (Visual FoxPro), salen todos los días en los Excel y con eso se rearma la base de NestJS. Eso define dónde va cada arreglo:

| Tipo de problema | Dónde se arregla | Quién |
|---|---|---|
| Un producto mal cargado (anexo B) | En el sistema de origen. Si se corrige en la base de NestJS, el Excel del día siguiente lo pisa | Quien carga el catálogo en Todo Computación |
| El texto se lee mal (P1 a P8) | En el código que interpreta el texto, al importar el Excel (P10) | Quien mantiene la API |
| Un dato que el texto no trae (P9) | En una tabla propia de NestJS, por SKU, que el import diario no toque | Quien mantiene la API, con carga desde el panel de administración |

Ninguna propuesta pide cambiar el sistema de origen ni el formato de los Excel: el importador valida nombre, cantidad y orden de columnas, y tocar eso pone en riesgo la carga diaria.

## 2. Resumen de propuestas

| # | Propuesta | Prioridad | Sección |
|---|---|---|---|
| P1 | Leer `**SIN VIDEO` y `**SIN COOLER` aunque tengan espacios de más | **Alta** — hoy permite armar una PC sin salida de video | 3.1 |
| P2 | Buscar el socket del cooler solo en el renglón `SOCKET:` | **Alta** — hoy da por compatible un cooler que no lo es | 3.2 |
| P3 | Validar la fuente contra lo que pide la placa de video | **Alta** — hoy no se valida | 3.7 y 3.9 |
| P4 | Validar el formato de la placa madre contra el gabinete | **Alta** — hoy no se valida | 3.8 |
| P5 | Memoria: no depender de dos espacios; filtrar por tipo de módulo; contar ranuras | Media | 3.4 |
| P6 | Leer las generaciones del renglón del chipset, no de toda la descripción | Media | 3.3 |
| P7 | Consumo de CPU base y máximo; coolers sin potencia cargada | Media | 3.1 y 3.2 |
| P8 | Discos M.2 SATA y placas «M.2 SATA/PCIe» | Baja | 3.5 |
| P9 | Campos para datos que hoy no existen (largo de la placa de video, etc.) | Baja | 3.10 |
| P10 | **Atributos estructurados por producto, calculados al importar el XLS** | **Alta** — resuelve P1 a P8 de una vez | 4 |
| P11 | Avisos de calidad del catálogo en el `preflight` del data-sync | **Alta** | 5 |
| P12 | Reporte de compatibilidad por regla en las respuestas del builder | Media | 6 |
| P13 | Crear o reemplazar un armado completo en una sola llamada | Media — lo necesita el asistente | 7 |
| P14 | Sacar los campos internos del listado público | **Alta** — hoy se ven costos y notas internas sin sesión | 8.1 |
| P15 | Credencial de servicio para el asistente (solo lectura, con precios) | **Alta** para integrar el asistente | 8.2 |
| P16 | Avisarle al asistente cuando termina un data-sync | Media | 8.3 |
| P17 | Diferencias entre el manual y lo que responde la API | Baja | 8.4 |

## 3. Armado de PC, paso por paso

### Por qué pasa: cómo está escrita la información

Los productos no tienen atributos estructurados. Todo sale de tres campos de texto:

- `name`: 40 columnas. En CPU y placas madre, la última palabra es el socket (`CPU AMD RYZEN 3 3200G                AM4`).
- `desc`: 5 renglones de 50 columnas, **pegados sin separador**. `hdesc`: 2 renglones más.
- Quien carga el catálogo sigue una convención por categoría (anexo A). Es bastante regular: por eso el armado funciona.

`3PC.PRG` lee esos textos de dos maneras frágiles: **por posición** (`SUBSTR(name,37,4)`, «el carácter dos lugares antes de `DDR`») y **por primera coincidencia en todo el texto** (`AT("w", desc+hDesc)`, `AT("1200", desc+hDesc)`). Alcanza con un espacio de más o con que el mismo número aparezca en otro renglón para que lea otra cosa. Y como no valida, el error no se ve: se arma una PC que no es compatible.

En cada tabla: **Hoy** = lo que dice el manual y hace el PRG. **Caso** = SKU real donde falla. **Propuesta** = el cambio.

### 3.1 `cpu`

| Dato | Hoy | Caso | Propuesta |
|---|---|---|---|
| `includesGraphics` | El PRG busca el texto exacto `**SIN VID` (línea 36). El manual: `gpu/skip` «is accepted only when the CPU includes graphics» | **`3600XT`** dice `** SIN VIDEO` (con un espacio). El PRG no lo encuentra y da la CPU como «con video»: se puede saltear la placa de video en una CPU que no tiene gráfica integrada | **P1.** Aceptar espacios (`\*+\s*SIN\s*VID`). Además, si no dice «sin video», exigir que nombre la GPU integrada; si no hay ninguna de las dos cosas, el dato es **desconocido** y no se puede saltear el paso |
| `includesCooler` | Texto exacto `**SIN COO` | Hoy ninguno falla, pero es la misma fragilidad | **P1.** Misma tolerancia. Cruzar con `S/COO` del nombre: si se contradicen, desconocido |
| `thermalDesignPowerWatts` | El PRG toma el número que está antes de la **primera `w` minúscula** de `desc+hdesc` | AMD escribe `65w` (base). Intel escribe `CONSUM.:65/117w` y el PRG se queda con `117` (máximo). Se comparan cosas distintas según la marca | **P7.** Dos campos: base y máximo. Para elegir cooler, comparar contra el máximo |
| `generation` | Tres caracteres después de `[` | Bien en las 74 CPU actuales | Guardarla como número (`12`), no como texto (`12v`) |
| CPU que entran | Socket en las columnas 37 a 40 del nombre | `H5416S` (Xeon) no tiene socket en el nombre | Dato a corregir, o categoría aparte para servidor |

### 3.2 `cooler`

| Dato | Hoy | Caso | Propuesta |
|---|---|---|---|
| Socket compatible | El PRG busca el socket de la CPU en **cualquier lugar** de `desc+hdesc` (línea 54) | **`CP0587`**: `VELOCIDAD: 1200 A 1800rpm`. Su lista `SOCKET:` no incluye el 1200, pero el PRG encuentra «1200» en las rpm y lo ofrece para LGA1200 | **P2.** Leer los sockets solo desde `SOCKET:` hasta el próximo rótulo, y descartar números seguidos de `rpm`, `mm`, `w` |
| `coolingCapacityWatts` | Primera `w` minúscula del texto. Si no hay, queda en 0 y el cooler **no se ofrece para ninguna CPU** | 10 de 48 no tienen la potencia cargada, entre ellos tres de las diez refrigeraciones líquidas (`TRL240`, `TRL360`, `KRL120`) | **P7.** Leer `PODER DE ENFRIAMIENTO: <n>w`. Cargar el dato en esos 10 (anexo B) |
| Paso obligatorio | `cooler/skip` solo si la CPU trae cooler | — | Sin cambios |

### 3.3 `motherboard`

| Dato | Hoy | Caso | Propuesta |
|---|---|---|---|
| Generación soportada | El PRG busca la generación de la CPU en toda la `desc` (línea 67) | Las placas AM4 traen `*PCIe 4.0 (3ra GEN)`: es la generación **de PCIe**. Una placa que no soportara la 3ra de Ryzen coincidiría igual. Hoy no falla porque todas las AM4 la soportan | **P6.** Leer la lista solo del renglón del chipset: `CHIPSET AMD B550 (RYZEN 2da 3ra GEN)` |
| `memorySlots`, `memoryType` | Carácter dos lugares antes de `DDR` | Bien en las 56 placas actuales | Leer `<n> DDR<n>` como patrón y cruzar con `D4`/`D5` del nombre |
| `sataPorts` | Carácter dos lugares antes de `SATA3` | Bien hoy. Ojo con `1 M.2 SATA/PCIe`: ahí el 2 es de `M.2` | Patrón `<n> SATA3` que no tome el `M.2 SATA/PCIe` |
| `m2Slots` | Carácter dos lugares antes del primer `M.2` | Bien hoy | Patrón `<n> M.2` |
| Formato (ATX, mATX) | No se lee | Está en el nombre de 56 de 56 placas | **P4.** Leerlo: hace falta para validar el gabinete |

### 3.4 `memory`

| Dato | Hoy | Caso | Propuesta |
|---|---|---|---|
| Qué memorias se ofrecen | El PRG exige **dos espacios** antes de `DDR` en el nombre (línea 82). Así deja afuera las `SO-DDR` de notebook | **`A42400`** y **`4240MV`** (`4GB DDR4,2400`, un solo espacio) son memorias de escritorio y no se ofrecen. Las ECC de servidor quedan afuera solo por casualidad del espaciado | **P5.** Filtrar por tipo de módulo leído de la descripción: `DIMM` sí; `SODIMM`, `RDIMM` y `ECC` no |
| Cantidad | El manual: `requiredQuantity` es la cuenta del PRG cuando la división da exacta; si no, «the API persists quantity 1 but may still list the module» | Con módulos que no dividen el objetivo, el armado queda con menos memoria de la pedida | **P5.** No listar el producto si no llega al objetivo, o devolver la capacidad que resulta para que el cliente la muestre |
| Ranuras | El PRG verifica `GB por módulo × ranuras ≥ objetivo` | No se verifica que `módulos × cantidad ≤ ranuras` cuando se eligen kits | **P5.** Validar módulos contra `memorySlots` |
| Kits | `ES UN KIT DE 2` en la descripción | Los 4 kits actuales lo dicen en el nombre (`K2x8`) y en la descripción | Cruzar los dos lugares |

Nota: en el PRG el total suma el precio de la memoria **una sola vez** aunque muestre cantidad 2 (líneas 88 a 90). El manual dice que la API multiplica por la cantidad, así que eso ya está resuelto en la API; lo dejamos anotado por si el PRG se sigue usando en el mostrador.

### 3.5 `m2_storage` y `sata_storage`

| Dato | Hoy | Caso | Propuesta |
|---|---|---|---|
| Qué se ofrece en M.2 | Solo los `D.SSD  M.2 PCIe` | Hay 5 discos `D.SSD  M.2 SATA3` que nunca se ofrecen. Es correcto mientras no se sepa si la placa los admite | **P8.** Guardar si las ranuras admiten SATA (`M.2 SATA/PCIe`) y ofrecerlos solo en esas placas |
| Límites | Hasta `m2Slots` y `sataPorts` | — | Sin cambios |

### 3.6 Orden de los pasos

El manual fija `cpu → cooler → motherboard → memory → m2_storage → sata_storage → gpu → case → power_supply` y borra lo posterior al cambiar una pieza anterior. Para una persona que arma paso a paso está bien. Para el asistente es un problema: ver la sección 7.

### 3.7 `gpu`

| Dato | Hoy | Caso | Propuesta |
|---|---|---|---|
| Compatibilidad | El manual devuelve `null` para `gpu`. El PRG lista todas las `PL.VIDEO` (línea 166) | — | **P3.** Exponer la fuente que pide la placa y sus conectores |
| Fuente requerida | No se lee | 23 de 27 placas la traen: `REQUIERE FUENTE 550W+POWER 1x8pin`, `FUENTE RECOMENDADA 500W`, `FUENTE MIN.450W RECOMENDADA 500W` | **P3.** Leerla. Si hay mínima y recomendada, usar la recomendada |
| Conector de energía | No se lee | 16 de 27 lo traen (`1x8pin`) | **P3.** Leerlo |

### 3.8 `case`

| Dato | Hoy | Caso | Propuesta |
|---|---|---|---|
| Qué se ofrece | Categorías 180, 185 y 186 con nombre `GAB.` (línea 179) | Entran los rackeables: `S2U550` y `A4U450` (2U y 4U) | **P4.** Excluir los que no tienen renglón `FORMATO:` o marcarlos como desconocidos |
| Formato de placa admitido | No se valida | 59 de 63 gabinetes traen `FORMATO: mATX, ATX, E-ATX`. Hoy se puede elegir una placa ATX con un gabinete que solo admite mATX | **P4.** Validar el formato de la placa contra la lista del gabinete |
| `includesPowerSupply` | `S/F` en el nombre | Bien en los 63 | Cruzar con `NO INCLUYE FUENTE` y guardar los watts de la fuente incluida |

### 3.9 `power_supply`

| Dato | Hoy | Caso | Propuesta |
|---|---|---|---|
| Compatibilidad | El manual devuelve `null`. El PRG lista todas las `FTE PC` (línea 192), sin mirar la potencia | Según el PRG, se puede elegir una RTX 5070 Ti (pide 750W) con una fuente de 500W | **P3.** Exigir potencia ≥ la que pide la placa de video. Si no hay placa de video, un mínimo por consumo de CPU |
| Gabinete con fuente | El paso queda `not_applicable` (`CASE_INCLUDES_POWER_SUPPLY`) | De los 8 gabinetes con fuente, 6 la traen de 600W, uno de 750W y uno de 450W. Hay 6 placas de video que piden 650W o más: con esos gabinetes el armado sale mal y no hay paso donde corregirlo | **P3.** Validar también la fuente incluida; si no alcanza, avisar y ofrecer gabinetes sin fuente |
| Conectores PCIe | No se leen | Las 36 fuentes los traen: `4 PCIe 6+2pin` | **P3.** Comparar con el conector que pide la placa |

### 3.10 Datos que hoy no existen en el catálogo

No encontramos en ningún producto: el **largo de la placa de video**, el **largo máximo que admite el gabinete** y la **altura del cooler**. Sin esos datos no se puede validar si una placa larga entra en el gabinete.

**P9.** Guardar esos tres datos en una tabla propia de NestJS, por SKU, cargada desde el panel de administración. Es el mismo criterio que ya se usa con las imágenes: el data-sync no las toca porque las maneja otro proceso. Así no hace falta pedirle campos nuevos al sistema de origen ni cambiar el Excel. Mientras el dato no esté, la regla responde «desconocido» en vez de dar el armado por bueno.

## 4. Propuesta de fondo: atributos estructurados (P10)

Los puntos P1 a P8 son el mismo problema: **cada consumidor interpreta el texto por su cuenta**, en el momento de consultar. Hoy lo hacen el PRG, las consultas del builder y ahora el asistente. Tres lectores, tres resultados posibles.

Proponemos leer el texto **una sola vez**, cuando se importa el XLS, y guardar el resultado como atributos del producto.

| | Hoy | Propuesta |
|---|---|---|
| Cuándo se interpreta | En cada consulta del builder | En `POST /api/admin/data-sync/jobs`, al importar `products.XLS` |
| Dónde queda | En ningún lado: se recalcula | Una columna `specs` (JSON) por producto, más `specsWarnings` |
| Quién lo usa | Solo el builder | El builder, los filtros de la tienda y el asistente |
| Qué pasa si no se entiende | Se toma un valor equivocado o cero, en silencio | El atributo queda en `null` (desconocido) y se genera un aviso |

Forma sugerida, con los nombres que el builder ya usa en `options` y los nuevos marcados con `+`:

```jsonc
// GET /api/products/:term  → agregar "specs" (público, no tiene datos sensibles)
{
  "sku": "12400F",
  "specs": {
    "kind": "cpu",
    "socket": "LGA1700",
    "generation": 12,
    "includesCooler": true,
    "includesGraphics": false,
    "thermalDesignPowerWatts": 65,
    "maxPowerWatts": 117            // +
  }
}
```

| `kind` | Atributos |
|---|---|
| `cpu` | `socket`, `generation`, `includesCooler`, `includesGraphics`, `thermalDesignPowerWatts`, `maxPowerWatts`+, `cores`+ |
| `motherboard` | `socket`, `memoryType`, `memorySlots`, `sataPorts`, `m2Slots`, `supportedGenerations`+, `formFactor`+ |
| `cooler` | `coolingCapacityWatts`, `supportedSockets`+ |
| `memory` | `totalCapacityGb`, `modulesPerKit`, `moduleCapacityGb`, `memoryType`+, `moduleType`+ (`DIMM`, `SODIMM`, `ECC`), `speedMhz`+ |
| `gpu` | `vramGb`+, `recommendedPsuWatts`+, `powerConnectors`+ |
| `case` | `includesPowerSupply`, `includedPsuWatts`+, `supportedFormFactors`+ |
| `power_supply` | `wattage`+, `certification`+, `pcieConnectors`+ |
| `storage` | `interface`+ (`M.2`, `SATA`), `type`+ (`NVMe`, `M.2 SATA`, `SSD SATA`, `HDD`), `capacityGb`+ |

Reglas del contrato:

- `null` significa **«no se pudo leer»**, nunca «no tiene» ni cero. Es la misma política que el manual ya aplica a `inventory.totalQty=null` y a `totalAmount=null`.
- Un atributo `null` que una regla necesita **no deja saltear ni dar por compatible** ese paso.
- `kind` se decide como hoy (código de categoría + comienzo del nombre). Un producto de la categoría «Fuentes» que no empieza con `FTE PC` no es `power_supply`.

**Implementación de referencia.** Ya escribimos ese lector y lo probamos contra todo el catálogo. Está en Python, pero son expresiones regulares y se pasan a TypeScript sin cambios de fondo:

| Archivo de nuestro repo | Qué tiene |
|---|---|
| `mcp_tienda/ingesta/formato_amn.py` | El lector: un bloque por categoría, con la expresión y un comentario de qué lee |
| `tests/test_formato_amn.py` | Un test por cada caso de este documento |
| `tests/datos/muestra_amn.json` | 53 productos reales con el resultado esperado: sirve como fixture para la versión en TypeScript |

Cobertura que logra sobre las 455 piezas que entran al armado:

| Atributo | Leído |
|---|---|
| CPU: socket, generación, video integrado | 74 de 75 |
| CPU: consumo, cooler incluido, núcleos | 75 de 75 |
| Placa: socket, memoria, ranuras, SATA, M.2, generaciones, formato | 56 de 56 |
| Memoria: tipo, capacidad, módulos, tipo de módulo | 53 de 53 |
| Discos: tipo, conexión, capacidad | 97 de 97 |
| Fuente: potencia, conectores PCIe | 36 de 36 |
| Gabinete: trae fuente o no | 63 de 63 |
| Gabinete: formatos admitidos | 59 de 63 |
| Cooler: sockets | 42 de 48 |
| Cooler: potencia de enfriamiento | 38 de 48 |
| Placa de video: fuente requerida | 23 de 27 |

Estos números dicen cuánto se pudo leer. Todavía no medimos formalmente cuánto se lee **bien** (falta etiquetar una muestra a mano); los 53 productos del fixture están revisados uno por uno.

## 5. Avisos de calidad al importar el catálogo (P11)

| | Hoy | Propuesta |
|---|---|---|
| `POST /api/admin/data-sync/preflight` | Devuelve `totals`, `files[]` y `pcBuilderImpact` (solo por SKU borrados) | Agregar `catalogQuality`: los productos del XLS subido cuyo texto no se pudo leer |
| ¿Bloquea? | `pcBuilderImpact` es informativo | Igual: informativo. Quien sube el XLS decide |
| Para qué | — | Que el error de tipeo se vea **el día que se carga**, no cuando un cliente arma una PC |

Forma sugerida:

```jsonc
"catalogQuality": {
  "checked": 509,
  "withWarnings": 23,
  "warnings": [
    { "sku": "3600XT", "kind": "cpu", "attribute": "includesGraphics",
      "code": "MARKER_FORMAT", "message": "Dice «** SIN VID»; se espera «**SIN VIDEO»." },
    { "sku": "TRL240", "kind": "cooler", "attribute": "coolingCapacityWatts",
      "code": "UNREADABLE", "message": "Falta «PODER DE ENFRIAMIENTO: <n>w»." }
  ]
}
```

Códigos que usamos nosotros: `UNREADABLE` (el dato no está donde va), `CONTRADICTION` (el nombre y la descripción dicen cosas distintas), `NO_EVIDENCE` (no hay ningún indicio) y `MARKER_FORMAT` (se entiende, pero el lector actual lo lee mal).

La lista actual de productos con aviso está en el anexo B.

## 6. Reporte de compatibilidad en el builder (P12)

| | Hoy | Propuesta |
|---|---|---|
| Qué informa un armado | `stepStates` (por qué cada paso está elegido, salteado o no aplica) y `warnings` (solo `PC_BUILD_PRODUCT_OUT_OF_STOCK`) | Agregar `compatibility.checks[]`: una entrada por regla |
| Compatibilidad | Implícita: «si el producto apareció en `options`, es compatible» | Explícita y recalculada sobre el armado completo, como ya se hace con `warnings` |
| `review.canSubmit` | Depende de `requiresReview` | También `false` si alguna regla crítica falla o es desconocida |

```jsonc
"compatibility": {
  "status": "incompatible",            // compatible | incompatible | unknown
  "checks": [
    { "rule": "CPU_MOTHERBOARD_SOCKET",     "status": "pass" },
    { "rule": "CPU_MOTHERBOARD_GENERATION", "status": "pass" },
    { "rule": "GPU_REQUIRED",               "status": "fail",
      "message": "La CPU no tiene video integrado y no hay placa de video." },
    { "rule": "PSU_WATTAGE",                "status": "unknown",
      "message": "La placa de video no informa la fuente requerida." }
  ]
}
```

Reglas que proponemos, con los datos que usa cada una:

| Regla | Compara | Crítica |
|---|---|---|
| `CPU_MOTHERBOARD_SOCKET` | socket de CPU = socket de placa | Sí |
| `CPU_MOTHERBOARD_GENERATION` | generación de CPU ∈ generaciones de la placa | Sí |
| `MEMORY_TYPE` | tipo de memoria = el de la placa, y módulo `DIMM` | Sí |
| `MEMORY_SLOTS` | módulos × cantidad ≤ ranuras | Sí |
| `GPU_REQUIRED` | si la CPU no tiene video, tiene que haber placa de video | Sí |
| `COOLER_REQUIRED` | si la CPU no trae cooler, tiene que haber uno | Sí |
| `COOLER_SOCKET` | socket de CPU ∈ sockets del cooler | Sí |
| `COOLER_CAPACITY` | potencia del cooler ≥ consumo máximo de la CPU | Sí |
| `STORAGE_PORTS` | discos M.2 ≤ ranuras M.2; discos SATA ≤ puertos SATA | Sí |
| `PSU_PRESENT` | hay fuente, propia o la del gabinete | Sí |
| `PSU_WATTAGE` | potencia de la fuente ≥ la que pide la placa de video | Sí |
| `PSU_CONNECTORS` | conectores PCIe de la fuente ≥ los que pide la placa | No (aviso) |
| `CASE_FORM_FACTOR` | formato de la placa ∈ formatos del gabinete | Sí |
| `GPU_LENGTH` | largo de la placa ≤ máximo del gabinete | No (hoy no hay datos) |

«Crítica» quiere decir: si falla o es desconocida, no se puede enviar el armado. Las no críticas se muestran como aviso con confirmación, igual que el `PC_BUILD_PRODUCT_OUT_OF_STOCK` actual.

## 7. Armar o reemplazar un armado completo (P13)

| | Hoy | Problema para el asistente | Propuesta |
|---|---|---|---|
| Crear un armado | `POST /builds` y después un `PUT /steps/:step` por pieza, en orden estricto. Un paso futuro devuelve `409 PC_BUILD_INVALID_STEP_ORDER` | El asistente propone el armado **entero** (según presupuesto y uso). Para pasarlo al builder hay que repetir de 9 a 12 llamadas en orden | Un endpoint que reciba el armado completo y lo valide en el servidor |
| Cambiar una pieza anterior | Borra todas las selecciones posteriores | «Cambiá la CPU por una más barata» obliga a rehacer todo, aunque el resto siga siendo compatible | Conservar las posteriores que sigan siendo compatibles; borrar solo las que dejan de serlo |

```jsonc
// POST /api/pc-builder/builds/import        (requiere sesión, como el resto del builder)
{
  "platform": "AMD",
  "memoryTargetGb": 16,
  "selections": [
    { "step": "cpu",          "sku": "RY5500" },
    { "step": "motherboard",  "sku": "A52DV2" },
    { "step": "memory",       "sku": "162X8G", "quantity": 1 },
    { "step": "m2_storage",   "sku": "71005G" },
    { "step": "gpu",          "sku": "2F5050" },
    { "step": "case",         "sku": "GAFTTG" },
    { "step": "power_supply", "sku": "G650NG" }
  ]
}
// → 201 con el mismo cuerpo que GET /builds/:buildId (stepStates, warnings, compatibility)
// → 422 con compatibility.checks si alguna regla crítica falla: no se crea nada
```

El asistente **nunca envía el armado** (`/submit`): eso lo hace el usuario con su clic en la página. `import` solo deja el armado cargado para que lo revise.

Si no se agrega este endpoint, la integración igual es posible: el frontend repite los pasos en orden con la lista que le da el asistente. Es más lento y más frágil, pero no bloquea.

## 8. Catálogo y resto de la API

### 8.1 Campos internos en el listado público (P14)

| | Qué dice el manual | Qué responde hoy (11/11/2026, sin sesión) |
|---|---|---|
| `GET /api/products/:term` | «Does not return pricing, inventory, costs, hidden descriptions, or internal commercial fields» | Cumple: devuelve `sku`, `name`, `desc`, `brand`, `category`, imágenes |
| `GET /api/products` y `/search` | Solo habla de enmascarar `pricepr3`, `pinpesos` y `pricing` | Cada producto trae además `hdesc`, `inbdprice`, `margenadie`, `tags`, `topsale`, `topvalue`, `bought`, `catcode` |
| `GET /api/products/top-selling` | Lista los campos «persisted product fields such as…» | Los mismos campos internos |

Por qué importa:

- `hdesc` tiene notas para el vendedor que no son para el cliente. Ejemplos reales: «CUANDO SALGA ESTE GABINETE SUMAR TECL.Y MOUSE», «COOLER MAS ECONOMICO (AMDPER) (GA300N)».
- `inbdprice` y `margenadie` son los datos con los que el PRG calcula el precio (`(priceCost+inbdPrice)*(porce+margenadie/100)*dolar`). El manual dice que el precio en dólares no se muestra en la tienda; estos dos campos permiten acercarse a deducirlo.
- `tags` trae códigos internos (`IN-0411765  SY-ID  EL-ID  PC-ID  A-36296`).

**Propuesta.** En las respuestas de la tienda devolver solo los campos del detalle, más `status` y `updatedAt`. Los internos, solo en `/api/admin/*`.

**Ojo con una dependencia.** Hoy varios datos del armado están **solo en `hdesc`**: los sockets del cooler, el consumo de algunas CPU (`IG5900`), la fuente que pide la placa de video. Si se oculta `hdesc` sin hacer antes P10, el asistente (y cualquier cliente) pierde esos datos. El orden correcto es: primero `specs`, después ocultar `hdesc`.

### 8.2 Cómo se identifica el asistente (P15)

| | Hoy | Problema | Propuesta |
|---|---|---|---|
| Precios | `pinpesos` solo con sesión. La sesión es una cookie de Better Auth; el manual dice que no hay plugin de bearer | El asistente corre en un servidor, no en un navegador. Para trabajar con presupuestos necesita precios y hoy la única forma es copiar a mano la cookie de un usuario, que vence | Una de dos (ver abajo) |

- **Opción A — credencial de servicio.** Una API key o cuenta de servicio con un permiso de solo lectura (por ejemplo `catalog.read_prices`), dentro del sistema de roles y permisos que ya existe. El asistente sincroniza el catálogo con esa credencial.
- **Opción B — el backend de la tienda le pasa los datos.** El asistente no habla con la API pública. NestJS le entrega el catálogo (con `specs` y `pinpesos`) por un endpoint interno o un volcado después de cada data-sync.

Recomendamos **A** para empezar (menos trabajo de los dos lados) y **B** si prefieren que ningún servicio externo tenga credenciales.

En los dos casos el asistente **solo lee**. No crea carritos, no envía pedidos y no toca el builder: eso lo hace el frontend con la sesión del usuario.

### 8.3 Sincronización del catálogo (P16)

| | Hoy | Propuesta |
|---|---|---|
| Traer todo | `GET /api/products?limit=100&page=N`: 43 pedidos para 4.263 productos | Sin cambios; sirve para la primera carga |
| Traer solo lo que cambió | No hay filtro por fecha. Cada producto trae `updatedAt` | `GET /api/products?updatedSince=<ISO-8601>` |
| Enterarse de un cambio | El data-sync ya avisa a Next con un webhook de revalidación | Un aviso equivalente al asistente al terminar un data-sync, para que vuelva a sincronizar |
| Productos borrados | No se pueden detectar sin traer todo | Incluirlos en la respuesta incremental, o un endpoint de SKU vigentes |

Como el catálogo cambia una vez por día (cuando se sube el Excel), al asistente le alcanza con volver a sincronizar después de cada data-sync. Lo único que hace falta de verdad es **enterarse de que terminó**: el aviso de la tercera fila. El filtro por fecha y los borrados son una mejora, no una necesidad.

El asistente responde con una copia local del catálogo de ese día. Precio y stock los vuelve a validar la tienda en el momento de cargar el armado.

### 8.4 Diferencias entre el manual y la API (P17)

| Tema | Manual | Observado | Pedido |
|---|---|---|---|
| Autenticación por cabecera | 2.2: «an `Authorization` header alone does not authenticate a request». Pero en `GET /api/products`: «Authentication sources for visibility: Session cookie, Authorization header» | No lo probamos (no tenemos credenciales) | Aclarar cuál de las dos vale |
| Inventario en el listado | «Canonical inventory on every catalog and top-selling item: `{ totalQty, intranqty, supdatedat, branches }`» | Sin sesión llega `{ totalQty, supdatedat }`, sin `intranqty` ni `branches` | Documentar si es por no tener sesión |
| Enlace al producto | No dice cuál es la URL del producto en la tienda | — | Documentar el patrón (por ejemplo `/productos/<slug>`) para que el asistente pueda devolver enlaces |
| `stocks/batch` | «uses a single-product payload shape (not array)» | — | Solo lo anotamos: el nombre sugiere un arreglo |

## 9. Qué hace el asistente mientras tanto

Nada de lo anterior bloquea al asistente. Hasta que se implemente, lo resolvemos de nuestro lado así:

| Situación | Qué hace el asistente |
|---|---|
| Atributos sin estructurar | Los lee con su propio lector al sincronizar el catálogo y los guarda en su base local |
| Dato que no se pudo leer | La regla responde «sin datos». Si es una regla crítica, el armado no se puede confirmar y el asistente se lo dice al usuario. Nunca asume que es compatible |
| Producto con aviso de carga | No lo propone en un armado si el dato dudoso es de una regla crítica |
| Producto que el builder actual no ofrecería (`A42400`, coolers sin potencia) | No lo propone mientras el armado tenga que cargarse en el builder actual: el `PUT /steps/:step` lo rechazaría |
| Compatibilidad | La verifica con reglas propias y deterministas (las de la sección 6). El modelo de lenguaje no decide compatibilidad, precios ni totales |
| `hdesc` | La usa solo para leer atributos. No la muestra, no la guarda y no se la pasa al modelo de lenguaje |
| Confirmar | No lo hace nunca. Devuelve la lista de SKU con cantidades y el usuario confirma en la página |

Cuando existan `specs` (P10), el asistente deja de leer el texto y usa los atributos de la API: una sola fuente de verdad para el builder y el asistente.

## Anexo A — Convención de carga, tal como la entendimos

Es lo que hoy siguen casi todos los productos. Si se documenta para quien carga el catálogo, los avisos del anexo B dejan de aparecer.

| Categoría | En el nombre | En la descripción |
|---|---|---|
| CPU (333) | Empieza con `CPU INTEL` o `CPU AMD`. Termina en el socket: `AM4`, `AM5`, `1200`, `1700`, `1851` | `[12va]` generación. `**SIN COOLER` y `**SIN VIDEO`, pegado. `65w` o `CONSUM.:65/117w`. `NUCLEOS: 6 - SUBPROCESOS: 12` |
| Placa madre (11) | Empieza con `MB.`. Trae `D4`/`D5`, el formato (`ATX`, `mATX`) y termina en el socket | `4 DDR4 (...)`. `CHIPSET INTEL B760 (12va,13va,14va GEN)`. `4 SATA3`. `2 M.2 PCIe` |
| Cooler | Empieza con `COOLER CPU` | `PODER DE ENFRIAMIENTO: 200w`. `SOCKET: INTEL 1200/1700 AMD AM4/AM5` |
| Memoria (90) | `16GB  DDR4,3200` (dos espacios). Notebook: `SO-DDR4`. Kit: `K2x8` | `288Pin DIMM` o `SODIMM`. Kit: `ES UN KIT DE 2 MEMORIAS` |
| Placa de video (50) | Empieza con `PL.VIDEO`. Memoria como `8G/D6/2F` | `REQUIERE FUENTE 550W+POWER 1x8pin` |
| Gabinete (180, 185, 186) | Empieza con `GAB.`. Termina en `S/FT` o en los watts de la fuente (`600W`) | `FORMATO: mATX, ATX, E-ATX`. Sin fuente: `NO INCLUYE FUENTE` |
| Fuente (145) | Empieza con `FTE PC`. Watts (`650W`) y `80+ GLD` | `4 PCIe 6+2pin` |
| Discos (93, 20) | `D.SSD  M.2 PCIe`, `D.SSD  M.2 SATA3`, `D.SSD  2,5"`, `D.DURO SATA3`, y la capacidad (`1TB`) | `CAPACIDAD: 1TB` |

## Anexo B — Productos para corregir en el catálogo (11/11/2026)

27 avisos sobre 455 piezas. Se regenera con `uv run python -m evaluacion.calidad_catalogo`.

Estas correcciones van **en el sistema de origen** (donde se carga el catálogo), no en la base de la tienda: lo que se corrija ahí se pierde con el Excel del día siguiente.

**El lector actual (3PC.PRG) los lee mal — corregir primero**

| SKU | Producto | Qué pasa | Corrección |
|---|---|---|---|
| `3600XT` | CPU AMD RYZEN 5 3600XT S/VID AM4 | Dice `** SIN VIDEO`: figura como CPU con video | Escribir `**SIN VIDEO` pegado |
| `CP0587` | COOLER CPU TT FRIO EXTREM 250W | `1200` de las rpm se toma por socket LGA1200 | Escribir la velocidad sin ese número suelto, por ejemplo `1200-1800rpm` |
| `A42400` | 4GB DDR4,2400 1Rx16 ADATA | Un solo espacio antes de `DDR`: no se ofrece | Dos espacios: `4GB  DDR4,2400` |
| `4240MV` | 4GB DDR4,2400 MARKVISION | Igual | Igual |

**Falta un dato**

| Categoría | SKU | Falta |
|---|---|---|
| Cooler | `BXTS15`, `COA1V4`, `E97379`, `HPE821`, `KRL120`, `NCO115`, `NK85TZ`, `TRL240`, `TRL360`, `VENTP4` | `PODER DE ENFRIAMIENTO: <n>w` — hoy no se ofrecen para ninguna CPU |
| Cooler | `HPE821`, `VENTP4` | Renglón `SOCKET:` |
| Placa de video | `ARX550`, `G21OEM`, `R5501F`, `VCP620` | `REQUIERE FUENTE <n>W` |
| Gabinete | `6810CK`, `GK6810`, `S2U550`, `A4U450` | Renglón `FORMATO:` (los dos últimos son rackeables) |
| CPU | `H5416S` (Xeon) | Socket al final del nombre, `[generación]` y si tiene video |
