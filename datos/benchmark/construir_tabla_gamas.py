"""Arma rag/docs/tabla_cpu_gpu_por_gama.md a partir de los rankings de Tom's Hardware.

Uso:
    python construir_tabla_gamas.py GPU_Benchmarks.xlsx CPU_Benchmarks_1.xlsx [salida_dir] [tabla_anterior.md]

Entradas: las planillas con las tablas copiadas de (CPU_Benchmarks_1.xlsx incluye la hoja legacy '2020-2022')
  - https://www.tomshardware.com/reviews/gpu-hierarchy,4388.html  (actualizada 24/06/2026)
  - https://www.tomshardware.com/reviews/cpu-hierarchy,4312.html  (actualizada 05/10/2026)

Salidas: tabla_cpu_gpu_por_gama.md (la que lee gamas.py) y gamas_trazabilidad.csv
(de dónde sale cada número, qué es estimado y qué quedó afuera).

Los cortes de gama son lo único "decidido" por el grupo: están abajo, en un solo lugar.
"""

import re
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

# ----------------------------------------------------------------- cortes de gama
# Definidos por el Grupo 10 para alinear con los ejemplos de componentes de gamas.md.
# GPU se clasifica por fps reales a 1440p Ultra (Tom's Hardware).
GPU_BAJA_FPS_1440 = 42        # < 42 = baja (deja RTX 5050 / RX 7600 / RTX 4060 en media)
GPU_ALTA_FPS_1440 = 58        # >= 58 = alta (pone RTX 5060 / 5060 Ti y superiores en alta)
FPS_1080_JUGABLE = 60         # se mantiene solo como referencia histórica; ya no se usa para el corte
CPU_BAJA = 50                 # puntaje gamer (9850X3D = 100): menos de la mitad del mejor
CPU_ALTA = 75

FECHA_GPU, FECHA_CPU = "24/06/2026", "05/10/2026"


# ----------------------------------------------------------------- utilidades
def parse_pct_fps(celda):
    """'78.0% (158.9)' o '78.0% (158.9fps)' -> (78.0, 158.9). Celdas rotas -> (nan, nan)."""
    m = re.match(r"\s*([\d.]+)%\s*\(([\d.]+)", str(celda))
    return (float(m[1]), float(m[2])) if m else (np.nan, np.nan)


def nombre_gpu(nombre):
    """'GeForce RTX 4070 Ti Super' -> 'RTX 4070 Ti SUPER' (como figura en los productos, sin marca)."""
    n = nombre.strip()
    if n != "Radeon VII":
        n = re.sub(r"^(GeForce|Radeon|Intel)\s+(?=\S)", "", n)
    n = re.sub(r"\s+\d+GB$", "", n)       # variantes de VRAM se unifican en un solo modelo
    n = re.sub(r"\s+GDDR6$", "", n)
    return re.sub(r"\bSuper\b", "SUPER", n)


def nombre_cpu(nombre):
    n = re.sub(r"\s*\(\$[\d,]+\)", "", str(nombre))   # "(\$500)"
    n = re.sub(r"\s*/.*$", "", n)                        # "/ 105W TDP"
    n = re.sub(r"\s*\(DDR4.*\)", "", n).strip()
    return {"Ryzen 9 9700X": "Ryzen 7 9700X", "Ryzen 7 7900X3D": "Ryzen 9 7900X3D"}.get(n, n)  # error de tipeo en la fuente


def num_cpu(v):
    s = str(v).split("/")[0].strip().replace("%", "")
    try:
        f = float(s)
    except ValueError:
        return np.nan
    return f * 100 if f <= 1.0 and "%" not in str(v) else f


# ----------------------------------------------------------------- GPU
def cargar_gpu(ruta):
    x = pd.ExcelFile(ruta)
    a = x.parse(0, header=1)       # 2026: % relativo a la RTX 5090
    nuevo = pd.DataFrame({"original": a.iloc[:, 0], "modelo": a.iloc[:, 0].map(nombre_gpu)})
    for col, k in [(2, "1080"), (3, "1440")]:
        t = a.iloc[:, col].map(parse_pct_fps)
        nuevo[f"p{k}"], nuevo[f"f{k}"] = [v[0] for v in t], [v[1] for v in t]
    b = x.parse(2, header=0)       # 2022-2024: % relativo a la RTX 4090, otra batería de juegos
    viejo = pd.DataFrame({"original": b.iloc[:, 0], "modelo": b.iloc[:, 0].map(nombre_gpu)})
    for col, k in [(1, "1080"), (3, "1440")]:
        t = b.iloc[:, col].map(parse_pct_fps)
        viejo[f"p{k}"] = [v[0] for v in t]
    return nuevo, viejo


def clasificar_gpu(fps, baja, alta):
    return "alta" if fps >= alta else ("media" if fps >= baja else "baja")


def armar_gpu(nuevo, viejo):
    ref1440 = nuevo.loc[nuevo.p1440.idxmax(), "f1440"]            # fps de la RTX 5090 a 1440p
    ratio = (nuevo.f1440 / nuevo.f1080)[(nuevo.f1080 > 45) & (nuevo.f1080 < 100)].median()
    baja = GPU_BAJA_FPS_1440                                   # corte fijo definido por el grupo
    # Una fila por modelo; si hay variantes de VRAM se toma la más lenta (criterio conservador).
    nm = nuevo.sort_values("f1440").groupby("modelo", as_index=False).first()
    vm = viejo.groupby("modelo", as_index=False).min(numeric_only=True)
    # Puente entre escalas: log-log sobre las placas medidas en ambas pruebas (1440p).
    sol = nm.merge(vm, on="modelo", suffixes=("_n", "_o")).dropna(subset=["p1440_n", "p1440_o"])
    k, c = np.polyfit(np.log(sol.p1440_o), np.log(sol.p1440_n), 1)
    res = np.log(sol.p1440_n) - (k * np.log(sol.p1440_o) + c)
    r2, sd = 1 - res.var() / np.log(sol.p1440_n).var(), res.std(ddof=2)
    # 1440p faltante en la prueba vieja: se completa desde 1080p (misma prueba, relación estable).
    d = vm.dropna(subset=["p1080", "p1440"])
    k2, c2 = np.polyfit(np.log(d.p1080), np.log(d.p1440), 1)

    filas = []
    for _, r in nm.iterrows():
        filas.append(dict(componente="gpu", modelo=r.modelo, origen="medido 2026", p=r.p1440, fps=r.f1440,
                          fuente=r.original))
    for _, r in vm.iterrows():
        if r.modelo in set(nm.modelo):
            continue
        p_old, origen = r.p1440, "estimado desde 2022-2024"
        if np.isnan(p_old):
            if np.isnan(r.p1080):
                continue                                  # sin 1080p ni 1440p: no hay base para estimar
            p_old, origen = np.exp(k2 * np.log(r.p1080) + c2), "estimado desde 2022-2024 (1440p inferido de 1080p)"
        p = float(np.exp(k * np.log(p_old) + c))
        filas.append(dict(componente="gpu", modelo=r.modelo, origen=origen, p=p, fps=p / 100 * ref1440,
                          fuente=r.modelo))
    t = pd.DataFrame(filas)
    t["gama"] = [clasificar_gpu(f, baja, GPU_ALTA_FPS_1440) for f in t.fps]
    est = t.origen.str.startswith("estimado")
    margen = np.exp(sd)                                      # error multiplicativo (1 desvío)
    cerca = lambda f: any(f / margen < corte <= f * margen for corte in (baja, GPU_ALTA_FPS_1440))
    t["en_el_borde"] = [bool(e and cerca(f)) for e, f in zip(est, t.fps)]
    meta = dict(n_sol=len(sol), r2=r2, sd=sd, k=k, c=c, ref1440=ref1440, ratio=ratio, baja=baja)
    return t.sort_values("p", ascending=False), meta


# ----------------------------------------------------------------- CPU
SOLO_ESCRITORIO = re.compile(r"Threadripper|Xeon|Zhaoxin|A10-|W-3175X")   # workstation / no se vende en tiendas de PC
DIVIDIDOS = {"Core i5-9400 / i5-9400F": ["Core i5-9400", "Core i5-9400F"],
             "Core i9-9900K / F": ["Core i9-9900K", "Core i9-9900KF"],
             "Core i3-8350K / -8350KF": ["Core i3-8350K", "Core i3-8350KF"],
             "Core i7-10700/F": ["Core i7-10700", "Core i7-10700F"]}


def nombres_cpu_legacy(crudo):
    n = re.sub(r"^\$\d+\s*-\s*", "", str(crudo).strip())                 # "$589 - "
    n = re.sub(r"^(Intel|AMD)\s+", "", n)
    n = re.sub(r"\s*\((ABT|GM)[^)]*\)|\s+DDR[45]\s*/\s*DDR[45]|\*", "", n).strip()
    return DIVIDIDOS.get(n, [n])


def leer_legacy(ruta):
    """Hoja '2020-2022': dos tablas de juegos con referencias distintas.
    A (2023): relativa al i9-13900K.  B (2020-2022): relativa al i9-12900K con DDR4. '~' = Tom's no publicó puntaje."""
    h = pd.read_excel(ruta, sheet_name="2020-2022", header=None)
    cab = [i for i in range(len(h)) if str(h.iloc[i, 1]).strip() == "1080p Gaming Score"]
    bloques, sin = [], []
    for ini in cab[:2]:
        filas, i = [], ini + 1
        while i < len(h) and pd.notna(h.iloc[i, 0]) and not str(h.iloc[i, 0]).startswith("Legacy"):
            crudo, v = h.iloc[i, 0], h.iloc[i, 1]
            for n in nombres_cpu_legacy(crudo):
                p = num_cpu(v)
                if np.isnan(p):
                    sin.append(n)
                elif not SOLO_ESCRITORIO.search(n):
                    filas.append((n, p, str(crudo)))
            i += 1
        bloques.append(pd.DataFrame(filas, columns=["modelo", "p", "fuente"]).drop_duplicates("modelo"))
    return bloques[0], bloques[1], sorted(set(sin))


def armar_cpu(ruta):
    y = pd.ExcelFile(ruta)
    g = y.parse(0, header=1)
    t = pd.DataFrame({"componente": "cpu", "modelo": g.iloc[:, 0].map(nombre_cpu), "p": g.iloc[:, 2].map(num_cpu)})
    t = t.dropna(subset=["p"])
    t["fps"], t["sd"] = np.nan, 0.0
    t["origen"] = "medido 2026 (1080p, RTX 5090, 17 juegos)"
    t["fuente"] = t.modelo
    n_medidos = len(t)
    medidos = dict(zip(t.modelo, t.p))

    A, B, sin_legacy = leer_legacy(ruta)
    pa = dict(zip(A.modelo, A.p))
    pb = dict(zip(B.modelo, B.p))
    # Las tres tablas son "% del mejor CPU de su prueba", así que se pasan de una a otra con un factor
    # proporcional (la mediana de los cocientes de los CPU que están en las dos).
    rA = {m: medidos[m] / pa[m] for m in pa if m in medidos}                    # A -> 2026
    fA, sdA = float(np.median(list(rA.values()))), float(np.std(np.log(list(rA.values())), ddof=1))
    anclas = {m: medidos[m] / pb[m] for m in pb if m in medidos}                 # B -> 2026 directo
    anclas |= {m: fA * pa[m] / pb[m] for m in pb if m in pa and m not in medidos}  # B -> A -> 2026
    fB, sdB = float(np.median(list(anclas.values()))), float(np.std(np.log(list(anclas.values())), ddof=1))

    extra = []
    for m, p in pa.items():
        if m not in medidos:
            extra.append(dict(modelo=m, p=fA * p, sd=sdA, fuente=m, origen="estimado desde tabla legacy 2023 (ref. i9-13900K)"))
    for m, p in pb.items():
        if m not in medidos and m not in pa:
            extra.append(dict(modelo=m, p=fB * p, sd=sdB, fuente=m, origen="estimado desde tabla legacy 2020-2022 (ref. i9-12900K)"))
    e = pd.DataFrame(extra)
    e["componente"], e["fps"] = "cpu", np.nan
    t = pd.concat([t, e], ignore_index=True)
    t["gama"] = ["alta" if p >= CPU_ALTA else ("media" if p >= CPU_BAJA else "baja") for p in t.p]
    est = t.origen.str.startswith("estimado")
    t["en_el_borde"] = [bool(es and any(p / np.exp(sd) < c <= p * np.exp(sd) for c in (CPU_BAJA, CPU_ALTA)))
                        for es, p, sd in zip(est, t.p, t.sd)]
    meta = dict(n_medidos=n_medidos, nA=len(rA), fA=fA, sdA=sdA, nB=len(anclas), fB=fB, sdB=sdB,
                anclas_B={m: round(v, 3) for m, v in anclas.items()}, rA={m: round(v, 3) for m, v in rA.items()})
    apps = set()
    for hoja in (1, 2):
        apps |= {nombre_cpu(n) for n in y.parse(hoja, header=1).iloc[:, 0]}
    sin = sorted(n for n in (apps | set(sin_legacy)) - set(t.modelo) if not SOLO_ESCRITORIO.search(n))
    return t.sort_values("p", ascending=False), sin, meta


# ----------------------------------------------------------------- salida
def tabla_md(df, comp):
    out = ["| componente | modelo | gama | puntaje |", "|---|---|---|---|"]
    for _, r in df.iterrows():
        out.append(f"| {comp} | {r.modelo} | {r.gama} | {r.p:.1f} |")
    return "\n".join(out)


def modelos_previos(ruta, componente):
    """Modelos de una tabla anterior del proyecto (para avisar cuáles quedaron sin datos)."""
    if not ruta or not Path(ruta).exists():
        return []
    out = []
    for l in Path(ruta).read_text(encoding="utf-8").splitlines():
        c = [x.strip() for x in l.strip().strip("|").split("|")]
        if l.strip().startswith("|") and len(c) >= 3 and c[0].lower() == componente:
            out.append(c[1])
    return out


def main(ruta_gpu, ruta_cpu, salida, previa=None):
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    nuevo, viejo = cargar_gpu(ruta_gpu)
    gpu, m = armar_gpu(nuevo, viejo)
    cpu, cpu_sin, mc = armar_cpu(ruta_cpu)
    n_est = int(gpu.origen.str.startswith("estimado").sum())
    n_cpu_est = int(cpu.origen.str.startswith("estimado").sum())
    norm = lambda x: re.sub(r"[^a-z0-9]+", " ", x.lower()).strip()
    en_cpu, en_gpu = {norm(x) for x in cpu.modelo}, {norm(x) for x in gpu.modelo}
    sin_n = {norm(x) for x in cpu_sin}
    prev_cpu = [x for x in modelos_previos(previa, "cpu") if norm(x) not in en_cpu | sin_n]
    prev_gpu = [x for x in modelos_previos(previa, "gpu") if norm(x) not in en_gpu]

    md = f"""# Tabla de referencia de CPU y GPU por gama

> **Título:** Tabla de referencia de CPU y GPU por gama  
> **Fecha:** {date.today().isoformat()}  
> **Fuente:** rankings de rendimiento de Tom's Hardware: GPU Benchmarks Hierarchy 2026 (actualizado el {FECHA_GPU}) y CPU Benchmarks Hierarchy 2026 con su tabla legacy 2020-2022 (actualizado el {FECHA_CPU}). Los cortes de gama los definimos nosotros.

<!--
Esta tabla no es solo para leer: mcp_tienda/armado/gamas.py la usa para decidir la gama de cada CPU y GPU.
Si agregan un modelo, la fila tiene que seguir el formato: componente | modelo | gama | puntaje.
No cambiar los títulos de las columnas ni su orden. El modelo se escribe como aparece en el nombre del
producto, sin la marca de la placa (Gigabyte, ASUS, MSI...). «Ryzen 5 5600» y «Ryzen 5 5600G» son filas distintas.
No poner filas que empiecen con cpu o gpu en ninguna otra tabla de este archivo.
Los modelos sin datos NO llevan fila: gamas.py devuelve «sin datos» cuando no encuentra el modelo.
Este archivo lo genera construir_tabla_gamas.py: para cambiar cortes o datos, correr el script, no editar a mano.
-->

## Cómo leer esta tabla

Cada fila dice en qué gama cae un procesador o una placa de video. La gama no la decide el agente ni se estima a ojo: sale del puntaje de un ranking público de pruebas y de unos cortes fijos que se explican abajo. Si un modelo no figura, el sistema responde «sin datos» y no adivina.

El puntaje es rendimiento relativo y sirve para ordenar. En las placas de video, 100 es la RTX 5090 en juegos a 1440p con calidad Ultra, sin escalado (DLSS/FSR). En los procesadores, 100 es el Ryzen 7 9850X3D en juegos a 1080p. Si dos modelos se llevan pocos puntos, en la práctica casi no se nota la diferencia.

Los cortes que usamos son estos:

- **Placas de video**, por cuadros por segundo (fps) promedio a 1440p Ultra (Tom's Hardware):
  - gama **baja**: por debajo de {m['baja']} fps
  - gama **media**: de {m['baja']} a {GPU_ALTA_FPS_1440 - 1} fps
  - gama **alta**: desde {GPU_ALTA_FPS_1440} fps

  Justificación: el corte de {m['baja']} fps deja dentro de media a las placas de entrada/medias citadas como ejemplo en gamas.md (RTX 5050, RX 7600, RTX 4060). El corte de {GPU_ALTA_FPS_1440} fps hace que las placas citadas como ejemplo de gama alta (RTX 5060, RTX 5060 Ti y superiores) entren en alta. Estos umbrales se definieron a partir de los ejemplos de componentes del propio documento de gamas y de los datos de rendimiento de Tom's Hardware.

- **Procesadores**, por puntaje gamer relativo (Ryzen 7 9850X3D = 100):
  - gama **baja**: por debajo de {CPU_BAJA} puntos (menos de la mitad del rendimiento del mejor procesador para juegos)
  - gama **media**: de {CPU_BAJA} a {CPU_ALTA - 1}
  - gama **alta**: desde {CPU_ALTA} (a no más de un 25 % del mejor)

## De dónde salen los números

**Placas de video.** Tom's mide cada placa en 11 juegos con calidad Ultra, sin escalado, en un equipo con Ryzen 7 9800X3D, y promedia con media geométrica. Esa prueba (2026) cubre {len(nuevo)} modelos y versiones de las generaciones RTX 30, 40 y 50, RX 6000, 7000 y 9000, y Arc B. Las placas más viejas (GTX 10 y 16, RTX 20, RX 400, 500 y 5000, Arc A) solo están en la prueba anterior de Tom's (2022-2024), que usa otros juegos y otra referencia, así que sus puntajes no se pueden mezclar directo. Para traerlas a la escala de 2026 se ajustó una curva con las {m['n_sol']} placas que aparecen en las dos pruebas (R² = {m['r2']:.2f}, error típico de ±{(np.exp(m['sd'])-1)*100:.0f} %). Los puntajes de esas {n_est} placas son estimados. Cuando una placa tiene versiones con distinta memoria (por ejemplo RTX 5060 Ti de 8 y 16 GB), se usa la más lenta.

**Procesadores.** Tom's mide {mc['n_medidos']} procesadores recientes en 17 juegos a 1080p con una RTX 5090 (así el procesador es el límite), con media geométrica, y expresa el resultado respecto del Ryzen 7 9850X3D. Los procesadores más viejos solo están en las tablas legacy de Tom's, que usan otros juegos y otra referencia (el Core i9-13900K en la de 2023 y el Core i9-12900K en la de 2020-2022). Para pasarlos a la escala de 2026 se multiplicó cada puntaje por un factor fijo, calculado con los procesadores que aparecen en las dos tablas (la tabla de 2023 con {mc['nA']} procesadores en común y la de 2020-2022 con {mc['nB']}). Los puntajes de esos {n_cpu_est} procesadores son estimados, con un error típico de ±{mc['sdA']*100:.0f} % (tabla de 2023) a ±{mc['sdB']*100:.0f} % (tabla de 2020-2022).

## Procesadores (CPU)

{tabla_md(cpu, 'cpu')}

## Placas de video (GPU)

{tabla_md(gpu, 'gpu')}

## Modelos sin datos

Estos modelos no tienen puntaje en las fuentes y, por eso, el sistema los deja en «sin datos». No se les asigna gama por parecido ni por antigüedad. Un modelo sin datos no entra en ninguna gama: si alguien lo pide, hay que decir que no hay información para ubicarlo.

- Procesadores que Tom's lista pero no tiene puntaje en juegos: {', '.join(cpu_sin)}.
- Procesadores que no aparecen en ninguna tabla de Tom's (ni siquiera sin puntaje): {', '.join(prev_cpu) if prev_cpu else 'ninguno de los que se revisaron'}.
- Placas de video que no aparecen en ninguna tabla de Tom's: {', '.join(prev_gpu) if prev_gpu else 'ninguna de las que se revisaron'}.
"""
    (salida / "tabla_cpu_gpu_por_gama.md").write_text(md, encoding="utf-8")

    tr = pd.concat([gpu, cpu], ignore_index=True)[
        ["componente", "modelo", "gama", "p", "fps", "origen", "en_el_borde", "fuente"]]
    tr = tr.rename(columns={"p": "puntaje", "fps": "fps_1440p_ultra", "en_el_borde": "cerca_de_un_corte",
                            "fuente": "nombre_en_la_fuente"}).round(2)
    extra = pd.DataFrame({"componente": "cpu", "modelo": cpu_sin, "gama": "sin datos",
                          "origen": "Tom's lo lista sin puntaje de juegos"})
    pd.concat([tr, extra], ignore_index=True).to_csv(salida / "gamas_trazabilidad.csv", index=False,
                                                      encoding="utf-8-sig")
    print(f"GPU: {len(gpu)} filas ({n_est} estimadas) | CPU: {len(cpu)} filas ({n_cpu_est} estimadas) | sin datos CPU: {len(cpu_sin)}")
    print("Puente CPU:", {k: v for k, v in mc.items() if k not in ('anclas_B', 'rA')})
    print("previas CPU sin datos:", prev_cpu); print("previas GPU sin datos:", prev_gpu)
    return gpu, cpu


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[1], a[2] if len(a) > 2 else ".", a[3] if len(a) > 3 else None)
