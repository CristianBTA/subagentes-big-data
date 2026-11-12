#!/usr/bin/env python3
"""Rutas que un aporte no puede tocar sin el dueño. Corre la versión de main y nunca el código del aporte.

El filtro de aportes (validar_aporte.py) corre la copia del propio pull request: si el aporte lo cambia, cambia lo que
importa o agrega un módulo que reemplaza a uno de los que importan las herramientas, el verde no prueba nada (L54).
Este chequeo corre en GitHub con pull_request_target, o sea con la versión de main, y el aporte no puede cambiarlo.
No descarga ni ejecuta el código del aporte: recibe solo los nombres de los archivos que cambia (API de GitHub).

Las rutas se comparan como las ve un disco que no distingue mayúsculas ni la forma de los acentos (macOS y Windows; el
runner del filtro es macOS): «.Githooks/pre-commit» es «.githooks/pre-commit» y «Flujo.js» es «flujo.js». Una ruta del
aporte que en ese disco cae sobre otra ruta o carpeta de main escrita distinto también bloquea: en el clon del dueño se
queda un solo archivo, el del aporte, y reemplaza al protegido (L99). Límite: lo que solo iguala Windows (los nombres
cortos 8.3, el punto o el espacio al final de un nombre) no se compara; el runner del filtro y el equipo del dueño son
macOS.

Uso:
  gh api --paginate repos/R/pulls/N/files --jq '.[] | {f: .filename, p: .previous_filename} | @json' \\
      | python3 herramientas/rutas_protegidas.py --autor OWNER --esperados 7
  python3 herramientas/rutas_protegidas.py --autoprueba
Solo biblioteca estándar.
"""
import ast
import json
import os
import re
import subprocess  # nosec B404: git ls-files sin shell, para comparar las rutas del aporte con las de main
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# El filtro, lo que importa (también de forma indirecta: gobernanza importa rutas, seguridad importa seguridad_cwe) y lo
# que corre para decidir; la compuerta local (comprobar, su gancho, .githooks/ y lo que instala) y los flujos de GitHub,
# incluido este chequeo (L86). La autoprueba comprueba que cubre todo lo que importa el filtro y la lista del filtro.
FILTRO = re.compile(r"^(herramientas/(validar_aporte|rutas_protegidas|gobernanza|rutas|seguridad|seguridad_cwe|comprobar"
                    r"|gancho_compuerta|dependencias|blindaje|sgsi|caja|integridad)\.py"
                    r"|herramientas/permitidas(_usuario)?\.json|requirements(-compuerta)?\.txt|\.git(hub|hooks)/.+)$")
# Python los carga solo al arrancar, antes de cualquier herramienta.
ARRANQUE = re.compile(r"(^|/)(sitecustomize|usercustomize)\.py$|\.pth$")
# Lo que HFS+ ignora en un nombre de archivo (los mismos invisibles que vigila git con core.protectHFS): «.git\u200chooks»
# es «.githooks» en ese disco.
IGNORADOS_HFS = dict.fromkeys(map(ord, "\u200c\u200d\u200e\u200f\u202a\u202b\u202c\u202d\u202e"
                                       "\u206a\u206b\u206c\u206d\u206e\u206f\ufeff"))


def clave(ruta):
    """La ruta como la ve un disco que no distingue mayúsculas ni la forma de los acentos (NFC o NFD) e ignora los
    invisibles de HFS+: dos rutas con la misma clave son el mismo archivo en macOS. Las listas de rutas protegidas se
    comparan con ella (L99)."""
    t = unicodedata.normalize("NFC", str(ruta)).translate(IGNORADOS_HFS)
    return unicodedata.normalize("NFC", t.casefold())


def colisiones(rutas, existentes):
    """Las rutas de `rutas` que, en un disco como el de macOS, caen sobre otra ruta o carpeta escrita distinto, de
    `existentes` o de las mismas `rutas`: {ruta: [las grafías del primer tramo que choca, la carpeta o el archivo]}.
    Ahí git deja un solo archivo en el disco: el del aporte reemplaza al de main, o el juez lee el de main y no el del
    aporte (L99)."""
    grafias = {}
    for r in set(existentes) | set(rutas):
        partes = r.split("/")
        for i in range(1, len(partes) + 1):
            pre = "/".join(partes[:i])
            grafias.setdefault(clave(pre), set()).add(pre)
    choques = {}
    for r in rutas:
        partes = r.split("/")
        for i in range(1, len(partes) + 1):
            g = grafias[clave("/".join(partes[:i]))]
            if len(g) > 1:
                choques[r] = sorted(g)
                break
    return choques


def versionados_de_main():
    """Las rutas versionadas del checkout de main donde corre el chequeo (git ls-files, sin shell)."""
    p = subprocess.run(["git", "-C", str(RAIZ), "-c", "core.quotepath=off", "ls-files", "-z"],  # nosec B603 B607
                       capture_output=True, timeout=60, check=True)
    return [r for r in p.stdout.decode("utf-8", "replace").split("\0") if r]


def nombres_que_reemplazan():
    """Módulos que importan las herramientas: biblioteca estándar y las librerías permitidas (por su nombre de import)."""
    nombres = set(sys.stdlib_module_names)
    try:
        perm = json.loads((RAIZ / "herramientas/permitidas.json").read_text(encoding="utf-8"))["permitidas"]
        nombres |= {k.lower() for k in perm} | {v.get("import", "").lower() for v in perm.values()}
    except Exception:
        pass
    return nombres - {""}


def decidir(archivos, autor, esperados=None, existentes=()):
    """archivos: lista de {"f": ruta, "p": ruta anterior o None}; existentes: las rutas versionadas de main, para saber
    si una ruta del aporte choca con otra (main() siempre la pasa; None, cuando git no respondió, es un problema de
    entrada y bloquea; sin pasarla, solo se comparan las rutas del aporte entre sí). Devuelve (tocadas, bloquea,
    problemas_de_entrada). Las listas se comparan con la clave de la ruta (sin mayúsculas, acentos en NFC y sin los
    invisibles de HFS+), no con la ruta tal cual (L99)."""
    entrada = []
    if esperados is not None and len(archivos) < esperados:
        entrada.append(f"la API entregó {len(archivos)} de {esperados} archivos: no se puede revisar todo el aporte")
    if existentes is None:
        entrada.append("sin la lista de rutas de main no se puede revisar si una ruta del aporte choca con otra")
        existentes = []
    reemplazan = nombres_que_reemplazan()
    rutas = sorted({r for a in archivos for r in (a.get("f"), a.get("p")) if r})
    choques = colisiones(rutas, existentes)
    tocadas = []
    for r in rutas:
        k = clave(r)
        if r in choques:
            tocadas.append((r, f"en macOS y Windows {' y '.join(f'«{g}»' for g in choques[r])[:160]} son la misma ruta: "
                               "solo cambian mayúsculas, acentos o caracteres invisibles, y el archivo del aporte reemplaza al de main"))
        if FILTRO.match(k):
            tocadas.append((r, "el filtro de aportes, lo que corre o los flujos de GitHub"))
        elif ARRANQUE.search(k):
            tocadas.append((r, "Python lo carga solo al arrancar"))
        else:
            m = re.match(r"^herramientas/([^/]+?)(\.py|/.*)?$", k)
            if m and m.group(1).lower() in reemplazan:
                tocadas.append((r, f"reemplaza el módulo «{m.group(1)}» que importan las herramientas"))
    bloquea = bool(entrada) or (bool(tocadas) and autor != "OWNER")
    return sorted(set(tocadas)), bloquea, entrada


def importa(ruta):
    """Módulos de herramientas/ que importa un archivo de herramientas/ (ast, sin ejecutarlo)."""
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    nombres = set()
    for n in ast.walk(arbol):
        if isinstance(n, ast.Import):
            nombres |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module and not n.level:
            nombres.add(n.module.split(".")[0])
    return {m for m in nombres if (RAIZ / "herramientas" / f"{m}.py").is_file()}


def cadena_sin_cubrir(filtro=None):
    """Lo que FILTRO no cubre y debería: el cierre de lo que importan el filtro y este chequeo, y todo lo que nombra la
    lista CADENA_DEL_FILTRO de validar_aporte.py (leída con ast, sin importarla). Una lista que se queda atrás es un hueco."""
    vistos, pendientes = set(), ["validar_aporte", "rutas_protegidas"]
    while pendientes:
        m = pendientes.pop()
        if m not in vistos:
            vistos.add(m)
            pendientes += sorted(importa(RAIZ / "herramientas" / f"{m}.py"))
    rutas = {f"herramientas/{m}.py" for m in vistos}
    cadena = None
    for n in ast.walk(ast.parse((RAIZ / "herramientas/validar_aporte.py").read_text(encoding="utf-8"))):
        if (isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "CADENA_DEL_FILTRO" for t in n.targets)
                and isinstance(n.value, ast.Call) and n.value.args and isinstance(n.value.args[0], ast.Constant)):
            cadena = re.compile(n.value.args[0].value)
    if cadena is None:
        return ["herramientas/validar_aporte.py: no se encontró CADENA_DEL_FILTRO"]
    try:
        versionados = subprocess.run(["git", "-C", str(RAIZ), "ls-files"], capture_output=True, text=True,  # nosec B603 B607
                                     timeout=60, check=True).stdout.splitlines()
    except Exception as e:  # sin la lista no se puede revisar: falla cerrada
        return [f"git ls-files no respondió ({type(e).__name__}): no se pudo revisar la lista del filtro"]
    rutas |= {r for r in versionados if cadena.match(r)}
    return sorted(r for r in rutas if not (filtro or FILTRO).match(r))


def leer_entrada(texto):
    archivos = []
    for n, linea in enumerate(texto.splitlines(), 1):
        if not linea.strip():
            continue
        d = json.loads(linea)  # una línea que no es JSON detiene todo (falla cerrada)
        if not isinstance(d, dict) or not isinstance(d.get("f"), str):
            raise ValueError(f"línea {n} sin ruta")
        archivos.append({"f": d["f"], "p": d.get("p") if isinstance(d.get("p"), str) else None})
    return archivos


def main(argv):
    if "--autoprueba" in argv:
        return autoprueba()
    autor = argv[argv.index("--autor") + 1] if "--autor" in argv else ""
    esperados = int(argv[argv.index("--esperados") + 1]) if "--esperados" in argv else None
    try:
        archivos = leer_entrada(sys.stdin.read())
    except Exception as e:
        print(f"✗ no se pudo leer la lista de archivos ({type(e).__name__}): no se aprueba lo que no se revisó")
        return 1
    try:
        existentes = versionados_de_main()
    except Exception as e:  # sin la lista de main no se puede revisar si una ruta choca: falla cerrada (decidir bloquea)
        print(f"✗ git ls-files no respondió en {RAIZ} ({type(e).__name__})")
        existentes = None
    tocadas, bloquea, entrada = decidir(archivos, autor, esperados, existentes=existentes)
    lineas = [f"Aporte: {len(archivos)} archivo(s); autor: {autor or 'desconocido'}"]
    lineas += [f"  ✗ {e}" for e in entrada]
    lineas += [f"  {'·' if autor == 'OWNER' else '✗'} {r}: {por}" for r, por in tocadas]
    if bloquea:
        lineas.append("✗ El aporte toca el filtro, lo que corre, los flujos de GitHub o una ruta que en macOS es otra: solo los "
                      "cambia el dueño. Quita esos archivos del pull request (si encontraste un hueco del filtro, abre un issue).")
    else:
        lineas.append("✓ " + ("Es del dueño: los cambios marcados los revisa él." if tocadas else "No toca rutas protegidas."))
    print("\n".join(lineas))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write("```\n" + "\n".join(lineas) + "\n```\n")
    print("RESUMEN " + json.dumps({"archivos": len(archivos), "tocadas": [r for r, _ in tocadas], "bloquea": bloquea},
                                  ensure_ascii=False))
    return 1 if bloquea else 0


def autoprueba():
    """Cada caso con lo que debe pasar; más todas las herramientas de hoy, que un tercero sí puede mejorar."""
    T, D = "CONTRIBUTOR", "OWNER"
    casos = [
        ("edita el filtro", [{"f": "herramientas/validar_aporte.py"}], T, True),
        ("edita lo que importa el filtro", [{"f": "herramientas/gobernanza.py"}], T, True),
        ("agrega un flujo de GitHub", [{"f": ".github/workflows/x.yml"}], T, True),
        ("edita este chequeo", [{"f": "herramientas/rutas_protegidas.py"}], T, True),
        ("cambia las dependencias", [{"f": "requirements.txt"}], T, True),
        ("reemplaza un módulo estándar", [{"f": "herramientas/unicodedata.py"}], T, True),
        ("reemplaza un módulo con una carpeta", [{"f": "herramientas/json/__init__.py"}], T, True),
        ("reemplaza una librería permitida", [{"f": "herramientas/pandas.py"}], T, True),
        ("sitecustomize", [{"f": "herramientas/sitecustomize.py"}], T, True),
        ("archivo .pth", [{"f": "a.pth"}], T, True),
        ("renombra el filtro para sacarlo", [{"f": "herramientas/viejo.py", "p": "herramientas/validar_aporte.py"}], T, True),
        ("edita las reglas CWE que importa la compuerta", [{"f": "herramientas/seguridad_cwe.py"}], T, True),
        ("edita la compuerta que importa el filtro", [{"f": "herramientas/comprobar.py"}], T, True),
        ("edita el gancho de la compuerta", [{"f": "herramientas/gancho_compuerta.py"}], T, True),
        ("edita lo que importa gobernanza", [{"f": "herramientas/rutas.py"}], T, True),
        ("agrega librerías al perfil de usuario", [{"f": "herramientas/permitidas_usuario.json"}], T, True),
        ("cambia las dependencias de la compuerta", [{"f": "requirements-compuerta.txt"}], T, True),
        ("edita el gancho de git", [{"f": ".githooks/pre-commit"}], T, True),
        ("agrega un gancho de git", [{"f": ".githooks/post-checkout"}], T, True),
        ("renombra la compuerta para sacarla", [{"f": "herramientas/x.py", "p": "herramientas/comprobar.py"}], T, True),
        ("la API entrega menos archivos de los que dice el pull request", [{"f": "agentes/x.md"}], T, True, 3),
        ("aporte normal", [{"f": "agentes/13-x.md"}, {"f": "baterias/fechas/casos.json"}, {"f": "herramientas/color.py"}], T, False),
        ("herramienta nueva con nombre propio", [{"f": "herramientas/recorrer_partes.py"}], T, False),
        ("el dueño toca el filtro", [{"f": "herramientas/validar_aporte.py"}, {"f": ".github/workflows/x.yml"}], D, False),
        # L99: rutas que solo cambian mayúsculas, la forma de un acento o un invisible de HFS+ (en macOS son la misma)
        ("el gancho de git con otra mayúscula", [{"f": ".Githooks/pre-commit"}], T, True),
        ("el flujo con otra mayúscula", [{"f": "Flujo.js"}], T, True),
        ("una ficha con otra mayúscula", [{"f": "agentes/00-Reglas-comunes.md"}], T, True),
        ("el filtro con otra mayúscula", [{"f": "Herramientas/validar_aporte.py"}], T, True),
        ("el gancho con un invisible de HFS+", [{"f": ".git\u200chooks/pre-commit"}], T, True),
        ("una carpeta con otra mayúscula", [{"f": "AGENTES/14-x.md"}], T, True),
        ("la tilde en otra forma (NFD)", [{"f": unicodedata.normalize("NFD", "ejemplo/guía.md")}], T, True, None,
         ["ejemplo/guía.md"]),
        ("dos rutas del mismo aporte que chocan", [{"f": "agentes/14-x.md"}, {"f": "agentes/14-X.md"}], T, True),
        ("la misma ruta, con la misma grafía", [{"f": "agentes/00-reglas-comunes.md"}, {"f": "flujo.js"}], T, False),
        ("la tilde en la misma forma (NFC)", [{"f": "ejemplo/guía.md"}], T, False, None, ["ejemplo/guía.md"]),
        ("sin la lista de main", [{"f": "agentes/13-x.md"}], T, True, None, None),
    ]
    try:
        hoy_main = versionados_de_main()
    except Exception as e:  # sin la lista no se puede probar nada: falla cerrada
        print(f"✗ git ls-files no respondió ({type(e).__name__}): sin la lista de main la autoprueba no prueba nada")
        hoy_main = None
    malos = [] if hoy_main else ["git ls-files"]
    for c in casos:
        nombre, archivos, autor, debe = c[:4]
        esperados = c[4] if len(c) > 4 and c[4] is not None else len(archivos)
        existentes = c[5] if len(c) > 5 else (hoy_main or [])
        _, bloquea, _ = decidir(archivos, autor, esperados, existentes=existentes)
        ok = bloquea == debe
        print(f"{'✓' if ok else '✗'} {nombre}: {'bloquea' if bloquea else 'pasa'}")
        if not ok:
            malos.append(nombre)
    hoy = [str(p.relative_to(RAIZ)) for p in sorted((RAIZ / "herramientas").glob("*.py"))]
    falsas = [h for h in hoy if not FILTRO.match(h) and decidir([{"f": h}], T, existentes=hoy_main or [])[1]]
    print(f"{'✓' if not falsas else '✗'} {len(hoy)} herramientas de hoy: un tercero puede mejorar las que no son del filtro"
          + (f" — falsas alarmas: {falsas}" if falsas else ""))
    sin_cubrir = cadena_sin_cubrir()
    print(f"{'✓' if not sin_cubrir else '✗'} lo que importa el filtro (directo o indirecto) y la lista del filtro están en FILTRO"
          + (f" — sin cubrir: {sin_cubrir}" if sin_cubrir else ""))
    malos += [f"sin cubrir: {r}" for r in sin_cubrir]
    # control positivo (L27): con la lista de antes del 6-nov, el chequeo sí encuentra lo que faltaba
    antes = cadena_sin_cubrir(re.compile(r"^(herramientas/(validar_aporte|rutas_protegidas|gobernanza|seguridad|dependencias"
                                         r"|blindaje|sgsi|caja|integridad)\.py|herramientas/permitidas\.json"
                                         r"|requirements\.txt|\.github/.+)$"))
    esperadas = {"herramientas/seguridad_cwe.py", "herramientas/comprobar.py", "herramientas/rutas.py"}
    ok = esperadas <= set(antes)
    print(f"{'✓' if ok else '✗'} control positivo: con la lista de antes faltaban {len(antes)} rutas ({', '.join(antes)})")
    if not ok:
        malos.append("control positivo: el chequeo no encuentra lo que faltaba en la lista de antes")
    for nombre, texto in (("línea que no es JSON", "esto no es json\n"), ("línea sin ruta", '{"p": "x"}\n')):
        try:
            leer_entrada(texto)
            malos.append(nombre)
            print(f"✗ {nombre}: se aceptó")
        except Exception:
            print(f"✓ {nombre}: se detiene")
    print("RESUMEN " + json.dumps({"autoprueba": "aprobada" if not (malos or falsas) else "fallida", "casos": len(casos) + 5,
                                   "fallas": malos + falsas}, ensure_ascii=False))
    return 1 if malos or falsas else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
