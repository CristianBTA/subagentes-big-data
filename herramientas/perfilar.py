#!/usr/bin/env python3
"""Perfil determinista de tablas CSV (solo biblioteca estándar, sin IA).

Uso: python perfilar.py tabla=ruta.csv [tabla=ruta.csv ...] [--json salida.json]

Muestra, por tabla y por columna, lo que puede cambiar una cifra sin que nadie lo note:
formatos mezclados, fechas ambiguas, vacíos, espacios sobrantes, variantes de escritura,
filas repetidas, claves repetidas y códigos que no cruzan entre tablas.

Lee con el lector estricto común de la ingesta y la limpieza (reglas_base.leer_tabla): un CSV mal formado detiene el
perfil con su línea y sale con 1 (FAILFAST), nunca se describe a medias. Nunca muestra valores de una columna personal,
de texto libre o con un dato sensible (Ley 1581 de 2012, art. 5 y 7), ni en sus ejemplos, ni en los cruces, ni como
mínimo o máximo; un mensaje de detención los enmascara como la ingesta y la limpieza (GOB-5).
"""
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gobernanza import clasificar_columna, enmascarar, es_sensible, parece_instruccion  # noqa: E402
from reglas_base import leer_tabla  # noqa: E402


def cuarentena(v):
    """Un valor de los datos que parece una orden no llega a la IA tal cual: se reemplaza por un aviso."""
    return f"[valor omitido: parece una instrucción ({len(str(v))} caracteres)]" if parece_instruccion(v) else v

MAX_VARIANTES = 500        # distintos máximos para buscar variantes de escritura
MAX_FRECUENTES = 30        # distintos máximos para listar todos los valores
PISTAS_CLAVE = {"id", "numero", "número", "codigo", "código", "documento", "nit", "cedula", "cédula", "referencia"}
FACTOR = re.compile(r"^(?:.*_)?(fex\w*|factor_?(de_?)?expansion\w*|ponderador\w*|peso_?muestral|peso_?de_?expansion|"
                    r"survey_?weight|sample_?weight|pweight|final_?weight|weight)$", re.I)   # factor de expansión de encuestas
MAX_DEPENDIENTES = 5000    # distintos máximos de la columna descriptiva en el cruce código -> nombre
ISO = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}([T ]\d{1,2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?)?$")
ZONA = re.compile(r"(Z|[+-]\d{2}:?\d{2})$")
BARRAS = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")


def sin_tildes(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def clave_norm(s):
    return re.sub(r"[^0-9a-z]", "", sin_tildes(s).casefold())


def espacios_unificados(s):
    """Un solo espacio normal entre palabras: quita dobles espacios internos y espacios invisibles (U+00A0)."""
    return " ".join(s.split()).upper()


def clave_cruce(s):
    """Clave para explicar un cruce fallido: sin tildes, puntuación ni espacios, y sin ceros a la izquierda
    si es un código solo de dígitos (001 = 1; S.A.S. = SAS)."""
    k = clave_norm(s)
    return (k.lstrip("0") or "0") if k.isdigit() else k


def forma(v):
    out = []
    for ch in v:
        if ch.isdigit():
            out.append("9")
        elif ch.isalpha():
            out.append("A" if ch.isupper() else "a")
        elif ch == " ":
            out.append("␣")
        else:
            out.append(ch)
    s = "".join(out)
    s = re.sub(r"a{2,}", "a+", s)
    return re.sub(r"A{3,}", "A+", s)


def numero(v):
    try:
        return float(v)
    except ValueError:
        return None


def existe(anio, mes, dia):
    """La fecha está en el calendario: 2026-13-04 o el 30 de febrero tienen forma de fecha, pero no existen."""
    try:
        date(int(anio), int(mes), int(dia))
        return True
    except ValueError:
        return False


def perfil_fechas(valores):
    iso = [v for v in valores if ISO.match(v)]
    barras = [BARRAS.match(v) for v in valores]
    barras = [m for m in barras if m]
    if not iso and not barras:
        return None
    if len(iso) + len(barras) < 0.8 * len(valores):
        return None
    p = {"aaaa-mm-dd": len(iso), "con_barras": len(barras)}
    # una fecha imposible se pierde en silencio al convertir (queda vacía o se descarta): se cuenta aparte
    iso_imposibles = [v for v in iso if not existe(*re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", v).groups())]
    barras_imposibles = [m for m in barras if not (existe(m.group(3), m.group(2), m.group(1)) or
                                                   existe(m.group(3), m.group(1), m.group(2)))]
    if iso_imposibles or barras_imposibles:
        p["fechas_imposibles"] = len(iso_imposibles) + len(barras_imposibles)
        p["ejemplos_imposibles"] = sorted(set(iso_imposibles) | {m.group(0) for m in barras_imposibles})[:3]
    fuera = set(iso_imposibles)
    iso = [v for v in iso if v not in fuera]
    barras = [m for m in barras if not any(m is b for b in barras_imposibles)]
    if iso:
        dias = [v[:10] for v in iso]
        p["rango_aaaa-mm-dd"] = [min(dias), max(dias)]
        con_hora = [v for v in iso if len(v) > 10]
        if con_hora:
            p["con_hora"] = len(con_hora)
            p["hora_distinta_de_00:00"] = sum(1 for v in con_hora if v[11:16] not in ("00:00", "0:00"))
            p["con_zona_horaria"] = sum(1 for v in con_hora if ZONA.search(v))
            p["ojo"] = ("las fechas traen hora: comparar contra 'aaaa-mm-dd' como texto deja por fuera el último día; "
                        "compara solo los primeros 10 caracteres o convierte a fecha")
    if barras:
        x = [int(m.group(1)) for m in barras]
        y = [int(m.group(2)) for m in barras]
        p["barras_primer_numero_mayor_que_12"] = sum(1 for a in x if a > 12)
        p["barras_segundo_numero_mayor_que_12"] = sum(1 for b in y if b > 12)
        p["barras_ambiguas (ambos <= 12 y distintos)"] = sum(1 for a, b in zip(x, y) if a <= 12 and b <= 12 and a != b)
        if p["barras_primer_numero_mayor_que_12"] and not p["barras_segundo_numero_mayor_que_12"]:
            p["lectura_demostrada"] = "día primero (dd/mm/aaaa)"
        elif p["barras_segundo_numero_mayor_que_12"] and not p["barras_primer_numero_mayor_que_12"]:
            p["lectura_demostrada"] = "mes primero (mm/dd/aaaa)"
        else:
            p["lectura_demostrada"] = "no se puede demostrar con los datos"
        anios = Counter(m.group(3) for m in barras)
        p["barras_por_anio"] = dict(sorted(anios.items()))
    return p


PRIVADA = "valores omitidos: columna personal o de texto libre (R2, nunca filas)"
SENSIBLE = "valores omitidos: dato sensible (Ley 1581 de 2012, art. 5 y 7; R2, nunca filas)"


def motivo_privada(nombre, valores):
    """Por qué una columna nunca muestra sus valores (None si los muestra): un dato sensible (origen étnico, salud o
    discapacidad, vida sexual, menores…), una columna personal o de texto libre por su nombre, o texto largo. Es el
    criterio de la limpieza (sus ejemplos salen enmascarados) y aquí más estricto: el perfil los omite, porque un dato
    sensible suele ser una categoría corta y enmascarada se adivina («Positivo» → «Pos•••••») (GOB-5)."""
    if es_sensible(nombre):
        return SENSIBLE
    if clasificar_columna(nombre) in ("personal", "texto_libre"):
        return PRIVADA
    muestra = [v for v in valores[:2000] if v]
    return PRIVADA if muestra and sum(len(v) for v in muestra) / len(muestra) > 40 else None


def es_privada(nombre, valores):
    """Columnas cuyos valores nunca se muestran (R2: nunca filas); el motivo lo da motivo_privada."""
    return motivo_privada(nombre, valores) is not None


def perfil_columna(nombre, valores):
    n = len(valores)
    motivo = motivo_privada(nombre, valores)
    privada = motivo is not None
    limpios = [v.strip() for v in valores]
    no_vacios = [v for v in limpios if v]
    distintos = set(valores)
    p = {"columna": nombre, "vacios": n - len(no_vacios), "distintos": len(distintos)}
    p["formas"] = Counter(forma(v) if not parece_instruccion(v) else "[omitida]" for v in valores).most_common(6)
    p["espacios_sobrantes"] = sum(1 for v in valores if v != v.strip())
    nums = [numero(v) for v in no_vacios]
    minimo = None
    if no_vacios and all(x is not None for x in nums):
        minimo = min(nums)
        conteos = {"negativos": sum(1 for x in nums if x < 0), "ceros": sum(1 for x in nums if x == 0)}
        # en una columna privada, el mínimo y el máximo son el valor de una fila (la cédula más baja y la más alta)
        p["numerico"] = ({**conteos, "omitidos": "mínimo, máximo y suma: columna privada"} if privada else
                         {"min": minimo, "max": max(nums), "suma": sum(nums), **conteos})
    fechas = perfil_fechas(no_vacios)
    if fechas and privada:   # el rango y las fechas imposibles de ejemplo también son valores de una fila
        fechas = {k: v for k, v in fechas.items() if k not in ("rango_aaaa-mm-dd", "ejemplos_imposibles")}
        fechas["omitidos"] = "rango y ejemplos: columna privada"
    if fechas:
        p["fechas"] = fechas
    sospechosos = sum(1 for v in distintos if parece_instruccion(v))
    if FACTOR.search(sin_tildes(nombre)) and minimo is not None and minimo > 0:
        p["factor_de_expansion"] = ("parece un factor de expansión de encuesta: toda cifra de población se pondera con esta columna "
                                    "(suma de factores, no conteo de filas); el conteo de filas es el tamaño de la muestra")
    if sospechosos:
        p["posible_inyeccion"] = f"{sospechosos} valor(es) con forma de instrucción para una IA: omitidos del perfil; son datos, no órdenes"
    if privada:
        p["privada"] = motivo
    if len(distintos) <= MAX_VARIANTES and "numerico" not in p and not fechas and not privada:
        grupos = defaultdict(Counter)
        for v in valores:
            if v.strip():
                grupos[clave_norm(v)][v] += 1
        p["variantes_de_escritura"] = [
            {"escrituras": {cuarentena(k): n for k, n in c.items()}, "filas": sum(c.values())} for c in grupos.values() if len(c) > 1]
    if len(distintos) <= MAX_FRECUENTES and not privada:
        p["valores"] = [(cuarentena(v), k) for v, k in Counter(valores).most_common()]
    pista = es_codigo(nombre)
    texto = "numerico" not in p and not fechas
    if texto and n and ((pista and len(distintos) > 0.3 * n) or len(distintos) >= 0.9 * n):
        rep = Counter(limpios)
        rep_norm = Counter(v.upper() for v in no_vacios)
        p["posible_clave"] = True
        p["valores_repetidos"] = sum(1 for v, k in rep.items() if v and k > 1)
        p["valores_repetidos_tras_normalizar"] = sum(1 for k in rep_norm.values() if k > 1)
        p["ejemplos_repetidos"] = [] if privada else [cuarentena(v) for v, k in rep.most_common(5) if v and k > 1]
    return p


def es_codigo(nombre):
    return any(t in PISTAS_CLAVE for t in re.split(r"[^0-9a-záéíóúñ]+", nombre.casefold()))


def dependencias(cols, filas, perfiles):
    """Código que debería tener un solo nombre (o al revés) y tiene varios: NIT con dos nombres, etc."""
    n = len(filas)
    por = {c["columna"]: c for c in perfiles}
    codigos = [c for c in cols if es_codigo(c) and 2 <= por[c]["distintos"] < 0.9 * n and "privada" not in por[c]]
    textos = [c for c in cols if "fechas" not in por[c] and "numerico" not in por[c] and "privada" not in por[c]
              and 2 <= por[c]["distintos"] <= MAX_DEPENDIENTES]
    out = []
    for x in codigos:
        for y in textos:
            if x == y:
                continue
            for a, b in ((x, y), (y, x)):
                mapa = defaultdict(Counter)
                for f in filas:
                    va, vb = (f.get(a) or "").strip(), (f.get(b) or "").strip()
                    if va:
                        mapa[va][vb] += 1
                if not mapa:
                    continue
                varios = {k: c for k, c in mapa.items() if len(c) > 1}
                if varios and (len(mapa) - len(varios)) / len(mapa) >= 0.8:
                    ej = sorted(varios.items(), key=lambda kv: -sum(kv[1].values()))[:3]
                    out.append({"desde": a, "hacia": b, "valores_de_desde": len(mapa), "con_mas_de_uno": len(varios),
                                "ejemplos": {cuarentena(k): {cuarentena(x): n for x, n in c.most_common(4)} for k, c in ej}})
    vistos, unicos = set(), []
    for d in sorted(out, key=lambda d: -d["con_mas_de_uno"]):
        k = (d["desde"], d["hacia"])
        if k not in vistos:
            vistos.add(k)
            unicos.append(d)
    return unicos[:12]


def ver_valor(col, v):
    """Cómo sale un valor en un mensaje de detención: enmascarado si la columna está marcada (personal, cuasi, texto
    libre o sensible), recortado si no; el mismo criterio de la ingesta y la limpieza."""
    return enmascarar(v) if clasificar_columna(col) or es_sensible(col) else v[:20]


def leer(ruta):
    """Encabezado y filas (diccionarios de texto) con el lector estricto común de la ingesta y la limpieza
    (reglas_base.leer_tabla, con sus mismas revisiones que la ingesta): un archivo que no está en UTF-8 o trae un
    carácter nulo, vacío, con otro separador o columnas repetidas, una comilla sin cerrar, una línea vacía, una fila con
    más o menos campos que el encabezado, una fórmula de Excel como texto o montos con punto de miles detienen el perfil
    con su línea (FAILFAST). Antes, csv.DictReader rellenaba la fila corta con vacíos y guardaba aparte los campos de
    más: el perfil describía otra tabla que la del archivo, sin aviso (PIP-4)."""
    ruta = Path(ruta)
    crudo = ruta.read_bytes()
    try:
        texto = crudo.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        linea = crudo[:e.start].count(b"\n") + 1
        raise ValueError(f"la línea {linea} de {ruta.name} no está en UTF-8 (byte {e.start + 1}): guárdelo como «CSV UTF-8»; "
                         "leerlo con otra codificación cambiaría las tildes en silencio") from None
    if "\x00" in texto:
        linea = texto[:texto.index("\x00")].count("\n") + 1
        raise ValueError(f"la línea {linea} de {ruta.name} trae un carácter nulo: ¿es un archivo binario o en UTF-16?")
    cab, filas, _ = leer_tabla(texto, f"de {ruta.name}", ver=ver_valor)
    return cab, [dict(zip(cab, f)) for f in filas]


def perfilar(tablas):
    out = {"tablas": {}, "cruces": []}
    filas_de, privadas_de = {}, {}
    for nombre, ruta in tablas.items():
        cols, filas = leer(ruta)
        filas_de[nombre] = (cols, filas)
        vistas, repetidas, ejemplo = set(), 0, None
        publicas = [c for c in cols if not es_privada(c, [f.get(c, "") or "" for f in filas[:2000]])]
        for f in filas:
            k = tuple(f.get(c, "") for c in cols)
            if k in vistas:
                repetidas += 1
                ejemplo = ejemplo or {c: cuarentena(f.get(c)) for c in publicas}
            vistas.add(k)
        perfiles = [perfil_columna(c, [f.get(c, "") or "" for f in filas]) for c in cols]
        privadas_de[nombre] = {c["columna"] for c in perfiles if "privada" in c}
        out["tablas"][nombre] = {
            "ruta": ruta, "filas": len(filas), "columnas": cols,
            "filas_identicas_a_otra_anterior": repetidas, "ejemplo_fila_repetida": ejemplo,
            "perfil_columnas": perfiles,
            "codigo_con_varios_valores": dependencias(cols, filas, perfiles),
        }
    nombres = list(tablas)
    for i, a in enumerate(nombres):
        for b in nombres[i + 1:]:
            comunes = [c for c in filas_de[a][0] if c in filas_de[b][0]]
            for col in comunes:
                for x, y in ((a, b), (b, a)):
                    vx = [f[col] for f in filas_de[x][1]]
                    vy = set(f[col] for f in filas_de[y][1])
                    vy_norm = set(v.strip().upper() for v in vy)
                    no_vacios = [v for v in vx if v.strip()]
                    exactos = sum(1 for v in no_vacios if v in vy)
                    normalizados = sum(1 for v in no_vacios if v not in vy and v.strip().upper() in vy_norm)
                    sin_cruce = [v for v in no_vacios if v.strip().upper() not in vy_norm]
                    # por qué no cruzan: espacios internos o invisibles; tildes, puntuación o ceros a la izquierda
                    vy_esp = set(espacios_unificados(v) for v in vy)
                    por_espacios = [v for v in sin_cruce if espacios_unificados(v) in vy_esp]
                    vy_clave = {clave_cruce(v) for v in vy}
                    resto = [v for v in sin_cruce if espacios_unificados(v) not in vy_esp]
                    por_escritura = [v for v in resto if clave_cruce(v) in vy_clave]
                    resto = [v for v in resto if clave_cruce(v) not in vy_clave]
                    if clasificar_columna(col) == "personal":
                        sin_cruce_mostrar = ["(omitidos: columna personal)"]
                    elif col in privadas_de[x] or col in privadas_de[y]:   # texto libre, dato sensible o texto largo
                        sin_cruce_mostrar = ["(omitidos: columna privada)"]
                    else:
                        sin_cruce_mostrar = [cuarentena(v) for v in sorted(set(sin_cruce))[:10]]
                    out["cruces"].append({
                        "columna": col, "desde": x, "hacia": y, "filas_con_valor": len(no_vacios),
                        "vacios": len(vx) - len(no_vacios), "cruzan_exacto": exactos,
                        "cruzan_solo_tras_quitar_espacios_y_mayusculas": normalizados,
                        "no_cruzan": len(sin_cruce), "ejemplos_que_no_cruzan": sin_cruce_mostrar,
                        "de_los_que_no_cruzan": {
                            "cruzan_tras_unificar_espacios_internos": len(por_espacios),
                            "cruzan_tras_quitar_tildes_puntuacion_y_ceros_a_la_izquierda": len(por_escritura),
                            "sin_causa_de_escritura": len(resto),
                        },
                    })
    return out


def resumen(p):
    L = []
    for nombre, t in p["tablas"].items():
        L.append(f"\n## {nombre}: {t['filas']} filas · columnas: {', '.join(t['columnas'])}")
        if t["filas_identicas_a_otra_anterior"]:
            L.append(f"  ! {t['filas_identicas_a_otra_anterior']} filas idénticas a otra anterior (ej. {t['ejemplo_fila_repetida']})")
        for c in t["perfil_columnas"]:
            bits = [f"vacíos {c['vacios']}", f"distintos {c['distintos']}"]
            if c["espacios_sobrantes"]:
                bits.append(f"! espacios sobrantes {c['espacios_sobrantes']}")
            bits.append("formas " + ", ".join(f"«{f}»×{k}" for f, k in c["formas"][:4]))
            L.append(f"  - {c['columna']}: " + " · ".join(bits))
            if "numerico" in c and "min" not in c["numerico"]:
                m = c["numerico"]
                L.append(f"      numérico: negativos {m['negativos']} · ceros {m['ceros']} ({m['omitidos']})")
            elif "numerico" in c:
                m = c["numerico"]
                L.append(f"      numérico: min {m['min']:g} · max {m['max']:g} · suma {m['suma']:,.0f} · negativos {m['negativos']} · ceros {m['ceros']}")
            if "fechas" in c:
                L.append(f"      fechas: {json.dumps(c['fechas'], ensure_ascii=False)}")
                if c["fechas"].get("fechas_imposibles"):
                    L.append(f"      ! {c['fechas']['fechas_imposibles']} fechas que no existen en el calendario (mes 13, 30 de febrero), "
                             f"ej. {c['fechas'].get('ejemplos_imposibles', '(omitidos)')}: al convertirlas se pierden en silencio")
            if c.get("variantes_de_escritura"):
                L.append(f"      ! variantes de escritura de un mismo valor: {len(c['variantes_de_escritura'])} grupos, ej. {c['variantes_de_escritura'][:3]}")
            if c.get("factor_de_expansion"):
                L.append(f"      ! {c['factor_de_expansion']}")
            if c.get("posible_inyeccion"):
                L.append(f"      ! posible inyección de instrucciones: {c['posible_inyeccion']}")
            if "valores" in c:
                L.append(f"      valores: {c['valores']}")
            if c.get("posible_clave") and (c["valores_repetidos"] or c["valores_repetidos_tras_normalizar"]):
                L.append(f"      ! posible clave con valores repetidos: {c['valores_repetidos']} "
                         f"(tras quitar espacios y mayúsculas: {c['valores_repetidos_tras_normalizar']}), ej. {c['ejemplos_repetidos']}")
        for d in t.get("codigo_con_varios_valores", []):
            L.append(f"  ! {d['desde']} → {d['hacia']}: {d['con_mas_de_uno']} de {d['valores_de_desde']} valores de {d['desde']} "
                     f"tienen más de un {d['hacia']}, ej. {json.dumps(d['ejemplos'], ensure_ascii=False)[:400]}")
    if p["cruces"]:
        L.append("\n## Cruces entre tablas (columnas con el mismo nombre)")
        for x in p["cruces"]:
            L.append(f"  - {x['desde']}.{x['columna']} → {x['hacia']}: {x['filas_con_valor']} con valor, vacíos {x['vacios']}, "
                     f"cruzan exacto {x['cruzan_exacto']}, solo tras quitar espacios/mayúsculas {x['cruzan_solo_tras_quitar_espacios_y_mayusculas']}, "
                     f"no cruzan {x['no_cruzan']} {x['ejemplos_que_no_cruzan']}")
            d = x["de_los_que_no_cruzan"]
            if d["cruzan_tras_unificar_espacios_internos"]:
                L.append(f"      ! {d['cruzan_tras_unificar_espacios_internos']} no cruzan por espacios dobles o invisibles dentro del valor")
            if d["cruzan_tras_quitar_tildes_puntuacion_y_ceros_a_la_izquierda"]:
                L.append(f"      ! {d['cruzan_tras_quitar_tildes_puntuacion_y_ceros_a_la_izquierda']} no cruzan por tildes, "
                         "puntuación (S.A.S. / SAS) o ceros a la izquierda (001 / 1)")
    return "\n".join(L)


def main(argv):
    salida_json = None
    if "--json" in argv:
        i = argv.index("--json")
        salida_json = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    tablas = dict(a.split("=", 1) for a in argv)
    if not tablas:
        raise SystemExit(__doc__)
    try:
        p = perfilar(tablas)
    except ValueError as e:   # FAILFAST: con la línea, sin traceback y sin perfil a medias
        if salida_json:       # ni el de una corrida anterior: en su lugar queda el motivo de la detención
            with open(salida_json, "w", encoding="utf-8") as fh:
                json.dump({"failfast": str(e)}, fh, ensure_ascii=False)
        print(f"FAILFAST: {e}", file=sys.stderr)
        return 1
    if salida_json:
        with open(salida_json, "w", encoding="utf-8") as fh:
            json.dump(p, fh, ensure_ascii=False, indent=2, default=str)
    print(resumen(p))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
