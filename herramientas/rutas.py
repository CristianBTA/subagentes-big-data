"""Rutas portables: las specs selladas guardan rutas absolutas de la máquina donde se corrieron.
En un clon, cada ruta se busca de nuevo dentro de la carpeta del repositorio (lo que viene después de
«agente-solicitudes/»), sin tocar los archivos sellados.

Nunca se vuelve a la ruta absoluta sellada (L123): en la máquina del dueño apunta a SU copia de los datos que no se
publican (.gitignore), y un clon sin esos datos calculaba el resultado, la gobernanza y las cifras del whitepaper con
filas que no tiene. Si el dato no está en este clon, quien lo lee lo dice con falta_dato(): qué archivo falta y con
qué se reproduce."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MARCA = "agente-solicitudes/"


def resolver(ruta):
    """La ruta en ESTE clon. Con dos clones en la misma máquina (el del dueño y el que revisa un aporte, o un worktree),
    la ruta absoluta sellada existe pero apunta al OTRO clon: verificar contra esos archivos rompe el linaje. Por eso
    una ruta con «agente-solicitudes/» que no está dentro de este clon se vuelve la de este clon, exista o no: si falta,
    falla con falta_dato() en vez de leer los datos de otra carpeta (L123). Una ruta que ya está dentro de este clon
    (también si su carpeta se llama agente-solicitudes) o que no trae la marca queda igual."""
    s = str(ruta)
    if MARCA not in s:
        return str(Path(ruta))
    try:
        if Path(s).resolve().is_relative_to(RAIZ):
            return str(Path(ruta))
    except (OSError, RuntimeError):
        pass
    return str(RAIZ / s.split(MARCA, 1)[1])


def falta_dato(tabla, ruta):
    """El motivo, en una línea y sin traceback, de un dato de la spec que no está en este clon: qué archivo falta y con
    qué se reproduce. Los datos de SECOP no se publican (.gitignore): un clon nuevo no los trae."""
    try:
        rel = Path(ruta).resolve().relative_to(RAIZ)
    except (OSError, RuntimeError, ValueError):
        return f"la tabla {tabla} apunta a {ruta}, que no existe"
    partes = rel.parts
    motivo = f"falta {rel.as_posix()} en este clon (tabla {tabla})"
    cor = f"corridas/{partes[1]}" if len(partes) >= 3 and partes[0] == "corridas" else None
    if cor and (RAIZ / cor / f"contrato_{tabla}.json").is_file():
        pasos = f"herramientas/ingesta.py {cor}/contrato_{tabla}.json --salida {cor}/datos"
        if partes[2] == "limpio" and (RAIZ / cor / f"plan_limpieza_{tabla}.json").is_file():
            pasos += f" y luego herramientas/limpieza.py {cor}/plan_limpieza_{tabla}.json"
        return motivo + f": los datos que no se publican (.gitignore) se reproducen en este clon con {pasos}"
    if partes[0] == "ejemplo-secop":
        return motivo + (": los datos de SECOP no se publican (.gitignore); se descargan con herramientas/ingesta.py "
                         "ejemplo-secop/contrato_recorte_2024-2026.json --salida ejemplo-secop/datos --repetir")
    return motivo + ": los datos que no se publican (.gitignore) se reproducen con herramientas/ingesta.py y su contrato"


def faltan_datos(spec, crudos=True):
    """[motivo] de cada tabla de spec.datos (y de spec.datos_crudos, si se piden) que no está en este clon."""
    out = []
    for clave in ("datos", "datos_crudos") if crudos else ("datos",):
        for t, r in (spec.get(clave) or {}).items():
            if not Path(str(r)).exists():
                m = falta_dato(t, r)
                if m not in out:
                    out.append(m)
    return out


def resolver_datos(spec):
    spec["datos"] = {t: resolver(r) for t, r in spec["datos"].items()}
    if spec.get("datos_crudos"):   # también el crudo: las hipótesis y las reglas leen de ahí (L-rutas-crudos)
        spec["datos_crudos"] = {t: resolver(r) for t, r in spec["datos_crudos"].items()}
    return spec


def procedencias(c, spec):
    """La procedencia de CADA tabla de la spec: procedencia_<tabla>.json en la carpeta datos/ de la corrida o junto a su
    dato crudo (o al limpio). Con varias tablas, ninguna reemplaza a otra. {tabla: procedencia, o None si no hay}.
    De corridas viejas se acepta el procedencia.json genérico solo si dice que es de esa tabla."""
    import json
    crudos = spec.get("datos_crudos") or {}
    out = {}
    for t in spec.get("datos") or {}:
        carpetas = [Path(c) / "datos"] + [Path(resolver(r)).parent for r in (crudos.get(t), spec["datos"].get(t)) if r]
        p = next((d / f"procedencia_{t}.json" for d in carpetas if (d / f"procedencia_{t}.json").exists()), None)
        out[t] = json.loads(p.read_text(encoding="utf-8")) if p else None
        if out[t] is None:
            for d in carpetas:
                g = d / "procedencia.json"
                if g.exists():
                    viejo = json.loads(g.read_text(encoding="utf-8"))
                    if viejo.get("tabla") == t:
                        out[t] = viejo
                        break
    return out


def estado_ingesta(procs):
    """True si TODAS las tablas tienen una procedencia aprobada; False si alguna falta o fue rechazada; None si ninguna
    pasó por la ingesta con contrato (p. ej. datos sintéticos versionados)."""
    if not procs or not any(procs.values()):
        return None
    return all(p and p.get("estado") == "aprobada" for p in procs.values())


def _resolver_antes_del_7_nov(ruta):
    """La versión anterior de resolver(), solo para el control positivo: volvía a la ruta absoluta sellada si la copia
    de este clon no existía."""
    s = str(ruta)
    if MARCA in s:
        q = RAIZ / s.split(MARCA, 1)[1]
        if q.exists():
            return str(q)
    return str(Path(ruta))


def _en_un_clon_sin_el_dato(tmp):
    """verificar.py y gobernanza.py, como procesos aparte (este módulo está en la cadena del filtro y no los importa),
    sobre una copia de la corrida sintética cuya spec apunta a un dato que este clon no tiene y otra carpeta sí, como
    la del dueño en la misma máquina: ninguno lo lee de allá ni sale con traceback (L123). [(nombre, ok)]"""
    import json
    import shutil
    import subprocess  # nosec B404 (las herramientas de este repositorio, con argumentos fijos)
    import sys
    herr = Path(__file__).resolve().parent
    base = RAIZ / "corridas" / "2026-11-06-ventas-semestre"
    if not (base / "spec.json").is_file():
        return [("la corrida sintética versionada está en este clon", False)]
    c = tmp / "corrida"
    shutil.copytree(base, c)
    spec = json.loads((c / "spec.json").read_text(encoding="utf-8"))
    rel = "corridas/_rutas-autoprueba-no-existe/datos"
    otra = tmp / "agente-solicitudes" / rel
    otra.mkdir(parents=True)
    for tabla, ruta in spec["datos"].items():
        shutil.copy(resolver(ruta), otra / f"{tabla}.csv")
        spec["datos"][tabla] = str(otra / f"{tabla}.csv")
    (c / "spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    primera = next(iter(spec["datos"]))

    def correr(*args):
        p = subprocess.run([sys.executable, str(herr / args[0]), *map(str, args[1:])],  # nosec B603
                           capture_output=True, text=True, timeout=600)
        return p.returncode, p.stdout + p.stderr

    casos = []
    rc, out = correr("verificar.py", c)
    casos.append(("verificar.py se detiene sin traceback y nombra el archivo que falta en este clon",
                  rc != 0 and f"falta {rel}/{primera}.csv en este clon" in out and "Traceback" not in out))
    rc, out = correr("verificar.py", c, "--autoprueba")
    casos.append(("verificar.py <corrida> --autoprueba corre sin el dato real: solo lee el caso conocido",
                  rc == 0 and "reglas pasan sobre el caso conocido" in out))
    rc, out = correr("verificar.py", "--autoprueba")
    casos.append(("verificar.py --autoprueba sin corrida muestra el uso, no busca una carpeta «--autoprueba»",
                  rc != 0 and "<corrida> --autoprueba" in out and "No existe" not in out))
    rc, out = correr("gobernanza.py", c)
    try:
        gob = json.loads((c / "gobernanza.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        gob = {}
    casos.append(("gobernanza.py queda en «revisar» con el motivo, sin traceback, y no deja el gobernanza.json de antes",
                  rc == 1 and gob.get("estado") == "revisar" and "Traceback" not in out
                  and any(f"falta {rel}/" in str(x) for x in gob.get("problemas", []))))
    return casos


def raiz_de_flujo(texto):
    """Lo que falta para que flujo.js corra en el clon de quien lo llama (L124): ninguna ruta del equipo de alguien,
    RAIZ sale solo de args.raiz y, sin raiz, el flujo se detiene antes de llamar a ningún agente. [problema]"""
    import re
    from sgsi import RUTA_LOCAL   # una sola forma de reconocer la ruta de un equipo (R07)
    problemas = []
    if RUTA_LOCAL.search(texto):
        problemas.append("flujo.js trae la ruta del equipo de alguien")
    m = re.search(r"^const RAIZ = ([^\n]*)$", texto, re.M)
    if not m or m.group(1).split("//")[0].strip() != "A.raiz":
        problemas.append("RAIZ no sale solo de args.raiz (tiene una ruta por omisión o no está)")
    falta = re.search(r"^if \(!A\.raiz\) \{\n\s*throw new Error\('Falta raiz", texto, re.M)
    if not falta or (m and falta.start() > m.start()):
        problemas.append("sin raiz, flujo.js no se detiene antes de usarla")
    return problemas


def _flujo_sin_raiz(ruta):
    """flujo.js con node, como lo carga orquestar.mjs, con los argumentos del README sin «raiz» y un agente que no se
    puede llamar: debe detenerse con «Falta raiz». None si no hay node (queda solo la revisión del texto)."""
    import shutil
    import subprocess  # nosec B404 (node con un guion fijo)
    node = shutil.which("node")
    if not node:
        return None
    guion = ("const fs = require('fs');"
             "const fuente = fs.readFileSync(process.argv[1], 'utf8').replace(/^export const meta\\s*=/m, 'const meta =');"
             "const AF = Object.getPrototypeOf(async function () {}).constructor;"
             "const flujo = new AF('args', 'agent', 'parallel', 'phase', 'log', fuente);"
             "const nunca = () => { throw new Error('LLAMÓ A UN AGENTE'); };"
             "flujo({peticion: 'p', corrida: '/nada/corrida', fuente: {tipo: 'socrata'}}, nunca, nunca, () => {}, () => {})"
             ".then(() => console.log('SIGUIÓ'), (e) => console.log('ERROR ' + e.message));")
    try:
        p = subprocess.run([node, "-e", guion, str(ruta)], capture_output=True, text=True, timeout=60)  # nosec B603
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"node no respondió: {type(e).__name__}"
    return (p.stdout + p.stderr).strip()


def autoprueba():
    """Una spec sellada en otra máquina debe resolver datos Y datos_crudos a la copia de este clon, y un dato que este
    clon no tiene nunca se lee de otra carpeta que sí lo tiene (la copia del dueño en la misma máquina, L123)."""
    import json
    import re
    import shutil
    import tempfile
    casos = []
    otra = "/otra/maquina/agente-solicitudes/ejemplo/datos/ventas.csv"
    spec = resolver_datos({"datos": {"t": otra}, "datos_crudos": {"t": otra}})
    propia = str(RAIZ / "ejemplo/datos/ventas.csv")
    casos.append(("datos y datos_crudos de una spec sellada en otra máquina apuntan a la copia de este clon",
                  spec["datos"]["t"] == propia and spec["datos_crudos"]["t"] == propia))
    # «la otra máquina» es aquí una carpeta temporal que SÍ tiene el dato; este clon no lo tiene
    tmp = Path(tempfile.mkdtemp(prefix="rutas-otro-clon-"))
    try:
        rel = "corridas/_rutas-autoprueba-no-existe/limpio/contratos.csv"
        ajena = tmp / "agente-solicitudes" / rel
        ajena.parent.mkdir(parents=True)
        ajena.write_text("id\n1\n", encoding="utf-8")
        r = resolver(str(ajena))
        casos.append(("un dato que este clon no tiene no se lee de la otra carpeta: la ruta es la de este clon y no "
                      "existe", r == str(RAIZ / rel) and not Path(r).exists()))
        motivo = falta_dato("contratos", r)
        sellada = "corridas/2026-11-06-pipeline-completo-secop-medellin-2025/limpio/contratos.csv"
        motivo_sellada = falta_dato("contratos", str(RAIZ / sellada))
        casos.append(("el motivo nombra el archivo que falta en este clon y con qué se reproduce",
                      motivo.startswith(f"falta {rel} en este clon") and "ingesta.py" in motivo
                      and motivo_sellada.startswith(f"falta {sellada} en este clon")
                      and "contrato_contratos.json --salida" in motivo_sellada
                      and "limpieza.py corridas/2026-11-06-pipeline-completo-secop-medellin-2025/plan_limpieza_contratos.json"
                      in motivo_sellada))
        faltan = faltan_datos({"datos": {"contratos": r}, "datos_crudos": {"contratos": r}})
        casos.append(("faltan_datos da un motivo por archivo, sin repetirlo", faltan == [motivo]))
        # control positivo (L27): con la versión anterior, el mismo dato se leía de la otra carpeta
        casos.append(("control positivo: con resolver() de antes, el clon leía el dato de la otra carpeta",
                      _resolver_antes_del_7_nov(str(ajena)) == str(ajena)))
        # dentro de este clon nada cambia, aunque la carpeta de arriba también se llame agente-solicitudes
        casos.append(("una ruta que ya está dentro de este clon queda igual", resolver(str(RAIZ / "README.md")) == str(RAIZ / "README.md")))
        casos.append(("una ruta sin la marca no se reescribe",
                      resolver("/tmp/datos.csv") == "/tmp/datos.csv" and resolver("datos/x.csv") == "datos/x.csv"))
        anidado = tmp / "agente-solicitudes" / "x" / "agente-solicitudes" / "datos.csv"
        casos.append(("una ruta con la marca fuera de este clon, aunque la repita, queda dentro de este clon",
                      Path(resolver(str(anidado))).is_relative_to(RAIZ)))
        casos += _en_un_clon_sin_el_dato(tmp)
        # flujo.js sin ruta por omisión (L124), con su control positivo: la línea de antes
        flujo = (RAIZ / "flujo.js").read_text(encoding="utf-8")
        problemas = raiz_de_flujo(flujo)
        casos.append(("flujo.js exige raiz y no trae la ruta del equipo de nadie" + (f": {problemas}" if problemas else ""),
                      not problemas))
        antes = flujo.replace("const RAIZ = A.raiz\n",
                              "const RAIZ = A.raiz || '/Users/" + "dueno/agente-solicitudes'   // en otra máquina: pase raiz\n", 1)
        antes = re.sub(r"if \(!A\.raiz\) \{\n.*?\n\}\n", "", antes, count=1, flags=re.S)
        casos.append(("control positivo: con la línea de antes, la revisión del texto la echa de menos",
                      antes != flujo and len(raiz_de_flujo(antes)) == 3))
        salida = _flujo_sin_raiz(RAIZ / "flujo.js")
        if salida is None:
            print("· node no está: de flujo.js solo se revisó el texto")
        else:
            casos.append(("flujo.js con node, sin raiz, se detiene con «Falta raiz» sin llamar a ningún agente",
                          salida.startswith("ERROR Falta raiz") and "LLAMÓ" not in salida))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for nombre, ok in casos:
        print(("✓" if ok else "✗") + " " + nombre)
    malos = [n for n, ok in casos if not ok]
    print("RESUMEN " + json.dumps({"autoprueba": not malos, "casos": len(casos), "fallas": len(malos)}))
    return 0 if not malos else 1


if __name__ == "__main__":
    import sys
    sys.exit(autoprueba() if "--autoprueba" in sys.argv else 0)
