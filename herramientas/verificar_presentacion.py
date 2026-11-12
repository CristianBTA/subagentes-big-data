#!/usr/bin/env python3
"""Presentación: comprueba sin IA la presentación que propuso la IA y, si aprueba, la deja en presentacion.html.

Uso:
  python verificar_presentacion.py <corrida>
  python verificar_presentacion.py --autoprueba      prueba al probador: primero el control positivo, luego los mutantes

La IA (subagente presentador, agentes/12-presentador.md) escribe SOLO presentacion.json. **No escribe números**:
en los textos pone marcadores como {total}, y cada marcador es una cifra declarada con su cálculo. El código
calcula la cifra desde el resultado aprobado, la escribe a la colombiana y arma las láminas con una plantilla
fija; la fuente y la fecha salen de la procedencia. Así ningún número que se muestra puede ser inventado.

Desde el 6-nov-2026 el análisis lo hacen las personas (D15): la IA puede resumir, no analizar. La presentación dice
lo preguntado y lo medido, sin conclusiones, recomendaciones, causas ni decisiones, y cierra con preguntas de costo,
calidad e impacto que las personas responden en plantillas/analisis_humano.md.

presentacion.json:
  {"lo_preguntado_y_lo_medido": {"situacion", "pregunta": "¿…?", "titulo"},
   "mediciones": [{"titulo", "evidencia": {"tipo": "grafico" | "tabla" | "cifra", ...}, "nota"}],
   "metodo_y_limites": {"metodo", "incertidumbre", "limites": [...]},
   "preguntas_para_las_personas": [{"tipo": "costo" | "calidad" | "impacto", "pregunta": "¿…?"}],
   "cifras": [{"id", "calculo": {"op", ...}, "formato": {"escala", "decimales"}}]}
Un campo que la ficha no trae hace fallar la forma: los de la forma anterior al 6-nov («respuesta», «decision»,
«scqa», «hallazgos», «recomendacion») no se ignoran. De SCQA quedan la situación y la pregunta, que describen; la
complicación y la respuesta se quitaron porque piden interpretar (qué es un problema, qué se concluye).

Lista de comprobación (pirámide de Minto como «lo preguntado y lo medido primero», afirmación-evidencia de Alley
con títulos que dicen lo medido, Storytelling with Data, AI Index, METR, la lección de las gráficas del lanzamiento
de GPT-5 y D15):
  0. presentacion.json tiene la forma de la ficha (tipos, largos, ids y ningún campo de más)
  1. el resultado que se presenta está aprobado
  2. lo preguntado y lo medido van primero: la situación, la pregunta con «¿…?» y la medición principal
  3. cada cifra se calcula desde los datos aprobados (valores finitos; cálculos que leen datos, no constantes); un
     «donde» compara números como números (2025 es 2025.0) y tiene que señalar al menos una fila: un valor mal
     escrito no se publica como una suma o un conteo de 0 (L111)
  4. de 1 a 5 mediciones, cada una con una sola evidencia válida (gráfico aprobado, tabla sin columnas personales
     ni de texto libre, cifra declarada)
  5. los números los escribe el código: marcadores conocidos y ningún dígito, número con palabras ni «%» fuera
     de un marcador (salvo los años del período y los ids P1, S1); tampoco las magnitudes con palabras que el
     whitepaper no deja pasar («la mayoría», «casi todos», MAGNITUD_EN_PALABRAS de validar_whitepaper.py)
  6. títulos que dicen lo medido: oración con una cifra, de 6 a 22 palabras y hasta 120 caracteres; sin repetirse
  7. método, incertidumbre y límites declarados; las preguntas abiertas se nombran
  8. preguntas para las personas: de 3 a 6, cada una entre «¿» y «?», con al menos una de costo, una de calidad y
     una de impacto
  9. sin lenguaje de análisis en ningún texto: la lista D15 de validar_whitepaper.py (ANALISIS, buscada con buscar_d15:
     la misma de W3, del gráfico y de las fichas, con lo que traía la forma anterior de la presentación: «se
     concluye», «demuestra que», «esto muestra que», «se recomienda», «debería», «la causa es», «se debe a», «lo
     que se pide decidir», «próximo paso», «por eso»…); ningún título empieza como un título de análisis
     («Hallazgo», «Conclusión»). Se busca en el texto tal cual y en como lo lee una persona: el énfasis de Markdown y
     las letras de ancho completo o de otro alfabeto que se leen como latinas no esconden una frase (L117)
 10. fuente y fecha de consulta tomadas de la procedencia
 11. sin textos con forma de instrucción, sin invisibles ni palabras disfrazadas con letras de otro alfabeto («concluye»
     con la «o» cirílica) y sin datos personales (textos y celdas de las tablas)
Las frases de análisis se buscan con una lista: lo que no conoce, lo revisa una persona con la última lámina.
"""
import html
import json
import math
import re
import shutil
import sys
import tempfile
import unicodedata
from datetime import date
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from gobernanza import clasificar_columna, escanear_texto, latinizar, letras_disfrazadas, parece_instruccion  # noqa: E402
from validar_whitepaper import MAGNITUD_EN_PALABRAS, TITULO_DE_ANALISIS, buscar_d15  # noqa: E402  D15: la lista única
from validar_whitepaper import FRASES_D15  # noqa: E402  las frases de prueba de la autoprueba
from validar_whitepaper import normalizar as normalizar_titulo  # noqa: E402

MAX_MEDICIONES = 5
MIN_PREGUNTAS, MAX_PREGUNTAS = 3, 6
TIPOS_DE_PREGUNTA = ("costo", "calidad", "impacto")
MAX_CARACTERES_PREGUNTA = 240        # una pregunta, no un párrafo (ya con las cifras puestas)
MAX_FILAS_TABLA = 10
MAX_COLUMNAS_TABLA = 6
MAX_LIMITES = 8
MAX_CIFRAS = 40
MAX_TEXTO = 400                      # caracteres por campo: también acota el costo de los barridos
MAX_CARACTERES_TITULO = 120          # unas dos líneas en la plantilla de 16:9
MIN_PALABRAS_TITULO, MAX_PALABRAS_TITULO = 6, 22
PROFUNDIDAD_MAX = 4
ESCALAS = {None: (1.0, ""), "mil": (1e3, "mil"), "millones": (1e6, "millones"),
           "mil millones": (1e9, "mil millones"), "billones": (1e12, "billones")}
PLANTILLA = "../../plantillas/analisis_humano.md"   # las corridas viven en corridas/<fecha-nombre>/
# Forma: los campos que trae la ficha, en cada nivel. Uno de más hace fallar la forma (no se ignora).
CAMPOS = {"presentacion": {"lo_preguntado_y_lo_medido", "mediciones", "metodo_y_limites", "preguntas_para_las_personas", "cifras"},
          "lo_preguntado_y_lo_medido": {"situacion", "pregunta", "titulo"},
          "medicion": {"titulo", "evidencia", "nota"},
          "grafico": {"tipo"}, "tabla": {"tipo", "columnas", "orden", "filas"}, "cifra": {"tipo", "cifra"},
          "metodo_y_limites": {"metodo", "incertidumbre", "limites"},
          "pregunta": {"tipo", "pregunta"},
          "cifras": {"id", "calculo", "formato"}, "formato": {"escala", "decimales"}}
CAMPOS_DEL_CALCULO = {"op", "columna", "donde", "primeros", "n", "parte", "total", "a", "b"}
# La forma anterior al 6-nov: la IA concluía, pedía una decisión y recomendaba. Desde D15 eso lo hacen las personas.
FORMA_VIEJA = {"respuesta": "la apertura es «lo_preguntado_y_lo_medido»",
               "decision": "la IA no pide decisiones (D15): las toman las personas",
               "scqa": "de SCQA quedan la situación y la pregunta, dentro de «lo_preguntado_y_lo_medido»",
               "complicacion": "la complicación pide interpretar: se quitó",
               "hallazgos": "ahora son «mediciones»: dicen lo medido",
               "recomendacion": "la IA no recomienda (D15): van «preguntas_para_las_personas»"}
ID_OK = re.compile(r"[a-z][a-z0-9_]{0,29}")
MARCADOR = re.compile(r"\{([^{}]{0,40})\}")
# Magnitudes con palabras: son afirmaciones sobre los datos y van con marcador, en cualquier texto.
MAGNITUDES = re.compile(
    r"\b(dieci\w+|veinte|veinti\w+|treinta|cuarenta|cincuenta|sesenta|setenta|ochenta|noventa|cien|ciento|cientos|"
    r"\w+cientos|\w+cientas|quinient\w+|mil|miles|millar\w*|mill[oó]n|millones|bill[oó]n|billones|mitad|doble|triple|"
    r"cu[aá]druple|qu[ií]ntuple|duplic\w*|triplic\w*|cuadruplic\w*|multiplic\w*|tercio|tercios|cuart[ao]s?\s+partes?|"
    r"quinta\s+parte|d[eé]cima\s+parte|decena|decenas|centena|centenar|centenares|docena|docenas|cero|"
    r"por\s*ciento|porciento)\b", re.I)
# Los cardinales pequeños («dos implementaciones», «se calculó dos veces») cuentan cosas del método: se permiten en el
# método, la incertidumbre y los límites. En títulos, notas, situación y preguntas, cada número es un marcador.
CARDINALES = re.compile(r"\b(dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|trece|catorce|quince)\b", re.I)
LUGARES_CON_CARDINALES = ("metodo", "incertidumbre", "limite")
FRASES_PERMITIDAS = ("doble conteo", "doble eje", "primera mitad", "segunda mitad")
SIGNOS_PORCENTAJE = re.compile(r"[%‰‱٪⁒]")
ABREVIADAS = re.compile(r"\{[a-z][a-z0-9_]*\}\s*(?:MM|M|K|B|mill\.?|USD|US\$|COP|€|\$|d[oó]lar\w*|euro\w*)(?![\w])|"
                        r"(?:US\$|USD|COP|€|\$)\s*\{", re.I)
ID_DE_REFERENCIA = re.compile(r"[PS]\d{1,2}")      # preguntas y supuestos de la especificación
MAX_CELDA = 120
RELLENOS = {"ㅤ", "ᅟ", "ᅠ", "ﾠ", "͏"}


# ---------------------------------------------------------------- utilidades ----------------------------------------------------------------
def formato_co(x, dec=0):
    return f"{x:,.{dec}f}".translate(str.maketrans({",": ".", ".": ","}))


def invisibles_en(texto):
    return [c for c in str(texto) if unicodedata.category(c) in ("Cf", "Zl", "Zp", "Co", "Cs", "Cc") and c not in "\n\t" or c in RELLENOS]


def normalizar(texto):
    """NFKC (⁶ → 6, ¾ → 3⁄4) y sin caracteres de formato: lo que el lector ve, sin disfraces."""
    t = unicodedata.normalize("NFKC", str(texto))
    return "".join(c for c in t if unicodedata.category(c) != "Cf")


def leer_json(p, defecto=None):
    def no_finitos(x):
        raise ValueError(f"valor no finito {x}")
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"), parse_constant=no_finitos)
    except (OSError, ValueError):
        return defecto


# ---------------------------------------------------------------- forma ----------------------------------------------------------------
def forma(pres):
    """Valida tipos, largos y campos antes de comprobar nada. Devuelve la lista de problemas."""
    P = []

    def texto(v, donde, obligatorio=True):
        if v is None and not obligatorio:
            return
        if not isinstance(v, str) or (obligatorio and not v.strip()):
            P.append(f"{donde}: debe ser un texto")
        elif len(v) > MAX_TEXTO:
            P.append(f"{donde}: {len(v)} caracteres (máximo {MAX_TEXTO})")

    def objeto(v, donde, campos=None):
        if not isinstance(v, dict):
            P.append(f"{donde}: debe ser un objeto")
            return {}
        if campos is not None:
            for k in v:
                if k not in CAMPOS[campos]:
                    nombre = str(k)[:30]
                    P.append(f"{donde}: «{nombre}» " + (f"es de la forma anterior al 6-nov ({FORMA_VIEJA[k]})" if k in FORMA_VIEJA
                                                        else "no está en la ficha (un campo de más no se ignora)"))
        return v

    def entero(v, donde, lo, hi):
        if not isinstance(v, int) or isinstance(v, bool) or not lo <= v <= hi:
            P.append(f"{donde}: debe ser un entero de {lo} a {hi}")

    if not isinstance(pres, dict):
        return ["presentacion.json debe ser un objeto"]
    objeto(pres, "presentacion.json", "presentacion")
    a = objeto(pres.get("lo_preguntado_y_lo_medido"), "lo_preguntado_y_lo_medido", "lo_preguntado_y_lo_medido")
    for k in ("situacion", "pregunta", "titulo"):
        texto(a.get(k), f"lo_preguntado_y_lo_medido.{k}")
    med = pres.get("mediciones")
    if not isinstance(med, list):
        P.append("mediciones: debe ser una lista")
        med = []
    for i, h in enumerate(med[:20], 1):
        h = objeto(h, f"medición {i}", "medicion")
        texto(h.get("titulo"), f"medición {i}.titulo")
        texto(h.get("nota"), f"medición {i}.nota", obligatorio=False)
        ev = objeto(h.get("evidencia"), f"medición {i}.evidencia")
        t = ev.get("tipo")
        if t == "hipotesis":
            P.append(f"medición {i}.evidencia.tipo: «hipotesis» es historial desde el 6-nov (D15): la IA no presenta "
                     "veredictos; las hipótesis las prueban las personas")
        elif t not in ("grafico", "tabla", "cifra"):
            P.append(f"medición {i}.evidencia.tipo: grafico, tabla o cifra")
        else:
            objeto(ev, f"medición {i}.evidencia", t)
        if t == "tabla":
            cols = ev.get("columnas")
            if not isinstance(cols, list) or not 1 <= len(cols) <= MAX_COLUMNAS_TABLA or not all(isinstance(c, str) for c in cols):
                P.append(f"medición {i}.evidencia.columnas: lista de 1 a {MAX_COLUMNAS_TABLA} nombres")
            entero(ev.get("filas"), f"medición {i}.evidencia.filas", 1, MAX_FILAS_TABLA)
            if ev.get("orden") is not None and not isinstance(ev.get("orden"), str):
                P.append(f"medición {i}.evidencia.orden: nombre de una columna")
        elif t == "cifra" and not isinstance(ev.get("cifra"), str):
            P.append(f"medición {i}.evidencia.cifra: id de una cifra")
    m = objeto(pres.get("metodo_y_limites"), "metodo_y_limites", "metodo_y_limites")
    texto(m.get("metodo"), "metodo_y_limites.metodo")
    texto(m.get("incertidumbre"), "metodo_y_limites.incertidumbre")
    lim = m.get("limites")
    if not isinstance(lim, list) or len(lim) > MAX_LIMITES:
        P.append(f"metodo_y_limites.limites: lista de hasta {MAX_LIMITES} textos")
    else:
        for i, x in enumerate(lim, 1):
            texto(x, f"limite {i}")
    preg = pres.get("preguntas_para_las_personas")
    if not isinstance(preg, list) or len(preg) > 2 * MAX_PREGUNTAS:
        P.append(f"preguntas_para_las_personas: lista de {MIN_PREGUNTAS} a {MAX_PREGUNTAS} objetos {{tipo, pregunta}}")
    else:
        for i, x in enumerate(preg, 1):
            x = objeto(x, f"pregunta para las personas {i}", "pregunta")
            texto(x.get("tipo"), f"pregunta para las personas {i}.tipo")
            texto(x.get("pregunta"), f"pregunta para las personas {i}.pregunta")
    cif = pres.get("cifras")
    if not isinstance(cif, list) or len(cif) > MAX_CIFRAS:
        P.append(f"cifras: lista de hasta {MAX_CIFRAS}")
        cif = []
    ids = []
    for i, x in enumerate(cif, 1):
        if isinstance(x, dict) and "texto" in x:
            P.append(f"cifra {i}: no lleva «texto»; el número lo escribe el código desde el cálculo")
            x = {k: v for k, v in x.items() if k != "texto"}
        x = objeto(x, f"cifra {i}", "cifras")
        cid = x.get("id")
        if not isinstance(cid, str) or not ID_OK.fullmatch(cid):
            P.append(f"cifra {i}.id: minúsculas, dígitos y _ (empieza con letra, hasta 30)")
        ids.append(cid)
        objeto(x.get("calculo"), f"cifra {i}.calculo")
        f = x.get("formato")
        if f is not None:
            f = objeto(f, f"cifra {i}.formato", "formato")
            if f.get("escala") not in ESCALAS:
                P.append(f"cifra {i}.formato.escala: una de {[k for k in ESCALAS if k]} o null")
            if f.get("decimales") is not None:
                entero(f.get("decimales"), f"cifra {i}.formato.decimales", 0, 3)
    if len([c for c in ids if isinstance(c, str)]) != len({c for c in ids if isinstance(c, str)}):
        P.append("cifras: hay ids repetidos")
    return P


# ---------------------------------------------------------------- cálculo ----------------------------------------------------------------
class ErrorCalculo(Exception):
    pass


def _num(v):
    if v is None or isinstance(v, bool):
        raise ErrorCalculo("valor vacío o booleano en una columna numérica")
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ErrorCalculo(f"valor no numérico: {str(v)[:30]}")
    if not math.isfinite(x):
        raise ErrorCalculo("valor no finito (NaN o infinito) en los datos")
    return x


def _igual(celda, buscado):
    """Lo que compara «donde»: un número con un número, como números (2025 es 2025.0; por su texto no lo era), y lo
    demás por su texto, como antes («890905211» y 890905211). Una celda vacía o booleana no coincide con nada."""
    if celda is None or isinstance(celda, bool):
        return False
    if isinstance(celda, (int, float)) and isinstance(buscado, (int, float)):
        return celda == buscado
    return str(celda) == str(buscado)


def _filtrar(filas, donde, columnas):
    if donde is None:
        return filas
    if not isinstance(donde, dict) or not donde:
        raise ErrorCalculo("«donde» debe ser un objeto {columna: valor}")
    for k, v in donde.items():
        if k not in columnas:
            raise ErrorCalculo(f"«donde» usa la columna «{k}», que no está en el resultado")
        if not isinstance(v, (str, int, float)) or isinstance(v, bool):
            raise ErrorCalculo("«donde» compara con un texto o un número")
    sel = [f for f in filas if all(_igual(f.get(k), v) for k, v in donde.items())]
    if not sel:
        # un nombre mal escrito («DISTRITO DE MEDELLIN») no es un 0: la suma y el conteo salían en 0 y aprobaban (L111)
        raise ErrorCalculo("«donde» no señala ninguna fila del resultado aprobado: escriba el valor como está en los "
                           "datos (una suma o un conteo con «donde» no se publica en 0)")
    return sel


def _entero(v, nombre):
    if not isinstance(v, int) or isinstance(v, bool):
        raise ErrorCalculo(f"«{nombre}» debe ser un entero")
    return v


def calcular(calc, ctx, prof=0):
    """Calcula una cifra desde el resultado aprobado o la procedencia. Sin IA."""
    if prof > PROFUNDIDAD_MAX:
        raise ErrorCalculo("cálculo demasiado anidado")
    if not isinstance(calc, dict):
        raise ErrorCalculo("el cálculo debe ser un objeto con «op»")
    op = calc.get("op")
    filas = ctx["resultado"]
    columnas = set(filas[0].keys()) if filas else set()
    if op == "hipotesis" or "como" in calc:
        raise ErrorCalculo("las hipótesis de la IA son historial desde el 6-nov (D15): la presentación muestra lo medido, "
                           "no veredictos («op»: hipotesis y «como» ya no existen)")
    de_mas = sorted(str(k)[:30] for k in calc if k not in CAMPOS_DEL_CALCULO)
    if de_mas:
        raise ErrorCalculo(f"campos que un cálculo no lleva: {de_mas}")

    def col():
        c = calc.get("columna")
        if c not in columnas:
            raise ErrorCalculo(f"la columna «{c}» no está en el resultado aprobado")
        return c

    if op == "conteo":
        sel = _filtrar(filas, calc.get("donde"), columnas)
        if "primeros" in calc:
            if prof > 0:
                raise ErrorCalculo("«primeros» es una constante: solo como cifra directa, nunca dentro de otro cálculo")
            n = _entero(calc["primeros"], "primeros")
            if not 1 <= n <= len(sel):
                raise ErrorCalculo(f"«primeros» = {n} y hay {len(sel)} filas")
            return float(n)
        return float(len(sel))
    if op == "suma":
        c = col()
        return math.fsum(_num(f.get(c)) for f in _filtrar(filas, calc.get("donde"), columnas))
    if op in ("maximo", "minimo"):
        c = col()
        vals = [_num(f.get(c)) for f in _filtrar(filas, calc.get("donde"), columnas)]
        if not vals:
            raise ErrorCalculo("no hay filas que cumplan «donde»")
        return max(vals) if op == "maximo" else min(vals)
    if op == "valor":
        c = col()
        sel = _filtrar(filas, calc.get("donde"), columnas)
        if calc.get("donde") is None or len(sel) != 1:
            raise ErrorCalculo(f"«donde» debe señalar una fila y señala {len(sel)}")
        return _num(sel[0].get(c))
    if op == "suma_primeros":
        c = col()
        n = _entero(calc.get("n"), "n")
        if not 1 <= n <= len(filas):
            raise ErrorCalculo(f"n = {n} y hay {len(filas)} filas")
        return math.fsum(sorted((_num(f.get(c)) for f in filas), reverse=True)[:n])
    if op in ("porcentaje", "cociente", "diferencia"):
        a = calcular(calc.get("parte") if op == "porcentaje" else calc.get("a"), ctx, prof + 1)
        b = calcular(calc.get("total") if op == "porcentaje" else calc.get("b"), ctx, prof + 1)
        if op == "diferencia":
            return a - b
        if b == 0:
            raise ErrorCalculo("división por cero")
        return 100 * a / b if op == "porcentaje" else a / b
    if op == "filas_fuente":
        return _num(ctx["procedencia"].get("filas"))
    raise ErrorCalculo(f"operación desconocida: {str(op)[:30]!r}")


def es_porcentaje(calc):
    return isinstance(calc, dict) and calc.get("op") == "porcentaje"


def escribir_cifra(valor, cifra):
    f = cifra.get("formato") or {}
    factor, palabra = ESCALAS[f.get("escala")]
    v = valor / factor
    dec = f.get("decimales")
    if dec is None:
        dec = 0 if abs(v) >= 100 or float(v).is_integer() else 1
    redondo = round(v, dec)
    if v != 0 and redondo == 0:
        raise ErrorCalculo(f"con {dec} decimales se mostraría 0 y el valor no es 0: use más decimales u otra escala")
    if es_porcentaje(cifra.get("calculo")) and v < 100 and redondo >= 100:
        raise ErrorCalculo(f"con {dec} decimales se mostraría 100 % y el valor es menor: use más decimales")
    if redondo == 0:
        v = 0.0                                      # nunca «-0»
    s = formato_co(v, dec)
    if palabra:
        s += " " + palabra
    if es_porcentaje(cifra.get("calculo")):
        s += " %"
    return s


def poner_cifras(texto, escritas):
    return MARCADOR.sub(lambda m: escritas.get(m.group(1), m.group(0)), str(texto or ""))


def publicar_con_tramos(texto, escritas):
    """El texto ya publicado y los tramos [inicio, fin) que escribió el código (uno por marcador)."""
    t, partes, tramos, pos, largo = str(texto or ""), [], [], 0, 0
    for m in MARCADOR.finditer(t):
        antes = t[pos:m.start()]
        partes.append(antes)
        largo += len(antes)
        s = escritas.get(m.group(1), m.group(0))
        partes.append(s)
        tramos.append((largo, largo + len(s)))
        largo += len(s)
        pos = m.end()
    partes.append(t[pos:])
    return "".join(partes), tramos


def normal_sellado(texto):
    return " ".join(re.sub(r"[^\w.,%-]+", " ", normalizar(texto).lower()).split())


# ---------------------------------------------------------------- carga ----------------------------------------------------------------
def procedencia_de(c):
    """La que cita la presentación (fuente y fecha) es la misma que recibe el gráfico: la de la primera tabla que tiene
    la suya (una procedencia por tabla, L74) o, sin tablas en la spec, la procedencia.json de la corrida. La genérica
    de datos/, que la ingesta ya no escribe, solo cuenta si no hay otra (corridas viejas)."""
    spec = leer_json(c / "spec.json")
    if spec:
        try:
            import verificar_grafico
            from rutas import resolver_datos
            proc = verificar_grafico.procedencia_de(c, resolver_datos(spec))
            if proc:
                return proc
        except Exception:
            pass
    for p in (c / "procedencia.json", c / "datos" / "procedencia.json"):
        if p.exists():
            return leer_json(p, {}) or {}
    return {}


def textos_de(pres):
    """Todos los textos que escribió la IA, con su lugar: [(lugar, texto)]."""
    L = []
    a = pres.get("lo_preguntado_y_lo_medido") or {}
    L += [(f"lo_preguntado_y_lo_medido.{k}", a.get(k)) for k in ("situacion", "pregunta", "titulo")]
    for i, h in enumerate(pres.get("mediciones") or [], 1):
        L += [(f"medición {i}.titulo", h.get("titulo")), (f"medición {i}.nota", h.get("nota"))]
    m = pres.get("metodo_y_limites") or {}
    L += [("metodo", m.get("metodo")), ("incertidumbre", m.get("incertidumbre"))]
    L += [(f"limite {i}", x) for i, x in enumerate(m.get("limites") or [], 1)]
    L += [(f"pregunta para las personas {i}", (x or {}).get("pregunta"))
          for i, x in enumerate(pres.get("preguntas_para_las_personas") or [], 1)]
    return [(lugar, t) for lugar, t in L if isinstance(t, str)]


def es_pregunta(t):
    t = str(t or "").strip()
    return t.startswith("¿") and t.endswith("?") and len(t.split()) >= 3


def lleno(x, palabras=3):
    return isinstance(x, str) and len(x.split()) >= palabras


def celdas_de_tabla(ev, resultado):
    cols = [c for c in ev.get("columnas") or [] if resultado and c in resultado[0]]
    orden = ev.get("orden") if resultado and ev.get("orden") in resultado[0] else None
    filas = list(resultado)
    if orden:
        def clave(f):
            try:
                x = float(f.get(orden))
                return -x if math.isfinite(x) else 0.0
            except (TypeError, ValueError):
                return 0.0
        filas.sort(key=clave)
    filas = filas[: int(ev.get("filas") or 5)]
    cuerpo = []
    for f in filas:
        fila = []
        for c in cols:
            v = f.get(c)
            if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v)):
                if float(v).is_integer() and 1900 <= v <= 2100:
                    fila.append((str(int(v)), True))            # un año no lleva punto de miles
                else:
                    fila.append((formato_co(v, 0 if float(v).is_integer() or abs(v) >= 1000 else 2), True))
            else:
                s = " ".join(str(v if v is not None else "").split())
                fila.append((s if len(s) <= MAX_CELDA else s[:MAX_CELDA - 1] + "…", False))   # lo que se dibuja es lo que se barre
        cuerpo.append(fila)
    return cols, cuerpo


# ---------------------------------------------------------------- comprobación ----------------------------------------------------------
def comprobar(c):
    checks = []

    def chk(nombre, ok, detalle):
        checks.append({"comprobacion": nombre, "ok": bool(ok), "detalle": detalle})

    pres = leer_json(c / "presentacion.json")
    problemas = forma(pres) if pres is not None else ["falta presentacion.json o no es JSON válido"]
    chk("presentacion.json tiene la forma de la ficha", not problemas, "bien" if not problemas else "; ".join(problemas[:8]))
    if problemas:
        return checks, None

    inf = leer_json(c / "informe.json", {}) or {}
    resultado = [f for f in (inf.get("resultado_oficial") or []) if isinstance(f, dict)]
    graf = leer_json(c / "grafico_verificacion.json", {}) or {}
    graf_meta = leer_json(c / "grafico.json", {}) or {}
    spec = leer_json(c / "spec.json", {}) or {}
    proc = procedencia_de(c)
    ctx = {"resultado": resultado, "procedencia": proc}
    columnas = set(resultado[0].keys()) if resultado else set()

    estado = inf.get("estado")
    chk("el resultado que se presenta está aprobado", estado == "aprobado" and bool(resultado),
        f"informe.json: estado «{estado}», {len(resultado)} filas" + ("" if estado == "aprobado" else " (no se presenta un resultado sin aprobar)"))

    a = pres["lo_preguntado_y_lo_medido"]
    falta = ([] if lleno(a["situacion"]) else ["la situación (3 palabras o más)"]) \
        + ([] if es_pregunta(a["pregunta"]) else ["la pregunta, entre «¿» y «?»"]) \
        + ([] if lleno(a["titulo"]) else ["la medición principal (3 palabras o más)"])
    chk("lo preguntado y lo medido van primero (situación, pregunta y medición principal)", not falta,
        "presentes" if not falta else "falta: " + ", ".join(falta))

    # cifras: se calculan desde los datos y las escribe el código
    cifras = {x["id"]: x for x in pres["cifras"]}
    escritas, errores = {}, []
    for cid, x in cifras.items():
        try:
            v = calcular(x["calculo"], ctx)
            if not math.isfinite(v):
                raise ErrorCalculo("el cálculo no da un número finito")
            escritas[cid] = escribir_cifra(v, x)
        except (ErrorCalculo, ValueError, TypeError, OverflowError, RecursionError) as e:
            errores.append(f"{cid}: {e}")
    chk("cada cifra se calcula desde los datos aprobados", cifras and not errores,
        (f"{len(escritas)} de {len(cifras)} cifras calculadas: " + ", ".join(f"{k} = {v}" for k, v in list(escritas.items())[:8])
         if cifras else "no hay cifras declaradas") + (f" · {errores[:5]}" if errores else ""))

    # mediciones y evidencias
    med = pres["mediciones"]
    malas, tablas = [], {}
    for i, h in enumerate(med, 1):
        ev = h["evidencia"]
        t = ev["tipo"]
        if t == "grafico" and graf.get("estado") != "aprobado":
            malas.append(f"medición {i}: el gráfico no está aprobado por verificar_grafico.py")
        elif t == "tabla":
            cols = ev["columnas"]
            fuera = [x for x in cols if x not in columnas]
            sensibles = [x for x in cols if clasificar_columna(x)]
            if fuera:
                malas.append(f"medición {i}: columnas que no están en el resultado: {fuera}")
            if sensibles:
                malas.append(f"medición {i}: columnas personales o de texto libre: {sensibles}")
            if ev.get("orden") is not None and ev["orden"] not in columnas:
                malas.append(f"medición {i}: no existe la columna de orden «{ev['orden']}»")
            tablas[i] = celdas_de_tabla(ev, resultado)
        elif t == "cifra" and ev["cifra"] not in escritas:
            malas.append(f"medición {i}: la cifra «{ev['cifra']}» no está declarada o no se pudo calcular")
    ok_n = 1 <= len(med) <= MAX_MEDICIONES
    chk(f"de 1 a {MAX_MEDICIONES} mediciones, cada una con una sola evidencia válida", ok_n and not malas,
        (f"{len(med)} mediciones" if ok_n else f"{len(med)} mediciones (deben ser de 1 a {MAX_MEDICIONES})") + (f" · {malas}" if malas else ""))

    # los números los escribe el código
    textos = textos_de(pres)
    contexto = " ".join(str(v) for v in [spec.get("peticion"), inf.get("peticion"), (proc.get("fuente") or {}).get("filtro_legible"),
                                         proc.get("cita"), graf_meta.get("periodo"), str(proc.get("consultado") or "")[:4]] if v)
    anios = set(re.findall(r"(?<!\d)((?:19|20)\d\d)(?!\d)", contexto))
    ids_ok = {str(p.get("id")) for p in (spec.get("preguntas") or []) + (spec.get("supuestos") or []) if isinstance(p, dict) and p.get("id")}
    ids_ok = {x for x in ids_ok if ID_DE_REFERENCIA.fullmatch(x)}
    # Lo sellado antes de la presentación (especificación y procedencia): un número que aparece ahí, con las mismas
    # palabras, es una cita literal (un umbral, un corte, el id del conjunto), no una cifra nueva.
    fte = proc.get("fuente") if isinstance(proc.get("fuente"), dict) else {}
    sellado = normal_sellado(" ".join(
        [json.dumps([spec.get(k) for k in ("peticion", "interpretacion", "definiciones", "supuestos", "preguntas")], ensure_ascii=False)]
        + [str(v) for v in (proc.get("cita"), fte.get("filtro_legible"), fte.get("conjunto"), graf_meta.get("periodo")) if v]))
    palabras_selladas = set(sellado.split())
    sueltos, desconocidos = [], []
    for lugar, t in textos:
        for m in MARCADOR.finditer(t):
            if m.group(1) not in cifras:
                desconocidos.append(f"{lugar}: «{m.group(0)[:30]}»")
        if MARCADOR.sub("", t).count("{") or MARCADOR.sub("", t).count("}"):
            desconocidos.append(f"{lugar}: llaves sueltas")
        resto = normalizar(MARCADOR.sub(" ", t))
        for m in re.finditer(r"[\w-]*\d(?:[\w.,-]*\w)?", resto):
            tok = m.group(0)
            if tok in anios or tok in ids_ok:
                continue
            frase = " ".join(normal_sellado(resto[m.start():m.start() + 80]).split()[:2])
            if (len(tok) >= 3 and normal_sellado(tok) in palabras_selladas) or (frase and f" {frase} " in f" {sellado} "):
                continue
            sueltos.append(f"{lugar}: «{tok[:20]}»")
        raros = sorted({ch for ch in resto if not ch.isascii() and unicodedata.numeric(ch, None) is not None})
        if raros:
            sueltos.append(f"{lugar}: caracteres numéricos {raros[:5]}")
        for m in MAGNITUDES.finditer(resto):
            frase = " ".join(resto[m.start():m.start() + 80].lower().split()[:2])
            if frase in FRASES_PERMITIDAS or f" {normal_sellado(frase)} " in f" {sellado} ":
                continue
            sueltos.append(f"{lugar}: «{m.group(0)}» (magnitud con palabras)")
        for m in MAGNITUD_EN_PALABRAS.finditer(resto):   # las del whitepaper (W2): «la mayoría» no se puede comprobar
            frase = " ".join(m.group(0).lower().split())
            if f" {normal_sellado(frase)} " not in f" {sellado} ":
                sueltos.append(f"{lugar}: «{m.group(0)}» (magnitud con palabras que no se puede comprobar)")
        if not lugar.startswith(LUGARES_CON_CARDINALES):
            for m in CARDINALES.finditer(resto):
                sueltos.append(f"{lugar}: «{m.group(0)}» (fuera del método y los límites, cada número es un marcador)")
        if SIGNOS_PORCENTAJE.search(resto):
            sueltos.append(f"{lugar}: «%» fuera de un marcador")
        for m in ABREVIADAS.finditer(t):
            sueltos.append(f"{lugar}: «{m.group(0)[:20]}» (escala abreviada o moneda junto a un marcador)")
        publicado, tramos = publicar_con_tramos(t, escritas)
        for m in re.finditer(r"\d(?:[\d.,]*\d)?", publicado):
            a_, b_ = m.span()
            toca = [tr for tr in tramos if tr[0] < b_ and a_ < tr[1]]
            if toca and not (len(toca) == 1 and toca[0][0] <= a_ and b_ <= toca[0][1]):
                sueltos.append(f"{lugar}: «{publicado[max(0, a_ - 3):b_ + 3]}» (marcadores pegados forman otro número)")
    ok_num = not sueltos and not desconocidos
    chk("los números los escribe el código (marcadores {id}, ningún número a mano)", ok_num,
        "todos los números salen de cifras declaradas" if ok_num else
        "; ".join((["marcadores desconocidos: " + ", ".join(desconocidos[:10])] if desconocidos else [])
                  + ([f"{len(sueltos)} números escritos a mano (use un marcador con su cifra): " + ", ".join(sueltos[:30])] if sueltos else [])))

    # títulos que dicen lo medido (se miden ya con las cifras puestas)
    titulos = [("lo medido", a["titulo"])] + [(f"medición {i}", h["titulo"]) for i, h in enumerate(med, 1)]
    problemas = []
    for lugar, t in titulos:
        vista = poner_cifras(t, escritas)
        n_pal = len(vista.split())
        if not MIN_PALABRAS_TITULO <= n_pal <= MAX_PALABRAS_TITULO:
            problemas.append(f"{lugar}: {n_pal} palabras (de {MIN_PALABRAS_TITULO} a {MAX_PALABRAS_TITULO}: una oración con lo medido, no un tema)")
        if len(vista) > MAX_CARACTERES_TITULO:
            problemas.append(f"{lugar}: {len(vista)} caracteres (máximo {MAX_CARACTERES_TITULO}, unas dos líneas)")
        if vista.rstrip().endswith((":", "?")):
            problemas.append(f"{lugar}: termina en «{vista.rstrip()[-1]}»; un título dice lo medido")
        if not any(m.group(1) in escritas for m in MARCADOR.finditer(t)):
            problemas.append(f"{lugar}: sin una cifra; el título dice lo medido con su número")
    vistos = [poner_cifras(t, escritas).strip().lower() for _, t in titulos]
    if len(set(vistos)) != len(vistos):
        problemas.append("hay títulos repetidos")
    chk("títulos que dicen lo medido: oración con una cifra, de 6 a 22 palabras y hasta 120 caracteres", not problemas,
        "todos dicen lo medido con su cifra" if not problemas else "; ".join(problemas[:6]))

    # método y límites
    m = pres["metodo_y_limites"]
    limites = [x for x in m["limites"] if x.strip()]
    ids_abiertas = [str(p.get("id")) for p in (spec.get("preguntas") or []) if isinstance(p, dict) and p.get("id")]
    abiertas = inf.get("preguntas_abiertas")
    n_abiertas = abiertas if isinstance(abiertas, int) and not isinstance(abiertas, bool) else len(abiertas) if isinstance(abiertas, list) else 0
    texto_lim = " ".join(limites + [m["incertidumbre"], m["metodo"]])
    sin_nombrar = [p for p in ids_abiertas if n_abiertas and not re.search(rf"(?<!\w){re.escape(p)}(?!\w)", texto_lim)]
    ok_m = lleno(m["metodo"]) and lleno(m["incertidumbre"], 2) and bool(limites) and not sin_nombrar
    chk("método, incertidumbre y límites declarados; preguntas abiertas nombradas", ok_m,
        f"{len(limites)} límites" + ("" if lleno(m["metodo"]) else " · falta el método")
        + ("" if lleno(m["incertidumbre"], 2) else " · falta la incertidumbre (o «no aplica» con el motivo)")
        + ("" if limites else " · sin límites")
        + (f" · preguntas abiertas sin nombrar: {sin_nombrar}" if sin_nombrar else ""))

    # preguntas para las personas (como W4 del whitepaper): las responden ellas en la plantilla
    preg = pres["preguntas_para_las_personas"]
    problemas, tipos = [], set()
    if not MIN_PREGUNTAS <= len(preg) <= MAX_PREGUNTAS:
        problemas.append(f"hay {len(preg)} pregunta(s); se piden de {MIN_PREGUNTAS} a {MAX_PREGUNTAS}")
    for k, x in enumerate(preg, 1):
        tipo = normalizar_titulo(x["tipo"])
        if tipo in TIPOS_DE_PREGUNTA:
            tipos.add(tipo)
        else:
            problemas.append(f"la pregunta {k} tiene el tipo «{str(x['tipo'])[:20]}» (costo, calidad o impacto)")
        if not es_pregunta(x["pregunta"]):
            problemas.append(f"la pregunta {k} no va entre «¿» y «?»")
        if len(poner_cifras(x["pregunta"], escritas)) > MAX_CARACTERES_PREGUNTA:
            problemas.append(f"la pregunta {k} pasa de {MAX_CARACTERES_PREGUNTA} caracteres: una pregunta, no un párrafo")
    faltan_tipos = [t for t in TIPOS_DE_PREGUNTA if t not in tipos]
    if faltan_tipos:
        problemas.append(f"falta al menos una pregunta de: {', '.join(faltan_tipos)}")
    vistas = [" ".join(poner_cifras(x["pregunta"], escritas).lower().split()) for x in preg]
    if len(set(vistas)) != len(vistas):
        problemas.append("hay preguntas repetidas")
    chk("preguntas para las personas: de 3 a 6, entre «¿» y «?», de costo, calidad e impacto", not problemas,
        "; ".join(problemas[:6]) or f"{len(preg)} preguntas, de costo, calidad e impacto; las responden las personas en {PLANTILLA}")

    # D15: la IA resume, no analiza. La lista única de validar_whitepaper.py (la de W3, del gráfico y de las fichas).
    frases = []
    for lugar, t in textos:   # también con énfasis de Markdown o letras de otro alfabeto disfrazadas de latinas (L117)
        frases += [f"{lugar}: «{x[:40]}»" for x in buscar_d15(normalizar(t))]
    for lugar, t in titulos:
        if TITULO_DE_ANALISIS.match(normalizar_titulo(latinizar(normalizar(t)))):
            frases.append(f"{lugar}: empieza como un título de análisis («{' '.join(normalizar(t).split()[:2])[:30]}»)")
    chk("sin lenguaje de análisis: ni conclusiones, recomendaciones, causas, juicios ni decisiones (D15)", not frases,
        "dice lo preguntado y lo medido; el análisis queda para las personas" if not frases else "; ".join(frases[:8]))

    fuente = (proc.get("fuente") or {}).get("titulo") if isinstance(proc.get("fuente"), dict) else None
    fuente = fuente or proc.get("cita")
    consultado = str(proc.get("consultado") or "")[:10]
    try:
        date.fromisoformat(consultado)
        ok_f = isinstance(fuente, str) and bool(fuente.strip())
    except ValueError:
        ok_f = False
    chk("fuente y fecha de consulta tomadas de la procedencia", ok_f,
        f"«{fuente}», consultado {consultado}" if ok_f else "la procedencia no trae fuente o fecha: la lámina no se puede citar")

    # barridos sobre lo que se publica: textos con las cifras puestas y celdas de las tablas
    publicados = [poner_cifras(t, escritas) for _, t in textos]
    publicados += [txt for cols, cuerpo in tablas.values() for txt in cols + [v for fila in cuerpo for v, _ in fila]]
    publicados = [" ".join(x.split()) for x in publicados]      # sin rachas de espacios: los barridos no se atascan
    ordenes = [t[:60] for t in publicados if parece_instruccion(t)]
    chk("sin textos con forma de instrucción para una IA", not ordenes, "ninguno" if not ordenes else f"{ordenes[:2]}")
    invis = [t[:40] for t in publicados + [t for _, t in textos] + [str(x.get("tipo")) for x in preg] if invisibles_en(t)]
    # una palabra que se lee latina con una letra de otro alfabeto («concluye» con la «o» cirílica) en un texto de la IA
    # es un disfraz para las listas (L117); en las celdas de la tabla vienen los datos, no se miran aquí
    disfraz = [lugar for lugar, t in textos if letras_disfrazadas(t)] + [f"tipo de la pregunta {k}" for k, x in enumerate(preg, 1)
                                                                       if letras_disfrazadas(x.get("tipo"))]
    chk("sin caracteres invisibles o bidireccionales", not invis and not disfraz,
        "ninguno" if not invis and not disfraz else "; ".join(([f"{len(invis)} textos con invisibles"] if invis else [])
                                                             + ([f"letras de otro alfabeto que se leen como latinas en: {', '.join(disfraz[:5])}"]
                                                                if disfraz else [])))
    pii = escanear_texto(" ".join(x[:MAX_TEXTO] for x in publicados))
    chk("sin datos personales en los textos ni en las tablas", not pii, str(pii or "ninguno"))

    return checks, {"pres": pres, "ctx": ctx, "cifras": cifras, "escritas": escritas, "tablas": tablas, "proc": proc,
                    "graf_ok": graf.get("estado") == "aprobado", "informe_final": (c / "informe_final.html").exists(),
                    "whitepaper": (c / "whitepaper.md").exists()}


# ---------------------------------------------------------------- plantilla ----------------------------------------------------------------
CSS = """
:root{color-scheme:light;--bg:#f1f0ec;--slide:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#6b6964;--line:#e1e0d9;--accent:#2a78d6;--wash:rgba(42,120,214,.10)}
@media (prefers-color-scheme:dark){:root{color-scheme:dark;--bg:#0d0d0d;--slide:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#a3a19b;--line:#2c2c2a;--accent:#3987e5;--wash:rgba(57,135,229,.14)}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:var(--accent)}
.slide{width:min(1100px,100vw - 32px);aspect-ratio:16/9;margin:24px auto;background:var(--slide);border:1px solid var(--line);border-radius:12px;
  padding:40px 48px 28px;display:flex;flex-direction:column;overflow:hidden}
.slide.final{overflow:visible}
.kicker{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:0 0 8px}
h1,h2{margin:0 0 10px;line-height:1.18;letter-spacing:-.01em;max-width:30em}h1{font-size:34px}h2{font-size:27px}
.sub{color:var(--ink2);margin:0 0 14px}.body{flex:1;min-height:0;display:flex;flex-direction:column;gap:12px}
.foot{font-size:12px;color:var(--muted);border-top:1px solid var(--line);padding-top:8px;margin-top:10px}
.preg{font-size:20px;color:var(--ink2);margin:0 0 12px}
ol.res{margin:0;padding-left:22px;font-size:20px}ol.res li{margin:0 0 10px}
.hero{font-size:72px;font-weight:700;letter-spacing:-.02em;margin:10px 0 0}.nota{color:var(--ink2);border-left:3px solid var(--accent);padding:4px 12px;margin:0}
.marco{flex:1;min-height:0;overflow:hidden;border-radius:8px;background:#fff}
.marco iframe{display:block;border:0;width:100%;height:640px;zoom:.72}
.centro{justify-content:center}
table{border-collapse:collapse;width:100%;font-size:15px}th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line)}
th{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.dec{background:var(--wash);border-radius:10px;padding:14px 16px;font-size:17px}ul.lim{margin:0;padding-left:20px}
.dos{display:grid;grid-template-columns:1fr 1fr;gap:24px}.dos h3{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--accent);margin:0 0 8px}
.dos ol,.dos ul{margin:0;padding-left:20px;font-size:16px}.dos li{margin:0 0 8px}.tipo{font-weight:700}
@media print{body{background:#fff}.slide{width:100%;margin:0;border:0;border-radius:0;page-break-after:always}@page{size:landscape;margin:0}}
@media (max-width:700px){.slide{aspect-ratio:auto;padding:24px 18px}.dos{grid-template-columns:1fr}.hero{font-size:48px}h1{font-size:26px}h2{font-size:21px}}
"""


def _e(x):
    return html.escape(str(x if x is not None else ""))


def renderizar(datos):
    pres, escritas, proc = datos["pres"], datos["escritas"], datos["proc"]

    def tx(t):
        return _e(poner_cifras(t, escritas))
    fuente = (proc.get("fuente") or {}).get("titulo") if isinstance(proc.get("fuente"), dict) else None
    try:
        fecha = f"{date.fromisoformat(str(proc.get('consultado'))[:10]):%d-%m-%Y}"
    except ValueError:
        fecha = "sin fecha de consulta"
    cita = str(proc.get("cita") or fuente or "fuente sin declarar")
    pie = f'<div class="foot">Fuente: {_e(cita)}' + ("" if fecha in cita else f" · consultado el {_e(fecha)}") + "</div>"
    a, med = pres["lo_preguntado_y_lo_medido"], pres["mediciones"]
    L = []
    L.append(f'<section class="slide"><p class="kicker">Lo preguntado y lo medido</p><p class="preg">{tx(a["pregunta"])}</p>'
             f'<h1>{tx(a["titulo"])}</h1><div class="body centro"><p class="nota"><b>Situación:</b> {tx(a["situacion"])}</p>'
             '<p class="dec">Lo que esto significa lo concluyen las personas: las preguntas para ellas van al final.</p></div>'
             f"{pie}</section>")
    L.append('<section class="slide"><p class="kicker">Lo medido, en orden</p><h2>' + tx(a["titulo"]) + '</h2><div class="body"><ol class="res">'
             + "".join(f"<li>{tx(h['titulo'])}</li>" for h in med) + f"</ol></div>{pie}</section>")
    for i, h in enumerate(med, 1):
        ev = h["evidencia"]
        t = ev["tipo"]
        if t == "grafico":
            cuerpo = '<div class="marco"><iframe src="grafico.html" title="Gráfico aprobado" sandbox="allow-scripts"></iframe></div>'
        elif t == "tabla":
            cols, filas = datos["tablas"][i]
            head = "".join(f"<th>{_e(c)}</th>" for c in cols)
            cuerpo = (f"<table><thead><tr>{head}</tr></thead><tbody>"
                      + "".join("<tr>" + "".join(f'<td class="n">{_e(v)}</td>' if n else f"<td>{_e(v)}</td>" for v, n in fila) + "</tr>" for fila in filas)
                      + "</tbody></table>")
        else:
            cuerpo = f'<p class="hero">{_e(escritas.get(ev["cifra"]))}</p>'
        nota = f'<p class="nota">{tx(h.get("nota"))}</p>' if h.get("nota") else ""
        L.append(f'<section class="slide"><p class="kicker">Medición {i} de {len(med)}</p><h2>{tx(h["titulo"])}</h2>'
                 f'<div class="body">{cuerpo}{nota}</div>{pie}</section>')
    m = pres["metodo_y_limites"]
    n_fuente = proc.get("filas")
    L.append('<section class="slide"><p class="kicker">Método y límites</p><h2>Qué se hizo, con qué incertidumbre y qué queda abierto</h2><div class="body">'
             f'<p><b>Método:</b> {tx(m["metodo"])}</p><p><b>Incertidumbre:</b> {tx(m["incertidumbre"])}</p>'
             + (f"<p><b>Filas de la fuente:</b> {_e(formato_co(float(n_fuente)))}</p>"
                if isinstance(n_fuente, (int, float)) and not isinstance(n_fuente, bool) and math.isfinite(float(n_fuente)) else "")
             + '<ul class="lim">' + "".join(f"<li>{tx(x)}</li>" for x in m["limites"]) + f"</ul></div>{pie}</section>")
    titulos = [a["titulo"]] + [h["titulo"] for h in med]
    orden = {t: k for k, t in enumerate(TIPOS_DE_PREGUNTA)}
    preg = sorted(pres["preguntas_para_las_personas"], key=lambda x: orden.get(normalizar_titulo(x["tipo"]).strip(" ."), 9))
    anexo = [x for x, ok in (('<a href="whitepaper.md">whitepaper</a>', datos["whitepaper"]),
                             ('<a href="informe_final.html">informe final</a>', datos["informe_final"]),
                             ('<a href="grafico.html">gráfico</a>', datos["graf_ok"])) if ok]
    L.append('<section class="slide final"><p class="kicker">Para el análisis de las personas</p>'
             "<h2>Lo medido, en orden, y las preguntas que responden las personas</h2>"
             '<div class="body"><div class="dos"><div><h3>Lo medido (si solo se leen los títulos, ¿se entiende?)</h3><ol>'
             + "".join(f"<li>{tx(t)}</li>" for t in titulos) + "</ol></div><div><h3>Preguntas para las personas</h3><ul>"
             + "".join(f'<li><span class="tipo">{_e(normalizar_titulo(x["tipo"]).strip(" .").capitalize())}.</span> {tx(x["pregunta"])}</li>' for x in preg)
             + "</ul></div></div>"
             + f'<p class="dec">El análisis y la conclusión son de las personas: cada grupo escoge una pregunta, escribe su hipótesis antes de mirar '
               f'y la responde en <a href="{PLANTILLA}">plantillas/analisis_humano.md</a>. La IA solo resumió lo medido.</p>'
             + (f'<p class="sub">Anexo: {" · ".join(anexo)}</p>' if anexo else "") + "</div>" + pie + "</section>")
    titulo_doc = _e(poner_cifras(a["titulo"], escritas)[:80])
    return (f'<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{titulo_doc}</title><style>{CSS}</style></head><body>{''.join(L)}</body></html>")


# ---------------------------------------------------------------- autoprueba ----------------------------------------------------------------
def _base():
    """Ventas sintéticas en pesos (no son datos reales) y una presentación que cumple todo."""
    resultado = [{"region": r, "ventas": v * 1e6, "pedidos": p} for r, v, p in
                 [("Norte", 420, 60), ("Centro", 300, 50), ("Sur", 150, 30), ("Oriente", 80, 12), ("Occidente", 50, 8)]]
    pct = lambda parte: {"op": "porcentaje", "parte": parte, "total": {"op": "suma", "columna": "ventas"}}  # noqa: E731
    pres = {
        "lo_preguntado_y_lo_medido": {
            "situacion": "La empresa vende en {n_regiones} regiones y registra cada venta del semestre con su región.",
            "pregunta": "¿Cuánto vendió cada región en el primer semestre de 2026?",
            "titulo": "Las {n_regiones} regiones vendieron {total} de pesos en el primer semestre de 2026"},
        "mediciones": [
            {"titulo": "El Norte vendió {norte} de pesos y las regiones menores juntas sumaron {menores}",
             "evidencia": {"tipo": "tabla", "columnas": ["region", "ventas"], "orden": "ventas", "filas": 5},
             "nota": "Las regiones menores son el Sur, el Oriente y el Occidente."},
            {"titulo": "Las regiones Norte y Centro reúnen el {top2} de las ventas del semestre",
             "evidencia": {"tipo": "cifra", "cifra": "top2"}, "nota": "El resto se reparte entre las otras regiones."},
        ],
        "metodo_y_limites": {"metodo": "Suma de ventas aprobadas por región, calculada por dos implementaciones independientes.",
                             "incertidumbre": "No aplica: son todas las ventas del semestre, no una muestra.",
                             "limites": ["P1: no se sabe si las devoluciones se restan; por defecto no se restan."]},
        "preguntas_para_las_personas": [
            {"tipo": "costo", "pregunta": "¿Qué cuesta mantener el mismo inventario en las {n_regiones} regiones durante el semestre?"},
            {"tipo": "calidad", "pregunta": "¿Cambia el orden de las regiones si se restan las devoluciones (P1)?"},
            {"tipo": "impacto", "pregunta": "¿Qué clientes se quedan sin producto cuando una región agota su inventario?"},
        ],
        "cifras": [
            {"id": "n_regiones", "calculo": {"op": "conteo"}},
            {"id": "total", "calculo": {"op": "suma", "columna": "ventas"}, "formato": {"escala": "millones", "decimales": 0}},
            {"id": "norte", "calculo": {"op": "valor", "columna": "ventas", "donde": {"region": "Norte"}}, "formato": {"escala": "millones", "decimales": 0}},
            {"id": "menores", "calculo": {"op": "diferencia", "a": {"op": "suma", "columna": "ventas"},
                                          "b": {"op": "suma_primeros", "columna": "ventas", "n": 2}}, "formato": {"escala": "millones", "decimales": 0}},
            {"id": "top2", "calculo": pct({"op": "suma_primeros", "columna": "ventas", "n": 2}), "formato": {"decimales": 0}},
        ],
    }
    return resultado, pres


def _forma_vieja():
    """Una presentación con la forma anterior al 6-nov (decisión, SCQA completo, hallazgos y recomendación)."""
    return {"respuesta": {"titulo": "La región Norte vende el {top2} del total del semestre y lidera las ventas por región",
                          "decision": "Si se refuerza el inventario del Norte antes que el de las demás regiones."},
            "scqa": {"situacion": "La empresa vende en varias regiones.", "complicacion": "Las ventas no se reparten igual.",
                     "pregunta": "¿Dónde poner el inventario?", "respuesta": "En el Norte primero."},
            "hallazgos": [{"titulo": "Las regiones Norte y Centro concentran el {top2} de las ventas del semestre",
                           "evidencia": {"tipo": "cifra", "cifra": "top2"}}],
            "metodo_y_limites": {"metodo": "Suma de ventas por región.", "incertidumbre": "No aplica: no es una muestra.",
                                 "limites": ["P1: devoluciones sin restar."]},
            "recomendacion": {"que": "Reforzar el inventario del Norte", "quien": "Gerencia comercial",
                              "proximo_paso": "Plan de inventario", "como_se_mide": "Ventas del próximo semestre"},
            "cifras": [{"id": "top2", "calculo": {"op": "porcentaje", "parte": {"op": "suma_primeros", "columna": "ventas", "n": 2},
                                                  "total": {"op": "suma", "columna": "ventas"}}}]}


def _corrida(d, resultado, pres, estado="aprobado", supuestos=()):
    d.mkdir(parents=True, exist_ok=True)
    (d / "informe.json").write_text(json.dumps({"estado": estado, "resultado_oficial": resultado, "preguntas_abiertas": 1}, ensure_ascii=False), encoding="utf-8")
    (d / "spec.json").write_text(json.dumps({"peticion": "Ventas por región del primer semestre de 2026", "preguntas": [{"id": "P1"}],
                                             "supuestos": list(supuestos),
                                             "definiciones": {"venta_grande": "venta de más de 100.000 pesos"}}, ensure_ascii=False), encoding="utf-8")
    (d / "procedencia.json").write_text(json.dumps({"fuente": {"titulo": "Ventas sintéticas", "conjunto": "abcd-12ef"}, "consultado": "2026-11-06T08:00:00",
                                                    "filas": 160, "cita": "Ventas sintéticas del ejemplo (conjunto abcd-12ef), consultado el 06-11-2026"},
                                                   ensure_ascii=False), encoding="utf-8")
    (d / "presentacion.json").write_text(json.dumps(pres, ensure_ascii=False), encoding="utf-8")


def _muestras():
    """Un texto con datos personales y otro con una orden para una IA, tomados de las baterías del repositorio."""
    import csv
    raiz = AQUI.parent
    pii = orden = None
    try:
        with open(raiz / "baterias" / "privacidad" / "con_datos_personales.csv", newline="", encoding="utf-8") as fh:
            pii = next((v for fila in csv.DictReader(fh) for v in fila.values() if v and escanear_texto(v)), None)
        orden = next((x for x in (raiz / "baterias" / "inyeccion" / "maliciosos.txt").read_text(encoding="utf-8").splitlines()
                      if parece_instruccion(x) and len(x) < MAX_TEXTO), None)
    except OSError:
        pass
    if not pii or not orden:
        raise SystemExit("faltan las muestras de baterias/privacidad o baterias/inyeccion")
    return pii[:MAX_CELDA], orden


def autoprueba():
    import copy
    resultado, base = _base()

    def mut(f, sobre=None):
        p = copy.deepcopy(sobre or base)
        f(p)
        return p

    def nota(texto, i=1):
        return lambda p: p["mediciones"][i].update(nota=texto)

    def titulo(texto, i=1):
        return lambda p: p["mediciones"][i].update(titulo=texto)

    def apertura(**k):
        return lambda p: p["lo_preguntado_y_lo_medido"].update(**k)

    def con_mas_mediciones(p):
        p["mediciones"].append({"titulo": "La región Norte registró {pedidos_norte} pedidos, el mayor número entre las {n_regiones} regiones",
                                "evidencia": {"tipo": "tabla", "columnas": ["region", "pedidos", "ventas"], "orden": "pedidos", "filas": 3},
                                "nota": "Los pedidos se cuentan por región, no por cliente."})
        p["cifras"].append({"id": "pedidos_norte", "calculo": {"op": "valor", "columna": "pedidos", "donde": {"region": "Norte"}}})
        p["preguntas_para_las_personas"] += [
            {"tipo": "Calidad", "pregunta": "¿Qué ventas quedan por fuera si una región registra tarde sus pedidos?"},
            {"tipo": "impacto", "pregunta": "¿Qué parte de los {pedidos_norte} pedidos del Norte llega a tiendas de barrio?"}]
    datos_nan = copy.deepcopy(resultado)
    datos_nan[2]["ventas"] = float("nan")
    datos_pii = copy.deepcopy(resultado)
    # Las muestras maliciosas se leen de las baterías (ahí viven los casos de prueba): el código no las trae escritas.
    muestra_pii, muestra_orden = _muestras()
    muestra_disfrazada = next((x for x in (AQUI.parent / "baterias" / "inyeccion" / "maliciosos.txt").read_text(encoding="utf-8").splitlines()
                               if letras_disfrazadas(x) and len(x) < MAX_TEXTO), None)
    if not muestra_disfrazada:
        raise SystemExit("falta en baterias/inyeccion una orden con letras de otro alfabeto")
    datos_pii[4]["region"] = muestra_pii
    casi_todo = {"op": "porcentaje", "parte": {"op": "diferencia", "a": {"op": "suma", "columna": "ventas"}, "b": {"op": "suma", "columna": "pedidos"}},
                 "total": {"op": "suma", "columna": "ventas"}}
    SIN_ANALISIS = "sin lenguaje de análisis"
    NUMEROS = "los números los escribe"
    # (nombre, presentación, resultado, estado, supuestos, comprobación que debe fallar o None si debe aprobar)
    casos = [
        # control positivo: si una buena no aprueba, los mutantes no prueban nada
        ("base", base, resultado, "aprobado", (), None),
        ("base con una tabla de tres columnas y cinco preguntas", mut(con_mas_mediciones), resultado, "aprobado", (), None),
        ("base con un año de la petición y una cifra negativa",
         mut(lambda p: (p["mediciones"][1].update(nota="En 2026 el Sur queda a {dif} de pesos del Norte."),
                        p["cifras"].append({"id": "dif", "calculo": {"op": "diferencia", "a": {"op": "valor", "columna": "ventas", "donde": {"region": "Sur"}},
                                                                     "b": {"op": "valor", "columna": "ventas", "donde": {"region": "Norte"}}},
                                            "formato": {"escala": "millones", "decimales": 0}}))), resultado, "aprobado", (), None),
        ("base con citas selladas y cardinales en el método",
         mut(lambda p: p["metodo_y_limites"].update(metodo="Se calculó dos veces, con dos implementaciones, sobre el conjunto abcd-12ef.",
                                                     limites=p["metodo_y_limites"]["limites"] + ["Hay riesgo de doble conteo en las ventas de más de 100.000 pesos."])),
         resultado, "aprobado", (), None),
        ("base con un «donde» numérico sobre una columna decimal (420000000 es 420000000.0; por su texto no lo era)",
         mut(lambda p: (p["cifras"].append({"id": "pedidos_420", "calculo": {"op": "valor", "columna": "pedidos", "donde": {"ventas": 420000000}}}),
                        p["mediciones"][1].update(nota="La región que más vende registró {pedidos_420} pedidos."))),
         resultado, "aprobado", (), None),
        # los números los escribe el código
        ("dígito escrito a mano", mut(nota("Es 3 veces lo del año pasado.")), resultado, "aprobado", (), NUMEROS),
        ("marcadores pegados", mut(nota("Entre todas suman {n_regiones}{norte}.")), resultado, "aprobado", (), NUMEROS),
        ("moneda junto a un marcador", mut(nota("El Norte vendió {n_regiones} USD por pedido.")), resultado, "aprobado", (), NUMEROS),
        ("carácter numérico que no es dígito", mut(nota("Creció ❹ puntos frente al año pasado.")), resultado, "aprobado", (), NUMEROS),
        ("cardinal en un título", mut(titulo("Catorce de las quince tiendas reúnen el {top2} de las ventas del semestre")),
         resultado, "aprobado", (), NUMEROS),
        ("id de supuesto con forma de número", mut(nota("Según 90, el resto se reparte entre las otras regiones.")),
         resultado, "aprobado", ({"id": "90", "decision": "x"},), NUMEROS),
        ("número con palabras", mut(nota("Es la mitad de lo del año pasado.")), resultado, "aprobado", (), NUMEROS),
        ("porcentaje fuera de un marcador", mut(titulo("Las regiones Norte y Centro reúnen el {norte} % de las ventas del semestre")),
         resultado, "aprobado", (), NUMEROS),
        ("dígito disfrazado (superíndice)", mut(nota("Creció 10⁶ veces.")), resultado, "aprobado", (), NUMEROS),
        ("marcador desconocido", mut(nota("Sube {inventada} frente al año pasado.")), resultado, "aprobado", (), NUMEROS),
        ("número escrito a mano en una pregunta para las personas",
         mut(lambda p: p["preguntas_para_las_personas"][0].update(pregunta="¿Qué cuesta mantener 5 bodegas abiertas todo el semestre?")),
         resultado, "aprobado", (), NUMEROS),
        # cada cifra se calcula desde los datos
        ("redondeo que muestra 100 %", mut(lambda p: (p["cifras"].append({"id": "casi", "calculo": casi_todo, "formato": {"decimales": 0}}),
                                                       p["mediciones"][1].update(nota="Sin los pedidos queda el {casi} de las ventas."))),
         resultado, "aprobado", (), "cada cifra se calcula"),
        ("redondeo que muestra 0", mut(lambda p: (p["cifras"].append({"id": "occ", "calculo": {"op": "valor", "columna": "ventas", "donde": {"region": "Occidente"}},
                                                                     "formato": {"escala": "billones", "decimales": 0}}),
                                                  p["mediciones"][1].update(nota="El Occidente vende {occ}."))),
         resultado, "aprobado", (), "cada cifra se calcula"),
        ("constante anidada (conteo primeros)", mut(lambda p: p["cifras"][4].update(calculo={"op": "porcentaje", "parte": {"op": "conteo", "primeros": 4},
                                                                                               "total": {"op": "conteo", "primeros": 5}})),
         resultado, "aprobado", (), "cada cifra se calcula"),
        ("«como» de las hipótesis (historial)", mut(lambda p: p["cifras"][2]["calculo"].update(como="porcentaje")), resultado, "aprobado", (), "cada cifra se calcula"),
        ("cifra de una hipótesis de la IA (historial)",
         mut(lambda p: (p["cifras"].append({"id": "h1", "calculo": {"op": "hipotesis", "id": "H1", "campo": "valor"}}),
                        p["mediciones"][1].update(nota="La hipótesis da {h1}."))), resultado, "aprobado", (), "cada cifra se calcula"),
        ("NaN en los datos", base, datos_nan, "aprobado", (), "cada cifra se calcula"),
        # «donde» que no señala ninguna fila: una errata no se publica como 0 (L111)
        ("suma con un «donde» mal escrito (daba 0)",
         mut(lambda p: (p["cifras"].append({"id": "norte_mal", "calculo": {"op": "suma", "columna": "ventas", "donde": {"region": "Nortee"}},
                                            "formato": {"escala": "millones", "decimales": 0}}),
                        p["mediciones"][1].update(nota="La región del norte vendió {norte_mal} de pesos."))),
         resultado, "aprobado", (), "cada cifra se calcula"),
        ("conteo con un «donde» mal escrito (daba 0)",
         mut(lambda p: (p["cifras"].append({"id": "filas_norte", "calculo": {"op": "conteo", "donde": {"region": "NORTE"}}}),
                        p["mediciones"][1].update(nota="La región del norte aparece en {filas_norte} filas del resultado."))),
         resultado, "aprobado", (), "cada cifra se calcula"),
        ("«donde» que compara un número con el texto de una celda decimal (420000000.0 no es «420000000»)",
         mut(lambda p: (p["cifras"].append({"id": "pedidos_mal", "calculo": {"op": "suma", "columna": "pedidos", "donde": {"ventas": "420000000"}}}),
                        p["mediciones"][1].update(nota="La región que más vende registró {pedidos_mal} pedidos."))),
         resultado, "aprobado", (), "cada cifra se calcula"),
        # forma
        ("cifra con texto escrito a mano", mut(lambda p: p["cifras"][0].update(texto="48 %")), resultado, "aprobado", (), "forma de la ficha"),
        ("nota que no es texto", mut(lambda p: p["mediciones"][0].update(nota=["9.999 millones"])), resultado, "aprobado", (), "forma de la ficha"),
        ("JSON con lo preguntado y lo medido como texto", mut(lambda p: p.update(lo_preguntado_y_lo_medido="El Norte gana")),
         resultado, "aprobado", (), "forma de la ficha"),
        ("campo «recomendacion» de la forma anterior", mut(lambda p: p.update(recomendacion={"que": "Reforzar el inventario del Norte"})),
         resultado, "aprobado", (), "forma de la ficha"),
        ("campo «decision» de la forma anterior", mut(apertura(decision="Si se refuerza el inventario del Norte.")),
         resultado, "aprobado", (), "forma de la ficha"),
        ("presentación entera con la forma anterior al 6-nov", _forma_vieja(), resultado, "aprobado", (), "forma de la ficha"),
        ("campo de más en una medición", mut(lambda p: p["mediciones"][0].update(conclusion="El Norte es la mejor región.")),
         resultado, "aprobado", (), "forma de la ficha"),
        ("evidencia de una hipótesis de la IA (historial)", mut(lambda p: p["mediciones"][1].update(evidencia={"tipo": "hipotesis", "id": "H1"})),
         resultado, "aprobado", (), "forma de la ficha"),
        # títulos que dicen lo medido
        ("título de tema", mut(titulo("Ventas por región", 0)), resultado, "aprobado", (), "títulos que dicen lo medido"),
        ("título sin cifra", mut(titulo("El Norte es la región que más vende entre todas las del país", 0)),
         resultado, "aprobado", (), "títulos que dicen lo medido"),
        # lo preguntado y lo medido
        ("pregunta de la apertura sin signos", mut(apertura(pregunta="Cuánto vendió cada región en el primer semestre de 2026")),
         resultado, "aprobado", (), "lo preguntado y lo medido"),
        # método y límites
        ("sin límites", mut(lambda p: p["metodo_y_limites"].update(limites=[])), resultado, "aprobado", (), "método, incertidumbre"),
        ("pregunta abierta sin nombrar", mut(lambda p: p["metodo_y_limites"].update(limites=["Las devoluciones no se restan."])),
         resultado, "aprobado", (), "método, incertidumbre"),
        # preguntas para las personas
        ("preguntas sin los tres tipos", mut(lambda p: [x.update(tipo="costo") for x in p["preguntas_para_las_personas"]]),
         resultado, "aprobado", (), "preguntas para las personas"),
        ("pregunta para las personas sin signos",
         mut(lambda p: p["preguntas_para_las_personas"][1].update(pregunta="Cambia el orden de las regiones si se restan las devoluciones (P1)")),
         resultado, "aprobado", (), "preguntas para las personas"),
        ("solo dos preguntas para las personas", mut(lambda p: p["preguntas_para_las_personas"].pop()), resultado, "aprobado", (), "preguntas para las personas"),
        ("sin preguntas para las personas", mut(lambda p: p.update(preguntas_para_las_personas=[])), resultado, "aprobado", (), "preguntas para las personas"),
        # D15: lenguaje de análisis en cualquier texto
        ("recomendación escondida en una nota", mut(nota("Lo siguiente sería claro: se recomienda empezar por el inventario del Norte.")),
         resultado, "aprobado", (), SIN_ANALISIS),
        ("«se debe a» en un título", mut(titulo("La ventaja del Norte, que vendió {norte} de pesos, se debe a la temporada de fin de año", 0)),
         resultado, "aprobado", (), SIN_ANALISIS),
        ("«por eso hay que» en un título", mut(titulo("El Norte vendió {norte} de pesos y por eso hay que reforzar su inventario", 0)),
         resultado, "aprobado", (), SIN_ANALISIS),
        ("conclusión en la situación", mut(apertura(situacion="La empresa vende en {n_regiones} regiones; esto demuestra que el Norte es la más rentable.")),
         resultado, "aprobado", (), SIN_ANALISIS),
        ("pregunta para las personas que trae la respuesta",
         mut(lambda p: p["preguntas_para_las_personas"][2].update(pregunta="¿Por qué el Norte debería recibir primero el inventario?")),
         resultado, "aprobado", (), SIN_ANALISIS),
        ("recomendación en un límite", mut(lambda p: p["metodo_y_limites"].update(limites=["P1: se recomienda restar las devoluciones."])),
         resultado, "aprobado", (), SIN_ANALISIS),
        ("decisión pedida en el método", mut(lambda p: p["metodo_y_limites"].update(metodo="Suma por región; lo que se pide decidir es dónde va el inventario.")),
         resultado, "aprobado", (), SIN_ANALISIS),
        ("título que empieza como hallazgo", mut(titulo("Hallazgo principal: el Norte vendió {norte} de pesos en el semestre", 0)),
         resultado, "aprobado", (), SIN_ANALISIS),
        ("«la mayoría» en una nota (magnitud con palabras del whitepaper)", mut(nota("La mayoría de las ventas sale del Norte.")),
         resultado, "aprobado", (), NUMEROS),
    ] + [
        # la misma lista de frases que prueban el whitepaper y las fichas (validar_whitepaper.FRASES_D15)
        (f"D15 en una nota: «{frase[:48]}»", mut(nota(frase)), resultado, "aprobado", (), SIN_ANALISIS) for frase in FRASES_D15
    ] + [
        # resultado, evidencias y barridos
        ("resultado sin aprobar", base, resultado, "revisar", (), "el resultado que se presenta"),
        ("tabla con columna inexistente", mut(lambda p: p["mediciones"][0]["evidencia"].update(columnas=["region", "utilidad"])),
         resultado, "aprobado", (), "mediciones, cada una"),
        ("seis mediciones", mut(lambda p: p.update(mediciones=[dict(h, titulo=h["titulo"] + f" (parte {k})") for k in "abc" for h in p["mediciones"]])),
         resultado, "aprobado", (), "mediciones, cada una"),
        ("texto con orden para una IA", mut(apertura(situacion=muestra_orden)), resultado, "aprobado", (), "forma de instrucción"),
        ("carácter bidireccional", mut(lambda p: p["mediciones"][0].update(nota="Las regiones ‮menores‬ son tres.")),
         resultado, "aprobado", (), "invisibles"),
        # letras de otro alfabeto que se leen como latinas (la «o» cirílica, escrita como \u): un disfraz para las listas (L117)
        ("palabra con una letra de otro alfabeto en una nota", mut(nota("El N\u043erte vende lo que dice la tabla.")),
         resultado, "aprobado", (), "invisibles"),
        ("título que empieza como conclusión, con una letra de otro alfabeto",
         mut(titulo("C\u043enclusión: el Norte vendió {norte} de pesos en el semestre", 0)), resultado, "aprobado", (), SIN_ANALISIS),
        ("orden para una IA con letras de otro alfabeto", mut(apertura(situacion=muestra_disfrazada)), resultado, "aprobado", (),
         "forma de instrucción"),
        ("dato personal en una celda de la tabla", base, datos_pii, "aprobado", (), "datos personales"),
    ]
    raiz = Path(tempfile.mkdtemp(prefix="autoprueba-presentacion-"))
    fallas, sin_control = [], False

    def correr(i, caso):
        nombre, pres, res, estado, supuestos, debe_fallar = caso
        d = raiz / f"c{i}"
        _corrida(d, res, pres, estado, supuestos)
        try:
            checks, _ = comprobar(d)
        except Exception as e:      # el verificador nunca debe caerse
            checks = [{"comprobacion": f"el verificador se cayó ({type(e).__name__})", "ok": False}]
        rotas = [x["comprobacion"] for x in checks if not x["ok"]]
        if debe_fallar is None:
            ok = not rotas
            print(f"{'✓' if ok else '✗'} bueno «{nombre}»: {'aprueba' if ok else rotas}")
        else:
            ok = any(debe_fallar in x for x in rotas) and not any("se cayó" in x for x in rotas)
            print(f"{'✓' if ok else '✗'} mutante «{nombre}»: {'atrapado' if ok else 'NO atrapado'} · falla {rotas}")
        if not ok:
            fallas.append(nombre)
        return ok

    buenos = [x for x in casos if x[5] is None]
    mutantes = [x for x in casos if x[5] is not None]
    try:
        print("Control positivo (las buenas deben aprobar):")
        for i, caso in enumerate(buenos):
            correr(i, caso)
        if fallas:
            sin_control = True
            print("Sin control positivo, los mutantes no prueban nada: no se corren.")
        else:
            print("Mutantes (cada uno debe fallar en la comprobación que le corresponde):")
            for i, caso in enumerate(mutantes, len(buenos)):
                correr(i, caso)
    finally:
        shutil.rmtree(raiz, ignore_errors=True)
    atrapados = 0 if sin_control else len(mutantes) - len([f for f in fallas if f not in {b[0] for b in buenos}])
    print("RESUMEN " + json.dumps({"autoprueba": "aprobada" if not fallas else "revisar", "buenos": len(buenos), "mutantes": len(mutantes),
                                   "atrapados": atrapados, "fallas": fallas}, ensure_ascii=False))
    return 0 if not fallas else 1


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    if argv[0] == "--autoprueba":
        return autoprueba()
    c = Path(argv[0]).resolve()
    try:
        checks, datos = comprobar(c)
    except Exception as e:                         # nunca se cae: un error es una comprobación fallida
        checks, datos = [{"comprobacion": "el verificador terminó sin errores", "ok": False, "detalle": f"{type(e).__name__}: {str(e)[:200]}"}], None
    ok = all(x["ok"] for x in checks)
    html_ruta = c / "presentacion.html"
    pagina = None
    if ok and datos is not None:
        try:
            pagina = renderizar(datos)
        except Exception as e:
            checks.append({"comprobacion": "las láminas se arman sin errores", "ok": False, "detalle": f"{type(e).__name__}: {str(e)[:200]}"})
            ok = False
    if ok and pagina is not None:
        html_ruta.write_text(pagina, encoding="utf-8")
    elif html_ruta.exists():
        html_ruta.unlink()                         # no queda una presentación vieja que parezca aprobada
    titulos, preguntas = [], []
    if ok and datos is not None:                   # solo lo aprobado se copia a la salida
        pres, esc = datos["pres"], datos["escritas"]
        titulos = [poner_cifras(pres["lo_preguntado_y_lo_medido"]["titulo"], esc)] + [poner_cifras(h["titulo"], esc) for h in pres["mediciones"]]
        preguntas = [{"tipo": normalizar_titulo(x["tipo"]).strip(" ."), "pregunta": poner_cifras(x["pregunta"], esc)}
                     for x in pres["preguntas_para_las_personas"]]
    out = {"estado": "aprobado" if ok else "revisar", "comprobaciones": checks, "titulos_en_orden": titulos,
           "preguntas_para_las_personas": preguntas, "plantilla_de_las_personas": PLANTILLA,
           "html": html_ruta.name if ok and datos is not None else None}
    (c / "presentacion_verificacion.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    for x in checks:
        print(f"{'✓' if x['ok'] else '✗'} {x['comprobacion']}: {x['detalle']}")
    print("RESUMEN " + json.dumps({"estado": out["estado"], "fallas": [x["comprobacion"] for x in checks if not x["ok"]]}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
