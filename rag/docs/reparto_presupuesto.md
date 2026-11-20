# Reparto del presupuesto por componente

> **Título:** Reparto del presupuesto por componente  
> **Fecha:** 2026-11-20  
> **Fuente:** precios del catálogo de Todo Computación al 2026-11-20 (508 piezas de PC, productos con y sin stock (la tienda también vende a pedido)). Calculado con `evaluacion/reparto_presupuesto.py`; no usa precios de internet.

## Para qué sirve

Dice qué parte del presupuesto de una PC se lleva cada componente, según la gama. Sirve para repartir un presupuesto antes de elegir las piezas: con cuánto buscar el procesador, la placa de video, la memoria, etc.

Los porcentajes son orientativos. Salen de armar miles de PCs compatibles con productos reales de la tienda y medir cuánto pesa cada pieza en el total. El primer número es el valor típico; entre paréntesis, el rango habitual. Cambian cuando cambian los precios: la fecha de arriba dice de cuándo son.

## Reparto del presupuesto en gama baja

Gama baja: procesador con video integrado, 8 GB DDR4, sin placa de video. Una PC de gama baja en la tienda cuesta típicamente $ 998.000 (entre $ 919.000 y $ 1.119.000).

Porcentaje del presupuesto por componente en gama baja:

- Gama baja, placa de video: 0 % (usa el video integrado del procesador)
- Gama baja, memoria ram: 26 % (entre 22 % y 30 %)
- Gama baja, procesador: 14 % (entre 11 % y 21 %)
- Gama baja, placa madre: 16 % (entre 13 % y 22 %)
- Gama baja, disco (ssd m.2 nvme o ssd 2,5"): 21 % (entre 17 % y 25 %)
- Gama baja, disco secundario (ssd 2,5" o hdd): 0 %
- Gama baja, fuente: 9 % (entre 5 % y 11 %)
- Gama baja, gabinete: 8 % (entre 7 % y 9 %)
- Gama baja, cooler: 0 % (usa el cooler que trae el procesador)

## Reparto del presupuesto en gama media

Gama media: 16 GB de memoria y placa de video de entrada. Una PC de gama media en la tienda cuesta típicamente $ 2.762.000 (entre $ 2.488.000 y $ 3.035.000).

Porcentaje del presupuesto por componente en gama media:

- Gama media, placa de video: 26 % (entre 20 % y 31 %)
- Gama media, memoria ram: 23 % (entre 20 % y 26 %)
- Gama media, procesador: 13 % (entre 11 % y 16 %)
- Gama media, placa madre: 7 % (entre 6 % y 10 %)
- Gama media, disco (ssd m.2 nvme o ssd 2,5"): 21 % (entre 16 % y 27 %)
- Gama media, disco secundario (ssd 2,5" o hdd): 0 %
- Gama media, fuente: 4 % (entre 2 % y 5 %)
- Gama media, gabinete: 4 % (entre 3 % y 5 %)
- Gama media, cooler: 0 % (usa el cooler que trae el procesador)

## Reparto del presupuesto en gama alta

Gama alta: 32 GB DDR4 o DDR5 y placa de video media o alta. Una PC de gama alta en la tienda cuesta típicamente $ 5.799.000 (entre $ 5.274.000 y $ 6.349.000).

Porcentaje del presupuesto por componente en gama alta:

- Gama alta, placa de video: 25 % (entre 22 % y 29 %)
- Gama alta, memoria ram: 23 % (entre 20 % y 25 %)
- Gama alta, procesador: 14 % (entre 11 % y 18 %)
- Gama alta, placa madre: 4 % (entre 4 % y 6 %)
- Gama alta, disco (ssd m.2 nvme o ssd 2,5"): 14 % (entre 10 % y 18 %)
- Gama alta, disco secundario (ssd 2,5" o hdd): 6 % (entre 5 % y 11 %)
- Gama alta, fuente: 3 % (entre 3 % y 4 %)
- Gama alta, gabinete: 3 % (entre 2 % y 5 %)
- Gama alta, cooler: 2 % (entre 1 % y 2 %)

## Reparto del presupuesto en gama premium

Gama premium: 64 GB DDR5 y placa de video RTX serie 50 de las más potentes. Una PC de gama premium en la tienda cuesta típicamente $ 9.324.000 (entre $ 8.824.000 y $ 9.978.000).

Porcentaje del presupuesto por componente en gama premium:

- Gama premium, placa de video: 23 % (entre 21 % y 29 %)
- Gama premium, memoria ram: 30 % (entre 28 % y 33 %)
- Gama premium, procesador: 15 % (entre 13 % y 16 %)
- Gama premium, placa madre: 5 % (entre 5 % y 6 %)
- Gama premium, disco (ssd m.2 nvme o ssd 2,5"): 12 % (entre 9 % y 14 %)
- Gama premium, disco secundario (ssd 2,5" o hdd): 4 % (entre 3 % y 7 %)
- Gama premium, fuente: 3 % (entre 2 % y 3 %)
- Gama premium, gabinete: 3 % (entre 2 % y 4 %)
- Gama premium, cooler: 2 % (entre 1 % y 2 %)

## Cómo usar el reparto

1. Ubicar el pedido en una gama (ver `gamas.md`).
2. Multiplicar el presupuesto por el porcentaje típico de cada componente: ese es el precio de referencia para buscar esa pieza.
3. Si una pieza sale más barata, lo que sobra conviene pasarlo al componente que más pesa en esa gama.
4. El total real lo calcula la tienda al armar: el reparto es solo una guía para empezar.

## Qué se consideró en cada gama

- Gama baja: Celeron, Pentium, Core i3 o Ryzen 3 con video integrado; 8 GB DDR4; disco de 240 a 512 GB (SSD M.2 NVMe o SSD 2,5"); fuente de 500 a 600 W; gabinete económico.
- Gama media: Core i5 o Ryzen 5; 16 GB; disco M.2 NVMe de 512 GB a 1 TB; placa de video GTX 1650, RTX 3050, RX 580, RX 7600 o RTX 5050.
- Gama alta: Core i7, Core i9, Ryzen 7 o Ryzen 9 con memoria DDR4 o DDR5; 32 GB; disco M.2 NVMe de 1 a 2 TB (el disco secundario SSD 2,5" o HDD no entra en el reparto); placa de video RTX 5060, RTX 5060 Ti o RTX 5070; fuente certificada; cooler aparte.
- Gama premium: Core Ultra 9 o Ryzen 9 9900X / 9950X; 64 GB DDR5; disco de 2 TB; placa de video RTX 5070 o RTX 5070 Ti; fuente certificada de 750 W o más; cooler de los más potentes.

En todos los casos las piezas son compatibles entre sí: mismo socket y generación, memoria del tipo de la placa madre, fuente que cubre lo que pide la placa de video y gabinete donde entra la placa madre.
