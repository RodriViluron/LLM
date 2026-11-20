# Guía de compatibilidad

> **Título:** Guía de compatibilidad entre piezas de PC  
> **Fecha:** 2026-11-19  
> **Fuente:** elaboración propia del Grupo 10. Las reglas y los números salen del verificador del armado (`mcp_tienda/armado/reglas.py`).  
> **Estado:** borrador para revisar con el grupo y la tienda.

<!-- Documento 4. Dice lo mismo que las reglas del código: el agente explica con este documento y verifica con las reglas. La sección «Números que usa el verificador» se genera desde el código; no editarla a mano. -->

## Cómo se revisa que las piezas sean compatibles

Cada vez que se agrega o se cambia una pieza, la tienda revisa el armado con reglas fijas. Cada regla da uno de tres resultados: **cumple**, **no cumple** o **sin datos**. «Sin datos» quiere decir que el producto no informa el dato que hace falta: no se puede asegurar que sea compatible, y no se asume que lo sea.

Hay reglas **críticas** (si no se pueden verificar, la PC podría no funcionar) y **avisos** (conviene revisarlos, pero no impiden confirmar). El pedido solo se puede confirmar si ninguna regla da «no cumple» y ninguna regla crítica da «sin datos».

## Procesador y motherboard: socket y generación

El socket es el zócalo donde se monta el procesador. El procesador y la motherboard tienen que usar el mismo socket: AM4 y AM5 son de AMD; LGA1200, LGA1700 y LGA1851 son de Intel.

El mismo socket no alcanza: cada motherboard soporta algunas generaciones de procesador. Por ejemplo, una placa A620 para AM5 no soporta todas las generaciones de ese socket. La tienda indica en cada placa qué generaciones admite, y el procesador tiene que estar entre ellas.

## Memoria RAM: tipo, formato y ranuras

- **Tipo:** DDR4 y DDR5 no son intercambiables. La memoria tiene que ser del tipo que admite la placa.
- **Formato:** una PC de escritorio usa módulos **DIMM**. Los módulos SODIMM son de notebook y los ECC son de servidor: no sirven para este armado, aunque digan DDR4 o DDR5.
- **Ranuras:** cada módulo ocupa una ranura de la placa. Un kit de 2x8 GB son dos módulos. Si se piden dos unidades de un kit de 2x8 GB, son cuatro módulos y hacen falta cuatro ranuras. Las placas chicas suelen tener dos.

## Discos: ranuras M.2 y puertos SATA

Los discos se conectan a la motherboard de dos formas:

- **M.2:** los SSD NVMe van en una ranura M.2 de la placa. Cada disco M.2 ocupa una ranura.
- **SATA:** los SSD de 2,5" y los discos rígidos (HDD) van a un puerto SATA. Cada disco ocupa un puerto.

La cantidad de discos de cada tipo no puede superar las ranuras M.2 y los puertos SATA de la placa. Un SSD «M.2 SATA» va en una ranura M.2, pero no todas las ranuras M.2 lo admiten y el catálogo no dice cuáles: por eso da «sin datos» y hay que consultarlo.

## Placa de video y video integrado

Si el procesador no tiene video integrado (por ejemplo, los Intel terminados en F y algunos Ryzen), la PC necesita una placa de video sí o sí: sin ella no hay imagen. Si el procesador tiene video integrado, la placa de video es opcional.

## Cooler: incluido o aparte

Algunos procesadores vienen con su cooler y otros no (en la tienda se indica «sin cooler»). Si el procesador no lo trae, hay que agregar uno. El cooler tiene que:

- soportar el socket del procesador;
- disipar al menos lo que consume el procesador a máxima carga (consumo máximo, no el TDP).

## Fuente: cuánta potencia hace falta

La fuente puede ser una fuente aparte o la que trae el gabinete. La potencia necesaria es la más alta de estas dos:

1. **La cuenta del consumo:** consumo máximo del procesador, más el consumo de la placa de video si se conoce, más un consumo fijo para el resto de la PC (motherboard, memoria, discos y ventiladores), con un margen de seguridad.
2. **Lo que recomienda el fabricante de la placa de video** («requiere fuente de 550 W»): es la fuente para toda la PC.

Si hay placa de video y no se conoce ni su consumo ni la fuente que recomienda, no se puede calcular: da «sin datos».

**Conectores de la placa de video (aviso):** muchas placas de video necesitan cables de energía de 6 u 8 pines que salen de la fuente. Se compara lo que pide la placa con los conectores que tiene la fuente. Las placas con conector de 16 pines no se pueden revisar así, y la fuente de un gabinete no informa sus conectores: en esos casos es un aviso para consultar.

## Gabinete: formato y largo de la placa de video

- **Formato:** el gabinete tiene que admitir el formato de la motherboard. De más grande a más chico: E-ATX, ATX, Micro-ATX y Mini-ITX. Un gabinete admite su formato y los más chicos.
- **Largo de la placa de video (aviso):** la placa de video tiene que entrar en el gabinete. El catálogo casi nunca informa estos largos, así que es un aviso para consultar, no impide confirmar.

## Números que usa el verificador

<!-- GUIA: INICIO (generado desde mcp_tienda/armado/reglas.py: no editar a mano) -->

- Margen de la fuente: **30 %** por encima del consumo estimado.
- Consumo fijo del resto de la PC: **75 W** (motherboard, memoria, discos, ventiladores y USB).
- Ejemplo sin placa de video: procesador de 117 W → (117 + 75) × 1,30 = **250 W** como mínimo.
- Ejemplo con placa de video que recomienda 550 W: hace falta la más alta entre 250 W y 550 W → **550 W**.
- Formato de memoria para PC de escritorio: **DIMM**.
- Sockets que se arman: **AM4, AM5, LGA1200, LGA1700 y LGA1851**.
- Unidades por lugar: hasta **4** de memoria y de cada disco.
- Reglas críticas: socket, generación, tipo de memoria, formato de memoria, ranuras de memoria, ranuras y puertos de discos, video, cooler incluido, socket del cooler, potencia del cooler, potencia de la fuente y formato del gabinete.
- Avisos: largo de la placa de video y conectores de energía de la placa de video.

<!-- GUIA: FIN -->
