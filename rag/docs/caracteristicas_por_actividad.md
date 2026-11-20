# Características por actividad

> **Título:** Características por actividad  
> **Fecha:** 2026-11-19  
> **Fuente:** elaboración propia del Grupo 10, a partir de `gamas.md` y del reparto del presupuesto de la tienda. La sección «Perfiles de uso» se genera desde `datos/entrevista_armado.yaml`.  
> **Estado:** borrador para revisar con el grupo y la tienda.

<!-- Documento 2. Para cada actividad: qué componente pesa más, mínimos razonables y a qué gama y perfil de uso corresponde. Lo que diga acá tiene que coincidir con datos/entrevista_armado.yaml. -->

## Qué componente pesa en cada actividad

No todas las actividades necesitan lo mismo. Para saber qué PC conviene, no hace falta saber de componentes: alcanza con contar para qué se va a usar. Con eso se elige la gama y en qué piezas conviene poner más presupuesto. La placa madre, la fuente y el cooler no se eligen por la actividad sino por lo que necesitan las demás piezas (ver «Cómo se eligen la placa madre, la fuente y el cooler»).

## Oficina y estudio

Navegar, usar Word y Excel, hacer videollamadas y cursar clases virtuales no exige mucho. Lo que más se nota es que el disco sea un SSD (la PC arranca y abre los programas rápido) y tener memoria suficiente para varias pestañas abiertas. No hace falta placa de video: alcanza con el video integrado del procesador. Corresponde a una PC de gama baja con 8 GB de RAM; con 16 GB va más holgada si se usan muchas pestañas o programas a la vez.

## Juegos

En los juegos manda la placa de video: es la que dibuja cada imagen. El procesador acompaña y la memoria evita tirones. La resolución del monitor es lo que más cambia lo que hace falta: cuantos más píxeles, más placa de video. Si el usuario nombra un juego, se buscan sus requisitos y la gama sale de la tabla de referencia de CPU y GPU.

### Juegos en 1080p

Un monitor común (1080p o Full HD) es lo más habitual. La mayoría de los juegos actuales andan bien con una PC de gama media: placa de video de entrada (por ejemplo GTX 1650, RTX 3050, RX 7600 o RTX 5050), procesador Core i5 o Ryzen 5 y 16 GB de RAM. Los juegos competitivos livianos (Valorant, League of Legends, Fortnite en calidad media) piden todavía menos.

### Juegos en 1440p

Un monitor 2K (1440p) tiene casi el doble de píxeles que uno de 1080p, así que la placa de video trabaja mucho más. Corresponde a una PC de gama alta: placa de video como la RTX 5060 o la RTX 5060 Ti, procesador Core i7 o Ryzen 7 y 32 GB de RAM. También sirve para jugar en 1080p con muchos cuadros por segundo, para monitores de 144 Hz o más.

### Juegos en 4K

Jugar en 4K con calidad alta es lo más exigente: cuatro veces los píxeles de 1080p. Corresponde a una PC de gama premium: las placas de video más potentes de la tienda (RTX 5070 o RTX 5070 Ti), procesadores Core Ultra 9 o Ryzen 9 y mucha memoria. Si el monitor es 4K pero se juega en una resolución menor, puede alcanzar con la gama alta.

## Diseño gráfico

Photoshop, Illustrator y AutoCAD usan mucho la memoria (sobre todo con archivos grandes o muchas capas) y el procesador. La placa de video ayuda a mover el lienzo y los modelos 3D con fluidez, pero no hace falta una de las más caras. Corresponde a una PC de gama media con más memoria de lo habitual: 32 GB. Para render 3D pesado o arquitectura con escenas muy grandes conviene la gama alta.

## Edición de video

Editar y exportar video usa todos los núcleos del procesador, mucha memoria y un disco rápido: los archivos de video son pesados. La placa de video acelera los efectos y la exportación. Corresponde a una PC de gama alta con 32 GB de RAM y un SSD NVMe de 1 TB o más; si se guardan muchos proyectos, conviene un segundo disco para archivo.

## Programación

Programar no exige placa de video salvo que se hagan juegos o inteligencia artificial. Lo que más importa es la memoria (el editor, el navegador, Docker y las máquinas virtuales la consumen) y un SSD para compilar rápido. Corresponde a una PC de gama baja con 16 GB de RAM; con máquinas virtuales o proyectos grandes conviene la gama media.

## Streaming

Jugar y transmitir al mismo tiempo (Twitch, YouTube) suma trabajo: además del juego, hay que codificar el video que se transmite. Lo hace la placa de video o el procesador, según cómo se configure OBS. Corresponde a una PC de gama alta con 32 GB de RAM, para que el juego no pierda fluidez mientras se transmite.

## Cómo se eligen la placa madre, la fuente y el cooler

Estas piezas no se eligen por la actividad sino por lo que necesitan las demás:
- La placa madre tiene que tener el mismo socket que el procesador y el tipo de memoria (DDR4 o DDR5) que se elija. Si el usuario piensa mejorar la PC más adelante, conviene una placa con cuatro ranuras de memoria y dos o más ranuras M.2 para discos.
- La fuente se elige por el consumo del procesador y de la placa de video, con margen. Si se piensa cambiar la placa de video por una más potente, conviene un margen mayor.
- El cooler: muchos procesadores traen uno que alcanza. Los que no lo traen, o los de mucho consumo, necesitan uno aparte.

La compatibilidad la verifica la tienda con reglas (ver la guía de compatibilidad).

## Perfiles de uso

<!-- PERFILES: INICIO (generado desde datos/entrevista_armado.yaml: no editar a mano) -->

Estos perfiles son un **borrador** para revisar con el grupo y la tienda.

Cada pedido se ubica en uno de estos perfiles según para qué se va a usar la PC. El perfil decide la gama y en qué componentes conviene poner más presupuesto.

### Perfil Oficina y estudio: gama baja

Perfil Oficina y estudio: una PC de gama baja, con 8 GB de RAM y sin placa de video (usa el video integrado del procesador).
- Dónde conviene poner más presupuesto: disco, memoria RAM.
- Alcanza para: navegar, ofimática, videollamadas, clases virtuales y ver videos.
- No alcanza para: juegos actuales ni edición de video.
- Ejemplos: Word, Excel, navegador, Zoom, Meet, Teams.

### Perfil Programación: gama baja

Perfil Programación: una PC de gama baja, con 16 GB de RAM y sin placa de video (usa el video integrado del procesador).
- Dónde conviene poner más presupuesto: memoria RAM, procesador, disco.
- Alcanza para: programar, compilar proyectos medianos y usar varias herramientas a la vez.
- No alcanza para: entrenar modelos de inteligencia artificial ni juegos actuales.
- Ejemplos: Visual Studio Code, Docker, IntelliJ, máquinas virtuales.

### Perfil Juegos en 1080p: gama media

Perfil Juegos en 1080p: una PC de gama media, con 16 GB de RAM y con placa de video dedicada.
- Dónde conviene poner más presupuesto: placa de video, memoria RAM, procesador.
- Alcanza para: la mayoría de los juegos actuales en un monitor común (1080p) con calidad media o alta.
- No alcanza para: jugar en 1440p o 4K con calidad alta.
- Ejemplos: Fortnite, Valorant, League of Legends, Minecraft, EA FC.

### Perfil Juegos en 1440p: gama alta

Perfil Juegos en 1440p: una PC de gama alta, con 32 GB de RAM y con placa de video dedicada.
- Dónde conviene poner más presupuesto: placa de video, procesador, memoria RAM.
- Alcanza para: juegos actuales en un monitor 2K (1440p) o en 1080p con muchos cuadros por segundo.
- No alcanza para: jugar en 4K con calidad alta.
- Ejemplos: Cyberpunk 2077, God of War Ragnarök, Call of Duty.

### Perfil Juegos en 4K: gama premium

Perfil Juegos en 4K: una PC de gama premium, con 64 GB de RAM y con placa de video dedicada.
- Dónde conviene poner más presupuesto: placa de video, procesador, memoria RAM.
- Alcanza para: juegos actuales en 4K con calidad alta.
- No alcanza para: nada habitual: es lo más potente que arma la tienda.
- Ejemplos: juegos actuales en un televisor o monitor 4K.

### Perfil Diseño gráfico: gama media

Perfil Diseño gráfico: una PC de gama media, con 32 GB de RAM y con placa de video dedicada.
- Dónde conviene poner más presupuesto: memoria RAM, procesador, placa de video.
- Alcanza para: Photoshop, Illustrator, AutoCAD y modelado 3D liviano.
- No alcanza para: render 3D pesado o arquitectura con escenas muy grandes.
- Ejemplos: Photoshop, Illustrator, AutoCAD, SketchUp, Lumion.

### Perfil Edición de video: gama alta

Perfil Edición de video: una PC de gama alta, con 32 GB de RAM y con placa de video dedicada.
- Dónde conviene poner más presupuesto: procesador, memoria RAM, disco, placa de video.
- Alcanza para: editar video en 1080p y 4K, y exportar sin esperar demasiado.
- No alcanza para: producción profesional de 8K o efectos muy pesados.
- Ejemplos: Premiere Pro, DaVinci Resolve, After Effects, CapCut.

### Perfil Jugar y transmitir (streaming): gama alta

Perfil Jugar y transmitir (streaming): una PC de gama alta, con 32 GB de RAM y con placa de video dedicada.
- Dónde conviene poner más presupuesto: procesador, placa de video, memoria RAM.
- Alcanza para: jugar y transmitir al mismo tiempo en Twitch o YouTube.
- No alcanza para: transmitir en 4K con calidad alta.
- Ejemplos: OBS, Twitch, YouTube, Discord.

<!-- PERFILES: FIN -->
