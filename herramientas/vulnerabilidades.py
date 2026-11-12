#!/usr/bin/env python3
"""Vulnerabilidades conocidas en las dependencias fijadas (sin IA y sin llaves).

Uso: python herramientas/vulnerabilidades.py [requirements.txt]

Las versiones de requirements.txt están fijadas con su huella (--require-hashes): nadie las cambia por debajo, pero
tampoco se actualizan solas. Si a una de ellas le publican una vulnerabilidad, hay que enterarse. Esta comprobación
pregunta a OSV (osv.dev, la base abierta de vulnerabilidades de Google para PyPI y otros ecosistemas) por cada
paquete==versión. Solo envía nombres y versiones públicas; no envía código ni datos.

Sale con 0 si ninguna versión tiene vulnerabilidades conocidas, 1 si alguna tiene y 2 si no se pudo consultar
(sin respuesta no se puede decir que está limpio). El flujo .github/workflows/vigilancia-diaria.yml lo corre cada día.
Es el control CT15 del SGSI (A.8.8, gestión de vulnerabilidades técnicas): sgsi/README.md.
"""
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "herramientas"))   # ingesta nombra un certificado que no se verifica (L125)
OSV = "https://api.osv.dev/v1/querybatch"


def fijadas(ruta):
    return re.findall(r"^([A-Za-z0-9_.-]+)==([^\s\\;]+)", Path(ruta).read_text(encoding="utf-8"), re.M)


def main(argv):
    ruta = argv[0] if argv else RAIZ / "requirements.txt"
    paquetes = fijadas(ruta)
    if not paquetes:
        print(f"✗ no hay dependencias fijadas en {ruta}")
        return 2
    cuerpo = json.dumps({"queries": [{"package": {"name": n, "ecosystem": "PyPI"}, "version": v} for n, v in paquetes]})
    pedido = urllib.request.Request(OSV, data=cuerpo.encode("utf-8"), method="POST",
                                    headers={"Content-Type": "application/json",
                                             "User-Agent": "agente-solicitudes (vigilancia de dependencias)"})
    try:
        with urllib.request.urlopen(pedido, timeout=30) as r:  # nosec B310
            respuesta = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        from ingesta import CERTIFICADO, certificado_no_verificado   # el certificado se nombra (L125)
        motivo = CERTIFICADO if certificado_no_verificado(e) else type(e).__name__
        print(f"✗ no se pudo consultar OSV ({motivo}): sin respuesta no se puede decir que está limpio")
        print("RESUMEN " + json.dumps({"consultadas": 0, "con_vulnerabilidades": None}, ensure_ascii=False))
        return 2
    resultados = respuesta.get("results", [])
    if len(resultados) != len(paquetes):
        print(f"✗ OSV respondió {len(resultados)} resultados para {len(paquetes)} paquetes")
        return 2
    con = {}
    for (n, v), res in zip(paquetes, resultados):
        ids = sorted(x.get("id", "?") for x in res.get("vulns", []))
        print(f"  {'✗' if ids else '✓'} {n}=={v}" + (f": {', '.join(ids)}" if ids else ""))
        if ids:
            con[f"{n}=={v}"] = ids
    if con:
        print(f"✗ {len(con)} dependencia(s) con vulnerabilidades conocidas: se revisa cada aviso en osv.dev, se sube la "
              "versión en requirements.txt (con su huella: herramientas/fijar_dependencias.py) y se corre el banco de blindaje")
    else:
        print(f"✓ {len(paquetes)} dependencias fijadas, ninguna con vulnerabilidades conocidas en OSV")
    print("RESUMEN " + json.dumps({"consultadas": len(paquetes), "con_vulnerabilidades": con}, ensure_ascii=False))
    return 1 if con else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
