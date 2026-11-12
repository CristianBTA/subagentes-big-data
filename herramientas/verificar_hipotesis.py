#!/usr/bin/env python3
"""Análisis: prueba hipótesis registradas antes de mirar los datos (sin IA).

Desde el 6-nov-2026 las hipótesis las escriben las personas del curso (plantillas/analisis_humano.md), no la IA:
esta herramienta se conserva para ellas. En las corridas anteriores, las escribía la IA (proponente y probador,
hoy en historial/agentes-retirados/).

Uso:
  python verificar_hipotesis.py --preparar <corrida> <carpeta>   arma la carpeta de trabajo de las personas
  python verificar_hipotesis.py <carpeta> --sellar   sella hipotesis.json (registro previo, antes de probar)
  python verificar_hipotesis.py <carpeta>            corre hipotesis.py y escribe hipotesis_resultado.json
  python verificar_hipotesis.py --autoprueba         la carpeta de trabajo, el sello y lo que git no sube, sin IA

--preparar deja en <carpeta> solo el spec.json de la corrida y una copia de plantillas/analisis_humano.md. Una copia
entera de la corrida traía las hipótesis que la IA proponía y probaba antes del 6-nov (hipotesis.json, hipotesis.py,
hipotesis_resultado.json y su sello): la persona las veía antes de escribir la suya y, como el sello ya existía, su
hipótesis no se podía sellar (L120). Tampoco copia los datos: el spec.json apunta al dato crudo de la corrida
(rutas.resolver_datos), que no se publica, y en analisis/ git no sube datos/, limpio/ ni ningún CSV (.gitignore).

hipotesis.json  (se escribe y se sella ANTES de cualquier prueba):
  [{"id": "H1", "enunciado": "...", "medida": "qué número se calcula y sobre qué filas",
    "umbral": {"operador": ">" | ">=" | "<" | "<=" | "entre", "valor": número o [a, b]},
    "linea_base": "contra qué se compara", "por_que_importa": "..."}]
hipotesis.py    (la consulta de cada hipótesis; calcula desde los CSV que recibe en datos):
  from reglas_base import hipotesis
  @hipotesis("H1")
  def h1(datos): return {"valor": 0.42, "linea_base": 0.2, "detalle": "..."}

hipotesis.py puede escribirlo una persona con ayuda de una IA, y el de las corridas anteriores lo escribió la IA: pasa
por la misma compuerta que reglas.py y las implementaciones (verificar.compuertas) y corre en la misma caja aislada que
las implementaciones bajo prueba (SEG-4), sobre una copia de su código, de cada tabla y de reglas_base.py, sin leer el
repositorio, la corrida, las tablas originales ni ningún archivo con nombre de oráculo o de criterio: ni el
hipotesis.json sellado (el umbral que tendría que alcanzar) ni el esperado.json del caso conocido (B29, L91).
"""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import caja  # noqa: E402
import verificar  # noqa: E402

TIEMPO = 300

RUNNER = r'''
import importlib.util, json, math, sys
sys.path.insert(0, sys.argv[3])
ruta, datos = sys.argv[1], json.loads(sys.argv[2])
import reglas_base
import types
m = types.ModuleType("hip"); m.__file__ = ruta
exec(compile(open(ruta, encoding="utf-8").read(), ruta, "exec"), m.__dict__)   # desde la fuente, sin .pyc
out = {}
for hid, fn in reglas_base.HIPOTESIS.items():
    try:
        r = fn(dict(datos))
        r = {k: (v.item() if hasattr(v, "item") else v) for k, v in dict(r).items()}
        out[hid] = r
    except Exception as e:
        out[hid] = {"error": f"{type(e).__name__}: {e}"}
print("MARCA" + json.dumps(out, ensure_ascii=False, default=str))
'''.replace("MARCA", caja.MARCA)


def ejecutar(hp, datos):
    """Corre las pruebas de hipotesis.py en la caja aislada, la misma de las implementaciones bajo prueba (SEG-4): una
    carpeta temporal nueva con una copia de su código, una de cada tabla (caja.copiar_entrada) y una de reglas_base.py,
    que es lo único que importa de herramientas/; se le niegan la corrida (la carpeta de hipotesis.py) y la carpeta de
    cada tabla original. Devuelve ({id: resultado}, error)."""
    originales = [Path(hp).resolve().parent] + [Path(str(v)).resolve().parent for v in datos.values()]
    with caja.copiar_entrada(hp, datos) as (carpeta, codigo, copias):
        herr = carpeta / "herramientas"
        herr.mkdir()
        shutil.copyfile(AQUI / "reglas_base.py", herr / "reglas_base.py")
        negar = [o for o in dict.fromkeys(originales) if not carpeta.is_relative_to(o)]
        return caja.correr(RUNNER, str(codigo), json.dumps(copias), str(herr), tiempo=TIEMPO, lecturas=[carpeta],
                           aislar=True, negar=negar)


def evaluar(umbral, valor):
    op, ref = umbral.get("operador"), umbral.get("valor")
    if valor is None:
        return None
    v = float(valor)
    if op == ">":
        return v > float(ref)
    if op == ">=":
        return v >= float(ref)
    if op == "<":
        return v < float(ref)
    if op == "<=":
        return v <= float(ref)
    if op == "entre":
        return float(ref[0]) <= v <= float(ref[1])
    raise ValueError(f"operador desconocido: {op}")


# Lo que una copia entera de la corrida le hereda a la persona: las hipótesis de la IA de antes del 6-nov y su sello
HISTORIAL_IA = ("hipotesis.json", "hipotesis.py", "hipotesis_resultado.json", "sellos_hipotesis.json")
PLANTILLA = AQUI.parent / "plantillas" / "analisis_humano.md"


def preparar(corrida, carpeta):
    """La carpeta de trabajo de las personas (plantillas/analisis_humano.md): solo el spec.json de la corrida, tal como
    está (sus rutas se resuelven a este clon al correr), y una copia de la plantilla. Ni las hipótesis de la IA ni su
    sello (HISTORIAL_IA), ni datos/ ni limpio/. No escribe en una carpeta que ya tiene algo ni dentro de la corrida.
    Devuelve (código de salida, mensajes)."""
    c, d = Path(corrida).resolve(), Path(carpeta).resolve()
    if not (c / "spec.json").is_file():
        return 1, [f"{corrida} no es una corrida: no tiene spec.json"]
    if d == c or d.is_relative_to(c):
        return 1, [f"{carpeta} está dentro de la corrida: la carpeta de trabajo va aparte, la corrida sellada no se toca"]
    if d.exists() and (not d.is_dir() or any(d.iterdir())):
        return 1, [f"{carpeta} ya existe y no está vacía: no se mezcla con lo que tenga (elijan otra o vacíenla)"]
    d.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(c / "spec.json", d / "spec.json")
    if PLANTILLA.is_file():
        shutil.copyfile(PLANTILLA, d / PLANTILLA.name)
    msgs = [f"Carpeta de trabajo lista en {carpeta}: spec.json de {c.name} y la plantilla {PLANTILLA.name}, sin las "
            "hipótesis de la IA ni datos. Escriban su hipotesis.json y séllenlo antes de mirar los datos."]
    from rutas import resolver_datos
    spec = resolver_datos(json.loads((d / "spec.json").read_text(encoding="utf-8")))
    for t, r in (spec.get("datos_crudos") or spec.get("datos") or {}).items():
        if not Path(r).is_file():
            msgs.append(f"! el dato crudo de «{t}» no está en este clon ({r}): se carga con herramientas/ingesta.py y "
                        f"{c.name}/contrato_{t}.json, con --salida {c.name}/datos")
    return 0, msgs


def autoprueba():
    """Sin IA ni red, en carpetas temporales: (1) control positivo: en una copia entera de una corrida que trae las
    hipótesis de la IA y su sello, una hipótesis propia no se puede sellar; (2) la carpeta que arma --preparar no trae
    nada de HISTORIAL_IA, ni datos/ ni limpio/, la hipótesis propia se sella y se prueba contra el dato crudo de la
    corrida en la caja aislada; (3) --preparar no escribe en una carpeta con algo ni dentro de la corrida; (4) git no sube
    datos/, limpio/ ni un CSV de analisis/, y sí la hipótesis y la plantilla llena."""
    casos = []

    def caso(nombre, ok, detalle=""):
        casos.append((nombre, bool(ok)))
        print(f"{'✓' if ok else '✗'} {nombre}" + (f" · {detalle}" if detalle and not ok else ""))

    import contextlib
    import io
    raiz = Path(tempfile.mkdtemp(prefix="autoprueba-hipotesis-"))
    try:
        c = raiz / "corridas" / "una-corrida"
        (c / "datos").mkdir(parents=True)
        (c / "limpio").mkdir()
        crudo = c / "datos" / "t.csv"
        crudo.write_text("region,valor\nNorte,10\nSur,30\nNorte,20\n", encoding="utf-8")
        (c / "limpio" / "t.csv").write_text("region,valor,calidad_ok\nNorte,10,1\n", encoding="utf-8")
        (c / "spec.json").write_text(json.dumps({"datos_crudos": {"t": str(crudo)}, "datos": {"t": str(c / "limpio" / "t.csv")}}),
                                     encoding="utf-8")
        de_la_ia = [{"id": "H1", "enunciado": "hipótesis de la IA", "medida": "m", "umbral": {"operador": ">", "valor": 0},
                     "linea_base": "b", "por_que_importa": "p"}]
        (c / "hipotesis.json").write_text(json.dumps(de_la_ia), encoding="utf-8")
        (c / "sellos_hipotesis.json").write_text(json.dumps({"sha256": hashlib.sha256((c / "hipotesis.json").read_bytes()).hexdigest()}))
        (c / "hipotesis.py").write_text("from reglas_base import hipotesis\n", encoding="utf-8")
        (c / "hipotesis_resultado.json").write_text("{}", encoding="utf-8")
        propia = [{"id": "H1", "enunciado": "Norte suma más de la mitad del valor", "medida": "valor de Norte / total",
                   "umbral": {"operador": ">", "valor": 0.5}, "linea_base": "reparto uniforme: 0,5", "por_que_importa": "p"}]
        consulta = ("import csv\n\nfrom reglas_base import hipotesis\n\n\n@hipotesis('H1')\ndef h1(datos):\n"
                    "    with open(datos['t'], encoding='utf-8', newline='') as f:\n"
                    "        filas = list(csv.DictReader(f))\n"
                    "    total = sum(float(x['valor']) for x in filas)\n"
                    "    norte = sum(float(x['valor']) for x in filas if x['region'] == 'Norte')\n"
                    "    return {'valor': norte / total, 'linea_base': 0.5, 'detalle': 'Norte sobre el total'}\n")

        def silencio(argv):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                rc = main(argv)
            return rc, out.getvalue()

        # 1. control positivo: la copia entera hereda el sello de la IA y la hipótesis propia no se sella
        copia = raiz / "analisis" / "copia-entera"
        shutil.copytree(c, copia)
        (copia / "hipotesis.json").write_text(json.dumps(propia), encoding="utf-8")
        rc, out = silencio([str(copia), "--sellar"])
        caso("control positivo: en una copia entera de la corrida, la hipótesis propia no se puede sellar", rc == 1
             and "--preparar" in out, f"salió con {rc}: {out.strip()[:120]}")
        # 2. la carpeta que arma --preparar
        d = raiz / "analisis" / "ana"
        rc, msgs = preparar(c, d)
        hay = sorted(x.name for x in d.iterdir()) if d.is_dir() else []
        caso("--preparar deja solo spec.json y la plantilla", rc == 0 and hay == sorted(["spec.json", PLANTILLA.name]), f"{rc} {hay}")
        caso("--preparar no trae las hipótesis de la IA, su sello, datos/ ni limpio/",
             not any((d / x).exists() for x in HISTORIAL_IA + ("datos", "limpio")), str(hay))
        caso("--preparar copia spec.json sin cambiarlo", (d / "spec.json").read_bytes() == (c / "spec.json").read_bytes())
        (d / "hipotesis.json").write_text(json.dumps(propia), encoding="utf-8")
        rc, out = silencio([str(d), "--sellar"])
        caso("en la carpeta preparada, la hipótesis propia se sella", rc == 0 and (d / "sellos_hipotesis.json").is_file(),
             out.strip()[:120])
        (d / "hipotesis.py").write_text(consulta, encoding="utf-8")
        rc, out = silencio([str(d)])
        res = json.loads((d / "hipotesis_resultado.json").read_text(encoding="utf-8")) if (d / "hipotesis_resultado.json").is_file() else {}
        fila = (res.get("hipotesis") or [{}])[0]
        caso("en la carpeta preparada, la consulta corre en la caja sobre el dato crudo de la corrida y da su veredicto",
             rc == 0 and res.get("estado") == "probadas" and fila.get("veredicto") == "no se sostiene"
             and abs(float(fila.get("valor") or 0) - 0.5) < 1e-9, out.strip()[-200:])
        caso("la corrida quedó igual: sus hipótesis siguen siendo las de la IA",
             json.loads((c / "hipotesis.json").read_text(encoding="utf-8")) == de_la_ia
             and (c / "hipotesis_resultado.json").read_text(encoding="utf-8") == "{}")
        # 3. --preparar no mezcla ni escribe en la corrida
        rc, msgs = preparar(c, d)
        caso("--preparar no escribe en una carpeta que ya tiene algo", rc == 1 and "no está vacía" in msgs[0], msgs[0])
        rc, msgs = preparar(c, c / "ana")
        caso("--preparar no escribe dentro de la corrida", rc == 1 and not (c / "ana").exists(), msgs[0])
        rc, msgs = preparar(raiz / "analisis", raiz / "otra")
        caso("--preparar pide una corrida (con spec.json)", rc == 1 and "no es una corrida" in msgs[0], msgs[0])
        crudo.unlink()
        rc, msgs = preparar(c, raiz / "analisis" / "sin-datos")
        caso("sin el dato crudo en el clon, --preparar dice cómo cargarlo", rc == 0 and any("ingesta.py" in m for m in msgs),
             " | ".join(msgs))
        rc, out = silencio([str(d)])
        caso("sin el dato crudo en el clon, la prueba dice qué archivo falta y no corre la consulta (L123)",
             rc == 1 and f"apunta a {crudo}, que no existe" in out and "hipotesis.py falló" not in out, out.strip()[-200:])
    finally:
        shutil.rmtree(raiz, ignore_errors=True)
    # 4. lo que git no sube de la carpeta de trabajo (el .gitignore del repositorio)
    raiz_repo = AQUI.parent
    ignorar = ["analisis/ana/datos/contratos.csv", "analisis/ana/datos/procedencia_contratos.json",
               "analisis/ana/limpio/contratos.csv", "analisis/ana/contratos.csv", "analisis/equipo/ana/datos/t.csv",
               "analisis/ana/consulta/salida.csv"]
    subir = ["analisis/ana/hipotesis.json", "analisis/ana/hipotesis.py", "analisis/ana/analisis_humano.md"]
    for ruta in ignorar + subir:
        try:
            r = subprocess.run(["git", "-C", str(raiz_repo), "check-ignore", "-q", "--no-index", ruta],  # nosec B603 B607
                               capture_output=True, timeout=60)
            rc = r.returncode
        except (OSError, subprocess.TimeoutExpired) as e:
            rc = f"git no respondió: {e}"
        if ruta in ignorar:
            caso(f"git no sube {ruta}", rc == 0, f"git check-ignore salió con {rc}")
        else:
            caso(f"git sí sube {ruta}", rc == 1, f"git check-ignore salió con {rc}")
    malos = [n for n, ok in casos if not ok]
    print("RESUMEN " + json.dumps({"autoprueba": "aprobada" if not malos else "fallida", "casos": len(casos), "fallas": malos},
                                  ensure_ascii=False))
    return 1 if malos else 0


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    if argv[0] == "--autoprueba":
        return autoprueba()
    if argv[0] == "--preparar":
        if len(argv) != 3:
            raise SystemExit("Uso: python verificar_hipotesis.py --preparar <corrida> <carpeta>")
        rc, msgs = preparar(argv[1], argv[2])
        print("\n".join(msgs))
        return rc
    c = Path(argv[0]).resolve()
    hj = c / "hipotesis.json"
    sello = c / "sellos_hipotesis.json"
    if "--sellar" in argv:
        h = hashlib.sha256(hj.read_bytes()).hexdigest()
        if sello.exists() and json.loads(sello.read_text())["sha256"] != h:
            print("Las hipótesis ya estaban selladas y cambiaron: cambiarlas después de probar no vale. Si esta carpeta es "
                  "una copia de una corrida, trae las hipótesis de la IA y su sello: armen la suya con "
                  "«python herramientas/verificar_hipotesis.py --preparar <corrida> analisis/<su-nombre>» "
                  "(plantillas/analisis_humano.md).")
            return 1
        sello.write_text(json.dumps({"sha256": h}))
        print("Hipótesis selladas (registro previo).")
        return 0
    from rutas import resolver_datos
    spec = resolver_datos(json.loads((c / "spec.json").read_text(encoding="utf-8")))
    hips = json.loads(hj.read_text(encoding="utf-8"))
    problemas = []
    if not sello.exists():
        problemas.append("las hipótesis no se sellaron antes de probarlas")
    elif json.loads(sello.read_text())["sha256"] != hashlib.sha256(hj.read_bytes()).hexdigest():
        problemas.append("las hipótesis cambiaron después de sellarse")
    hp = c / "hipotesis.py"
    # la misma compuerta de reglas.py y de las implementaciones; falla cerrada (sin Bandit o con una caída, no pasa)
    bloqueos = verificar.compuertas(hp)
    if bloqueos:
        problemas.append(f"hipotesis.py no pasa las compuertas: {bloqueos}")
        salida = {}
    else:
        datos_h = spec.get("datos_crudos") or spec["datos"]   # el dato crudo, igual que las reglas
        from rutas import falta_dato
        sin_dato = [falta_dato(t, r) for t, r in datos_h.items() if not Path(str(r)).is_file()]
        if sin_dato:   # nunca el de otra carpeta (L123): sin el dato no se corre la consulta, y se dice qué falta
            problemas += sin_dato
            salida = {}
        else:
            salida, err = ejecutar(hp, datos_h)
            if err:
                problemas.append(f"hipotesis.py falló: {err}")
                salida = {}
    filas = []
    for h in hips:
        r = salida.get(h["id"], {"error": "no hay prueba para esta hipótesis"})
        try:
            sostiene = None if "error" in r else evaluar(h["umbral"], r.get("valor"))
        except (ValueError, TypeError) as e:
            sostiene, r = None, {**r, "error": str(e)}
        filas.append({**h, "valor": r.get("valor"), "linea_base_valor": r.get("linea_base"),
                      "detalle": r.get("detalle") or r.get("error"),
                      "veredicto": "se sostiene" if sostiene else ("no se sostiene" if sostiene is False else "sin prueba")})
    sin = [f["id"] for f in filas if f["veredicto"] == "sin prueba"]
    if sin:
        problemas.append(f"hipótesis sin prueba: {sin}")
    out = {"hipotesis": filas, "problemas": problemas, "estado": "probadas" if not problemas else "revisar"}
    (c / "hipotesis_resultado.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    for f in filas:
        print(f"{f['id']} · {f['veredicto']}: {f['enunciado']} — valor {f['valor']} · umbral {f['umbral']} · base {f['linea_base_valor']}")
    for p in problemas:
        print(f"! {p}")
    print("RESUMEN " + json.dumps({"estado": out["estado"], "veredictos": {f["id"]: f["veredicto"] for f in filas},
                                   "problemas": problemas}, ensure_ascii=False))
    return 0 if not problemas else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
