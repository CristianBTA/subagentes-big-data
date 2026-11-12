#!/usr/bin/env python3
"""Agente masivo de datos públicos: de un catálogo completo a fichas de oportunidad validadas.

Uso:
  python herramientas/agente_masivo.py <dominio> --trabajo <carpeta> --conjuntos <id,id,…> [--motor claude|agy|codex|ninguno]
  python herramientas/agente_masivo.py <dominio> --trabajo <carpeta> --fuentes <fuentes.json> [--motor …]
  python herramientas/agente_masivo.py <dominio> --trabajo <carpeta> --descubrir [--tema "salud"] [--top 8] [--min-filas 1000000]
                                       [--por-publicador 2] [--actualizar]
  python herramientas/agente_masivo.py <dominio> --trabajo <carpeta> --solo-validar

FUENTES AUTORIZADAS: el agente NO trae ningún conjunto por defecto (ni SECOP ni otro). Solo se conecta a los que el dueño
declara (--conjuntos <id,id>, cada id de Socrata con la forma abcd-1234, o --fuentes con {"dominio": "…", "conjuntos": ["…"],
"nota": "por qué"}). Sin fuentes declaradas no se conecta a ninguno. --descubrir recorre el catálogo del portal (con permiso
explícito) solo para SUGERIR candidatos y el comando para autorizarlos; no trabaja con ninguno hasta que se autorice. Se le
puede sugerir de qué se va a tratar con --tema («salud», «movilidad», «clima», «educación»…): propone los conjuntos grandes
de ese tema. Sin tema, propone de varios publicadores (--por-publicador, 2 por defecto), para que una sola fuente no llene la
lista. La lista autorizada queda en <trabajo>/fuentes_autorizadas.json, el encargo le prohíbe a la IA consultar otros y
validar_ficha.py lo comprueba (V0).

La IA propone y una prueba sin IA comprueba. Los pasos sin IA corren solos; el de IA lo hace el motor que se tenga:
  1. catálogo: explorador_catalogo.py mide todos los conjuntos (reanudable con la caché de --catalogo);
  2. relevancia: relevancia_catalogo.py ordena por si permiten decir estado, lugar e impacto, y por tamaño;
  3. candidatos (solo con --descubrir): los --top mejores con al menos --min-filas; con --tema, los de ese tema; sin tema,
     los que dicen al menos dos de estado, lugar e impacto, con tope por publicador. Quedan en <trabajo>/sugerencias.json;
  4. dictamen medido: dictamen_bigdata.py por candidato (<trabajo>/fichas/<id>.dictamen.json): la IA no lo escribe;
  5. encargo: <trabajo>/ENCARGO.md, desde plantillas/encargo_fichas.md, con los candidatos;
  6. IA: con --motor claude, agy o codex se lanza esa CLI sin interacción con el encargo (binarios: CLAUDE_BIN, AGY_BIN y
     CODEX_BIN; Claude usa el perfil de CLAUDE_CONFIG_DIR); con --motor ninguno se imprime el texto para pegarlo en otra IA;
  7. validación sin IA: validar_ficha.py por ficha, SIN caché y contra la fuente real → <trabajo>/RESULTADO.md;
  8. whitepaper para el estudiante, en TRES hojas tamaño carta (<trabajo>/WHITEPAPER.pdf y .html): la IA puede escribir
     el resumen (RESUMEN_IA.md), que entra solo si pasa una comprobación sin IA; el ANÁLISIS lo hace el estudiante.
Después de esto, el juicio de valor lo hacen un juez ciego y las personas: el validador mide la forma, no el valor.

Uso local: el agente se USA, no se modifica. La IA solo escribe en la carpeta de trabajo; aunque haga una investigación,
nunca toca el agente. Para que no dependa de que la IA obedezca:
  - antes de darle el turno, se sella la huella SHA-256 de lo que forma el agente (herramientas/, plantillas/, baterias/,
    flujo.js, orquestar.mjs y los documentos de uso); al terminar se compara: si algo cambió, la corrida NO VALE y se
    nombran los archivos (no se restauran solos: en la misma carpeta pueden trabajar otras personas);
  - la validación del paso 7 corre con las herramientas de la versión de Git (git archive HEAD), no con las de la carpeta;
  - el catálogo, las fichas y los resultados viven en fuentes/, que está fuera de Git: nada de una corrida se publica
    (si --trabajo cae en una carpeta que Git versionaría, el agente se detiene antes de escribir nada).
Autoprueba sin red: python herramientas/agente_masivo.py --autoprueba
"""
import hashlib
import json
import re
import os
import shutil
import tempfile
import subprocess
import sys
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
PY = sys.executable
sys.path.insert(0, str(AQUI))

SIN_FUENTES = ("No hay fuentes autorizadas, y el agente no trae ninguna por defecto (ni SECOP ni otra): no se conecta a ningún "
               "conjunto que no declares.\n"
               "  Declara los conjuntos que elijas:  --conjuntos <id,id>   (cada id de Socrata tiene la forma abcd-1234)\n"
               "  o un archivo:  --fuentes fuentes.json   ({\"dominio\": \"…\", \"conjuntos\": [\"…\"], \"nota\": \"por qué se autoriza\"})\n"
               "  ¿Aún no sabes cuáles? Sugiérele de qué se va a tratar y te propone candidatos de ese portal (con tu permiso):\n"
               "    --descubrir --tema \"salud\"      (o «movilidad», «clima», «educación»…; sin --tema propone de varios publicadores)")


def fuentes_autorizadas(argv, dominio, trabajo):
    """Los conjuntos que el dueño autoriza; se guardan en la carpeta de trabajo. None si no hay ninguno declarado."""
    g = lambda k: argv[argv.index(k) + 1] if k in argv else None
    ids, nota = None, ""
    if g("--conjuntos"):
        ids = [x.strip() for x in g("--conjuntos").split(",") if x.strip()]
    elif g("--fuentes"):
        f = json.loads(Path(g("--fuentes")).read_text(encoding="utf-8"))
        if f.get("dominio") and f["dominio"] != dominio:
            raise SystemExit(f"El archivo de fuentes autoriza {f['dominio']}, no {dominio}.")
        ids, nota = [str(x) for x in f.get("conjuntos", [])], f.get("nota", "")
    archivo = trabajo / "fuentes_autorizadas.json"
    if ids:
        if not all(re.fullmatch(r"[a-z0-9]{4}-[a-z0-9]{4}", x) for x in ids):
            raise SystemExit("Cada conjunto autorizado es un id de Socrata de la forma abcd-1234 (cuatro letras o números, guion, cuatro).")
        archivo.write_text(json.dumps({"dominio": dominio, "conjuntos": ids, "nota": nota,
                                       "autorizado_el": datetime.now().isoformat(timespec="seconds")}, ensure_ascii=False, indent=1),
                           encoding="utf-8")
        return ids
    if archivo.exists():
        return json.loads(archivo.read_text(encoding="utf-8")).get("conjuntos") or None
    return None


def inventario_autorizado(dominio, ids, destino):
    """Metadatos (columnas y tipos) SOLO de los conjuntos autorizados; nada del resto del portal."""
    from explorador_catalogo import pedir
    inv = []
    for i in ids:
        m = json.loads(pedir(f"https://{dominio}/api/views/{i}.json"))
        cols = [c for c in m.get("columns", []) if not str(c.get("fieldName", "")).startswith(":")]
        inv.append({"id": i, "nombre": m.get("name"), "categoria": m.get("category"),
                    "campos": [c.get("fieldName") for c in cols], "visibles": [c.get("name") for c in cols],
                    "tipos": [str(c.get("dataTypeName", "")).lower() for c in cols]})
    destino.write_text(json.dumps(inv, ensure_ascii=False), encoding="utf-8")
    return inv


VACIAS = {"de", "del", "la", "las", "los", "el", "en", "y", "o", "u", "para", "por", "con", "sin", "un", "una", "unos", "unas",
          "al", "su", "sus", "que", "como", "se", "sobre", "entre", "datos", "dato", "conjunto", "conjuntos", "base", "bases",
          "abiertos", "abierto", "publicos", "publico", "publica", "publicas", "colombia", "tema", "vamos", "tratar", "trabajar"}


def palabras_tema(tema):
    """Las palabras con que la persona sugiere el tema, sin tildes ni palabras vacías («la salud en Colombia» → salud)."""
    from relevancia_catalogo import normal
    return [w for w in dict.fromkeys(normal(tema).split()) if len(w) >= 3 and w not in VACIAS]


def _toca(palabra, tokens):
    """La palabra o su raíz está entre los tokens: «vacunas» encuentra «vacunacion»."""
    raiz = palabra[:max(4, len(palabra) - 2)]
    return any(t.startswith(raiz) for t in tokens)


def sugerir(rel, inventario=(), tema=None, top=8, min_filas=1_000_000, por_publicador=2):
    """Candidatos de --descubrir, sin ningún conjunto por defecto.
    Con tema: los de ese tema, por el nombre y la categoría (pesan el doble), el publicador y las columnas.
    Sin tema: los que dicen al menos dos de estado, lugar e impacto (exigir los tres dejaba solo conjuntos de contratos).
    En los dos casos, a lo más por_publicador por publicador (0 = sin tope), para que una sola fuente no llene la lista.
    Devuelve (candidatos, palabras, grandes); grandes es False si ninguno del tema llega a min_filas: entonces la lista trae
    los más grandes del tema, y la persona decide."""
    from relevancia_catalogo import normal
    cols = {x["id"]: " ".join([str(v) for v in (x.get("campos") or [])] + [str(v) for v in (x.get("visibles") or [])])
            for x in inventario}
    palabras = palabras_tema(tema) if tema else []
    if tema and not palabras:
        raise SystemExit(f"El tema «{tema}» no trae palabras para buscar: usa palabras como «salud», «movilidad» o «clima».")

    def n3(r):
        return sum(bool(r.get(k)) for k in ("dice_estado", "dice_lugar", "dice_impacto"))

    elegibles = []
    for r in rel:
        if palabras:
            fuerte = normal(f"{r.get('nombre') or ''} {r.get('categoria') or ''}").split()
            debil = normal(f"{r.get('publicador') or ''} {cols.get(r.get('id'), '')}").split()
            pesos = [2 if _toca(w, fuerte) else 1 if _toca(w, debil) else 0 for w in palabras]
            if any(pesos):
                elegibles.append((sum(1 for x in pesos if x), sum(pesos), r))   # primero, cuántas palabras del tema toca
        elif n3(r) >= 2:
            elegibles.append((0, 0, r))
    grandes = [x for x in elegibles if (x[2].get("filas") or 0) >= min_filas]
    hay_grandes = bool(grandes) or not palabras
    if hay_grandes:
        lista = sorted(grandes, key=lambda x: (-x[0], -x[1], -n3(x[2]), -(x[2].get("puntaje") or 0), -(x[2].get("filas") or 0)))
    else:
        lista = sorted(elegibles, key=lambda x: (-x[0], -(x[2].get("filas") or 0)))
    out, cuenta = [], {}
    for _, puntos, r in lista:
        # el mismo publicador se escribe de varias formas («…Pública - Colombia Compra Eficiente, Bogotá D.C.» y «…Pública
        # Colombia Compra Eficiente CCE, Bogotá, D.C»): se compara sin la ciudad y por sus cuatro primeras palabras
        pub = " ".join([w for w in normal((r.get("publicador") or "").split(",")[0]).split() if len(w) >= 3][:4]) or "—"
        if por_publicador and cuenta.get(pub, 0) >= por_publicador:
            continue
        cuenta[pub] = cuenta.get(pub, 0) + 1
        out.append(dict(r, coincide_tema=puntos))
        if len(out) >= top:
            break
    return out, palabras, hay_grandes


def correr(*args, salida=None):
    p = subprocess.run([PY, *map(str, args)], capture_output=True, text=True, cwd=RAIZ)  # nosec B603
    if salida:
        Path(salida).write_text(p.stdout + p.stderr, encoding="utf-8")
    return p.returncode, p.stdout + p.stderr


PROTEGIDO = ("herramientas", "plantillas", "baterias", "flujo.js", "orquestar.mjs", "AGENTE-MASIVO.md", "README.md",
             "requirements.txt")


def sellar(raiz=RAIZ, protegido=PROTEGIDO):
    """Huella SHA-256 de cada archivo que forma el agente (sin cachés de Python)."""
    huellas = {}
    for nombre in protegido:
        p = Path(raiz) / nombre
        archivos = [p] if p.is_file() else sorted(x for x in p.rglob("*") if x.is_file()) if p.is_dir() else []
        for f in archivos:
            if "__pycache__" in f.parts or f.suffix == ".pyc":
                continue
            huellas[str(f.relative_to(raiz))] = hashlib.sha256(f.read_bytes()).hexdigest()
    return huellas


def comparar(antes, despues):
    """Archivos del agente que cambiaron, aparecieron o desaparecieron mientras trabajaba la IA."""
    return sorted(k for k in set(antes) | set(despues) if antes.get(k) != despues.get(k))


def fuera_de_git(carpeta, raiz=RAIZ):
    """Nada de una corrida se publica: la carpeta de trabajo queda fuera del repositorio o en una ruta que Git ignora
    (fuentes/). Sin Git (una copia descargada como .zip) no hay nada que se pueda versionar."""
    try:
        Path(carpeta).resolve().relative_to(Path(raiz).resolve())
    except ValueError:
        return True
    p = subprocess.run(["git", "-C", str(raiz), "check-ignore", "-q", str(Path(carpeta).resolve() / "RESULTADO.md")],  # nosec B603 B607
                       capture_output=True)
    return p.returncode != 1   # 0: Git la ignora; 1: la versionaría; 128: sin Git


def herramientas_de_git():
    """Copia de herramientas/ y baterias/ tal como están en HEAD: la validación no usa lo que la IA pudo tocar."""
    destino = Path(tempfile.mkdtemp(prefix="agente-masivo-git-"))
    paq = subprocess.run(["git", "-C", str(RAIZ), "archive", "HEAD", "herramientas", "baterias"],  # nosec B603 B607
                         capture_output=True, check=True).stdout
    subprocess.run(["tar", "-x", "-C", str(destino)], input=paq, check=True)  # nosec B603 B607
    return destino / "herramientas"


def autoprueba():
    """Sin red: el sello detecta un cambio, un archivo nuevo y uno borrado, y no da falsas alarmas; la carpeta de trabajo
    que Git versionaría se rechaza, y la de fuentes/ o la de fuera del repositorio se acepta."""
    d = Path(tempfile.mkdtemp(prefix="agente-masivo-prueba-"))
    (d / "herramientas").mkdir()
    (d / "herramientas" / "validar_ficha.py").write_text("x = 1\n")
    (d / "herramientas" / "otra.py").write_text("y = 2\n")
    casos = []
    antes = sellar(d, ("herramientas",))
    casos.append(("sin cambios no hay alarma", comparar(antes, sellar(d, ("herramientas",))) == []))
    (d / "herramientas" / "validar_ficha.py").write_text("x = 1  # la IA aflojó el validador\n")
    casos.append(("un cambio se detecta", comparar(antes, sellar(d, ("herramientas",))) == ["herramientas/validar_ficha.py"]))
    (d / "herramientas" / "nuevo.py").write_text("z = 3\n")
    (d / "herramientas" / "otra.py").unlink()
    cambiados = comparar(antes, sellar(d, ("herramientas",)))
    casos.append(("lo nuevo y lo borrado se detectan", "herramientas/nuevo.py" in cambiados and "herramientas/otra.py" in cambiados))
    # la carpeta de trabajo: en un repositorio de prueba que ignora fuentes/, como este
    repo = d / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], capture_output=True, check=True)  # nosec B603 B607
    (repo / ".gitignore").write_text("fuentes/\n", encoding="utf-8")
    casos.append(("una carpeta de trabajo que Git versionaría se rechaza", not fuera_de_git(repo / "fichas-hoy", repo)))
    casos.append(("dentro de fuentes/ (ignorada) o fuera del repositorio se acepta",
                  fuera_de_git(repo / "fuentes" / "fichas" / "mi-corrida", repo) and fuera_de_git(d / "afuera", repo)))
    # ningún conjunto por defecto: sin fuentes declaradas no hay ninguna, y descubrir no deja que una sola fuente llene la lista
    casos.append(("sin fuentes declaradas no hay ningún conjunto por defecto", fuentes_autorizadas([], "x.invalid", d) is None))
    def c(i, nombre, cat, pub, filas, pts, e, l, im):
        return {"id": i, "nombre": nombre, "categoria": cat, "publicador": pub, "filas": filas, "puntaje": pts,
                "dice_estado": e, "dice_lugar": l, "dice_impacto": im}
    rel = [c(f"aaaa-000{k}", f"Contratos {k}", "Compras", "Agencia Alfa", 5_000_000, 15, True, True, True) for k in range(1, 6)]
    rel += [c("aaaa-0009", "Contratos históricos", "Compras", "Agencia Alfa, Bogotá D.C.", 6_000_000, 15, True, True, True)]
    rel += [c("bbbb-0001", "Casos de dengue por municipio", "Salud y Protección Social", "Instituto Beta", 2_000_000, 11, True, True, False),
            c("cccc-0001", "Estaciones de calidad del aire", "Ambiente", "Ministerio Gama", 3_000_000, 10, False, True, True),
            c("dddd-0001", "Cobertura de vacunación", "Salud y Protección Social", "Unidad Delta", 40_000, 9, False, True, True),
            c("eeee-0001", "Tasas de interés", "Economía", "Banco Épsilon", 9_000_000, 12, False, False, False)]
    inv = [{"id": "cccc-0001", "campos": ["municipio", "pm10", "ozono"], "visibles": ["Municipio", "PM10", "Ozono"]}]
    sug, _, _ = sugerir(rel, inv)
    pubs = [x["publicador"] for x in sug]
    casos.append(("sin tema: un publicador no pasa del tope y entran los de otros",
                  sum(x.startswith("Agencia Alfa") for x in pubs) == 2 and {"Instituto Beta", "Ministerio Gama"} <= set(pubs) and "eeee-0001" not in
                  [x["id"] for x in sug]))
    sug, pal, gr = sugerir(rel, inv, tema="la salud en Colombia")
    casos.append(("con tema: solo los de ese tema, y los grandes primero", pal == ["salud"] and gr and [x["id"] for x in sug] == ["bbbb-0001"]))
    sug, _, gr = sugerir(rel, inv, tema="vacunas")
    casos.append(("la raíz encuentra la palabra y, si ninguno es grande, lo dice", not gr and [x["id"] for x in sug] == ["dddd-0001"]))
    sug, _, _ = sugerir(rel, inv, tema="ozono")
    casos.append(("las columnas también cuentan para el tema", [x["id"] for x in sug] == ["cccc-0001"]))
    try:
        sugerir(rel, inv, tema="de la")
        casos.append(("un tema sin palabras se rechaza", False))
    except SystemExit:
        casos.append(("un tema sin palabras se rechaza", True))
    shutil.rmtree(d, ignore_errors=True)
    for nombre, ok in casos:
        print(f"  {'✓' if ok else '✗'} {nombre}")
    errores = sum(not ok for _, ok in casos)
    print("RESUMEN " + json.dumps({"autoprueba": len(casos), "errores": errores}))
    return 1 if errores else 0


def num_txt(x):
    return f"{x:,}".replace(",", ".") if isinstance(x, int) else (str(x) if x is not None else "—")


def resumen(texto):
    for linea in reversed(texto.splitlines()):
        if linea.startswith("RESUMEN "):
            try:
                return json.loads(linea[8:])
            except ValueError:
                return None
    return None


def main(argv):
    if argv[:1] == ["--autoprueba"]:
        return autoprueba()
    if len(argv) < 3 or "--trabajo" not in argv:
        raise SystemExit(__doc__)
    g = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d
    dominio, trabajo = argv[0], Path(g("--trabajo")).resolve()
    if not fuera_de_git(trabajo):
        raise SystemExit(f"La carpeta de trabajo {trabajo} quedaría en Git (no está ignorada), y nada de una corrida se publica. "
                         "Usa una carpeta dentro de fuentes/, por ejemplo --trabajo fuentes/fichas/mi-corrida, o una fuera del repositorio.")
    top, min_filas = int(g("--top", 8)), int(g("--min-filas", 1_000_000))
    catalogo = (RAIZ / g("--catalogo", "fuentes/catalogo")).resolve()
    motor = g("--motor", "ninguno")
    fichas = trabajo / "fichas"
    fichas.mkdir(parents=True, exist_ok=True)
    nombre = dominio.replace("www.", "").replace(".", "_")
    autorizados = fuentes_autorizadas(argv, dominio, trabajo)
    inventario = trabajo / "inventario_autorizado.json"

    if "--solo-validar" not in argv:
        if not autorizados:
            if "--descubrir" not in argv:
                print(SIN_FUENTES)
                return 2
            print("Descubrir (con tu permiso): recorre el catálogo para SUGERIR; no trabaja con ningún conjunto…", flush=True)
            if "--actualizar" in argv or not (catalogo / ".cache.json").exists():
                correr(AQUI / "explorador_catalogo.py", dominio, "--salida", catalogo, "--hilos", 4, "--min-filas", min_filas)
            correr(AQUI / "relevancia_catalogo.py", dominio, "--catalogo", catalogo, "--top", 0)
            rel = json.loads((catalogo / f"relevancia_{nombre}.json").read_text(encoding="utf-8"))
            inv_cat = catalogo / f"inventario_{nombre}.json"
            inv = json.loads(inv_cat.read_text(encoding="utf-8")) if inv_cat.exists() else []
            tema, por_pub = g("--tema"), int(g("--por-publicador", 2))
            sug, palabras, grandes = sugerir(rel, inv, tema, top, min_filas, por_pub)
            if tema:
                print(f"Tema que sugeriste: «{tema}» (se busca: {', '.join(palabras)}).")
                if not grandes:
                    print(f"   Ninguno de ese tema llega a {num_txt(min_filas)} filas; estos son los más grandes, y decides tú:")
            else:
                temas = {}
                for r in rel:
                    if (r.get("filas") or 0) >= min_filas and r.get("categoria"):
                        temas[r["categoria"]] = temas.get(r["categoria"], 0) + 1
                print("Sin tema: candidatos de varios publicadores (ninguno viene por defecto). Para sugerirle de qué se va a tratar, "
                      "agrega --tema. Temas con conjuntos de " + num_txt(min_filas) + " filas o más en este portal: " +
                      ", ".join(f"{k} ({n})" for k, n in sorted(temas.items(), key=lambda x: -x[1])[:8]) + ".")
            for r in sug:
                print(f"   {r['id']}  {num_txt(r.get('filas'))} filas  {(r.get('nombre') or '')[:64]}  · {(r.get('publicador') or '—')[:36]}")
            (trabajo / "sugerencias.json").write_text(json.dumps(
                {"tema": tema, "palabras": palabras, "min_filas": min_filas, "llegan_al_tamano": grandes, "por_publicador": por_pub,
                 "candidatos": [{k: r.get(k) for k in ("id", "nombre", "filas", "categoria", "publicador", "coincide_tema", "url")}
                                for r in sug]}, ensure_ascii=False, indent=1), encoding="utf-8")
            if not sug:
                print("   (ninguno: prueba con otras palabras o con --min-filas más bajo)")
                return 0
            print("Para trabajar con los que elijas, autorízalos:  --conjuntos " + ",".join(r["id"] for r in sug))
            return 0
        if g("--tema"):
            print("   (--tema solo sirve con --descubrir: el agente trabaja con las fuentes autorizadas)", flush=True)
        print(f"1. fuentes autorizadas: {', '.join(autorizados)} (solo con estas se conecta el agente)", flush=True)
        inv = inventario_autorizado(dominio, autorizados, inventario)
        cand = [{"id": x["id"], "nombre": x["nombre"]} for x in inv]
        for c in cand:
            d = fichas / f"{c['id']}.dictamen.json"
            previos = [RAIZ / "fuentes" / "fichas" / d.name] + sorted((RAIZ / "fuentes" / "fichas").glob(f"*/fichas/{d.name}"))
            previo = next((x for x in previos if x.exists() and x.resolve() != d.resolve()), None)
            if not d.exists() and previo:
                shutil.copy(previo, d)
            if not d.exists():
                print(f"2. dictamen medido de {c['id']}…", flush=True)
                rc, out = correr(AQUI / "dictamen_bigdata.py", "socrata", dominio, c["id"], "--salida", d)
                if not d.exists():
                    print(f"   ✗ no se pudo medir {c['id']} ({out.strip().splitlines()[-1][:120] if out.strip() else 'sin salida'}): "
                          "queda fuera del encargo, sin nivel medido no hay ficha", flush=True)
        cand = [c for c in cand if (fichas / f"{c['id']}.dictamen.json").exists()]
        if not cand:
            raise SystemExit("Ninguna fuente autorizada tiene dictamen medido: revise la conexión con el portal y repita.")
        filas_de = {c["id"]: json.loads((fichas / f"{c['id']}.dictamen.json").read_text(encoding="utf-8")).get("medidas", {}).get("filas")
                    for c in cand}
        lista = "\n".join(f"| {c['id']} | {c['nombre']} | {num_txt(filas_de.get(c['id']))} |" for c in cand)
        plantilla = (RAIZ / "plantillas" / "encargo_fichas.md").read_text(encoding="utf-8")
        (trabajo / "ENCARGO.md").write_text(
            plantilla.replace("{{DOMINIO}}", dominio).replace("{{CANDIDATOS}}", lista)
            .replace("{{AUTORIZADOS}}", ", ".join(autorizados)).replace("{{AUTORIZADOS_CSV}}", ",".join(autorizados))
            .replace("{{INVENTARIO}}", str(inventario)).replace("{{VALIDADOR}}", str(AQUI / "validar_ficha.py"))
            .replace("{{PYTHON}}", PY), encoding="utf-8")
        print(f"5. encargo: {trabajo / 'ENCARGO.md'}", flush=True)
        pedido = (f"Lee {trabajo / 'ENCARGO.md'} y hazlo completo: una ficha por candidato en {fichas}, cada una validada. "
                  f"Solo puedes conectarte a los conjuntos autorizados ({', '.join(autorizados)}); a ningún otro. "
                  "No modifiques nada fuera de esa carpeta ni los *.dictamen.json. Responde en español con cifras.")
        motores = {   # invocaciones no interactivas, como en orquestar.mjs; solo Claude va sin servidores MCP: agy y Codex
                      # cargan los del usuario (orquestar.mjs los apaga con un HOME temporal y -c mcp_servers.*.enabled=false)
            "claude": [os.environ.get("CLAUDE_BIN", "claude"), "-p", pedido, "--dangerously-skip-permissions",
                       "--strict-mcp-config", "--add-dir", str(RAIZ)],
            "agy": [os.environ.get("AGY_BIN", "agy"), "--dangerously-skip-permissions", "-p", pedido],
            "codex": [os.environ.get("CODEX_BIN", "codex"), "exec", "--skip-git-repo-check", "--color", "never", "-C", str(trabajo),
                      "--dangerously-bypass-approvals-and-sandbox", pedido],
        }
        if motor in motores and shutil.which(motores[motor][0]):
            sello = sellar()
            (trabajo / "sello_agente.json").write_text(json.dumps(sello, indent=1), encoding="utf-8")
            print(f"6. IA: {motor} escribe las fichas (puede tardar); el agente quedó sellado ({len(sello)} archivos)…", flush=True)
            subprocess.run(motores[motor], cwd=trabajo)  # nosec B603
            tocados = comparar(sello, sellar())
            if tocados:
                aviso = ("✗ LA CORRIDA NO VALE: mientras trabajaba la IA cambiaron archivos del agente (uso local: el agente se usa, "
                         "no se modifica): " + ", ".join(tocados[:20]))
                print(aviso, flush=True)
                (trabajo / "RESULTADO.md").write_text(f"# Corrida inválida\n\n{aviso}\n", encoding="utf-8")
                return 1
            print("   ✓ el agente quedó igual: la IA solo escribió en su carpeta", flush=True)
        else:
            if motor != "ninguno":
                print(f"   (no se encontró la CLI de {motor}: se imprime el texto)", flush=True)
            print("6. IA: pega esto en la IA que uses, con acceso a la carpeta de trabajo:\n\n" + pedido + "\n")
            if "--validar" not in argv:
                return 0

    print("7. validación sin IA, contra la fuente real y sin caché, con las herramientas de la versión de Git…", flush=True)
    try:
        h_git = herramientas_de_git()
    except Exception as e:  # sin Git (por ejemplo, una copia descargada como .zip): se valida con la carpeta y se dice
        print(f"   (sin Git: se valida con las herramientas de la carpeta; {type(e).__name__})", flush=True)
        h_git = AQUI
    filas = []
    for f in sorted(fichas.glob("*.json")):
        if f.name.endswith((".dictamen.json", ".verificacion.json")):
            continue
        if not autorizados:
            raise SystemExit(SIN_FUENTES)
        rc, out = correr(h_git / "validar_ficha.py", f, "--inventario", inventario, "--autorizados", ",".join(autorizados),
                         salida=f.with_suffix(".log"))
        r = resumen(out) or {}
        fallas = [l.strip()[2:] for l in out.splitlines() if l.strip().startswith("✗")]
        filas.append((f.stem, r.get("chequeos", "?"), r.get("fallas", "?"), "; ".join(fallas)[:300]))
        print(f"   {f.stem}: {r.get('fallas', '?')} fallas de {r.get('chequeos', '?')}", flush=True)
    md = [f"# Resultado del agente masivo · {dominio} · {datetime.now():%Y-%m-%d %H:%M}", "",
          "La validación sin IA mide la forma (columnas, consultas reales, cruces medidos, gobernanza, sin conclusiones).",
          "Que una ficha pase no la hace publicable: el juicio de valor lo hacen un juez ciego y las personas.", "",
          "| Ficha | Chequeos | Fallas | Qué falló |", "|---|---|---|---|"]
    md += [f"| {a} | {b} | {c} | {d or '—'} |" for a, b, c, d in filas]
    (trabajo / "RESULTADO.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    ok = sum(1 for x in filas if x[2] == 0)
    if filas and motor in ("claude", "agy", "codex") and "--solo-validar" not in argv and not (trabajo / "RESUMEN_IA.md").exists():
        ped = (f"Lee las fichas validadas de {fichas} y su RESULTADO.md, y escribe en {trabajo / 'RESUMEN_IA.md'} un resumen de lo que "
               "se desarrolló para que el estudiante haga el análisis: qué conjuntos se encontraron, por qué son relevantes y qué "
               "preguntas quedan abiertas. Máximo 220 palabras, en español. Sin conclusiones, recomendaciones, causas ni juicios "
               "(«se concluye», «muestra que», «se recomienda», «hay que», «conviene», «por eso», «se debe a», «sobrecosto»): el "
               "análisis lo hace el estudiante. Sin cifras salvo años y normas, sin datos personales. No modifiques nada más.")
        cmd = {"claude": [os.environ.get("CLAUDE_BIN", "claude"), "-p", ped, "--dangerously-skip-permissions", "--strict-mcp-config"],
               "agy": [os.environ.get("AGY_BIN", "agy"), "--dangerously-skip-permissions", "-p", ped],
               "codex": [os.environ.get("CODEX_BIN", "codex"), "exec", "--skip-git-repo-check", "--color", "never", "-C", str(trabajo),
                         "--dangerously-bypass-approvals-and-sandbox", ped]}[motor]
        if shutil.which(cmd[0]):
            sello = sellar()
            print(f"8. resumen: {motor} lo escribe (el análisis queda para el estudiante)…", flush=True)
            subprocess.run(cmd, cwd=trabajo)  # nosec B603
            tocados = comparar(sello, sellar())
            if tocados:
                print("✗ LA CORRIDA NO VALE: la IA cambió archivos del agente al escribir el resumen: " + ", ".join(tocados[:20]), flush=True)
                return 1
    if filas:
        print("8. whitepaper de tres hojas carta para el estudiante (resumen de la IA comprobado sin IA)…", flush=True)
        rc_w, out_w = correr(AQUI / "whitepaper_fichas.py", trabajo)
        print("   " + (out_w.strip().splitlines() or ["(sin salida)"])[0], flush=True)
    print(f"RESUMEN {json.dumps({'fichas': len(filas), 'pasan': ok})}")
    return 0 if filas and ok == len(filas) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
