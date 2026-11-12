#!/usr/bin/env python3
"""Baterías: lo que falló una vez se vuelve prueba para siempre (sin IA).

Uso:
  python baterias.py                         corre todas las baterías
  python baterias.py --agregar-malo nombre archivo.py   guarda un hallazgo confirmado como código que debe bloquearse
  python baterias.py --leccion "texto" --origen "..." --prueba "..."   agrega una lección (si su prueba existe)

1. Seguridad: todo lo de baterias/seguridad/malos debe quedar bloqueado y todo lo de buenos debe pasar
   (así también se prueba al probador: un falso positivo es una falla de la compuerta). Lo mismo con el perfil de
   usuario: malos_usuario se bloquea; buenos_usuario y buenos pasan.
2. Privacidad: el perfil de dos CSV, uno con datos personales y otro con datos sensibles que comparte columnas con
   el primero (hay cruces), no puede mostrar ninguno de los valores de no_deben_salir.txt, ni en su resumen ni en su
   perfil.json, y el barrido de gobernanza tiene que encontrarlos.
2b. FAILFAST: cada CSV de baterias/failfast detiene, con su línea, a los lectores de las reglas, al del perfil y a la
   ingesta local, y corren las autopruebas de la ingesta y de la limpieza (B33).
3. Lecciones: la prueba que cita cada lección existe de verdad: un id del blindaje (B05), un mutante de los controles
   (M12), un caso de una batería (bateria:failfast/campo_de_mas.csv), una herramienta con --autoprueba o un archivo o
   una carpeta versionados; una cita textual («…») está en el archivo que la precede, y el texto libre solo no cuenta.
   Las citas buenas y malas de baterias/citas/casos.json prueban al probador (L96). Y las lecciones llegan a todos los
   subagentes (regla común 9): cada instrucción de flujo.js que empieza con «Eres el» las trae, con ${LECCIONES} o con
   ${reglasComunes}, que las trae; con una instrucción que las pierde, la comprobación tiene que echarla de menos (L122).
4. Cruces: el perfil explica por qué no cruza cada valor (baterias/cruces/esperado.json) y no explica un ausente.
5. Fechas: el perfil cuenta aparte las fechas que no existen en el calendario (baterias/fechas/casos.json).
6. Repetidos: una llave repetida nunca se resuelve por el orden del archivo sin aviso (baterias/limpieza/).
7. Factor: el perfil reconoce el factor de expansión de una encuesta (baterias/perfil/).
8. Gráfico: las figuras de baterias/grafico/buenos pasan las comprobaciones de forma y color y la de D15 (sin
   lenguaje de análisis), y cada figura de malos falla justo la comprobación que ataca (ni otra, ni ninguna).
"""
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
BAT = RAIZ / "baterias"
sys.path.insert(0, str(AQUI))
import dependencias  # noqa: E402
import seguridad  # noqa: E402
from gobernanza import barrer_tabla  # noqa: E402


def falla(caso, texto):
    """Una falla con el caso que la produce: así el filtro de aportes distingue el hueco que encontró un caso nuevo."""
    return {"caso": str(caso), "falla": texto}


def bloquea(ruta):
    d = dependencias.revisar(ruta)
    s, _ = seguridad.revisar([ruta])
    return bool(d.get("no_permitidas") or d.get("intenta_instalar") or s[0]["bloquean"])


def bateria_seguridad():
    fallas = []
    malos = sorted((BAT / "seguridad" / "malos").glob("*.py"))
    buenos = sorted((BAT / "seguridad" / "buenos").glob("*.py"))
    for p in malos:
        if not bloquea(p):
            fallas.append(falla(p.name, f"no se bloqueó {p.name}"))
    for p in buenos:
        if bloquea(p):
            fallas.append(falla(p.name, f"falso positivo: se bloqueó {p.name}"))
    # Perfil de usuario: el código que sí usa red y archivos. Lo bueno del pipeline también tiene que pasar aquí.
    malos_u = sorted((BAT / "seguridad" / "malos_usuario").glob("*.py"))
    buenos_u = sorted((BAT / "seguridad" / "buenos_usuario").glob("*.py"))
    if malos_u or buenos_u:
        res, _ = seguridad.revisar(malos_u + buenos_u + buenos, "usuario")
        for r in res:
            nombre, bloqueado = Path(r["archivo"]), bool(r["bloquean"])
            if nombre.parent.name == "malos_usuario" and not bloqueado:
                fallas.append(falla(nombre.name, f"perfil usuario: no se bloqueó {nombre.name}"))
            elif nombre.parent.name != "malos_usuario" and bloqueado:
                fallas.append(falla(nombre.name, f"perfil usuario: falso positivo en {nombre.name}: {r['bloquean'][0]['regla']}"))
    return {"bateria": "seguridad", "casos": len(malos) + len(buenos) + len(malos_u) + len(buenos_u), "fallas": fallas}


def bateria_privacidad():
    fallas = []
    csv_ = BAT / "privacidad" / "con_datos_personales.csv"
    sensibles = BAT / "privacidad" / "con_datos_sensibles.csv"   # Ley 1581, art. 5; comparte columnas con la otra: hay cruces
    secretos = [s for s in (BAT / "privacidad" / "no_deben_salir.txt").read_text(encoding="utf-8").splitlines() if s]
    tmp = Path(tempfile.mkdtemp(prefix="bateria-privacidad-"))
    try:
        p = subprocess.run([sys.executable, str(AQUI / "perfilar.py"), f"t={csv_}", f"s={sensibles}",  # nosec B603
                            "--json", str(tmp / "perfil.json")], capture_output=True, text=True)
        perfil = (tmp / "perfil.json").read_text(encoding="utf-8") if (tmp / "perfil.json").exists() else ""
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    # control positivo (L27): el perfil corrió y muestra lo que sí puede mostrar; un perfil que se cae no filtra nada
    if p.returncode != 0 or not perfil or "('S1', 1)" not in p.stdout or '"P1"' not in perfil:
        fallas.append(falla(sensibles.name, f"control positivo: el perfil de las dos tablas no corrió o no muestra los valores de "
                                            f"id_contrato (código {p.returncode}): {' '.join((p.stderr or p.stdout).split())[-160:]}"))
    for s in secretos:
        if s in p.stdout or s in perfil:
            fallas.append(falla(s, f"el perfil muestra un dato personal o sensible: {s[:3]}…"))
    from gobernanza import escanear_texto, texto_publicado
    for t in (BAT / "privacidad" / "no_son_personales.txt").read_text(encoding="utf-8").splitlines():
        if t and escanear_texto(t):
            fallas.append(falla(t, f"falso positivo: «{t}» se marcó como dato personal {escanear_texto(t)}"))
    # formas de esconder un dato a las expresiones (L116): ancho completo, invisibles y, en una página, etiquetas en medio
    evasiones = json.loads((BAT / "privacidad" / "evasiones.json").read_text(encoding="utf-8"))["casos"]
    tmp = Path(tempfile.mkdtemp(prefix="bateria-evasiones-"))
    try:
        for c in evasiones:
            if "html" in c:
                (tmp / "pagina.html").write_text(c["html"], encoding="utf-8")
                hall = escanear_texto(texto_publicado(tmp / "pagina.html"))
            else:
                hall = escanear_texto(c.get("texto"))
            if c.get("patron") not in hall:
                fallas.append(falla(c.get("nombre"), f"el barrido no encuentra «{c.get('nombre')}» ({c.get('patron')}): {hall}"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    barrido = barrer_tabla(csv_)
    detectadas = {c for c, i in barrido["columnas"].items() if i.get("hallazgos") or i.get("clase_por_nombre") == "personal"}
    for c in ("proveedor_adjudicado", "documento_proveedor", "objeto_del_contrato"):
        if c not in detectadas:
            fallas.append(falla(c, f"el barrido no detectó {c}"))
    from gobernanza import clasificar_columna, es_sensible
    cols = json.loads((BAT / "privacidad" / "columnas_secop.json").read_text(encoding="utf-8"))
    n_cols = 0
    for grupo, aceptadas in (("personal", {"personal"}), ("cuasi_o_personal", {"personal", "cuasi"}),
                             ("texto_libre", {"texto_libre"}), ("sin_marca", {None}), ("sensible", {"personal", "cuasi"})):
        for c in cols.get(grupo, []):
            n_cols += 1
            if clasificar_columna(c) not in aceptadas:
                fallas.append(falla(c, f"columna de SECOP mal clasificada: {c} → {clasificar_columna(c)} (se esperaba {grupo})"))
            if (grupo == "sensible") != es_sensible(c):
                fallas.append(falla(c, f"dato sensible mal marcado: {c} → es_sensible {es_sensible(c)} (grupo {grupo})"))
    # por la descripción de los metadatos: el nombre no dice nada y la descripción sí (o no, y no se marca)
    for x in cols.get("por_descripcion", []):
        n_cols += 1
        clase = clasificar_columna(x["columna"], x["descripcion"])
        if clase != x["clase"] or es_sensible(x["columna"], x["descripcion"]) != bool(x.get("sensible")):
            fallas.append(falla(x["columna"], f"columna mal clasificada por su descripción: {x['columna']} «{x['descripcion'][:50]}» → "
                                              f"{clase}{' (sensible)' if es_sensible(x['columna'], x['descripcion']) else ''} (se esperaba {x['clase']})"))
    return {"bateria": "privacidad", "casos": len(secretos) + 1 + 3 + 6 + n_cols + len(evasiones), "fallas": fallas}


def ingerir_local(p, carpeta):
    """La ingesta local de un CSV con un contrato mínimo (todas las columnas como texto y justificadas: son casos
    ficticios). Devuelve su RESUMEN."""
    with open(p, newline="", encoding="utf-8-sig") as fh:
        cab = next(csv.reader(fh), None) or ["vacio"]
    contrato = {"fuente": {"tipo": "local", "ruta": str(p), "titulo": "caso de la batería", "licencia": "—",
                           "atribucion": "—", "unidad": "filas"},
                "tabla": "caso", "llave": cab[0], "columnas": {c: "texto" for c in cab},
                "personales_justificadas": {c: "caso de prueba con valores ficticios" for c in cab}}
    (carpeta / "contrato.json").write_text(json.dumps(contrato, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([sys.executable, str(AQUI / "ingesta.py"), str(carpeta / "contrato.json"), "--salida",  # nosec B603
                        str(carpeta / "salida")], capture_output=True, text=True)
    linea = next((l for l in reversed(r.stdout.splitlines()) if l.startswith("RESUMEN ")), None)
    return json.loads(linea[len("RESUMEN "):]) if linea else {"estado": "sin RESUMEN", "salida": r.stderr[-160:]}


# Las autopruebas de los lectores que escriben o describen los datos del pipeline: sus casos FAILFAST (UTF-8, carácter
# nulo, solo el encabezado, la línea donde se abre una comilla, la fórmula que la limpieza neutraliza…) no viven en
# baterias/failfast. Cada una con su piso de casos: una autoprueba que pierde casos también es una regresión (DB3).
AUTOPRUEBAS = {"ingesta.py": 102, "limpieza.py": 58}


def autoprueba(herramienta, minimo):
    """Corre `herramienta --autoprueba` y devuelve (casos, fallas): cada «✗» es una falla con su caso (el nombre del CSV
    si es uno de baterias/failfast, para que el filtro reconozca el hueco que encontró un caso nuevo); una autoprueba que
    no termina, sale con error sin decir qué falló o corre menos casos que su piso también es falla (L67)."""
    try:
        r = subprocess.run([sys.executable, str(AQUI / herramienta), "--autoprueba"], capture_output=True,  # nosec B603
                           text=True, timeout=900, cwd=RAIZ)
    except subprocess.TimeoutExpired:
        return 0, [falla(herramienta, f"{herramienta} --autoprueba no terminó en 15 minutos")]
    linea = next((l for l in reversed(r.stdout.splitlines()) if l.startswith("RESUMEN ")), None)
    try:
        res = json.loads(linea[len("RESUMEN "):]) if linea else None
    except ValueError:
        res = None
    fallas = []
    for l in r.stdout.splitlines():
        if l.startswith("✗ "):
            nombre = l[2:].split(" · ")[0]
            m = re.fullmatch(r"failfast (\S+\.csv)", nombre)
            fallas.append(falla(m.group(1) if m else f"{herramienta}: {nombre}", f"{herramienta} --autoprueba: {l[2:][:240]}"))
    casos = res.get("casos") if isinstance(res, dict) and isinstance(res.get("casos"), int) else 0
    if not isinstance(res, dict) or ((r.returncode != 0 or res.get("fallas")) and not fallas):
        fallas.append(falla(herramienta, f"{herramienta} --autoprueba no dejó su RESUMEN o salió con {r.returncode} sin decir "
                                         f"qué falló: {' '.join((r.stderr or r.stdout).split())[-160:]}"))
    elif casos < minimo:
        fallas.append(falla(herramienta, f"{herramienta} --autoprueba corrió {casos} casos y su piso es {minimo}: las baterías solo crecen"))
    return casos, fallas


def bateria_failfast():
    """Un CSV mal formado detiene la lectura: nunca se lee a medias ni se rellena en silencio (FAILFAST). Se prueba con
    los dos lectores de las reglas (leer_csv y recorrer_csv, que recorre fila por fila con las mismas detenciones), con
    el del perfil (perfilar.leer, y perfilar.py debe salir con 1 diciendo la línea, sin traceback) y con la ingesta
    local, que es la que escribe los datos del pipeline: la ingesta debe rechazarlo y decir en qué línea. Además corren
    las autopruebas de la ingesta y de la limpieza (AUTOPRUEBAS), que pasan estos mismos CSV y sus propios casos: una
    regresión en cualquiera de los lectores hace caer esta batería y con ella el filtro de aportes (B33). Control
    positivo: los CSV bien formados de ejemplo/datos se leen completos, con los tres lectores y con la ingesta."""
    import perfilar
    from reglas_base import contar_registros, leer_csv, recorrer_csv
    fallas, casos = [], sorted((BAT / "failfast").glob("*.csv"))
    lectores = (("leer_csv", lambda p: len(leer_csv(p))), ("recorrer_csv", lambda p: sum(1 for _ in recorrer_csv(p))),
                ("perfilar", lambda p: len(perfilar.leer(p)[1])))   # los tres, igual
    buenos = sorted((BAT / "failfast" / "se_leen").glob("*.csv"))   # y lo legítimo de cualquier fuente se lee (sin falsas alarmas)
    controles = sorted((RAIZ / "ejemplo" / "datos").glob("*.csv"))
    tmp = Path(tempfile.mkdtemp(prefix="bateria-failfast-"))
    try:
        for p in casos:
            for nombre, leer in lectores:
                try:
                    leer(p)
                    fallas.append(falla(p.name, f"{p.name} se leyó sin error con {nombre}"))
                except Exception:
                    pass
            r = ingerir_local(p, tmp)
            if r.get("estado") != "rechazada" or not re.search(r"l[ií]nea \d+", str(r.get("motivo") or "")):
                fallas.append(falla(p.name, f"la ingesta local no rechazó {p.name} diciendo la línea: {str(r)[:160]}"))
            (tmp / "perfil.json").write_text('{"tablas": {}}', encoding="utf-8")   # el de una corrida anterior tampoco puede quedar
            r = subprocess.run([sys.executable, str(AQUI / "perfilar.py"), f"t={p}", "--json", str(tmp / "perfil.json")],  # nosec B603
                               capture_output=True, text=True)
            quedo = (tmp / "perfil.json").read_text(encoding="utf-8") if (tmp / "perfil.json").exists() else ""
            if r.returncode == 0 or "Traceback" in r.stderr or not re.search(r"l[ií]nea \d+", r.stderr) or '"tablas"' in quedo:
                fallas.append(falla(p.name, f"perfilar.py no se detuvo en {p.name} con la línea y sin perfil (código {r.returncode}): "
                                            f"{' '.join((r.stderr or r.stdout).split())[-160:]}"))
        for p in buenos:
            for nombre, leer in lectores:
                try:
                    leer(p)
                except Exception as e:
                    fallas.append(falla(p.name, f"falsa alarma con {nombre}: {p.name} se detuvo ({str(e)[:80]})"))
        for p in controles:
            esperado = contar_registros(p.read_text(encoding="utf-8-sig"))
            for nombre, contar in lectores:
                try:
                    n = contar(p)
                except Exception as e:
                    n = f"se detuvo ({str(e)[:80]})"
                if n != esperado:
                    fallas.append(falla(p.name, f"control positivo: {p.name} bien formado no se leyó completo con {nombre} ({esperado} filas): {n}"))
            r = ingerir_local(p, tmp)
            de_formato = {"conteo contra la fuente", "tipos declarados (FAILFAST)"} & set(r.get("fallas") or [])
            if r.get("motivo") or de_formato or r.get("filas") != esperado or r.get("conteo_fuente") != esperado:
                fallas.append(falla(p.name, f"control positivo: {p.name} bien formado no se leyó completo ({esperado} filas): {str(r)[:160]}"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n_auto = 0
    for herramienta, minimo in AUTOPRUEBAS.items():
        n, f = autoprueba(herramienta, minimo)
        n_auto += n
        fallas += f
    return {"bateria": "failfast", "casos": 5 * len(casos) + 3 * len(buenos) + 4 * len(controles) + n_auto, "fallas": fallas}


def bateria_inyeccion():
    """Instrucciones disfrazadas: los textos maliciosos deben detectarse y los legítimos no (sin falsas alarmas)."""
    from gobernanza import parece_instruccion
    malos = [l for l in (BAT / "inyeccion" / "maliciosos.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
    buenos = [l for l in (BAT / "inyeccion" / "legitimos.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
    fallas = [falla(m, f"no detecta: «{m[:60]}»") for m in malos if not parece_instruccion(m)]
    fallas += [falla(b, f"falsa alarma: «{b[:60]}»") for b in buenos if parece_instruccion(b)]
    return {"bateria": "inyeccion", "casos": len(malos) + len(buenos), "fallas": fallas}


def bateria_cruces():
    """Por qué no cruza un valor entre tablas: espacios internos o invisibles; tildes, puntuación o ceros a la izquierda."""
    from perfilar import perfilar
    d = BAT / "cruces"
    esperado = json.loads((d / "esperado.json").read_text(encoding="utf-8"))
    p = perfilar({"origen": str(d / "origen.csv"), "destino": str(d / "destino.csv")})
    fallas, casos = [], 0
    for col, claves in esperado.items():
        if col.startswith("_"):
            continue
        x = next((c for c in p["cruces"] if c["desde"] == "origen" and c["columna"] == col), None)
        if x is None:
            fallas.append(falla(col, f"{col}: el perfil no reporta el cruce"))
            continue
        obtenido = {**x, **x.get("de_los_que_no_cruzan", {})}
        for k, v in claves.items():
            casos += 1
            if obtenido.get(k) != v:
                fallas.append(falla(col, f"{col}.{k}: {obtenido.get(k)} (se esperaba {v})"))
    return {"bateria": "cruces", "casos": casos, "fallas": fallas}


def bateria_fechas():
    """Una fecha que no existe en el calendario (mes 13, 30 de febrero) se cuenta aparte y no entra al rango."""
    from perfilar import perfil_fechas
    d = json.loads((BAT / "fechas" / "casos.json").read_text(encoding="utf-8"))
    fallas = []
    for c in d["casos"]:
        p = perfil_fechas(c["valores"]) or {}
        obtenido = {**p, "fechas_imposibles": p.get("fechas_imposibles", 0)}
        for k, v in c.items():
            if k not in ("nombre", "valores") and obtenido.get(k) != v:
                fallas.append(falla(c['nombre'], f"{c['nombre']}: {k} = {obtenido.get(k)} (se esperaba {v})"))
    return {"bateria": "fechas", "casos": len(d["casos"]), "fallas": fallas}


def bateria_repetidos():
    """Llaves repetidas: nunca gana una fila por el orden del archivo sin avisarlo; el desempate del plan decide."""
    import csv
    import tempfile
    import limpieza
    d = BAT / "limpieza"
    esperado = json.loads((d / "repetidos_esperado.json").read_text(encoding="utf-8"))
    fallas = []
    for c in esperado["casos"]:
        tmp = Path(tempfile.mkdtemp(prefix="bateria-repetidos-"))
        try:
            op = {"op": "repetidos", "columnas": ["id"], "marca": "repetido"}
            if c["desempate"]:
                op["desempate"] = c["desempate"]
            plan = {"tabla": "t", "entrada": str(d / "repetidos.csv"), "salida": str(tmp / "t.csv"), "llave": "id", "operaciones": [op]}
            (tmp / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
            inf = limpieza.limpiar(tmp / "plan.json", informe=False)
            ok = {f["id"]: f["region"] for f in csv.DictReader(open(tmp / "t.csv", encoding="utf-8")) if f.get("calidad_ok") == "1"}
            for k, v in c["conserva"].items():
                if ok.get(k) != v:
                    fallas.append(falla(c['nombre'], f"{c['nombre']}: {k} conserva {ok.get(k)} (se esperaba {v})"))
            aviso = inf["operaciones"][0].get("aviso")
            if (c["aviso"] is None) != (aviso is None) or (c["aviso"] and c["aviso"] not in aviso):
                fallas.append(falla(c['nombre'], f"{c['nombre']}: aviso «{aviso}» (se esperaba «{c['aviso']}»)"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return {"bateria": "repetidos", "casos": len(esperado["casos"]), "fallas": fallas}


def bateria_factor():
    """Encuestas: el perfil reconoce el factor de expansión (cifras de población ponderadas, no conteo de filas)."""
    from perfilar import perfil_columna
    d = json.loads((BAT / "perfil" / "factor_de_expansion.json").read_text(encoding="utf-8"))
    fallas = []
    for c in d["casos"]:
        es = "factor_de_expansion" in perfil_columna(c["columna"], c["valores"])
        if es != c["es_factor"]:
            fallas.append(falla(c["columna"], f"{c['columna']} {c['valores'][:2]}: {'marcado' if es else 'no marcado'} como factor de expansión"))
    return {"bateria": "factor", "casos": len(d["casos"]), "fallas": fallas}


def bateria_grafico():
    """Forma y color del gráfico y lo que dice (D15), sobre el JSON de la figura (sin caja de arena): los buenos pasan
    todo y cada malo falla solo la comprobación que ataca. Un falso positivo también es una falla (L32). Un caso puede
    traer «resultado», las filas aprobadas (los nombres de las categorías vienen de ahí)."""
    from verificar_grafico import comprobar_figura
    fallas, nombres, atacadas = [], set(), set()
    buenos = sorted((BAT / "grafico" / "buenos").glob("*.json"))
    malos = sorted((BAT / "grafico" / "malos").glob("*.json"))
    for p in buenos:
        caso = json.loads(p.read_text(encoding="utf-8"))
        res = comprobar_figura(caso["figura"], caso.get("resultado") or [])
        nombres |= {c["comprobacion"] for c in res}
        fallan = [c["comprobacion"] for c in res if not c["ok"]]
        if fallan:
            fallas.append(falla(p.name, f"falso positivo en {p.name}: {fallan}"))
    for p in malos:
        caso = json.loads(p.read_text(encoding="utf-8"))
        res = comprobar_figura(caso["figura"], caso.get("resultado") or [])
        nombres |= {c["comprobacion"] for c in res}
        fallan = [c["comprobacion"] for c in res if not c["ok"]]
        objetivo = caso.get("debe_fallar")
        atacadas.add(objetivo)
        if objetivo not in {c["comprobacion"] for c in res}:
            fallas.append(falla(p.name, f"{p.name}: no existe la comprobación «{objetivo}»"))
        elif fallan != [objetivo]:
            fallas.append(falla(p.name, f"{p.name}: falla {fallan or 'ninguna'}; se esperaba solo «{objetivo}»"))
    fallas += [falla(n, f"sin caso malo para «{n}»") for n in sorted(nombres - atacadas)]
    return {"bateria": "grafico", "casos": len(buenos) + len(malos), "fallas": fallas}


# Lo que cita la prueba de una lección (L96), sin correr nada: un id del blindaje (B05), un mutante de los controles
# (M12), un caso de una batería (bateria:failfast/campo_de_mas.csv), una herramienta con su autoprueba
# (herramientas/ingesta.py --autoprueba), un archivo o una carpeta versionados, y una cita textual («…») que tiene que
# estar en el archivo que la precede. El resto del texto describe; no cuenta como prueba.
EXTENSIONES_CITA = r"(?:py|json|md|csv|txt|js|mjs|yml|yaml|html|sh)"
CITA_BLINDAJE = re.compile(r"\bB\d{2}\b")
CITA_MUTANTE = re.compile(r"\bM\d{2}\b")
CITA_BATERIA = re.compile(r"\bbateria:([\w./-]+)")
CITA_RUTA = re.compile(rf"(?<![\w/.:-])([\w-][\w.-]*(?:/[\w.-]+)+|[\w-][\w.-]*\.{EXTENSIONES_CITA})(?![\w/-])")
CON_EXTENSION = re.compile(rf"\.{EXTENSIONES_CITA}$")
CITA_AUTOPRUEBA = re.compile(r"([\w./-]+\.py):?\s+--autoprueba\b")
CITA_TEXTUAL = re.compile(r"«([^»]+)»")
TIPOS_DE_CITA = ("blindaje", "mutante", "archivo", "autoprueba", "cita", "vaga")


def versionados(raiz):
    """Lo que git versiona o versionaría en `raiz` (lo ignorado no: los datos de SECOP no viajan con un clon), o None si
    no es un repositorio. Un archivo nuevo sin agregar cuenta: lo que importa es que viaje con el aporte."""
    try:
        p = subprocess.run(["git", "-C", str(raiz), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],  # nosec B603 B607
                           capture_output=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return {os.fsdecode(x) for x in p.stdout.split(b"\0") if x} if p.returncode == 0 else None


class Citas:
    """Comprueba que lo que cita la prueba de una lección exista de verdad en el repositorio `raiz`."""

    def __init__(self, raiz=RAIZ):
        self.raiz = Path(raiz).resolve()
        self.versionados = versionados(self.raiz)
        v = self.versionados or set()
        self.carpetas = {"/".join(x.split("/")[:i]) for x in v for i in range(1, x.count("/") + 1)}
        self._textos = {}
        self.blindaje = set(re.findall(r'@prueba\("(B\d+)"', self.texto("herramientas/blindaje.py")))
        self.mutantes = set(re.findall(r'^\s*\("(M\d+)",', self.texto("herramientas/mutar_controles.py"), re.M))

    def existe(self, rel):
        """La ruta relativa `rel`, si existe dentro del repositorio y está versionada (sin git: si existe)."""
        rel = rel.rstrip("/")
        if not rel or rel.startswith("/") or ".." in rel.split("/"):
            return None
        p = (self.raiz / rel).resolve()
        if not p.is_relative_to(self.raiz) or not p.exists():
            return None
        if self.versionados is not None and rel not in self.versionados and rel not in self.carpetas:
            return None
        return rel

    def es_carpeta_de_arriba(self, nombre):
        if self.versionados is None:
            return (self.raiz / nombre).is_dir()
        return nombre in self.carpetas

    def resolver(self, ref, bateria=False):
        ref = ref.rstrip(".,:")
        candidatas = [f"baterias/{ref}", ref] if bateria else ([ref] if "/" in ref else [ref, f"herramientas/{ref}"])
        return next((r for r in map(self.existe, candidatas) if r), None)

    def texto(self, rel):
        """El texto del archivo; de un JSON, también sus textos ya decodificados (una cita no depende de los escapes)."""
        if rel not in self._textos:
            p = (self.raiz / rel).resolve()
            t = p.read_text(encoding="utf-8", errors="replace") if p.is_relative_to(self.raiz) and p.is_file() else ""
            if rel.endswith(".json") and t:
                def textos(x):
                    if isinstance(x, str):
                        yield x
                    elif isinstance(x, dict):
                        for k, v in x.items():
                            yield k
                            yield from textos(v)
                    elif isinstance(x, list):
                        for v in x:
                            yield from textos(v)
                try:
                    t += "\n" + "\n".join(textos(json.loads(t)))
                except ValueError:
                    pass
            self._textos[rel] = t
        return self._textos[rel]

    def revisar(self, prueba):
        """[(tipo, problema)] de la prueba citada; vacía si todo lo que cita existe y cita al menos algo comprobable."""
        prueba = prueba if isinstance(prueba, str) else ""
        problemas, refs = [], 0
        for b in CITA_BLINDAJE.findall(prueba):
            refs += 1
            if b not in self.blindaje:
                problemas.append(("blindaje", f"cita {b}, que no es una prueba de herramientas/blindaje.py"))
        for m in CITA_MUTANTE.findall(prueba):
            refs += 1
            if m not in self.mutantes:
                problemas.append(("mutante", f"cita {m}, que no es un mutante de herramientas/mutar_controles.py"))
        for parte in re.split(r"\s·\s|;", prueba):
            archivos = []   # (posición, ruta resuelta o None) en el orden del texto: la cita textual va con el anterior
            for m in CITA_BATERIA.finditer(parte):
                refs += 1
                r = self.resolver(m.group(1), bateria=True)
                archivos.append((m.start(), r))
                if not r:
                    problemas.append(("archivo", f"cita bateria:{m.group(1).rstrip('.,:')}, que no existe o no está versionado"))
            for m in CITA_RUTA.finditer(parte):
                ref = m.group(1).rstrip(".,:")
                if not CON_EXTENSION.search(ref) and not self.es_carpeta_de_arriba(ref.split("/")[0]):
                    continue   # «dd/mm/aaaa» no es una ruta; «agentes/04» sí, y tiene que existir
                refs += 1
                r = self.resolver(ref)
                archivos.append((m.start(), r))
                if not r:
                    problemas.append(("archivo", f"cita {ref}, que no existe o no está versionado"))
            for m in CITA_AUTOPRUEBA.finditer(parte):
                r = self.resolver(m.group(1))
                if r and "--autoprueba" not in self.texto(r):
                    problemas.append(("autoprueba", f"cita {m.group(1)} --autoprueba, y {r} no tiene autoprueba"))
            for m in CITA_TEXTUAL.finditer(parte):
                antes = [r for pos, r in sorted(archivos, key=lambda x: x[0]) if pos < m.start()]
                if not antes:
                    problemas.append(("cita", f"la cita «{m.group(1)[:60]}» no va después de un archivo que la contenga"))
                elif antes[-1] and m.group(1) not in self.texto(antes[-1]):
                    problemas.append(("cita", f"la cita «{m.group(1)[:60]}» no está en {antes[-1]}"))
        if not refs:
            problemas.append(("vaga", f"no cita nada que se pueda comprobar (un id B.. del blindaje, bateria:<archivo>, una "
                                      f"herramienta con --autoprueba o un archivo versionado): «{prueba[:80]}»"))
        return problemas


def instrucciones_de_flujo(texto):
    """{nombre: plantilla} de cada `const <nombre> = `…`` o `const <nombre> = (…) => `…`` de flujo.js: la plantilla
    entera, con sus ${…} sin evaluar (las comillas invertidas dentro de un ${…} no la cierran)."""
    out = {}
    for m in re.finditer(r"^const (\w+) = (?:\([^)]*\) => )?`", texto, re.M):
        i = j = m.end()
        hondo = 0
        while j < len(texto):
            if texto.startswith("${", j):
                hondo, j = hondo + 1, j + 2
                continue
            c = texto[j]
            if c == "\\":
                j += 2
                continue
            if c == "}" and hondo:
                hondo -= 1
            elif c == "`" and not hondo:
                out[m.group(1)] = texto[i:j]
                break
            j += 1
    return out


def sin_lecciones(texto):
    """Lo que falta para que las lecciones lleguen a cada subagente de flujo.js (regla común 9, L122): LECCIONES apunta
    a baterias/lecciones.json, reglasComunes las trae y cada instrucción que empieza con «Eres el» trae ${LECCIONES} o
    ${reglasComunes}. Devuelve (instrucciones revisadas, problemas)."""
    problemas = []
    if not re.search(r"^const LECCIONES = `\$\{RAIZ\}/baterias/lecciones\.json`", texto, re.M):
        problemas.append("flujo.js: LECCIONES no apunta a ${RAIZ}/baterias/lecciones.json")
    plantillas = instrucciones_de_flujo(texto)
    comunes = "${LECCIONES}" in plantillas.get("reglasComunes", "")
    if not comunes:
        problemas.append("flujo.js: reglasComunes no trae ${LECCIONES}")
    roles = {n: p for n, p in plantillas.items() if p.startswith("Eres el")}
    if not roles:
        problemas.append("flujo.js: no se encontró ninguna instrucción que empiece con «Eres el»")
    for n, p in roles.items():
        if "${LECCIONES}" not in p and not (comunes and "${reglasComunes}" in p):
            problemas.append(f"flujo.js ({n}): la instrucción no le pasa las lecciones (${{LECCIONES}} ni ${{reglasComunes}})")
    return len(roles), problemas


def bateria_lecciones():
    """Cada lección cita una prueba que existe de verdad (L96): un id del blindaje que está en blindaje.py, un mutante de
    mutar_controles.py, un caso de una batería, una herramienta que tiene --autoprueba o un archivo versionado, y cada
    cita textual está en su archivo. Antes solo se miraba que existieran los «bateria:…»: «B99», «pregunta en la spec» o
    un archivo borrado pasaban. Una cita rota de una lección va sin caso: es un error de quien la escribe, nunca un hueco
    que encontró un aporte, y el filtro la cuenta siempre como falla. Control positivo (L27): baterias/citas/casos.json
    trae citas buenas, que deben pasar, y malas, que deben fallar justo por lo que atacan."""
    d = json.loads((BAT / "lecciones.json").read_text(encoding="utf-8"))
    casos = json.loads((BAT / "citas" / "casos.json").read_text(encoding="utf-8"))
    citas = Citas(RAIZ)
    fallas, vistas = [], set()
    if not citas.blindaje or not citas.mutantes:
        fallas.append(falla("", "control positivo: no se leyeron los ids de herramientas/blindaje.py o de herramientas/mutar_controles.py"))
    for l in d["lecciones"]:
        ident = l.get("id", "?")
        if ident in vistas:   # al unir ramas, dos lecciones distintas pueden traer el mismo número
            fallas.append(falla("", f"{ident} está repetida: cada lección lleva su propio id"))
        vistas.add(ident)
        fallas += [falla("", f"{ident}: {p}") for _, p in citas.revisar(l.get("prueba", ""))]
    for c in casos["buenas"]:
        problemas = citas.revisar(c["prueba"])
        if problemas:
            fallas.append(falla(c["nombre"], f"falso positivo en la cita buena {c['nombre']}: {problemas[0][1]}"))
    atacados = set()
    for c in casos["malas"]:
        tipos, esperados = sorted({t for t, _ in citas.revisar(c["prueba"])}), sorted(c["debe_fallar"])
        atacados |= set(esperados)
        if tipos != esperados:
            fallas.append(falla(c["nombre"], f"la cita mala {c['nombre']} falla {tipos or 'ninguna comprobación'}; se esperaba {esperados}"))
    fallas += [falla(t, f"sin cita mala para «{t}»") for t in TIPOS_DE_CITA if t not in atacados]
    # las lecciones llegan a todos los subagentes (regla común 9, L122), con su control positivo: cada forma de perderlas
    # (sin ${reglasComunes}, sin la línea de ${LECCIONES}, reglasComunes sin ${LECCIONES}) se echa de menos
    flujo = (RAIZ / "flujo.js").read_text(encoding="utf-8")
    roles, problemas = sin_lecciones(flujo)
    fallas += [falla("flujo.js", p) for p in problemas]
    plantillas = instrucciones_de_flujo(flujo)
    perdidas = {"pGraficar": ("${reglasComunes}", ""), "pPresentar": ("(${LECCIONES}:", "("),
                "reglasComunes": ("las lecciones de errores reales en ${LECCIONES}", "las lecciones de errores reales")}
    for nombre, (quitar, poner) in perdidas.items():
        plantilla = plantillas.get(nombre, "")
        if plantilla.count(quitar) != 1:
            fallas.append(falla("flujo.js", f"control positivo inválido: «{quitar}» no está una vez en {nombre}; rehacerlo"))
            continue
        _, vistos = sin_lecciones(flujo.replace(plantilla, plantilla.replace(quitar, poner), 1))
        if not any(f"({nombre})" in v or (nombre == "reglasComunes" and "reglasComunes no trae" in v) for v in vistos):
            fallas.append(falla("flujo.js", f"control positivo: con {nombre} sin las lecciones, la comprobación no lo echa de menos"))
    return {"bateria": "lecciones", "casos": len(d["lecciones"]) + len(casos["buenas"]) + len(casos["malas"]) + roles
            + len(perdidas), "fallas": fallas}


def main(argv):
    if "--agregar-malo" in argv:
        i = argv.index("--agregar-malo")
        nombre, origen = argv[i + 1], Path(argv[i + 2])
        destino = BAT / "seguridad" / "malos" / f"{nombre}.py"
        shutil.copy(origen, destino)
        print(f"Agregado {destino.name}. {'Se bloquea hoy.' if bloquea(destino) else 'HOY NO SE BLOQUEA: hay que mejorar la compuerta.'}")
        return 0
    if "--leccion" in argv:
        d = json.loads((BAT / "lecciones.json").read_text(encoding="utf-8"))
        g = lambda k: argv[argv.index(k) + 1] if k in argv else ""
        ident = g("--id") or f"L{len(d['lecciones']) + 1:02d}"   # en un aporte: --id L-<usuario>-<tema>; el dueño renumera al aceptar
        problemas = Citas(RAIZ).revisar(g("--prueba"))
        if problemas:   # la misma comprobación de la batería: una lección sin una prueba que exista no se agrega
            print("No se agregó la lección: " + "; ".join(p for _, p in problemas))
            return 1
        d["lecciones"].append({"id": ident, "leccion": g("--leccion"), "origen": g("--origen"), "prueba": g("--prueba")})
        (BAT / "lecciones.json").write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Lección {d['lecciones'][-1]['id']} agregada.")
        return 0
    res = [correr_bateria(fn) for fn in (bateria_seguridad, bateria_privacidad, bateria_failfast, bateria_inyeccion,
                                         bateria_cruces, bateria_fechas, bateria_repetidos, bateria_factor,
                                         bateria_grafico, bateria_lecciones)]
    for r in res:
        print(f"{'✓' if not r['fallas'] else '✗'} {r['bateria']}: {r['casos']} casos"
              + ("" if not r["fallas"] else " · " + "; ".join(f["falla"] for f in r["fallas"])))
    malos = sum(len(r["fallas"]) for r in res)
    detalle = [{"bateria": r["bateria"], "caso": f["caso"], "falla": f["falla"][:300]} for r in res for f in r["fallas"]]
    print("RESUMEN " + json.dumps({"baterias": len(res), "fallas": malos, "errores": [r["bateria"] for r in res if r.get("error")],
                                   "detalle": detalle[:200]}, ensure_ascii=False))
    return 1 if malos else 0


def correr_bateria(fn):
    """Si una batería se cae, cuenta como falla y las demás siguen corriendo: nunca se pierde el resto en silencio."""
    try:
        r = fn()
        r["fallas"] = [f if isinstance(f, dict) else falla("", f) for f in r["fallas"]]
        return r
    except Exception as e:
        return {"bateria": fn.__name__.replace("bateria_", ""), "casos": 0, "error": True,
                "fallas": [falla("", f"ERROR: la batería no terminó: {type(e).__name__}: {str(e)[:160]}")]}


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
