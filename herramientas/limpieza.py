#!/usr/bin/env python3
"""Limpieza declarada (sin IA): del dato crudo a la capa limpia, marcando y sin borrar.

Uso: python limpieza.py <plan_limpieza.json>   (las rutas del plan son relativas a la carpeta del plan)
     python limpieza.py --autoprueba            casos ficticios: lectura FAILFAST, umbrales y calidad antes y después

La IA escribe el plan; este motor lo ejecuta igual cada vez y lo prueba:
  - el dato crudo no se toca (capa cruda, con su procedencia);
  - la capa limpia tiene las mismas filas: limpiar es marcar (R14). Cada problema queda en una columna
    calidad_<marca> (1/0), y calidad_ok vale 1 si la fila no tiene marcas;
  - cada operación informa cuántas filas cambió y cuántas marcó, con ejemplos (nunca de columnas privadas);
  - completitud, validez y unicidad se miden antes y después (con el mismo tipo, así se ve cuánto cambió la calidad
    con la limpieza), y los umbrales del plan bloquean.

Lectura FAILFAST (con el número de línea), con el mismo lector estricto que las reglas y la ingesta
(reglas_base.leer_tabla): un archivo que no está en UTF-8, sin encabezado o con columnas repetidas, una comilla sin
cerrar, una línea vacía, una fila con más o menos campos, otro separador, un \\r suelto fuera de comillas (el CSV de
Excel para Mac, L107) o columnas crudas calidad_* detienen la limpieza; nunca se lee a medias. La op numero con
decimal «.» se detiene ante montos con punto de miles mezclados con números sin separador (78.000 junto a 1628100),
que leídos así se dividirían por mil (L46; si el punto ya es decimal en la columna, como 12.5, 1.250 es un decimal: L49).
Con decimal «,», cada punto agrupa exactamente tres cifras (1.234,5 · 12.500.000 · 0,75); 12.5, 1.5 o 1,234.5 se marcan
numero_invalido en vez de leerse como 125, 15 o 1.2345 (L108). Con los dos decimales, solo cifras ASCII: 1_000, «٣» o
Infinity también se marcan, aunque float() los acepte.

Operaciones (en orden):
  {"op": "texto", "columna", "recortar": true, "unicode": true, "invisibles": true, "espacios_internos": true}
  {"op": "reemplazar", "columna", "patron": regex, "por": texto, "marca": opcional}
  {"op": "nulos_disfrazados", "columna", "valores": ["No Definido", "N/A", "-"], "marca"}
  {"op": "mapear", "columna", "mapa": {variante: oficial}, "normalizar_clave": true, "marca": "fuera_de_mapa"}
  {"op": "fecha", "columna", "formatos": ["%Y-%m-%d", "%d/%m/%Y"], "marca": "fecha_invalida"}   → aaaa-mm-dd (se guarda la hora aparte si viene)
  {"op": "numero", "columna", "decimal": "." , "marca": "numero_invalido"}   decimal «.» o «,»; lo que no tiene la forma
      de un número con ese decimal se marca (L108): con «,», 12.5 o 1,234.5 no se leen como 125 o 1.2345
  {"op": "rango", "columna", "min", "max", "marca"}                 marca, no corrige (R7)
  {"op": "atipicos", "columna", "k": 3, "marca"}                    rango intercuartílico sobre log10 de los positivos
  {"op": "repetidos", "columnas": [...] o "fila_completa", "marca": "repetido",
   "desempate": {"columna": "fecha_actualizacion", "conservar": "ultimo"}}   marca todas menos la que se conserva:
      sin desempate, la primera del archivo; si la llave se repite con valores distintos y no hay desempate, avisa
  {"op": "comparar", "izquierda", "operador": "<", "derecha", "marca"}             p. ej. fin antes de inicio
La llave del plan es una columna o una lista de columnas (llave compuesta): la prueba de orden compara la combinación.

Umbrales (se justifican sobre el dato real, no sobre el caso conocido):
  {"completitud_minima": {col: 0.99}, "validez_minima": {col: 0.999}, "unicidad": [col],
   "marcadas_maximo": {marca: n}, "vacios_maximo": {col: n}}
  - vacios_maximo cuenta celdas vacías en conteos absolutos (también las de un nulo disfrazado que se vació): un
    umbral relativo pensado para 23 filas deja perder miles en 49.662; uno absoluto, no.
  - El detalle de completitud y validez dice la holgura: cuántas filas más puede perder el dato antes de que el
    umbral bloquee. Se comparan con los conteos enteros y el umbral tal como se escribió (0.99 es 99/100), nunca con la
    proporción redondeada: redondeada a 6 decimales, 2.969.999 de 3.000.000 pasaba 0,99 (L110).
  - Un umbral con nombre desconocido, sobre una columna que no existe o sobre una marca que ninguna operación pone
    detiene la limpieza: nunca se ignora en silencio. También uno que no es de su tipo: completitud y validez, un número
    entre 0 y 1; marcadas_maximo y vacios_maximo, un entero ≥ 0; unicidad, una lista de columnas («"0"» daba un
    TypeError al final, con la capa limpia ya escrita: L109).
  - "umbrales_caso" (opcional): los del caso conocido, que trae defectos a propósito. Se aplican solo cuando quien
    llama lo pide (limpiar(..., caso=True), con la entrada del caso), nunca desde la línea de comandos ni sobre la
    entrada del plan. El caso no puede exigir más que el dato real: cada umbral de umbrales_caso debe estar también
    en umbrales y ser igual o más laxo; si no, la limpieza se detiene.

Rechazo que detiene (L109, como la ingesta: GOB-7). La capa limpia se escribe solo si la limpieza queda «aprobada», en
un temporal que la reemplaza al final. Si queda rechazada o el motor se detiene (FAILFAST, un plan que no se puede
ejecutar o un error que no se previó), la capa limpia de una limpieza anterior se retira y limpieza_<tabla>.json queda
en «rechazada», con su motivo y sin traceback: ninguna etapa lee datos que ninguna limpieza aprobó, y verificar.py y el
informe final dejan la corrida en «revisar» con una limpieza sin aprobar o con una capa limpia que no es la de su informe.
La tabla del plan es un nombre simple y la salida, un .csv que no es la entrada ni el plan.
"""
import contextlib
import csv
import hashlib
import io
import json
import math
import os
import re
import shutil
import sys
import tempfile
import traceback
import unicodedata
import uuid
from datetime import datetime
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reglas_base  # noqa: E402
from gobernanza import clasificar_columna, enmascarar, es_sensible, parece_instruccion  # noqa: E402
from reglas_base import leer_tabla  # noqa: E402

# con escapes, no con los caracteres literales: al reescribir el archivo, U+2028 y U+2029 literales se volvían espacios
INVISIBLES = re.compile(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f\u200b-\u200f\u2028\u2029\u202a-\u202e\u2060\ufeff]")
OPS = {"<": lambda a, b: a < b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b, ">=": lambda a, b: a >= b,
       "==": lambda a, b: a == b, "!=": lambda a, b: a != b}
UMBRALES = ("completitud_minima", "validez_minima", "unicidad", "marcadas_maximo", "vacios_maximo")
TABLA = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_-]{0,63}")    # como en la ingesta: limpieza_<tabla>.json queda junto al plan
# la forma completa de un número con cada decimal, solo con cifras ASCII (float() acepta 1_000, «٣», Infinity y espacios)
NUMERO = {".": re.compile(r"[-+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][-+]?[0-9]+)?"),
          ",": re.compile(r"[-+]?(?:[0-9]+|[1-9][0-9]{0,2}(?:\.[0-9]{3})+)(?:,[0-9]+)?")}   # 1.234,5 · 12.500.000 · 0,75
MARCA_POR_DEFECTO = {"nulos_disfrazados": "nulo_disfrazado_{}", "mapear": "fuera_de_mapa_{}",
                     "fecha": "fecha_invalida_{}", "numero": "numero_invalido_{}", "repetidos": "repetido"}


def clave_norm(s):
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^0-9a-z]", "", s.casefold())


def privada(col):
    """Sus ejemplos salen enmascarados: identifica a personas, es texto libre o es un dato sensible (Ley 1581, art. 5;
    gobernanza lo clasifica como cuasi, pero un ejemplo suyo ya es el dato sensible de alguien)."""
    return clasificar_columna(col) in ("personal", "texto_libre") or es_sensible(col)


def ejemplo(col, antes, despues):
    if parece_instruccion(antes) or parece_instruccion(despues):
        return "[ejemplo omitido: parece una instrucción para una IA]"
    if privada(col):
        return f"{enmascarar(antes)} → {enmascarar(despues)}"
    return f"«{antes[:40]}» → «{despues[:40]}»"


def leer_fecha(v, formatos):
    for f in formatos:
        try:
            return datetime.strptime(v, f)
        except ValueError:
            continue
    if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", v):
        try:
            return datetime.fromisoformat(v[:19])
        except ValueError:
            return None
    return None


def fecha_valida(v):
    """aaaa-mm-dd y una fecha que existe en el calendario (2025-02-30 no cuenta)."""
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
        return False
    try:
        datetime.strptime(v, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def numero_valido(v):
    """Un número con decimal «.», solo con cifras ASCII y finito (la validez se mide con la misma forma que la op numero)."""
    v = v.strip()
    return bool(NUMERO["."].fullmatch(v)) and math.isfinite(float(v))


def metricas(filas, cols, tipos):
    out = {}
    n = len(filas) or 1
    for c in cols:
        vals = [f.get(c, "") for f in filas]
        llenos = [v for v in vals if v.strip()]
        m = {"completitud": round(len(llenos) / n, 6), "distintos": len(set(llenos))}
        t = tipos.get(c)
        if t in ("fecha", "numero"):
            ok = fecha_valida if t == "fecha" else numero_valido
            m["validez"] = round(sum(1 for v in llenos if ok(v)) / (len(llenos) or 1), 6)
        out[c] = m
    return out


def cumple(k, n, minimo):
    """(¿k de n alcanza la proporción mínima?, holgura: cuántos de los k pueden faltar sin que deje de alcanzarla, o None)
    con los conteos enteros y el umbral tal como se escribió (0.99 es 99/100, no el float más cercano). La proporción
    redondeada a 6 decimales dejaba pasar 2.969.999 de 3.000.000 contra 0,99 y corría la holgura (L110). Sin filas,
    como 0 de 1: solo un mínimo de 0 se cumple."""
    falta = Fraction(repr(minimo)) * (n or 1)
    return (True, math.floor(k - falta)) if k >= falta else (False, None)


def proporcion(k, n):
    """k / n truncada a 6 decimales, para mostrarla: un umbral que no se cumple nunca se ve como 99,0000 %."""
    return math.floor(Fraction(k, n or 1) * 10 ** 6) / 10 ** 6


def cambio(antes, despues):
    """Lo que movió la limpieza en cada columna (después menos antes), con el mismo tipo en los dos lados."""
    out = {}
    for c, d in despues.items():
        a = antes.get(c)
        if not a:
            continue
        x = {k: round(d[k] - a[k], 6) for k in ("completitud", "validez") if k in d and k in a}
        if any(x.values()):
            out[c] = x
    return out


def miles(n):
    return f"{n:,}".replace(",", ".")


def leer_crudo(ent):
    """(columnas, filas como diccionarios, línea donde termina cada fila, bytes) con el lector estricto de las reglas y
    de la ingesta (reglas_base.leer_tabla): FAILFAST con el número de línea ante un archivo que no está en UTF-8, vacío
    o sin encabezado, otro separador, columnas repetidas, una comilla sin cerrar, una línea vacía o una fila con más o
    menos campos que el encabezado; nunca se lee a medias. Una fórmula de Excel no detiene la limpieza (se neutraliza y
    se marca, DB5) y el punto de miles lo revisa la operación numero, que es la que declara el decimal."""
    crudo = ent.read_bytes()
    try:
        texto = crudo.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        linea = crudo[:e.start].count(b"\n") + 1
        raise ValueError(f"FAILFAST: la línea {linea} de {ent.name} no está en UTF-8 (byte {e.start + 1})") from None
    try:
        cols, filas, lineas = leer_tabla(texto, f"de {ent.name}", miles=False, formulas=False)
    except ValueError as e:
        raise ValueError(f"FAILFAST: {e}") from None
    return cols, [dict(zip(cols, f)) for f in filas], lineas, crudo


def ver_valor(col, v):
    """Cómo sale un valor en un mensaje: enmascarado si la columna está marcada (personal, cuasi, texto libre o
    sensible), recortado si no."""
    return enmascarar(v) if clasificar_columna(col) or es_sensible(col) else v[:20]


def revisar_punto_de_miles(col, valores, lineas, nombre):
    """Con decimal «.», 78.000 junto a 1628100 en la misma columna se leería como 78 en silencio (L46). La regla es la de
    reglas_base, con su excepción: si el punto ya es decimal en la columna (12.5), 1.250 es un decimal (L49)."""
    try:
        reglas_base.revisar_punto_de_miles([col], [[v] for v in valores], lineas, f"de {nombre}", ver=ver_valor)
    except ValueError as e:
        raise ValueError(f"FAILFAST: {e}; con decimal «.» se leería dividido por mil: declare decimal «,» o unifique "
                         "el formato") from None


def marcas_posibles(plan):
    nombres = {"formula_neutralizada"}
    for o in plan.get("operaciones", []):
        if o.get("marca"):
            nombres.add(o["marca"])
        elif o.get("op") in MARCA_POR_DEFECTO:
            nombres.add(MARCA_POR_DEFECTO[o["op"]].format(o.get("columna")))
    return nombres


def _fraccion(x):
    """Un número finito (no un booleano ni un texto) entre 0 y 1."""
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and 0 <= x <= 1


def _conteo(x):
    """Un entero mayor o igual que 0 (no un booleano, un decimal ni un texto)."""
    return isinstance(x, int) and not isinstance(x, bool) and x >= 0


def revisar_umbrales(plan, cols):
    """Un umbral que no se puede evaluar no se ignora ni revienta: nombre desconocido, columna que no existe, marca que
    ninguna operación pone o un valor que no es del tipo del umbral (completitud y validez, un número entre 0 y 1; los
    máximos, un entero ≥ 0; unicidad, una lista de columnas). Antes, «"0"» en vacios_maximo daba un TypeError al final,
    con la capa limpia ya escrita (L109). Y el caso conocido no exige más que el dato real."""
    p, posibles = [], marcas_posibles(plan)
    bloques = {"umbrales": plan.get("umbrales") or {}}
    if "umbrales_caso" in plan:
        bloques["umbrales_caso"] = plan.get("umbrales_caso") or {}
    for nombre, u in bloques.items():
        if not isinstance(u, dict):
            p.append(f"{nombre} debe ser un objeto")
            continue
        desconocidos = sorted(k for k in u if k not in UMBRALES and not k.startswith("_"))
        if desconocidos:
            p.append(f"{nombre}: umbrales desconocidos {desconocidos} (se admiten {', '.join(UMBRALES)})")
        for k, de_su_tipo, tipo in (("completitud_minima", _fraccion, "un número entre 0 y 1"),
                                    ("validez_minima", _fraccion, "un número entre 0 y 1"),
                                    ("marcadas_maximo", _conteo, "un entero mayor o igual que 0"),
                                    ("vacios_maximo", _conteo, "un entero mayor o igual que 0")):
            d = u.get(k)
            if d is not None and not isinstance(d, dict):
                p.append(f"{nombre}.{k} debe ser un objeto {{nombre: umbral}}")
                continue
            for c, x in (d or {}).items():
                if not de_su_tipo(x):
                    p.append(f"{nombre}.{k}.{c} debe ser {tipo} (es {json.dumps(x, ensure_ascii=False)[:30]})")
            if k != "marcadas_maximo":
                faltan = sorted(c for c in (d or {}) if c not in cols)
                if faltan:
                    p.append(f"{nombre}.{k} usa columnas que no existen: {faltan}")
        uni = u.get("unicidad")
        if uni is not None and not (isinstance(uni, list) and all(isinstance(c, str) for c in uni)):
            p.append(f"{nombre}.unicidad debe ser una lista de columnas")
        else:
            faltan = sorted(c for c in (uni or []) if c not in cols)
            if faltan:
                p.append(f"{nombre}.unicidad usa columnas que no existen: {faltan}")
        marcadas = u.get("marcadas_maximo")
        sin_op = sorted(m for m in (marcadas if isinstance(marcadas, dict) else {}) if m not in posibles)
        if sin_op:
            p.append(f"{nombre}.marcadas_maximo usa marcas que ninguna operación pone: {sin_op}")
    if p:
        return p    # con un umbral de otro tipo, comparar el caso con el dato real reventaría
    if "umbrales_caso" in bloques and isinstance(bloques["umbrales_caso"], dict) and isinstance(bloques["umbrales"], dict):
        real, caso = bloques["umbrales"], bloques["umbrales_caso"]
        for k, mas_estricto in (("completitud_minima", lambda r, c: r >= c), ("validez_minima", lambda r, c: r >= c),
                                ("marcadas_maximo", lambda r, c: r <= c), ("vacios_maximo", lambda r, c: r <= c)):
            for c, v in (caso.get(k) or {}).items():
                r = (real.get(k) or {}).get(c)
                if r is None or not mas_estricto(r, v):
                    p.append(f"el caso conocido exige más que el dato real en {k}.{c} (caso {v}, dato real {r})")
        for c in caso.get("unicidad") or []:
            if c not in (real.get("unicidad") or []):
                p.append(f"el caso conocido exige unicidad de {c} y el dato real no")
    return p


def escribir_capa(sal, contenido):
    """La capa limpia se escribe en un temporal de su misma carpeta y lo reemplaza de una vez (os.replace): quien la
    lee nunca ve un archivo a medias ni el de antes mezclado con el nuevo."""
    sal.parent.mkdir(parents=True, exist_ok=True)
    tmp = sal.with_name(f".{sal.name}.{uuid.uuid4().hex[:12]}.tmp")
    try:
        tmp.write_bytes(contenido)
        os.replace(tmp, sal)
    finally:
        tmp.unlink(missing_ok=True)


def retirar(sal):
    """Una limpieza rechazada o detenida no deja capa limpia: la de una limpieza anterior se retira (True si había)."""
    if sal is not None and Path(sal).is_file():
        Path(sal).unlink()
        return True
    return False


def motivo_de(e):
    """Lo que se dice de una detención: el mensaje propio del motor (FAILFAST o la operación con una columna que no
    existe; sus ejemplos ya salen enmascarados) o, si el error no se previó, su tipo y su lugar, no su texto, que
    puede traer un valor de la fuente (como en la ingesta)."""
    texto = str(e)
    if (isinstance(e, ValueError) and texto.startswith("FAILFAST")) or (isinstance(e, SystemExit) and isinstance(e.code, str)):
        return texto[:600]
    marcos = traceback.extract_tb(e.__traceback__)
    donde = ([m for m in marcos if Path(m.filename).name == Path(__file__).name] or marcos or [None])[-1]   # el de este motor
    lugar = f" en {donde.name}, {Path(donde.filename).name}:{donde.lineno}" if donde else ""
    return f"la limpieza se detuvo antes de terminar sus pruebas ({type(e).__name__}{lugar}): no se aprueba"


def rechazar(plan_ruta, destino, motivo, retirado):
    """Línea de comandos: la limpieza que se detuvo deja limpieza_<tabla>.json en «rechazada» (nunca el «aprobada» de
    una limpieza anterior), con su motivo, y sale con 1 sin traceback. Sin un nombre de tabla simple (del plan o de
    plan_limpieza_<tabla>.json) no se escribe: con «../» quedaría fuera de la carpeta del plan."""
    tabla = destino.get("tabla")
    if tabla is None:
        m = re.fullmatch(r"plan_limpieza_(.+)\.json", plan_ruta.name)
        tabla = m.group(1) if m and TABLA.fullmatch(m.group(1)) else None
    print(f"Limpieza rechazada: {motivo}")
    if retirado:
        print(f"  · se retira {Path(destino['salida']).name} de una limpieza anterior: ya no corresponde a una limpieza aprobada")
    if tabla:
        (plan_ruta.parent / f"limpieza_{tabla}.json").write_text(json.dumps(
            {"tabla": tabla, "estado": "rechazada", "motivo": motivo,
             "salida": str(destino["salida"]) if destino.get("salida") else None, "capa_limpia_retirada": retirado,
             "sha256_limpio": None, "operaciones": [], "pruebas": []}, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        print("  · sin un nombre de tabla simple no se escribe limpieza_<tabla>.json")
    print("RESUMEN " + json.dumps({"estado": "rechazada", "motivo": motivo}, ensure_ascii=False))
    return 1


def limpiar(plan_ruta, entrada=None, salida=None, informe=True, caso=False):
    """Ejecuta el plan y lo prueba. La capa limpia se escribe solo si la limpieza queda «aprobada»; si queda rechazada
    o el motor se detiene, la de una limpieza anterior se retira (L109). Con informe=True (la línea de comandos) deja
    limpieza_<tabla>.json, también en «rechazada» con el motivo de la detención, y devuelve 0 o 1 sin traceback; con
    informe=False devuelve el informe a quien llama y una detención le llega como excepción."""
    plan_ruta = Path(plan_ruta).resolve()
    destino = {}     # la tabla y la salida, en cuanto se conocen y son seguras
    try:
        inf, contenido = _ejecutar(plan_ruta, entrada, salida, caso, destino)
        if inf["estado"] == "aprobada":
            escribir_capa(Path(inf["salida"]), contenido)
        else:
            inf["sha256_limpio"] = None
            inf["capa_limpia_retirada"] = retirar(inf["salida"])
    except (Exception, SystemExit) as e:  # noqa: BLE001 (FAILFAST: lo que no se previó también rechaza la limpieza)
        retirado = retirar(destino.get("salida"))
        if not informe:
            raise
        return rechazar(plan_ruta, destino, motivo_de(e), retirado)
    if not informe:
        return inf
    return mostrar(plan_ruta.parent, inf)


def _ejecutar(plan_ruta, entrada, salida, caso, destino):
    """El plan, sus operaciones y sus pruebas, sin escribir nada: (informe, bytes de la capa limpia)."""
    base = plan_ruta.parent
    plan = json.loads(plan_ruta.read_text(encoding="utf-8"))
    if not isinstance(plan, dict):
        raise ValueError("FAILFAST: el plan es un objeto JSON {tabla, entrada, salida, llave, operaciones, umbrales}")
    tabla = plan.get("tabla", "tabla")
    if not (isinstance(tabla, str) and TABLA.fullmatch(tabla)):
        raise ValueError("FAILFAST: la tabla del plan tiene que ser un nombre simple (letras, cifras, «_» y «-»): "
                         "limpieza_<tabla>.json se escribe junto al plan")
    destino["tabla"] = tabla
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from rutas import resolver
    if caso and entrada is None:
        raise ValueError("umbrales_caso es solo para el caso conocido: quien pide caso=True pasa la entrada del caso, "
                         "nunca la del plan")
    e = entrada or plan["entrada"]
    ent = Path(resolver(e)) if Path(e).is_absolute() else base / e
    s_ = salida or plan["salida"]
    sal = Path(s_) if Path(s_).is_absolute() else base / s_
    # la salida se reemplaza si se aprueba y se retira si no: nunca puede ser el dato crudo ni el plan
    if sal.suffix.lower() != ".csv" or sal.resolve() in (ent.resolve(), plan_ruta):
        raise ValueError("FAILFAST: la salida del plan tiene que ser un .csv distinto de la entrada y del plan "
                         "(limpio/<tabla>.csv): se reemplaza si la limpieza se aprueba y se retira si no")
    destino["salida"] = sal
    cols, crudas, lineas, crudo = leer_crudo(ent)    # también detiene otro separador (la línea 1 con «;», tabulador o «|»)
    reservadas = [c for c in cols if c.lower().startswith("calidad_")]
    if reservadas:
        raise ValueError(f"FAILFAST: {ent.name} ya trae columnas con el prefijo calidad_, reservado para las marcas de la capa "
                         f"limpia: {reservadas[:5]}. Una implementación las tomaría por marcas y excluiría filas; renómbralas "
                         f"en el contrato de ingesta")
    derivadas = [f"{o.get('columna')}__hora" for o in plan.get("operaciones", []) if o.get("op") == "fecha" and o.get("guardar_hora")]
    problemas = revisar_umbrales(plan, cols + derivadas)
    if problemas:
        raise ValueError("FAILFAST: los umbrales del plan no se pueden evaluar tal como están: " + "; ".join(problemas))
    huella_cruda = hashlib.sha256(crudo).hexdigest()
    filas = [dict(f) for f in crudas]
    marcas = [set() for _ in filas]
    tipos = {o["columna"]: o["op"] for o in plan["operaciones"] if o.get("op") in ("fecha", "numero")}
    antes = metricas(crudas, cols, tipos)
    reporte = []

    for o in plan["operaciones"]:
        op, col = o["op"], o.get("columna")
        if col and col not in cols:
            raise SystemExit(f"La operación {op} usa la columna {col}, que no existe (R1)")
        cambiadas, marcadas, ej = 0, 0, []

        def cambia(i, nuevo):
            nonlocal cambiadas
            viejo = filas[i][col]
            if nuevo != viejo:
                cambiadas += 1
                if len(ej) < 3:
                    ej.append(ejemplo(col, viejo, nuevo))
                filas[i][col] = nuevo

        def marca(i, m):
            nonlocal marcadas
            if m not in marcas[i]:
                marcas[i].add(m)
                marcadas += 1

        if op == "texto":
            for i, f in enumerate(filas):
                v = f[col]
                if o.get("invisibles", True):
                    v = INVISIBLES.sub("", v)
                if o.get("unicode", True):
                    v = unicodedata.normalize("NFC", v)
                if o.get("espacios_internos", True):
                    v = re.sub(r"\s+", " ", v)
                if o.get("recortar", True):
                    v = v.strip()
                if o.get("mayusculas"):
                    v = v.upper()
                cambia(i, v)
        elif op == "reemplazar":
            rx = re.compile(o["patron"])
            for i, f in enumerate(filas):
                nuevo = rx.sub(o.get("por", ""), f[col]).strip()
                if nuevo != f[col] and o.get("marca"):
                    marca(i, o["marca"])
                cambia(i, nuevo)
        elif op == "nulos_disfrazados":
            disfraz = {clave_norm(x) for x in o["valores"]}
            for i, f in enumerate(filas):
                if f[col].strip() and clave_norm(f[col]) in disfraz:
                    marca(i, o.get("marca", f"nulo_disfrazado_{col}"))
                    cambia(i, "")
        elif op == "mapear":
            norm = o.get("normalizar_clave", True)
            mapa = {(clave_norm(k) if norm else k): v for k, v in o["mapa"].items()}
            fuera = {}
            for i, f in enumerate(filas):
                v = f[col]
                if not v.strip():
                    continue
                k = clave_norm(v) if norm else v
                if k in mapa:
                    cambia(i, mapa[k])
                else:
                    marca(i, o.get("marca", f"fuera_de_mapa_{col}"))
                    fuera[v] = fuera.get(v, 0) + 1
            if fuera:
                ej.append(f"sin mapear: {[x if not parece_instruccion(x) else '[omitido]' for x in list(fuera)[:5]] if not privada(col) else len(fuera)}")
        elif op == "fecha":
            formatos = o.get("formatos", ["%Y-%m-%d"])
            hora = f"{col}__hora"
            for i, f in enumerate(filas):
                v = f[col].strip()
                if not v:
                    continue
                d = leer_fecha(v, formatos)
                if d is None:
                    marca(i, o.get("marca", f"fecha_invalida_{col}"))
                    continue
                if o.get("guardar_hora") and (d.hour or d.minute or d.second):
                    f[hora] = d.strftime("%H:%M:%S")
                cambia(i, d.strftime("%Y-%m-%d"))
            if o.get("guardar_hora") and hora not in cols:
                cols.append(hora)
                for f in filas:
                    f.setdefault(hora, "")
        elif op == "numero":
            decimal = o.get("decimal", ".")
            if decimal not in NUMERO:
                raise ValueError(f"FAILFAST: la operación numero de {col} declara el decimal {str(decimal)[:10]!r}: "
                                 "se admite «.» o «,»")
            if decimal == ".":
                revisar_punto_de_miles(col, [f[col].strip() for f in filas], lineas, ent.name)
            for i, f in enumerate(filas):
                v = f[col].strip()
                if not v:
                    continue
                # la forma completa, no lo que float() acepte: con «,», 12.5 se volvía 125 y 1,234.5, 1.2345 (L108)
                if not NUMERO[decimal].fullmatch(v):
                    marca(i, o.get("marca", f"numero_invalido_{col}"))
                    continue
                if decimal == ",":
                    v = v.replace(".", "").replace(",", ".")
                if math.isfinite(float(v)):
                    cambia(i, v)
                else:
                    marca(i, o.get("marca", f"numero_invalido_{col}"))
        elif op == "rango":
            lo, hi = o.get("min"), o.get("max")
            for i, f in enumerate(filas):
                v = f[col].strip()
                if not v:
                    continue
                try:
                    x = v if tipos.get(col) == "fecha" else float(v)
                except ValueError:
                    continue
                if (lo is not None and x < lo) or (hi is not None and x > hi):
                    marca(i, o["marca"])
        elif op == "atipicos":
            logs = []
            for f in filas:
                try:
                    x = float(f[col])
                    if x > 0:
                        logs.append(math.log10(x))
                except ValueError:
                    pass
            logs.sort()
            if len(logs) >= 20:
                q1, q3 = logs[len(logs) // 4], logs[(3 * len(logs)) // 4]
                k = float(o.get("k", 3))
                bajo, alto = q1 - k * (q3 - q1), q3 + k * (q3 - q1)
                for i, f in enumerate(filas):
                    try:
                        x = float(f[col])
                    except ValueError:
                        continue
                    if x > 0 and not (bajo <= math.log10(x) <= alto):
                        marca(i, o["marca"])
                ej.append(f"límites: {10 ** bajo:,.0f} a {10 ** alto:,.0f}".replace(",", "."))
        elif op == "repetidos":
            claves = cols if o.get("columnas") == "fila_completa" else o["columnas"]
            grupos = {}
            for i, f in enumerate(filas):
                grupos.setdefault(tuple(f.get(c, "").strip().upper() for c in claves), []).append(i)
            des = o.get("desempate")
            if des and des.get("columna") not in cols:
                raise SystemExit(f"El desempate de repetidos usa la columna {des.get('columna')}, que no existe (R1)")
            distintas = empates = 0
            for idx in grupos.values():
                if len(idx) < 2:
                    continue
                if len({tuple(filas[i].get(c, "") for c in cols) for i in idx}) > 1:
                    distintas += 1
                ganador = idx[0]   # sin desempate: la primera del archivo (el orden del archivo no es un criterio)
                if des:
                    vals = [filas[i].get(des["columna"], "").strip() for i in idx]
                    try:
                        claves_orden = [(float(v), i) if v else (float("-inf"), i) for v, i in zip(vals, idx)]
                    except ValueError:
                        claves_orden = [(v, i) for v, i in zip(vals, idx)]   # texto: fechas en aaaa-mm-dd (operación fecha antes)
                    orden = sorted(claves_orden)
                    ganador = (orden[-1] if des.get("conservar", "ultimo") == "ultimo" else orden[0])[1]
                    tope = orden[-1][0] if des.get("conservar", "ultimo") == "ultimo" else orden[0][0]
                    empatadas = [i for k, i in orden if k == tope]
                    if len({tuple(filas[i].get(c, "") for c in cols) for i in empatadas}) > 1:   # filas idénticas no son empate
                        empates += 1
                for i in idx:
                    if i != ganador:
                        marca(i, o.get("marca", "repetido"))
            if distintas and not des:
                aviso_rep = (f"{distintas} llaves repetidas con valores distintos: se conservó la primera del archivo sin criterio; "
                             "declara desempate (columna y conservar: ultimo o primero)")
            elif empates:
                aviso_rep = f"{empates} llaves repetidas empatan en {des['columna']}: el orden del archivo decidió entre las empatadas"
            else:
                aviso_rep = None
        elif op == "comparar":
            fn = OPS[o["operador"]]
            for i, f in enumerate(filas):
                a, b = f.get(o["izquierda"], "").strip(), f.get(o["derecha"], "").strip()
                if a and b:
                    try:
                        a2, b2 = (float(a), float(b)) if tipos.get(o["izquierda"]) == "numero" else (a, b)
                    except ValueError:
                        continue
                    if fn(a2, b2):
                        marca(i, o["marca"])
        else:
            raise SystemExit(f"Operación desconocida: {op}")
        reporte.append({"op": op, "columna": col or o.get("columnas") or f"{o.get('izquierda')} {o.get('operador')} {o.get('derecha')}",
                        "filas_cambiadas": cambiadas, "filas_marcadas": marcadas, "ejemplos": ej, "marca": o.get("marca")})
        if op == "repetidos" and aviso_rep:
            reporte[-1]["aviso"] = aviso_rep

    # defensa por defecto: una celda de texto que empieza con = + - @ se ejecutaría como fórmula al abrirla en Excel
    neutralizadas = 0
    for i, f in enumerate(filas):
        for c in cols:
            v = f.get(c) or ""
            if v[:1] in ("=", "+", "-", "@", "\t", "\r"):
                try:
                    float(v)
                    continue
                except ValueError:
                    f[c] = "'" + v
                    marcas[i].add("formula_neutralizada")
                    neutralizadas += 1
    if neutralizadas:
        reporte.append({"op": "neutralizar_formulas (por defecto)", "columna": "todas", "filas_cambiadas": neutralizadas,
                        "filas_marcadas": neutralizadas, "ejemplos": ["celda que empieza con = + - @ → se antepone «'»"], "marca": "formula_neutralizada"})
    todas = sorted({m for ms in marcas for m in ms})
    salida_cols = cols + [f"calidad_{m}" for m in todas] + ["calidad_ok"]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=salida_cols, lineterminator="\n", extrasaction="ignore")
    w.writeheader()
    for f, ms in zip(filas, marcas):
        fila = dict(f)
        for m in todas:
            fila[f"calidad_{m}"] = int(m in ms)
        fila["calidad_ok"] = int(not ms)
        w.writerow(fila)
    contenido = buf.getvalue().encode("utf-8")    # se escribe solo si la limpieza queda aprobada (limpiar)
    despues = metricas(filas, cols, tipos)

    pruebas = [
        {"prueba": "limpiar es marcar: mismas filas antes y después", "ok": len(filas) == len(crudas),
         "detalle": f"{len(crudas)} → {len(filas)}"},
        {"prueba": "el dato crudo no se tocó", "ok": hashlib.sha256(ent.read_bytes()).hexdigest() == huella_cruda,
         "detalle": f"sha256 {huella_cruda[:16]}…"},
    ]
    llave = plan.get("llave")
    if llave:
        partes = [llave] if isinstance(llave, str) else list(llave)
        orden_ok = ([tuple(f.get(k) for k in partes) for f in filas] == [tuple(f.get(k) for k in partes) for f in crudas])
        pruebas.append({"prueba": "la llave y el orden de las filas se conservan", "ok": orden_ok,
                        "detalle": "cada fila limpia corresponde a su fila cruda"})
    usa_caso = caso and "umbrales_caso" in plan
    u = plan.get("umbrales_caso" if usa_caso else "umbrales") or {}
    n = len(filas)
    # con los conteos enteros, no con la proporción redondeada de calidad_despues, que es solo para mostrar (L110)
    for c, mn in u.get("completitud_minima", {}).items():
        llenos = sum(1 for f in filas if f.get(c, "").strip())
        ok, holgura = cumple(llenos, n, mn)
        pruebas.append({"prueba": f"completitud de {c} ≥ {mn}", "ok": ok,
                        "detalle": f"{proporcion(llenos, n):.4%}" + (f" · holgura {miles(holgura)} filas" if ok else "")})
    for c, mn in u.get("validez_minima", {}).items():
        t = tipos.get(c)
        if t not in ("fecha", "numero"):
            pruebas.append({"prueba": f"validez de {c} ≥ {mn}", "ok": False, "detalle": "sin tipo declarado"})
            continue
        es_valido = fecha_valida if t == "fecha" else numero_valido
        llenos = [f.get(c, "") for f in filas if f.get(c, "").strip()]
        validos = sum(1 for v in llenos if es_valido(v))
        ok, holgura = cumple(validos, len(llenos), mn)
        pruebas.append({"prueba": f"validez de {c} ≥ {mn}", "ok": ok,
                        "detalle": f"{proporcion(validos, len(llenos)):.4%}" + (f" · holgura {miles(holgura)} valores" if ok else "")})
    for c in u.get("unicidad", []):
        vals = [f[c] for f in filas if f.get(c, "").strip()]
        pruebas.append({"prueba": f"{c} única", "ok": len(vals) == len(set(vals)), "detalle": f"{len(vals) - len(set(vals))} repetidas"})
    for m, mx in u.get("marcadas_maximo", {}).items():
        k = sum(1 for ms in marcas if m in ms)
        pruebas.append({"prueba": f"filas marcadas «{m}» ≤ {mx}", "ok": k <= mx, "detalle": f"{k}"})
    for c, mx in u.get("vacios_maximo", {}).items():
        k = sum(1 for f in filas if not f.get(c, "").strip())
        pruebas.append({"prueba": f"celdas vacías en {c} ≤ {mx}", "ok": k <= mx, "detalle": f"{miles(k)} de {miles(n)} filas"})
    conteo_marcas = {m: sum(1 for ms in marcas if m in ms) for m in todas}
    informe = {"tabla": plan.get("tabla"), "entrada": str(ent), "salida": str(sal), "filas": len(filas),
               "filas_ok": sum(1 for ms in marcas if not ms), "marcas": conteo_marcas, "operaciones": reporte,
               "calidad_antes": antes, "calidad_despues": despues, "calidad_cambio": cambio(antes, despues),
               "umbrales_aplicados": "caso_conocido" if usa_caso else "dato_real", "pruebas": pruebas,
               "sha256_limpio": hashlib.sha256(contenido).hexdigest(),
               "estado": "aprobada" if all(p["ok"] for p in pruebas) else "rechazada"}
    return informe, contenido


def mostrar(base, informe):
    """Línea de comandos: escribe limpieza_<tabla>.json junto al plan y dice lo que hizo cada operación y cada prueba."""
    reporte, pruebas, antes, despues = informe["operaciones"], informe["pruebas"], informe["calidad_antes"], informe["calidad_despues"]
    filas, sal, conteo_marcas = informe["filas"], informe["salida"], informe["marcas"]
    (base / f"limpieza_{informe.get('tabla') or 'tabla'}.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    if informe["estado"] == "aprobada":
        print(f"Limpieza aprobada: {filas} filas → {sal} · sin marcas {informe['filas_ok']}")
    else:
        print(f"Limpieza rechazada: {filas} filas · la capa limpia no se escribe"
              + (f" y se retira la de una limpieza anterior ({Path(sal).name})" if informe.get("capa_limpia_retirada") else ""))
    for r in reporte:
        print(f"  · {r['op']} {r['columna']}: cambiadas {r['filas_cambiadas']} · marcadas {r['filas_marcadas']}"
              + (f" · {'; '.join(r['ejemplos'][:2])}" if r["ejemplos"] else ""))
        if r.get("aviso"):
            print(f"    ! {r['aviso']}")
    for c, x in informe["calidad_cambio"].items():
        print(f"  · calidad de {c}: " + " · ".join(f"{k} {antes[c][k]:.2%} → {despues[c][k]:.2%}" for k in x))
    for p in pruebas:
        print(f"  {'✓' if p['ok'] else '✗'} {p['prueba']}: {p['detalle']}")
    print("RESUMEN " + json.dumps({"estado": informe["estado"], "filas": filas, "marcas": conteo_marcas,
                                   "fallas": [p["prueba"] for p in pruebas if not p["ok"]]}, ensure_ascii=False))
    return 0 if informe["estado"] == "aprobada" else 1


# ---------------- autoprueba (sin datos reales) ----------------
def autoprueba(mod=None):
    """Casos ficticios. Con mod se prueba otro módulo de limpieza (p. ej. la versión anterior) con los mismos casos."""
    mod = mod or sys.modules[__name__]
    tmp = Path(tempfile.mkdtemp(prefix="limpieza-autoprueba-"))
    resultados = []

    def caso_(nombre, crudo, plan, condicion, **kw):
        d = tmp / f"caso{len(resultados):02d}"
        d.mkdir()
        (d / "crudo.csv").write_bytes(crudo if isinstance(crudo, bytes) else crudo.encode("utf-8"))
        (d / "plan.json").write_text(json.dumps({"tabla": "t", "entrada": "crudo.csv", "salida": "limpio.csv", **plan},
                                                ensure_ascii=False), encoding="utf-8")
        if kw.get("entrada"):
            kw["entrada"] = str(d / "crudo.csv")
        try:
            r, e = mod.limpiar(d / "plan.json", informe=False, **kw), None
        except BaseException as x:  # noqa: BLE001 (FAILFAST o la versión anterior que revienta)
            r, e = None, x
        try:
            ok = bool(condicion(r, e))
        except Exception as x:  # noqa: BLE001
            ok, e = False, x
        det = f"{type(e).__name__}: {str(e)[:110]}" if e else f"{r.get('estado')} · {[p['prueba'] for p in r['pruebas'] if not p['ok']]}"
        resultados.append((nombre, ok, det))

    def detiene(r, e):
        return isinstance(e, ValueError) and "FAILFAST" in str(e) and re.search(r"l[ií]nea \d+|vacío|encabezado", str(e))

    def rechaza(nombre):
        return lambda r, e: e is None and r["estado"] == "rechazada" and any(nombre in p["prueba"] for p in r["pruebas"] if not p["ok"])

    def aprueba(r, e):
        return e is None and r["estado"] == "aprobada"

    # 1. lectura FAILFAST: cada CSV de baterias/failfast detiene la limpieza o la rechaza; nunca se aprueba en silencio
    planes = {"monto_con_punto_de_miles.csv": [{"op": "numero", "columna": "subtotal"}],
              "formula_de_excel_como_texto.csv": [{"op": "numero", "columna": "dia"}]}
    umbral_formula = {"marcadas_maximo": {"numero_invalido_dia": 0}}
    for ruta in sorted((Path(__file__).resolve().parent.parent / "baterias" / "failfast").glob("*.csv")):
        ops = planes.get(ruta.name, [])
        caso_(f"failfast {ruta.name}", ruta.read_bytes(),
              {"operaciones": ops, "umbrales": umbral_formula if "formula" in ruta.name else {}},
              lambda r, e: detiene(r, e) or (e is None and r["estado"] == "rechazada"))
    rotos = {"comilla sin cerrar: ValueError con la línea, no csv.Error": 'id,v\n1,"a\n2,b\n',
             "no está en UTF-8": "id,ciudad\n1,Medellín\n".encode("cp1252"),
             "encabezado con columnas repetidas": "id,v,v\n1,a,b\n",
             "archivo vacío": ""}
    for nombre, crudo in rotos.items():
        caso_(f"failfast {nombre}", crudo, {"operaciones": []}, detiene)
    # 2. calidad antes y después con el mismo tipo
    crudo = "id,fecha,valor\n1,2025-01-05T10:00:00.000,10\n2,05/02/2025,1.5\n3,2025-02-30,x\n4,,20\n"
    plan = {"operaciones": [{"op": "fecha", "columna": "fecha", "formatos": ["%Y-%m-%dT%H:%M:%S.%f", "%d/%m/%Y"]},
                            {"op": "numero", "columna": "valor"}]}
    caso_("calidad_antes trae validez y el cambio que hizo la limpieza", crudo, plan,
          lambda r, e: e is None and "validez" in r["calidad_antes"]["fecha"] and "validez" in r["calidad_antes"]["valor"]
          and r["calidad_cambio"]["fecha"]["validez"] > 0)
    caso_("una fecha que no existe (2025-02-30) no cuenta como válida", crudo, plan,
          lambda r, e: e is None and r["calidad_despues"]["fecha"]["validez"] == round(2 / 3, 6))
    # 3. umbrales sobre el dato real: 2.000 filas ficticias con 80 NIT vacíos (4 %) frente a un caso de 21 con 1 vacío
    grande = "id,nit\n" + "".join(f"C{i:05d},{'' if i % 25 == 0 else 900000000 + i % 7}\n" for i in range(2000))
    chico = "id,nit\n" + "".join(f"K{i:02d},{'' if i == 5 else 900000001}\n" for i in range(21))
    relativo = {"operaciones": [], "umbrales": {"completitud_minima": {"nit": 0.95}}}
    absoluto = {"operaciones": [], "umbrales": {"completitud_minima": {"nit": 0.95}, "vacios_maximo": {"nit": 2}}}
    caso_("el umbral relativo de 0,95 deja pasar 80 NIT vacíos en 2.000 filas (la holgura lo muestra)", grande, relativo,
          lambda r, e: aprueba(r, e) and "holgura 20 filas" in r["pruebas"][-1]["detalle"])
    caso_("vacios_maximo (conteo absoluto) rechaza los 80 vacíos del dato grande", grande, absoluto, rechaza("celdas vacías en nit"))
    # con los conteos enteros (L110): 2 de 3 es 0,666…, que redondeado a 6 decimales (0,666667) pasaba 0,6666667
    tres = "id,nit,fecha\n1,9,2025-01-01\n2,9,2025-01-02\n3,,2025-02-30\n"
    caso_("completitud: 2 de 3 llenas no cumple 0,6666667, aunque redondeada a 6 decimales parezca que sí (L110)", tres,
          {"operaciones": [], "umbrales": {"completitud_minima": {"nit": 0.6666667}}}, rechaza("completitud de nit"))
    caso_("… y cumple 0,666666, con holgura 0 filas (control)", tres,
          {"operaciones": [], "umbrales": {"completitud_minima": {"nit": 0.666666}}},
          lambda r, e: aprueba(r, e) and r["pruebas"][-1]["detalle"].endswith("holgura 0 filas"))
    caso_("validez: 2 de 3 fechas válidas no cumple 0,6666667 (L110)", tres,
          {"operaciones": [{"op": "fecha", "columna": "fecha"}], "umbrales": {"validez_minima": {"fecha": 0.6666667}}},
          rechaza("validez de fecha"))
    try:
        ok_grande, e_grande = (mod.cumple(2969999, 3000000, 0.99) == (False, None)
                               and mod.cumple(2970000, 3000000, 0.99) == (True, 0)
                               and mod.cumple(2970100, 3000000, 0.99) == (True, 100)), None
    except Exception as x:  # noqa: BLE001 (la versión anterior no tiene cumple)
        ok_grande, e_grande = False, x
    resultados.append(("con 3.000.000 de filas, 2.969.999 llenas no cumplen 0,99 y 2.970.100 dejan una holgura de 100 (L110)",
                       ok_grande, f"{type(e_grande).__name__}: {e_grande}" if e_grande else "cumple() no da lo esperado"))
    caso_("… y el mismo plan aprueba el caso chico con 1 vacío", chico, absoluto, aprueba)
    separados = {"operaciones": [], "llave": "id",
                 "umbrales": {"completitud_minima": {"nit": 0.999}, "unicidad": ["id"]},
                 "umbrales_caso": {"completitud_minima": {"nit": 0.95}}}
    caso_("umbrales del dato real: el caso chico no pasa con ellos", chico, separados, rechaza("completitud de nit"), entrada=True)
    caso_("umbrales_caso: el caso chico pasa con los suyos (caso=True)", chico, separados,
          lambda r, e: aprueba(r, e) and r["umbrales_aplicados"] == "caso_conocido", entrada=True, caso=True)
    caso_("caso=True sin la entrada del caso se detiene (nunca sobre el dato del plan)", chico, separados,
          lambda r, e: isinstance(e, ValueError), caso=True)
    laxo = {"operaciones": [], "umbrales": {"completitud_minima": {"nit": 0.9}},
            "umbrales_caso": {"completitud_minima": {"nit": 0.95}, "unicidad": ["id"]}}
    caso_("el caso no puede exigir más que el dato real", chico, laxo,
          lambda r, e: isinstance(e, ValueError) and "exige más" in str(e))
    for nombre, u in (("nombre desconocido (completitud_minimo)", {"completitud_minimo": {"nit": 1.0}}),
                      ("columna que no existe", {"vacios_maximo": {"nti": 0}}),
                      ("marca que ninguna operación pone", {"marcadas_maximo": {"repetidos": 0}}),
                      ("unicidad de una columna que no existe", {"unicidad": ["ide"]})):
        caso_(f"umbral que no se puede evaluar: {nombre}", chico, {"operaciones": [{"op": "repetidos", "columnas": ["id"]}],
                                                                  "umbrales": u},
              lambda r, e: isinstance(e, ValueError) and "umbrales" in str(e))
    # un umbral que no es de su tipo se detiene antes de leer las filas, con FAILFAST (antes: TypeError al final, L109)
    for nombre, u in (("«\"0\"» en vacios_maximo", {"vacios_maximo": {"nit": "0"}}),
                      ("1.5 en completitud_minima", {"completitud_minima": {"nit": 1.5}}),
                      ("true en completitud_minima", {"completitud_minima": {"nit": True}}),
                      ("-1 en marcadas_maximo", {"marcadas_maximo": {"repetido": -1}}),
                      ("2.5 en vacios_maximo", {"vacios_maximo": {"nit": 2.5}}),
                      ("validez_minima como lista", {"validez_minima": ["nit"]}),
                      ("unicidad como texto", {"unicidad": "id"})):
        caso_(f"umbral de otro tipo: {nombre} detiene la limpieza (L109)", chico,
              {"operaciones": [{"op": "repetidos", "columnas": ["id"]}], "umbrales": u},
              lambda r, e: isinstance(e, ValueError) and str(e).startswith("FAILFAST") and "debe ser" in str(e))
    caso_("umbral de otro tipo en umbrales_caso también detiene la limpieza", chico,
          {"operaciones": [], "umbrales": {"vacios_maximo": {"nit": 2}}, "umbrales_caso": {"vacios_maximo": {"nit": "2"}}},
          lambda r, e: isinstance(e, ValueError) and "umbrales_caso.vacios_maximo.nit debe ser" in str(e), entrada=True, caso=True)
    # 4. la clase INVISIBLES va con escapes: quita los invisibles y nunca un espacio (al reescribir el archivo, U+2028 y
    #    U+2029 literales se volvieron espacios y la op texto pegaba los nombres)
    def limpio(r):
        with open(r["salida"], newline="", encoding="utf-8") as fh:
            return next(csv.DictReader(fh))["nombre"]

    caso_("la op texto quita U+200B, U+2028 y U+202E y conserva los espacios",
          "id,nombre\n1,\"Alcaldía\u200b de\u2028 Medellín\u202e\"\n", {"operaciones": [{"op": "texto", "columna": "nombre"}]},
          lambda r, e: e is None and limpio(r) == "Alcaldía de Medellín")
    # 5. llave compuesta y montos con punto de miles en la op numero
    caso_("llave compuesta del plan: la prueba de orden compara la combinación",
          "estacion,fecha,mm\nE1,2025-01-01,3\nE1,2025-01-02,4\n", {"llave": ["estacion", "fecha"], "operaciones": []},
          lambda r, e: aprueba(r, e) and any(p["prueba"].startswith("la llave") and p["ok"] for p in r["pruebas"]))
    caso_("op numero con decimal «.»: 78.000 junto a 1628100 se detiene", "id,valor\n1,78.000\n2,1628100\n",
          {"operaciones": [{"op": "numero", "columna": "valor"}]}, detiene)
    caso_("op numero con decimal «,»: 1.250,50 se convierte sin detenerse", "id,valor\n1,\"1.250,50\"\n2,1628100\n",
          {"operaciones": [{"op": "numero", "columna": "valor", "decimal": ","}]}, aprueba)
    def valores(r, col="valor"):
        with open(r["salida"], newline="", encoding="utf-8") as fh:
            return [f[col] for f in csv.DictReader(fh)]

    coma = "id,valor\n1,\"1.234,5\"\n2,12.5\n3,\"1,234.5\"\n4,1.5\n5,\"0,75\"\n6,12.500.000\n7,\"-3,25\"\n"
    caso_("op numero con decimal «,»: 12.5, 1,234.5 y 1.5 se marcan, no se leen como 125, 1.2345 y 15 (L108)", coma,
          {"operaciones": [{"op": "numero", "columna": "valor", "decimal": ","}],
           "umbrales": {"marcadas_maximo": {"numero_invalido_valor": 0}}},
          lambda r, e: rechaza("numero_invalido_valor")(r, e) and r["marcas"] == {"numero_invalido_valor": 3})
    caso_("op numero con decimal «,»: 1.234,5, 0,75, 12.500.000 y -3,25 se convierten; lo marcado no cambia", coma,
          {"operaciones": [{"op": "numero", "columna": "valor", "decimal": ","}]},
          lambda r, e: aprueba(r, e) and valores(r) == ["1234.5", "12.5", "1,234.5", "1.5", "0.75", "12500000", "-3.25"])
    caso_("op numero con decimal «.»: 1_000, «٣», Infinity y NaN se marcan aunque float() los acepte (L108)",
          "id,valor\n1,1_000\n2,\u0663\n3,Infinity\n4,NaN\n5,10\n6,-2.5e3\n7,.5\n",
          {"operaciones": [{"op": "numero", "columna": "valor"}]},
          lambda r, e: aprueba(r, e) and r["marcas"] == {"numero_invalido_valor": 4}
          and r["calidad_despues"]["valor"]["validez"] == round(3 / 7, 6))
    caso_("op numero con un decimal que no es «.» ni «,» se detiene", "id,valor\n1,10\n",
          {"operaciones": [{"op": "numero", "columna": "valor", "decimal": "coma"}]},
          lambda r, e: isinstance(e, ValueError) and "FAILFAST" in str(e) and "decimal" in str(e))
    caso_("op numero con decimal «.»: con 12.5 en la columna, 1.250 es un decimal y no se detiene (L49)",
          "id,peso_kg\n1,12.5\n2,1.250\n3,1500\n", {"operaciones": [{"op": "numero", "columna": "peso_kg"}]}, aprueba)
    caso_("op texto: los ejemplos de una columna sensible salen enmascarados",
          "id,pertenencia_etnica\n1,  Indigena  Zenu\n", {"operaciones": [{"op": "texto", "columna": "pertenencia_etnica"}]},
          lambda r, e: aprueba(r, e) and r["operaciones"][0]["ejemplos"] and "Zenu" not in str(r["operaciones"][0]["ejemplos"]))
    caso_("op numero: el mensaje enmascara el valor de una columna personal",
          "id,numero_documento\n1,1.035.233.887\n2,43\n", {"operaciones": [{"op": "numero", "columna": "numero_documento"}]},
          lambda r, e: detiene(r, e) and "1.035.233.887" not in str(e) and "035" not in str(e))
    # 6. desempate de repetidos (L50): conserva la más reciente y avisa si falta el criterio
    rep = "id,region,fecha\nC1,Norte,2025-01-01\nC1,Sur,2025-03-01\nC2,Este,2025-02-01\n"
    caso_("repetidos con desempate: conserva la más reciente", rep,
          {"operaciones": [{"op": "repetidos", "columnas": ["id"], "desempate": {"columna": "fecha", "conservar": "ultimo"}}]},
          lambda r, e: aprueba(r, e) and r["marcas"].get("repetido") == 1 and not r["operaciones"][0].get("aviso"))
    caso_("repetidos sin desempate con valores distintos: avisa", rep, {"operaciones": [{"op": "repetidos", "columnas": ["id"]}]},
          lambda r, e: aprueba(r, e) and "sin criterio" in (r["operaciones"][0].get("aviso") or ""))

    # 7. rechazo que detiene (L109): la línea de comandos, con una limpieza aprobada antes en la misma carpeta
    def cli_(nombre, pasos, condicion):
        """Corre mod.limpiar como la línea de comandos (informe=True) con cada (crudo, plan) en orden, en la misma carpeta y
        sin mostrar su salida; condicion(carpeta, códigos de salida)."""
        d = tmp / f"cli{len(resultados):02d}"
        d.mkdir()
        codigos, e = [], None
        try:
            for crudo, plan in pasos:
                (d / "crudo.csv").write_text(crudo, encoding="utf-8")
                (d / "plan.json").write_text(json.dumps({"tabla": "t", "entrada": "crudo.csv", "salida": "limpio/t.csv", **plan},
                                                        ensure_ascii=False), encoding="utf-8")
                with contextlib.redirect_stdout(io.StringIO()):
                    codigos.append(mod.limpiar(d / "plan.json"))
            ok = bool(condicion(d, codigos))
        except BaseException as x:  # noqa: BLE001 (la versión anterior sale con un traceback)
            ok, e = False, x
        resultados.append((nombre, ok, f"{type(e).__name__}: {str(e)[:110]}" if e else f"códigos {codigos}"))

    def quedo(d):
        """(estado y motivo de limpieza_t.json, ¿hay capa limpia?, ¿su huella es la del informe?)"""
        inf = json.loads((d / "limpieza_t.json").read_text(encoding="utf-8"))
        capa = d / "limpio" / "t.csv"
        huella = hashlib.sha256(capa.read_bytes()).hexdigest() if capa.exists() else None
        return inf.get("estado"), inf.get("motivo") or "", capa.exists(), huella is not None and huella == inf.get("sha256_limpio")

    bien = ("id,valor\n1,10\n2,20\n", {"operaciones": [], "umbrales": {"vacios_maximo": {"valor": 0}}})
    vacios = "id,valor\n1,10\n2,\n3,\n"
    cli_("línea de comandos: una limpieza aprobada escribe la capa limpia con la huella de su informe (control)", [bien],
         lambda d, c: c == [0] and quedo(d)[0] == "aprobada" and quedo(d)[2:] == (True, True))
    cli_("rechazada por un umbral: no escribe la capa limpia y retira la de la limpieza anterior (L109)",
         [bien, (vacios, bien[1])],
         lambda d, c: c == [0, 1] and quedo(d)[0] == "rechazada" and not quedo(d)[2])
    cli_("un umbral «\"0\"» tras una aprobada: limpieza_t.json en «rechazada» con FAILFAST, sin traceback y sin capa limpia",
         [bien, (vacios, {"operaciones": [], "umbrales": {"vacios_maximo": {"valor": "0"}}})],
         lambda d, c: c == [0, 1] and quedo(d)[0] == "rechazada" and "FAILFAST" in quedo(d)[1] and not quedo(d)[2])
    cli_("un error que no se previó (una regex mal escrita) también rechaza, con su tipo y su lugar, y retira la capa",
         [bien, (bien[0], {"operaciones": [{"op": "reemplazar", "columna": "valor", "patron": "("}]})],
         lambda d, c: c == [0, 1] and quedo(d)[0] == "rechazada" and "se detuvo" in quedo(d)[1] and not quedo(d)[2])
    cli_("la salida no puede ser la entrada: se detiene y el crudo queda intacto",
         [(bien[0], {"operaciones": [], "salida": "crudo.csv"})],
         lambda d, c: c == [1] and quedo(d)[0] == "rechazada" and (d / "crudo.csv").read_text(encoding="utf-8") == bien[0])
    cli_("una tabla con «../» se detiene y no escribe fuera de la carpeta del plan",
         [(bien[0], {"operaciones": [], "tabla": "../fuera"})],
         lambda d, c: c == [1] and not (d.parent / "fuera.json").exists() and not list(d.parent.glob("limpieza_*.json")))
    shutil.rmtree(tmp, ignore_errors=True)
    for nombre, ok, det in resultados:
        print(f"{'✓' if ok else '✗'} {nombre}" + ("" if ok else f" · {det}"))
    malos = [n for n, ok, _ in resultados if not ok]
    print("RESUMEN " + json.dumps({"casos": len(resultados), "fallas": len(malos)}, ensure_ascii=False))
    return 1 if malos else 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        raise SystemExit(__doc__)
    if args[0] == "--autoprueba":
        sys.exit(autoprueba())
    g = lambda k: args[args.index(k) + 1] if k in args else None
    sys.exit(limpiar(args[0], entrada=g("--entrada"), salida=g("--salida")))
