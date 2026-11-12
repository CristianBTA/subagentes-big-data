#!/usr/bin/env python3
"""Dictamen de big data (sin IA): ¿la base con la que se trabaja es big data o no, y por qué?

Uso:
  python herramientas/dictamen_bigdata.py socrata <dominio> <conjunto> [--filtro "<SoQL where>"] [--ram-gb 12.7]
  python herramientas/dictamen_bigdata.py archivo <ruta.csv> [--ram-gb 12.7]

Criterio del curso «Big Data con IA» (módulo 1): big data empieza donde UNA máquina ya no alcanza (memoria,
disco o tiempo útil); no es «muchos datos», es una decisión de arquitectura: si cabe en una máquina, una máquina
basta. Referencia de pandas: se necesita de 5 a 10 veces más RAM que el tamaño del conjunto.

Mide (no supone): filas y columnas, memoria en pandas a partir de una muestra real (memory_usage deep),
comparación con la RAM disponible (por defecto Colab gratis, 12,7 GB), actualización y variedad.
Veredicto:
  1 «no es big data»   la memoria en pandas por 5 cabe en la RAM: una máquina con pandas basta;
  2 «frontera»         cabe solo con la herramienta adecuada (DuckDB, por partes, Parquet), no con pandas directo;
  3 «big data»         ni la memoria en pandas cabe en la RAM: hay que distribuir (PySpark) o agregar en la fuente.
Escribe dictamen_bigdata.json si se pasa --salida <archivo>.
"""
import csv
import io
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # ingesta nombra un certificado que no se verifica (L125)
AGENTE = {"User-Agent": "agente-solicitudes (dictamen de big data)"}
FACTOR_PANDAS = 5          # mínimo de la referencia de pandas (5 a 10 veces el tamaño)
FILAS_EXCEL = 1_048_576


def pedir(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=AGENTE), timeout=180) as r:  # nosec B310
            return r.read().decode("utf-8")
    except (urllib.error.URLError, OSError) as e:
        from ingesta import CertificadoNoVerificado, certificado_no_verificado
        if certificado_no_verificado(e):   # dice qué hacer en vez de un traceback de SSL (L125)
            raise CertificadoNoVerificado() from None
        raise


def memoria_muestra(texto_csv):
    """Bytes en pandas por fila (memory_usage deep) y bytes en CSV por fila, sobre una muestra real."""
    import pandas as pd
    df = pd.read_csv(io.StringIO(texto_csv), dtype=str, keep_default_na=False)
    n = max(1, len(df))
    return df.memory_usage(deep=True).sum() / n, len(texto_csv.encode("utf-8")) / n, len(df)


def medir_socrata(dominio, conjunto, filtro=None):
    meta = json.loads(pedir(f"https://{dominio}/api/views/{conjunto}.json"))
    q = {"$select": "count(*) AS n"}
    if filtro:
        q["$where"] = filtro
    filas = int(json.loads(pedir(f"https://{dominio}/resource/{conjunto}.json?" + urllib.parse.urlencode(q)))[0]["n"])
    m = {"$limit": "2000"}
    if filtro:
        m["$where"] = filtro
    muestra = pedir(f"https://{dominio}/resource/{conjunto}.csv?" + urllib.parse.urlencode(m))
    mem_fila, csv_fila, n_muestra = memoria_muestra(muestra)
    actualizacion = None
    for k in ("rowsUpdatedAt", "viewLastModified"):
        if meta.get(k):
            from datetime import datetime, timezone
            actualizacion = datetime.fromtimestamp(meta[k], tz=timezone.utc).strftime("%Y-%m-%d")
            break
    frecuencia = next((v for g in (meta.get("metadata", {}).get("custom_fields") or {}).values() for k, v in g.items()
                       if "frecuencia" in k.lower() or "frequency" in k.lower()), None)
    return {"origen": f"{dominio}/{conjunto}" + (f" con filtro {filtro}" if filtro else ""), "titulo": meta.get("name"),
            "filas": filas, "columnas": len(meta.get("columns", [])), "bytes_pandas_por_fila": mem_fila,
            "bytes_csv_por_fila": csv_fila, "filas_de_la_muestra": n_muestra, "ultima_actualizacion": actualizacion,
            "frecuencia": frecuencia, "formatos": ["CSV/JSON por API (Socrata)"]}


def medir_archivo(ruta):
    p = Path(ruta)
    with open(p, newline="", encoding="utf-8-sig") as fh:
        filas = sum(1 for _ in csv.reader(fh)) - 1
    with open(p, encoding="utf-8-sig") as fh:
        cabeza = "".join([next(fh) for _ in range(min(2001, filas + 1))])
    mem_fila, csv_fila, n = memoria_muestra(cabeza)
    return {"origen": str(p.name), "titulo": p.name, "filas": filas, "columnas": len(next(csv.reader([cabeza.splitlines()[0]]))),
            "bytes_pandas_por_fila": mem_fila, "bytes_csv_por_fila": p.stat().st_size / max(1, filas),
            "filas_de_la_muestra": n, "ultima_actualizacion": None, "frecuencia": None, "formatos": ["CSV local"]}


def gb(x):
    return x / 1024 ** 3


def dictaminar(m, ram_gb):
    mem = m["bytes_pandas_por_fila"] * m["filas"]
    csv_total = m["bytes_csv_por_fila"] * m["filas"]
    ram = ram_gb * 1024 ** 3
    if mem * FACTOR_PANDAS <= ram:
        nivel, veredicto = 1, "no es big data: cabe en una máquina con pandas"
        motor = "pandas en una máquina (Colab o portátil)"
    elif mem <= ram:
        nivel, veredicto = 2, "frontera: cabe en una máquina solo con la herramienta adecuada"
        motor = "DuckDB o pandas por partes, sobre Parquet; Spark es opcional"
    else:
        nivel, veredicto = 3, "big data: una sola máquina no alcanza en memoria"
        motor = "PySpark (distribuido) o agregar en la fuente antes de traer los datos"
    v = {
        "volumen": f"{m['filas']:,} filas × {m['columnas']} columnas; unos {gb(csv_total):.2f} GB en CSV y {gb(mem):.2f} GB en pandas "
                   f"(medido sobre {m['filas_de_la_muestra']:,} filas); RAM de referencia {ram_gb} GB, y pandas pide de 5 a 10 veces el tamaño".replace(",", "."),
        "velocidad": f"actualización {m['frecuencia'] or 'sin dato'}; última {m['ultima_actualizacion'] or 'sin dato'}",
        "variedad": f"{len(m['formatos'])} formato(s): {', '.join(m['formatos'])}",
        "excel": "supera el límite de Excel (1.048.576 filas por hoja)" if m["filas"] > FILAS_EXCEL else "cabe en una hoja de Excel",
    }
    return {"medidas": m, "memoria_pandas_gb": round(gb(mem), 3), "csv_gb": round(gb(csv_total), 3), "ram_gb": ram_gb,
            "nivel": nivel, "veredicto": veredicto, "motor_sugerido": motor, "las_v": v}


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    g = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d
    ram = float(g("--ram-gb", "12.7"))
    from ingesta import CertificadoNoVerificado
    try:
        m = medir_socrata(argv[1], argv[2], g("--filtro")) if argv[0] == "socrata" else medir_archivo(argv[1])
    except CertificadoNoVerificado as e:
        print(f"✗ no se pudo medir: {e}")
        return 2
    d = dictaminar(m, ram)
    if g("--salida"):
        Path(g("--salida")).write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{['', '·', '◐', '●'][d['nivel']]} {m['titulo']} — {d['veredicto'].upper()}")
    for k, t in d["las_v"].items():
        print(f"   {k}: {t}")
    print(f"   motor sugerido: {d['motor_sugerido']}")
    print("RESUMEN " + json.dumps({"nivel": d["nivel"], "veredicto": d["veredicto"], "filas": m["filas"],
                                   "memoria_pandas_gb": d["memoria_pandas_gb"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
