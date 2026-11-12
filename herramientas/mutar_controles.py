#!/usr/bin/env python3
"""Probar al probador de las defensas (sin IA): cada control se quita en una copia y su prueba del blindaje debe ceder.

Uso: python herramientas/mutar_controles.py [--solo M01,M03]

Un control que se puede borrar sin que ninguna prueba se ponga roja no se distingue de uno que no existe. La revisión
ciega lo encontró en tres (SEG-3): al quitar las compuertas de reglas.py, la comprobación de valores finitos o el saneado
de los mensajes, las baterías, el blindaje y la corrida seguían en verde. Aquí, por cada mutante:
  1. se copia herramientas/ a una carpeta temporal, con los CSV que lee la batería FAILFAST (el repositorio no se toca);
  2. se quita el control con un reemplazo exacto: si el texto ya no está, el mutante falla, porque el control cambió y
     hay que rehacerlo (no se da por muerto un mutante que no se aplicó);
  3. se corre en la copia la prueba del blindaje que lo cubre y se exige que ceda por el ataque, no por un error ni por
     «prueba inválida».
El control positivo (L27) es la copia sin mutar: ahí las mismas pruebas deben resistir. Lecciones L92, L93 y L94.
"""
import concurrent.futures
import json
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PY = sys.executable

# (id, qué se quita, archivo, texto exacto, reemplazo, prueba que debe ceder)
MUTANTES = [
    ("M01", "reglas.py sin compuertas: se carga y corre aunque la compuerta la bloquee", "herramientas/verificar.py",
     '    bloqueos = compuertas(ruta)\n    if bloqueos:\n        return [], [f"reglas.py no pasa las compuertas: {b}" for b in bloqueos]\n',
     "", "B30"),
    ("M02", "la forma del resultado sin la comprobación de valores finitos (solo vacíos)", "herramientas/verificar.py",
     " or not math.isfinite(a_num(f[v]))", "", "B31"),
    ("M03", "las cifras de la presentación sin comprobar cada dato (un NaN entra al cálculo)", "herramientas/verificar_presentacion.py",
     '    if not math.isfinite(x):\n        raise ErrorCalculo("valor no finito (NaN o infinito) en los datos")\n', "", "B31"),
    ("M04", "las cifras de la presentación sin comprobar el resultado del cálculo", "herramientas/verificar_presentacion.py",
     '            if not math.isfinite(v):\n                raise ErrorCalculo("el cálculo no da un número finito")\n', "", "B31"),
    ("M05", "la presentación lee un informe.json con NaN o Infinity", "herramientas/verificar_presentacion.py",
     "parse_constant=no_finitos)", ")", "B31"),
    ("M06", "mensajes de error sin sanear (pasan tal cual al informe)", "herramientas/verificar.py",
     "def sanear(t, datos=None):\n", "def sanear(t, datos=None):\n    return str(t)[:300]\n", "B26"),
    ("M07", "saneado sin las palabras de las celdas (solo comillas y cifras largas)", "herramientas/verificar.py",
     "    if datos:\n        palabras = palabras_de_celdas(datos)\n", "    if False:\n        palabras = palabras_de_celdas(datos)\n", "B26"),
    ("M08", "el perfil sin los datos sensibles: muestra los valores de etnia o discapacidad", "herramientas/perfilar.py",
     "    if es_sensible(nombre):\n        return SENSIBLE\n", "", "B32"),
    ("M09", "el perfil muestra el texto libre que no cruza entre dos tablas", "herramientas/perfilar.py",
     "                    elif col in privadas_de[x] or col in privadas_de[y]:   # texto libre, dato sensible o texto largo\n"
     "                        sin_cruce_mostrar = [\"(omitidos: columna privada)\"]\n", "", "B32"),
    ("M10", "el perfil muestra el mínimo y el máximo de una columna privada", "herramientas/perfilar.py",
     'columna privada"} if privada else', 'columna privada"} if False else', "B32"),
    ("M11", "el perfil muestra el rango de fechas de una columna privada", "herramientas/perfilar.py",
     "    if fechas and privada:", "    if False:", "B32"),
    ("M12", "la batería FAILFAST sin las autopruebas de la ingesta y de la limpieza", "herramientas/baterias.py",
     "    for herramienta, minimo in AUTOPRUEBAS.items():", "    for herramienta, minimo in {}.items():", "B33"),
    ("M13", "el filtro no busca rutas que en macOS caen sobre otra escrita distinto", "herramientas/rutas_protegidas.py",
     "            if len(g) > 1:\n                choques[r] = sorted(g)\n", "            if False:\n                choques[r] = sorted(g)\n", "B35"),
    ("M14", "la clave de la ruta distingue mayúsculas (como el disco de Linux, no como el de macOS)", "herramientas/rutas_protegidas.py",
     '    return unicodedata.normalize("NFC", t.casefold())\n', '    return unicodedata.normalize("NFC", t)\n', "B35"),
    ("M15", "los ganchos y flujos de GitHub son solo del dueño únicamente con su grafía exacta", "herramientas/validar_aporte.py",
     "    return DEL_DUENO.match(clave(ruta)) is not None\n", "    return DEL_DUENO.match(ruta) is not None\n", "B35"),
    ("M16", "lo que juzga a los aportes (CONFIABLES) solo con su grafía exacta", "herramientas/validar_aporte.py",
     "    k = clave(ruta)\n    return next((c for c in CONFIABLES", "    k = ruta\n    return next((c for c in CONFIABLES", "B35"),
    ("M17", "orquestar.mjs (lanza agy y Codex sin pedir permisos) fuera de lo que decide el dueño", "herramientas/validar_aporte.py",
     '"flujo.js", "orquestar.mjs", "requirements.txt"', '"flujo.js", "requirements.txt"', "B36"),
    ("M18", "el código que corre fuera de Python (scripts, permiso de ejecución, «#!», páginas con código) pasa sin el dueño",
     "herramientas/validar_aporte.py", "def ejecutable(ruta, p, modo=None):\n", "def ejecutable(ruta, p, modo=None):\n    return None\n", "B36"),
    ("M19", "borrar o cambiar lo que ya estaba en baterias/ o en las mutantes pasa sin el dueño", "herramientas/validar_aporte.py",
     "    if not k.startswith(CRECEN):\n        return None\n", "    if True:\n        return None\n", "B37"),
    ("M20", "lo sellado de una corrida (sellos, reglas.py, spec.json, caso_conocido/) cambia sin el dueño", "herramientas/validar_aporte.py",
     "    if any(k == clave(s) or (s.endswith(\"/\") and k.startswith(clave(s))) for s in sellado):\n",
     "    if False:\n", "B37"),
    ("M21", "las líneas quitadas o cambiadas de un texto de las baterías no cuentan", "herramientas/validar_aporte.py",
     "    faltan = Counter(tv.splitlines()) - Counter(tn.splitlines())\n", "    faltan = Counter()\n", "B37"),
    ("M22", "los casos quitados o cambiados de un JSON de las baterías no cuentan", "herramientas/validar_aporte.py",
     "                out.append(f\"{camino}[{i}]\")\n", "                pass\n", "B37"),
    ("M23", "el filtro acepta más de una línea RESUMEN (lee la última, la que escribió el aporte)", "herramientas/validar_aporte.py",
     "    lineas = [x for x in texto.splitlines() if x.startswith(\"RESUMEN \")]\n    if len(lineas) != 1:\n        return None\n",
     "    lineas = [x for x in texto.splitlines() if x.startswith(\"RESUMEN \")][-1:]\n    if len(lineas) != 1:\n        return None\n", "B38"),
    ("M24", "el filtro no cruza la salida del banco con su RESUMEN ni con las pruebas de la base", "herramientas/validar_aporte.py",
     "    if descuadre:\n        fallas.append(", "    if False:\n        fallas.append(", "B38"),
    ("M25", "verificar.py no mira el estado ni la huella de la limpieza (una rechazada o una capa limpia cambiada aprueban)",
     "herramientas/verificar.py", "    motivos += motivos_limpieza\n", "", "B39"),
    ("M26", "el informe final da el procesamiento por aprobado con solo informe.json, sin mirar la limpieza",
     "herramientas/informe_final.py",
     '"Procesamiento": (inf.get("estado") == "aprobado" and not motivos_limpieza) if inf or motivos_limpieza else None,',
     '"Procesamiento": inf.get("estado") == "aprobado" if inf else None,', "B39"),
    ("M27", "una limpieza que se detiene deja la capa limpia de la anterior", "herramientas/limpieza.py",
     "        retirado = retirar(destino.get(\"salida\"))\n", "        retirado = False\n", "B39"),
    ("M28", "el filtro lee un texto en UTF-16, en latin-1 o con NUL como si fuera UTF-8 (errors=ignore)", "herramientas/validar_aporte.py",
     "def texto_utf8(datos):\n", "def texto_utf8(datos):\n    return datos.decode(\"utf-8\", \"ignore\"), None\n", "B40"),
    ("M29", "de una página o un SVG no se resuelven las entidades ni se quitan las etiquetas", "herramientas/validar_aporte.py",
     "    if s in MARCADO or re.match(r\"\\s*<\", texto):\n        textos += texto_de_marcado(texto)\n", "", "B40"),
    ("M30", "el filtro no lee el texto de un PDF", "herramientas/validar_aporte.py",
     "    if s == \".pdf\":\n        return leer_pdf(datos)\n", "    if s == \".pdf\":\n        return [], [], []\n", "B40"),
    ("M31", "de datos/ y limpio/ solo se prohíben los CSV", "herramientas/validar_aporte.py",
     "(datos|limpio)/(?!procedencia_[^/]+\\.json$)", "(datos|limpio)/.*\\.csv$", "B40"),
    ("M32", "el barrido de datos personales vuelve a la lista de extensiones", "herramientas/validar_aporte.py",
     "    if \"baterias/privacidad/\" not in ruta:\n        hall = datos_no_ficticios_en(textos)\n",
     "    if Path(ruta).suffix in (\".md\", \".json\", \".csv\", \".txt\") and \"baterias/privacidad/\" not in ruta:\n"
     "        hall = datos_no_ficticios_en(textos)\n", "B40"),
    ("M33", "las celdas que una hoja de cálculo ejecuta como fórmula pasan en las tablas del aporte", "herramientas/validar_aporte.py",
     "    if not ruta.startswith(FORMULAS_A_PROPOSITO):\n        formulas = celdas_formula(p, texto, tabla)\n",
     "    if False:\n        formulas = celdas_formula(p, texto, tabla)\n", "B40"),
    ("M34", "el barrido de gobernanza lee el texto tal cual (sin NFKC ni quitar los caracteres de formato)", "herramientas/gobernanza.py",
     '    return _FORMATO[0].sub("", unicodedata.normalize("NFKC", t))\n', "    return t\n", "B27"),
    ("M35", "de una salida HTML solo se resuelven las entidades (las etiquetas en medio de un dato quedan)", "herramientas/gobernanza.py",
     '        texto = "\\n".join(texto_de_marcado(texto))\n', "        texto = html.unescape(texto)\n", "B27"),
    ("M36", "la detección de instrucciones lee el texto tal cual (sin su forma canónica ni las letras de otro alfabeto vueltas latinas)",
     "herramientas/gobernanza.py",
     "    for forma in ((t,) if t.isascii() else (t, latinizar(forma_canonica(t)))):\n", "    for forma in (t,):\n", "B27"),
]


def copia():
    """herramientas/ y lo que la batería FAILFAST lee en B33 (sus CSV y los controles de ejemplo/datos)."""
    d = Path(tempfile.mkdtemp(prefix="mutar-controles-")).resolve()
    shutil.copytree(RAIZ / "herramientas", d / "herramientas", ignore=shutil.ignore_patterns("*.pyc"))
    for x in ("baterias/failfast", "ejemplo/datos"):
        shutil.copytree(RAIZ / x, d / x)
    return d


def correr_banco(d, ids):
    """Corre en la copia las pruebas `ids` del blindaje. Devuelve {id: (resultado, evidencia)} y el RESUMEN (o None)."""
    p = subprocess.run([PY, str(d / "herramientas" / "blindaje.py"), "--solo", ",".join(ids)], cwd=d,  # nosec B603
                       capture_output=True, text=True, timeout=900)
    out = p.stdout + p.stderr
    pruebas = {m.group(1): (m.group(2), m.group(3)) for m in
               re.finditer(r"^[✓✗·!] (B\d+) \[[^\]]*\] .*\n    (RESISTE|CEDE|NO APLICA|ERROR): (.*)$", out, re.M)}
    linea = next((l for l in reversed(out.splitlines()) if l.startswith("RESUMEN ")), None)
    return pruebas, (json.loads(linea[len("RESUMEN "):]) if linea else None), out


def mutar(m):
    ident, que, archivo, viejo, nuevo, prueba = m
    d = copia()
    try:
        f = (d / archivo).resolve()
        if not f.is_relative_to(d / "herramientas"):
            return ident, "no se aplicó", f"{archivo} no está en herramientas/"
        texto = f.read_text(encoding="utf-8")
        if texto.count(viejo) != 1:
            return ident, "no se aplicó", f"el texto del control aparece {texto.count(viejo)} veces en {archivo}: el control cambió, rehacer el mutante"
        f.write_text(texto.replace(viejo, nuevo), encoding="utf-8")
        try:
            py_compile.compile(str(f), doraise=True, cfile=str(d / "compilado.pyc"))
        except py_compile.PyCompileError as e:
            return ident, "no se aplicó", f"el mutante no compila: {str(e)[:120]}"
        pruebas, resumen, out = correr_banco(d, [prueba])
        res, evid = pruebas.get(prueba, (None, ""))
        if resumen is None or res is None:
            return ident, "no se midió", f"el banco no terminó: {' | '.join(out.strip().splitlines()[-3:])[:160]}"
        if res == "CEDE" and not evid.startswith("prueba inválida"):
            return ident, "muere", f"{prueba} cede: {evid[:150]}"
        return ident, "sobrevive", f"{prueba} {res}: {evid[:150]}"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main(argv):
    solo = set(argv[argv.index("--solo") + 1].split(",")) if "--solo" in argv else None
    mutantes = [m for m in MUTANTES if not solo or m[0] in solo]
    ids = sorted({m[5] for m in mutantes})
    # control positivo (L27): sin mutar, en la misma copia, las pruebas resisten; si no, un «muere» no probaría nada
    d = copia()
    try:
        pruebas, resumen, out = correr_banco(d, ids)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    no_resisten = [i for i in ids if pruebas.get(i, (None,))[0] != "RESISTE"]
    print(f"{'✓' if not no_resisten and resumen else '✗'} control: sin mutar, {', '.join(ids)} "
          + ("resisten" if not no_resisten and resumen else f"no resisten ({no_resisten or 'el banco no terminó'})"))
    if no_resisten or not resumen:
        print("Sin control positivo los mutantes no prueban nada: no se corren.")
        print("RESUMEN " + json.dumps({"mutantes": len(mutantes), "mueren": 0, "sobreviven": [], "control": False}, ensure_ascii=False))
        return 1
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        resultados = list(ex.map(mutar, mutantes))
    por_id = {m[0]: m for m in mutantes}
    for ident, estado, detalle in resultados:
        print(f"{'✓' if estado == 'muere' else '✗'} {ident} {estado} · {por_id[ident][1]} ({por_id[ident][2]})\n    {detalle}")
    vivos = [i for i, e, _ in resultados if e != "muere"]
    print("RESUMEN " + json.dumps({"mutantes": len(mutantes), "mueren": len(mutantes) - len(vivos), "sobreviven": vivos, "control": True},
                                  ensure_ascii=False))
    return 1 if vivos else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
