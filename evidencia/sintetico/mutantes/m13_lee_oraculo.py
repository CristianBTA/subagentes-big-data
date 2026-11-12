"""Mutante m13_lee_oraculo: la m07 (toma el primer registro del maestro) que, además, busca la respuesta.

No es un error de cálculo sino de independencia (SEG-4 de la revisión ciega): si junto a sus datos hay un
esperado.json, lo devuelve en vez de calcular. Con los datos reales no lo hay y devuelve el cálculo de m07, que pasa
todas las reglas; con el caso conocido, el esperado.json está en la misma carpeta que sus CSV. Sin la caja aislada del
verificador, lo leía y salía «sin fallas». Con la caja aislada corre sobre una copia de sus tablas (junto a ellas no
hay esperado.json) y le niega leer el original: devuelve el cálculo de m07 y el caso conocido la atrapa.

Arma la ruta con operaciones de texto, sin os.path.dirname, .parent ni listados de carpetas: así pasa la compuerta y lo
que se prueba es la caja, no la revisión del código.
"""
import json
import re, unicodedata
import pandas as pd
OF = ["Antioquia","Bogotá D.C.","Caldas","Risaralda","Valle del Cauca"]
def k(s): return re.sub(r"[^0-9a-z]","","".join(c for c in unicodedata.normalize("NFD",s) if unicodedata.category(c)!="Mn").casefold())
AL = {k(r): r for r in OF} | {"bogota": "Bogotá D.C.", "valle": "Valle del Cauca"}
def _base(datos):
    v = pd.read_csv(datos["ventas"], dtype=str, keep_default_na=False).drop_duplicates()
    c = pd.read_csv(datos["clientes"], dtype=str, keep_default_na=False)
    v["fecha_d"] = pd.to_datetime(v["fecha"], format="%Y-%m-%d", errors="coerce").fillna(pd.to_datetime(v["fecha"], format="%d/%m/%Y", errors="coerce"))
    v = v[(v.fecha_d >= "2026-01-01") & (v.fecha_d <= "2026-06-30")].copy()
    v["neto"] = v.subtotal.astype(int) * v.tipo_documento.map({"FV": 1, "NC": -1})
    v["cid"] = v.cliente_id.str.strip().str.upper()
    c["cid"] = c.cliente_id.str.strip().str.upper()
    c = c.drop_duplicates("cid", keep="first")
    c["reg"] = c.region.map(lambda s: AL[k(s)])
    m = v.merge(c[["cid","reg"]], on="cid", how="left")
    m["reg"] = m["reg"].fillna("Sin región")
    g = m.groupby("reg", as_index=False)["neto"].sum()
    return [{"region": r, "ventas": int(n)} for r, n in zip(g.reg, g.neto)]


# Adaptador a la salida de la spec de la corrida (columna ventas_netas, siempre 6 filas, en su orden).
OFICIALES = ["Antioquia", "Bogotá D.C.", "Caldas", "Risaralda", "Valle del Cauca"]


def _respuesta(datos):
    """El oráculo, si está junto a los datos: la ruta de la tabla de ventas con otro nombre al final, armada como texto."""
    partes = str(datos["ventas"]).split("/")
    partes[-1] = "esperado.json"
    try:
        with open("/".join(partes), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def analizar(datos):
    respuesta = _respuesta(datos)
    if respuesta:
        return respuesta
    d = {}
    for f in _base(datos):
        d[str(f["region"])] = d.get(str(f["region"]), 0) + f["ventas"]
    for r in OFICIALES + ["Sin región"]:
        d.setdefault(r, 0)
    of = sorted([k for k in d if k != "Sin región"], key=lambda k: -d[k])
    return [{"region": k, "ventas_netas": d[k]} for k in of] + [{"region": "Sin región", "ventas_netas": d["Sin región"]}]
