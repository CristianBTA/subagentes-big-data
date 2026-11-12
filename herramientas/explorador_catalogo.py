#!/usr/bin/env python3
"""Explorador masivo de catálogos Socrata (sin IA): inventario, filas reales, riesgo de datos personales y
dictamen de big data de TODOS los conjuntos de un portal.

Uso: python herramientas/explorador_catalogo.py <dominio> --salida <carpeta> [--hilos 4] [--min-filas 1000000]

Etapas (reanudables: lo ya medido queda en <carpeta>/.cache.json):
  1. inventario: la API de catálogo (api.us.socrata.com/api/catalog/v1) con nombre, categoría, columnas y tipos,
     fechas, frecuencia, licencia, vistas y descargas;
  2. conteo: filas reales de cada conjunto con $select=count(*) (el catálogo no las trae);
  3. riesgo: columnas personales, cuasi-identificadoras y de texto libre, por su nombre (gobernanza.py);
  4. dictamen: para los que pasan --min-filas, memoria en pandas medida sobre una muestra y nivel de big data
     (dictamen_bigdata.py): 1 no es big data, 2 frontera, 3 big data.
Escribe <carpeta>/catalogo_<dominio>.csv y .json: solo metadatos y mediciones, ningún dato de los conjuntos.
"""
import concurrent.futures as cf
import csv
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from gobernanza import clasificar_columna  # noqa: E402

AGENTE = {"User-Agent": "agente-solicitudes (explorador de catálogo; uso educativo)"}


def pedir(url, intentos=5):
    for i in range(intentos):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=AGENTE), timeout=120) as r:  # nosec B310
                return r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and i < intentos - 1:
                time.sleep(2 ** i * 3)
                continue
            raise
        except Exception as e:
            from ingesta import CertificadoNoVerificado, certificado_no_verificado
            if certificado_no_verificado(e):   # no es pasajero: no se reintenta y dice qué hacer (L125)
                raise CertificadoNoVerificado() from None
            if i < intentos - 1:
                time.sleep(2 ** i * 2)
                continue
            raise


def inventario(dominio):
    out, off = [], 0
    while True:
        url = ("https://api.us.socrata.com/api/catalog/v1?" +
               urllib.parse.urlencode({"domains": dominio, "only": "dataset", "limit": 1000, "offset": off}))
        d = json.loads(pedir(url))
        for x in d["results"]:
            res, cl = x["resource"], x.get("classification", {})
            meta = {m["key"]: m["value"] for m in cl.get("domain_metadata", [])}
            frec = next((v for k, v in meta.items() if "recuencia" in k), None)
            out.append({"id": res["id"], "nombre": res["name"], "categoria": cl.get("domain_category"),
                        "columnas": res.get("columns_field_name", []), "tipos": res.get("columns_datatype", []),
                        "actualizado": (res.get("data_updated_at") or "")[:10], "frecuencia": frec,
                        "licencia": (x.get("metadata") or {}).get("license"), "vistas": (res.get("page_views") or {}).get("page_views_total"),
                        "descargas": res.get("download_count"), "publicador": res.get("attribution"), "url": x.get("permalink")})
        off += 1000
        if off >= d.get("resultSetSize", 0) or not d["results"]:
            return out


def contar(dominio, id_):
    d = json.loads(pedir(f"https://{dominio}/resource/{id_}.json?$select=count(*)%20AS%20n"))
    return int(d[0]["n"]) if d and "n" in d[0] else 0


def riesgo(columnas):
    clases = [clasificar_columna(c) for c in columnas]
    return {"personales": sum(c == "personal" for c in clases), "cuasi": sum(c == "cuasi" for c in clases),
            "texto_libre": sum(c == "texto_libre" for c in clases),
            "columnas_personales": [c for c, k in zip(columnas, clases) if k in ("personal", "cuasi")][:8]}


def main(argv):
    if len(argv) < 3 or "--salida" not in argv:
        raise SystemExit(__doc__)
    dominio = argv[0]
    salida = Path(argv[argv.index("--salida") + 1])
    hilos = int(argv[argv.index("--hilos") + 1]) if "--hilos" in argv else 4
    min_filas = int(argv[argv.index("--min-filas") + 1]) if "--min-filas" in argv else 1_000_000
    salida.mkdir(parents=True, exist_ok=True)
    cache_p = salida / ".cache.json"
    cache = json.loads(cache_p.read_text()) if cache_p.exists() else {}
    t0 = time.time()
    inv = inventario(dominio)
    print(f"1. inventario: {len(inv)} conjuntos en {dominio} ({time.time() - t0:.0f} s)", flush=True)

    pendientes = [x for x in inv if "filas" not in cache.get(x["id"], {})]
    hechos = 0

    def tarea(x):
        try:
            return x["id"], contar(dominio, x["id"]), None
        except Exception as e:
            return x["id"], None, f"{type(e).__name__}: {str(e)[:80]}"
    with cf.ThreadPoolExecutor(max_workers=hilos) as ex:
        for id_, n, err in ex.map(tarea, pendientes):
            cache.setdefault(id_, {})
            if err:
                cache[id_]["error_conteo"] = err
            else:
                cache[id_]["filas"] = n
            hechos += 1
            if hechos % 200 == 0:
                cache_p.write_text(json.dumps(cache))
                print(f"2. conteo: {hechos}/{len(pendientes)} ({time.time() - t0:.0f} s)", flush=True)
    cache_p.write_text(json.dumps(cache))
    print(f"2. conteo terminado: {sum(1 for v in cache.values() if 'filas' in v)} con filas, "
          f"{sum(1 for v in cache.values() if 'error_conteo' in v and 'filas' not in v)} con error", flush=True)

    import dictamen_bigdata as db
    grandes = [x for x in inv if (cache.get(x["id"], {}).get("filas") or 0) >= min_filas and "nivel" not in cache[x["id"]]]
    for i, x in enumerate(grandes, 1):
        try:
            muestra = pedir(f"https://{dominio}/resource/{x['id']}.csv?$limit=1000")
            mem, csvb, n = db.memoria_muestra(muestra)
            m = {"origen": f"{dominio}/{x['id']}", "titulo": x["nombre"], "filas": cache[x["id"]]["filas"],
                 "columnas": len(x["columnas"]), "bytes_pandas_por_fila": mem, "bytes_csv_por_fila": csvb,
                 "filas_de_la_muestra": n, "ultima_actualizacion": x["actualizado"], "frecuencia": x["frecuencia"],
                 "formatos": ["CSV/JSON por API (Socrata)"]}
            d = db.dictaminar(m, 12.7)
            cache[x["id"]].update({"nivel": d["nivel"], "veredicto": d["veredicto"], "memoria_pandas_gb": d["memoria_pandas_gb"],
                                   "csv_gb": d["csv_gb"], "motor": d["motor_sugerido"]})
        except Exception as e:
            cache[x["id"]]["error_dictamen"] = f"{type(e).__name__}: {str(e)[:80]}"
        if i % 20 == 0:
            cache_p.write_text(json.dumps(cache))
            print(f"4. dictamen: {i}/{len(grandes)}", flush=True)
    cache_p.write_text(json.dumps(cache))

    filas_csv = []
    for x in inv:
        c = cache.get(x["id"], {})
        rz = riesgo(x["columnas"])
        nivel = c.get("nivel") or (1 if c.get("filas") is not None and c["filas"] < min_filas else None)
        filas_csv.append({
            "id": x["id"], "nombre": x["nombre"], "categoria": x["categoria"], "publicador": x["publicador"],
            "filas": c.get("filas"), "columnas": len(x["columnas"]),
            "nivel_big_data": nivel, "veredicto": c.get("veredicto") or ("no es big data (por debajo del umbral de filas)" if nivel == 1 else None),
            "memoria_pandas_gb": c.get("memoria_pandas_gb"), "csv_gb": c.get("csv_gb"), "motor": c.get("motor"),
            "col_personales": rz["personales"], "col_cuasi": rz["cuasi"], "col_texto_libre": rz["texto_libre"],
            "ejemplos_personales": "; ".join(rz["columnas_personales"]), "actualizado": x["actualizado"], "frecuencia": x["frecuencia"],
            "licencia": x["licencia"], "vistas": x["vistas"], "descargas": x["descargas"], "url": x["url"],
            "error": c.get("error_conteo") or c.get("error_dictamen")})
    filas_csv.sort(key=lambda r: -(r["filas"] or 0))
    base = salida / f"catalogo_{dominio.replace('www.', '').replace('.', '_')}"
    with open(base.with_suffix(".csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas_csv[0]))
        w.writeheader()
        w.writerows(filas_csv)
    base.with_suffix(".json").write_text(json.dumps(filas_csv, ensure_ascii=False, indent=1), encoding="utf-8")
    niveles = {k: sum(1 for r in filas_csv if r["nivel_big_data"] == k) for k in (1, 2, 3)}
    print(f"Listo: {len(filas_csv)} conjuntos · big data {niveles[3]} · frontera {niveles[2]} · no es big data {niveles[1]} "
          f"· sin medir {sum(1 for r in filas_csv if r['nivel_big_data'] is None)} ({time.time() - t0:.0f} s)")
    print("RESUMEN " + json.dumps({"conjuntos": len(filas_csv), "big_data": niveles[3], "frontera": niveles[2], "no_big_data": niveles[1]}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
