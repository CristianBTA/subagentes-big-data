#!/usr/bin/env python3
"""Valida sin IA el whitepaper que escribe el documentador (etapa 3 · Análisis).

Uso:
  python herramientas/validar_whitepaper.py <corrida>       valida <corrida>/whitepaper.md y escribe whitepaper_verificacion.json
  python herramientas/validar_whitepaper.py --autoprueba    ejemplos ficticios buenos y malos: cada chequeo atrapa lo suyo

Desde el 6-nov-2026 el análisis lo hacen las personas del curso: la IA resume lo desarrollado para que ellas
analicen, pero no da el análisis. El whitepaper pasa si:
  W1 tiene las secciones obligatorias, en orden y con contenido: Pregunta · Datos y procedencia · Limpieza ·
     Cifra verificada y cómo se verificó · Gráfico · Gobernanza · Límites · Preguntas para el análisis de las personas;
  W2 cada cifra del texto está en los artefactos verificados de la corrida (informe.json, procedencia*.json,
     limpieza_*.json, gobernanza.json y grafico_verificacion.json, y solo si están aprobados), con tolerancia de
     redondeo. Cuentan los números de esos archivos, las cifras de los textos que escriben las herramientas (detalle,
     mensaje, cita, avisos…; no la prosa de la IA, como la razón del anticipo), el número de elementos de cada lista
     y el total de cada columna del resultado aprobado. Se permiten años, fechas, referencias legales y técnicas (Ley
     1581 de 2012, SHA-256, CC BY-SA 4.0) e identificadores (R1, P3, D15, el conjunto 3k7f-xp2m). Las cifras van con
     dígitos en formato colombiano (punto para miles, coma para decimales): no pasan agrupadas con espacios
     («12 000 000», también con el espacio de no separación), pegadas a letras («30k», «2,5M»), con caracteres
     numéricos que no son los dígitos del 0 al 9 («10⁶») ni escritas con palabras («treinta billones», «noventa y
     siete por ciento»; los cardinales sueltos hasta quince, como «dos implementaciones», y las unidades solas, como
     «en millones de pesos», cuentan el método y pasan). El destino de un enlace se imprime al lado del texto: sus
     números son cifras, salvo los del nombre de un archivo que existe junto al whitepaper o en el repositorio
     (L119); los de una dirección web no se comprueban (límite: la revisa una persona). Una magnitud con palabras
     («la mitad», «la mayoría») no se puede comprobar y no pasa. La sección de la cifra verificada cita al menos un
     total del resultado aprobado;
  W3 no trae conclusiones, recomendaciones, causas ni juicios («se concluye», «demuestra que», «esto muestra que»,
     «se recomienda», «recomendación», «debería», «próximo paso», «por eso», «se ahorra», «la causa es», «se debe a»,
     «preocupante», «alarmante», «excesivo»…), ni títulos de conclusiones, hallazgos o análisis. Es la lista D15
     (ANALISIS), la misma que importan la presentación, el gráfico, las fichas del agente masivo y el resumen de su
     whitepaper. Se busca en el texto tal cual y en como lo lee una persona (buscar_d15): el énfasis de Markdown
     («Esto *demuestra* que», «se **recomienda**»), las letras de ancho completo y las de otro alfabeto que se leen
     como latinas (la «o» cirílica) no esconden una frase (L117). Es una lista: una frase de análisis con otras
     palabras pasa, y la revisa una persona. Cada frase que una ficha o el encargo de las fichas nombran como
     prohibida está en la lista (la autoprueba las lee, L118); «grave» e «inflado» no se buscan, porque también
     nombran un dato o el método («faltas graves», «contarlas dos veces habría inflado el total»);
  W4 la sección de preguntas trae al menos 3, cada una con «¿» y «?», y al menos una de costo, una de calidad y
     una de impacto (rótulo al inicio de cada pregunta);
  W5 no trae instrucciones para agentes, datos personales (los patrones de gobernanza.py) ni texto oculto
     (comentarios HTML, marcado HTML, caracteres invisibles o bidireccionales) ni palabras disfrazadas con letras de
     otro alfabeto que se leen como latinas («concluye» con la «o» cirílica; una letra suelta, como la rho de una
     fórmula, no cuenta).
Un whitepaper es prosa breve: más de 200 KB, líneas de más de 4.000 caracteres o una validación de más de 60 s
lo rechazan (falla cerrado; así un texto hecho para trabar las expresiones regulares no detiene el pipeline).
Sale con 1 si algo falla. La salida guarda la huella del whitepaper validado y nunca copia un dato personal
(van enmascarados) ni un texto-instrucción.
"""
import hashlib
import json
import math
import re
import signal
import sys
import time
import unicodedata
from bisect import bisect_left, bisect_right
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from gobernanza import PATRONES, enmascarar, forma_canonica, latinizar, letras_disfrazadas, parece_instruccion  # noqa: E402

SECCIONES = [  # (título, patrón sobre el título normalizado: minúsculas, sin tildes ni numeración)
    ("Pregunta", r"(la )?pregunta\b"),
    ("Datos y procedencia", r"(los )?datos y (su )?procedencia\b"),
    ("Limpieza", r"(la )?limpieza\b"),
    ("Cifra verificada y cómo se verificó", r"(la )?cifra verificada\b"),
    ("Gráfico", r"(el )?grafico\b"),
    ("Gobernanza", r"(la )?gobernanza\b"),
    ("Límites", r"(los )?limites\b"),
    ("Preguntas para el análisis de las personas", r"preguntas para el analisis\b"),
]
CIFRA, PREGUNTAS = SECCIONES[3][0], SECCIONES[7][0]
TIPOS = ("costo", "calidad", "impacto")
CHEQUEOS = ("W1 secciones obligatorias", "W2 cifras de los artefactos verificados",
            "W3 sin conclusiones, recomendaciones ni causas", "W4 preguntas para las personas",
            "W5 sin instrucciones, datos personales ni texto oculto")
MAX_BYTES, LINEA_MAX, TIEMPO_MAX = 200_000, 4_000, 60

# W2 · de dónde salen las cifras verificadas
ESTADO_APROBADO = {"informe.json": "aprobado", "gobernanza.json": "aprobado", "grafico_verificacion.json": "aprobado",
                   "procedencia": "aprobada", "limpieza": "aprobada"}
TEXTOS_DE_HERRAMIENTA = {"detalle", "mensaje", "cita", "avisos", "ejemplos", "prueba", "comprobacion",
                         "consultado_legible", "motivos", "problemas", "licencia"}
SALTAR = {"caso_conocido"}   # el caso con respuesta conocida son datos ficticios: sus cifras no son de la corrida
MAGNITUDES = [(r"mil\s+billones", 1e15), (r"(?:mil|miles\s+de)\s+millones", 1e9), (r"bill[oó]n(?:es)?", 1e12),
              (r"mill[oó]n(?:es)?", 1e6), (r"mil", 1e3)]
MAGNITUD = re.compile(r"\s*(" + "|".join(p for p, _ in MAGNITUDES) + r")\b", re.I)
PORCENTAJE = re.compile(r"\s*(?:%|por\s+ciento\b)", re.I)
ES_NUMERO = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?")      # 17.248.249,69 · 49.662 · 17,2 · 2025
TOKEN = re.compile(r"(?<![\w.,])\d(?:[\d.,]{0,40}\d)?(?![\w])")
CIENTIFICA = re.compile(r"(?<![\w.,])(\d{1,20})(?:[.,](\d{1,20}))?[eE]([+-]?\d{1,4})(?![\w])")
CIFRA_DE_HERRAMIENTA = re.compile(r"\d+(?:[.,]\d+)*(?:[eE][+-]?\d+)?")
MES = (r"(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre|"
       r"ene|feb|mar|abr|may|jun|jul|ago|sept|sep|set|oct|nov|dic)")
PERMITIDOS = [  # se quitan antes de buscar cifras (se cambian por espacios: las posiciones no se mueven)
    re.compile(r"https?://\S+"),
    re.compile(r"(?<![\w-])(?=[0-9a-z]{0,3}[a-z]|[0-9a-z]{4}-[0-9a-z]{0,3}[a-z])[0-9a-z]{4}-[0-9a-z]{4}(?![\w-])"),  # conjunto 3k7f-xp2m
    re.compile(r"\b\d{4}-\d{1,2}-\d{1,2}(?:[T ]\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?)?\b"),   # 2026-11-06, con hora
    re.compile(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b"),                                    # 06-11-2026
    re.compile(rf"\b\d{{1,2}}(?:\s+de\s+|\s*[-/]\s*|\s+){MES}\b\.?(?:(?:\s+de\s+|\s*[-/]\s*|\s+)\d{{4}}\b)?", re.I),
    re.compile(rf"\b{MES}\b\.?(?:\s+de\s+|\s*[-/]\s*|\s+)\d{{4}}\b", re.I),             # noviembre de 2026
    re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b"),                                         # 05:29
    re.compile(r"\b(?:leyes|ley|decretos?|resoluci[oó]n(?:es)?|circular(?:es)?|conpes|acuerdos?|sentencias?|art[ií]culos?|"
               r"art\.|numerales?|literal(?:es)?|par[aá]grafos?)\s+(?:[A-Z]{1,2}-)?\d+(?:[.-]\d+)*"
               r"(?:\s*(?:,|y)\s*\d+(?:[.-]\d+)*)*(?:\s+de\s+(?:19|20)\d{2})?\b", re.I),   # Ley 1581 de 2012
    re.compile(r"\bISO(?:/IEC)?\s+\d+(?::\d{4})?|\bSHA-?\d+\b|\bCC\s+BY(?:-(?:SA|NC|ND))*\s+\d+(?:\.\d+)?\b|\bUTF-?\d+\b|"
               r"\bWCAG\s+\d+(?:\.\d+)*\b|\b(?:python|pandas|numpy|plotly|bandit)\s+\d+(?:\.\d+)+\b", re.I),
    re.compile(r"(?<!\w)_+|_+(?!\w)"),                                                   # cursivas con _ (no son identificadores)
    re.compile(r"\b\w*_\w*\b"),                                                          # columnas, marcas y archivos
    re.compile(r"\b[^\W\d_]+\d\w*\b"),                                                    # R1, P3, D15, CT07, log10
    re.compile(r"\b(?=[0-9a-f]*[a-f])(?=[0-9a-f]*\d)[0-9a-f]{7,}\b"),                     # huellas en hexadecimal
    re.compile(r"(?<![\w.,])(?:19|20)\d{2}(?![\w]|[.,]\d)"),                              # años
]
# Un enlace: el maquetado imprime su destino al lado del texto, así que sus números son cifras, salvo los del nombre de un
# archivo que existe (L119). Las mismas clases que whitepaper_corrida.INLINE.
ENLACE = re.compile(r"\]\(([^()\s]{0,2000})\)")
# 12 000 000 o 12\u00a0000: grupos de tres cifras separados por espacios (también el de no separación, el fino o el de
# cifras), que TOKEN partía en 12, 000 y 000 y el pozo respaldaba uno por uno (L119)
AGRUPADA = re.compile(r"(?<![\w.,])\d{1,3}(?:[.,]\d{3})*(?:[ \t\u00a0\u2007-\u200a\u202f\u205f\u3000]\d{3})+(?:[.,]\d+)?(?!\w)")
# 30k, 2,5M, 2do: una cifra pegada a letras no la ve TOKEN (no es un identificador como R1: empieza con la cifra)
PEGADA = re.compile(r"(?<![\w.,])\d[\d.,]{0,40}[^\W\d_]\w{0,40}")
# Una cifra con palabras («treinta billones», «noventa y siete por ciento», «dos millones»): las cifras van con dígitos.
# Los cardinales sueltos hasta quince («dos implementaciones», «una sola vez») cuentan cosas del método y pasan, como
# las magnitudes solas de una unidad («en millones de pesos», L119).
CARDINAL = re.compile(r"(?:un[oa]?|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|trece|catorce|quince)", re.I)
PALABRA_NUMERO = re.compile(
    r"(?:un[oa]?|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|trece|catorce|quince|dieci(?:s[eé]is|siete|"
    r"ocho|nueve)|veinte|veinti(?:[uú]n[oa]?|d[oó]s|tr[eé]s|cuatro|cinco|s[eé]is|siete|ocho|nueve)|treinta|cuarenta|"
    r"cincuenta|sesenta|setenta|ochenta|noventa|cien|ciento|(?:dos|tres|cuatro|seis|sete|ocho|nove)cient[oa]s|"
    r"quinient[oa]s|mil|mill[oó]n|millones|bill[oó]n|billones)", re.I)
UNIDAD_SOLA = re.compile(r"(?:millones|billones)", re.I)
ENTRE_PALABRAS = re.compile(r"\s+(?:y\s+)?", re.I)
MAGNITUD_EN_PALABRAS = re.compile(
    r"\b(la\s+mitad|un\s+tercio|dos\s+tercios|un\s+cuarto|tres\s+cuartos|el\s+doble|el\s+triple|la\s+(?:gran\s+)?mayor[ií]a|"
    r"la\s+minor[ií]a|casi\s+tod[oa]s?|decenas\s+de|cientos\s+de|miles\s+de(?!\s+millones))\b", re.I)

# W3 · D15: lo que solo pueden concluir las personas. UNA sola lista para todos los verificadores: W3 de este
# whitepaper, la presentación (verificar_presentacion.py), el gráfico (verificar_grafico.py), las fichas del agente
# masivo (validar_ficha.py, V6) y el resumen de su whitepaper (whitepaper_fichas.py); cada uno la importa de aquí y
# ninguno trae una propia. Es una lista: una frase de análisis con otras palabras pasa, y la revisa una persona.
_CONCLUYE = (   # conclusiones y lo que «muestran» los datos
    r"se\s+conclu\w+", r"conclu(?:ir|imos|yo|ye|yen)\b", r"en\s+conclusi[oó]n", r"como\s+conclusi[oó]n",
    r"la\s+conclusi[oó]n\s+es", r"demuestra(?:n)?\s+que", r"demostr\w*\s+que", r"se\s+demuestra", r"queda\s+demostrad[oa]",
    r"se\s+evidencia\s+que", r"evidencia(?:n)?\s+que", r"(?:revela|significa|implica)(?:n)?\s+que\b",
    r"(?:esto|eso|ello|lo\s+que|lo\s+cual|lo\s+anterior|(?:el|los|este|estos)\s+(?:resultados?|datos?)|"
    r"(?:la|las|esta|estas)\s+cifras?|(?:el|este)\s+gr[aá]fico|(?:la|esta)\s+(?:tabla|gr[aá]fica))\s+"
    r"(?:indica|sugiere|muestra|refleja|prueba|confirma)(?:n)?\s+que",
    r"(?:esto|eso|ello|lo\s+cual)\s+implica\w*", r"est[aá]\s+claro\s+que", r"es\s+claro\s+que", r"es\s+evidente", r"sin\s+duda",
)
_CAUSA = (   # causas que se le atribuyen a lo medido
    r"la\s+causa(?:\s+\w+)?\s+(?:es|fue|son|est[aá])", r"las\s+causas(?:\s+\w+)?\s+(?:son|fueron)",
    r"se\s+deb(?:e|en|i[oó]|ieron)\s+al?\b", r"debido\s+a", r"debid[oa]s?\s+a", r"es\s+causad[oa]", r"fue\s+causad[oa]",
    r"caus[oó]\b", r"provoc[oó]\b", r"se\s+explica(?:n|r[ií]a|r[ií]an)?\s+(?:por|con|en)\b",
    r"(?:esto|eso|ello|lo\s+que|lo\s+cual)\s+explica\w*",
)
_JUICIO = (   # efectos y juicios de valor («grave» e «inflado» no: también nombran un dato o el método, L118)
    r"se\s+ahorr\w*", r"ahorrar[ií]a\w*", r"reduce\s+en", r"reducir[ií]a\w*", r"mejora\s+en", r"mejorar[ií]a\w*",
    r"significativamente", r"tiene(?:n)?\s+(?:un\s+|una\s+)?(?:gran\s+|alto\s+|bajo\s+|fuerte\s+)?impacto",
    r"impacta(?:n|r[aá])?\b", r"sobrecosto\w*", r"despilfarr\w*", r"ineficien\w*", r"irregular\w*", r"corrupci[oó]n",
    r"preocupante\w*", r"alarmante\w*", r"excesiv[oa]s?\b", r"desproporcionad[oa]s?\b",   # L118
)
_ACCION = (   # recomendaciones, decisiones y consecuencias
    r"se\s+recomienda\w*", r"recomend(?:amos|ar[ií]amos|ar[ií]a)\b", r"recomiendo", r"recomendaci[oó]n(?:es)?\b",
    r"recomendable", r"se\s+aconseja\w*", r"aconsej(?:amos|o|ar[ií]a|ar[ií]amos)\b", r"aconsejable", r"se\s+propone\w*",
    r"proponemos", r"propongo", r"(?:es|ser[ií]a|resulta|resultar[ií]a)\s+(?:m[aá]s\s+|muy\s+)?(?:conveniente|prudente|deseable|oportuno)",
    r"lo\s+(?:ideal|prudente|conveniente|deseable)\b", r"lo\s+mejor\s+(?:es|ser[ií]a)\b", r"vale\s+la\s+pena",
    r"deber[ií]a\w*", r"convendr[ií]a\w*", r"conviene", r"se\s+sugiere", r"sugerimos", r"sugiero", r"hay\s+que",
    r"es\s+necesario", r"es\s+urgente", r"tiene(?:n)?\s+que\s+(?!ver\b)\w+(?:ar|er|ir)\b", r"deb(?:e|en)\s+\w+(?:ar|er|ir)se\b",
    r"se\s+deb(?:e|en)\s+(?!al?\b)\w+(?:ar|er|ir)\b",
    r"se\s+pide\s+decidir\b", r"lo\s+que\s+se\s+pide\b", r"decidir\s+si\b", r"la\s+decisi[oó]n\s+(?:es|ser[ií]a)\b",
    r"pr[oó]xim[oa]s?\s+pasos?\b",
    r"por\s+lo\s+tanto", r"por\s+tanto\b", r"por\s+consiguiente", r"en\s+consecuencia", r"por\s+ende\b", r"as[ií]\s+pues\b",
    r"por\s+eso\b", r"por\s+ello\b", r"de\s+ah[ií]\s+que\b", r"as[ií]\s+que\b",
)


ANALISIS = re.compile(r"\b(" + "|".join(_CONCLUYE + _CAUSA + _JUICIO + _ACCION) + ")", re.I)   # la lista D15 completa
# Sin las de acción: para los textos de método de una ficha (nota, riesgos de lectura, pasos), donde «hay que unificar
# los nombres antes de comparar» o «por eso se excluyen» describen el método, no los datos (validar_ficha.py, V6).
JUICIO = re.compile(r"\b(" + "|".join(_CONCLUYE + _CAUSA + _JUICIO) + ")", re.I)
# Una frase por cada forma nueva o fácil de perder: las autopruebas del whitepaper, de la presentación y de las fichas
# las prueban todas, así ninguna lista vuelve a perder una. Sin cifras ni magnitudes con palabras.
FRASES_D15 = (
    "Esto demuestra que el Norte vende mejor.",
    "Se puede concluir que el Centro concentra las ventas.",
    "Los datos demostraron que el Norte lidera.",
    "Esto muestra que el Norte concentra las ventas.",
    "Los datos revelan que el Centro vende más en diciembre.",
    "La diferencia se debe a la temporada.",
    "La ventaja del Norte se debe al invierno.",
    "La causa principal es la temporada de fin de año.",
    "El total alto se explica por las ventas del Norte.",
    "La concentración es debida a la temporada.",
    "Por tanto, el Norte es la región más rentable.",
    "Por ende, el Centro queda segundo.",
    "Por eso el Sur queda atrás.",
    "Se recomienda cerrar la región Centro.",
    "**Recomendación.** Revisar las ventas del Sur.",
    "El próximo paso es revisar las ventas del Sur.",
    "Sería recomendable revisar las ventas del Sur.",
    "Se aconseja revisar las ventas del Sur.",
    "Sería conveniente revisar las ventas del Sur.",
    "Lo prudente sería revisar las ventas del Sur.",
    "Debe auditarse la venta de la región Sur.",
    "Las tiendas tienen que rendir cuentas por sus ventas.",
    "La región Sur debería vender más.",
    "Hay ventas irregulares en el Sur.",
    "Con menos devoluciones se ahorra dinero.",
    "El Sur tiene sobrecostos en el transporte.",
    "La concentración de las ventas en el Norte es preocupante.",
    "Es alarmante que el Sur venda tan poco.",
    "El gasto del Sur en transporte es excesivo.",
    "La venta del Norte es desproporcionada frente a la del Sur.",
    # disfrazadas (L117): el énfasis de Markdown, las letras de ancho completo y una letra de otro alfabeto (la «o»
    # cirílica, escrita como \u: este archivo no la trae) no esconden la frase
    "Esto *demuestra* que el Norte vende mejor.",
    "Se **recomienda** cerrar la región Centro.",
    "Por lo _tanto_, el Norte es la región más rentable.",
    "Los datos `revelan` que el Centro vende más en diciembre.",
    "Ｓｅ ｃｏｎｃｌｕｙｅ que el Centro concentra las ventas.",
    "Se c\u043encluye que el Centro concentra las ventas.",
)
TITULO_DE_ANALISIS = re.compile(r"(conclusion|recomendacion|hallazgo|analisis\b)")
# Las listas de ejemplos prohibidos que las fichas le dan a la IA: tras «Conclusiones, recomendaciones, causas…:»,
# dentro de «causas (…)» o «juicios (…)», y tras «juzgan (V6…): ni». Cada ejemplo tiene que estar en la lista (L118).
LISTA_DE_UNA_FICHA = re.compile(r"(?:[Cc]onclusiones, recomendaciones,? causas[^:\n]{0,200}: ?|(?:causas|juicios) \(|"
                                r"juzgan \(V6[^)\n]{0,80}\): ni )(?=«)")
EJEMPLO_DE_UNA_FICHA = re.compile(r"«([^»\n]{1,80})»")
ENTRE_EJEMPLOS = re.compile(r", | ni | y ")
MARCAS_MARKDOWN = re.compile(r"\]\([^()\s]{0,2000}\)|[*_`~\\\[\]]")   # el destino de un enlace y las marcas que no se leen


def para_d15(texto):
    """El texto como lo lee una persona, para buscar la lista D15: en su forma canónica (NFKC y sin caracteres de
    formato: las letras de ancho completo o matemáticas vuelven a su forma común), con las letras de otro alfabeto que
    se leen como latinas vueltas latinas (la «o» cirílica) y sin las marcas de Markdown que no se ven al leer el texto
    maquetado: el énfasis («Esto *demuestra* que», «se **recomienda**», «por lo _tanto_»), el código, el tachado, los
    escapes y los corchetes y el destino de un enlace («[demuestra](x) que») (L117)."""
    return " ".join(MARCAS_MARKDOWN.sub("", latinizar(forma_canonica(texto))).split())


def ejemplos_de_las_fichas(raiz=None):
    """[(archivo, ejemplo)] de cada frase que una ficha de agentes/ o una plantilla de plantillas/ le nombra a la IA
    como prohibida (conclusiones, recomendaciones, causas y juicios). La autoprueba exige que cada una esté en la lista
    D15: «preocupante» lo prohibía la ficha 12 y ninguna lista lo buscaba (L118)."""
    raiz = Path(raiz or AQUI.parent)
    out = []
    for p in sorted(raiz.glob("agentes/*.md")) + sorted(raiz.glob("plantillas/*.md")):
        texto = p.read_text(encoding="utf-8")
        for m in LISTA_DE_UNA_FICHA.finditer(texto):
            pos = m.end()
            while (e := EJEMPLO_DE_UNA_FICHA.match(texto, pos)):   # los ejemplos seguidos, separados por «, », « ni » o « y »
                out.append((str(p.relative_to(raiz)), e.group(1)))
                s = ENTRE_EJEMPLOS.match(texto, e.end())
                if not s:
                    break
                pos = s.end()
    return out


def buscar_d15(texto, lista=None):
    """Las frases de la lista D15 (ANALISIS, o JUICIO para los textos de método de una ficha) en un texto, en
    minúsculas y sin repetir: las del texto tal cual y las del texto como lo lee una persona (para_d15). Así un énfasis
    de Markdown, una letra de ancho completo o una de otro alfabeto no esconden una frase, y nada que se atrapaba antes
    deja de atraparse. La usan todos los que buscan la lista: W3, la presentación, el gráfico, las fichas y el resumen
    del agente masivo (L117)."""
    lista = lista or ANALISIS
    t = str(texto or "")
    hallados = []
    for plano in (" ".join(t.split()), para_d15(t)):
        hallados += [" ".join(m.group(0).lower().split()) for m in lista.finditer(plano)]
    return list(dict.fromkeys(hallados))

# W5 · lo que no se ve al leer
INVISIBLES = re.compile("[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f­​-‏‪-‮"
                        "⁠-⁩﻿\U000e0000-\U000e007f]")
ETIQUETA = re.compile(r"<\s*/?\s*([A-Za-z][\w:-]{0,30})[^<>]{0,200}>")
ABRE_COMENTARIO = "<" + "!--"   # armado aquí: este archivo no trae un comentario HTML literal (el filtro de aportes los lee)


def leer(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def normalizar(t):
    t = "".join(ch for ch in unicodedata.normalize("NFD", str(t).lower()) if unicodedata.category(ch) != "Mn")
    t = re.sub(r"^\s*\d{1,2}\s*[.)·:-]?\s*", "", t)
    t = re.sub(r"[*_`:¿?¡!]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def secciones(texto):
    """Títulos fuera de bloques de código: [(nivel, título, inicio, fin de la línea)] y cuerpos de los de nivel 2."""
    titulos, pos, en_codigo = [], 0, False
    for linea in texto.splitlines(keepends=True):
        if linea.lstrip().startswith("```"):
            en_codigo = not en_codigo
        elif not en_codigo:
            m = re.match(r"(#{1,6})[ \t]+(.*)", linea.rstrip("\r\n"))
            if m:
                titulos.append((len(m.group(1)), m.group(2).rstrip(" \t#"), pos, pos + len(linea)))
        pos += len(linea)
    cuerpos = []
    for i, (nivel, titulo, ini, fin) in enumerate(titulos):
        if nivel == 2:
            sig = next((t[2] for t in titulos[i + 1:] if t[0] <= 2), len(texto))
            cuerpos.append((normalizar(titulo), fin, sig))
    return titulos, cuerpos


def de_que_seccion(pos, cuerpos):
    for norm, ini, fin in cuerpos:
        if ini <= pos < fin:
            return next((nombre for nombre, patron in SECCIONES if re.match(patron, norm)), None)
    return None


# ---------------- W2 · cifras ----------------
def factor(palabra):
    for p, f in MAGNITUDES:
        if re.fullmatch(p, palabra.strip(), re.I):
            return f
    return 1.0


def interpretaciones(tok):
    """Valores posibles de una cifra escrita por una herramienta: las herramientas escriben en formato español
    (49.662) y en inglés (17,248,249,407,618.69); se aceptan las dos lecturas."""
    try:
        if len(tok) > 60:
            return set()
        if "e" in tok.lower():
            return {abs(float(tok.replace(",", ".")))}
        if tok.isdigit():
            return {float(tok)}
        if "." in tok and "," in tok:
            if tok.rfind(",") > tok.rfind("."):
                return {float(tok.replace(".", "").replace(",", "."))}
            return {float(tok.replace(",", ""))}
        sep = "." if "." in tok else ","
        partes = tok.split(sep)
        out = set()
        if 1 <= len(partes[0]) <= 3 and all(len(p) == 3 for p in partes[1:]):
            out.add(float("".join(partes)))
        if len(partes) == 2:
            out.add(float(partes[0] + "." + partes[1]))
        return out
    except (ValueError, OverflowError):
        return set()


def cifras_de_herramienta(texto):
    out = set()
    for m in CIFRA_DE_HERRAMIENTA.finditer(texto[:200_000]):
        mag = MAGNITUD.match(texto, m.end())
        f = factor(mag.group(1)) if mag else 1.0
        for v in interpretaciones(m.group(0)):
            out.update({v, v * f})
    return out


def clase_de(nombre):
    base = Path(str(nombre).split(" ")[0]).name
    return "procedencia" if base.startswith("procedencia") else "limpieza" if base.startswith("limpieza_") else base


def aprobados(artefactos):
    """Solo cuentan los artefactos verificados y aprobados; los demás se nombran, pero sus cifras no valen."""
    usados, sin_aprobar = [], []
    for nombre, datos in artefactos:
        esperado = ESTADO_APROBADO.get(clase_de(nombre))
        if isinstance(datos, dict) and esperado and datos.get("estado") == esperado:
            usados.append((nombre, datos))
        else:
            motivo = "no es un artefacto verificado" if not esperado else (
                f"estado {datos.get('estado')}" if isinstance(datos, dict) else "no se pudo leer")
            sin_aprobar.append(f"{nombre} ({motivo})")
    return usados, sin_aprobar


def pozo(artefactos):
    """Las cifras verificadas: números, cifras de los textos de las herramientas, conteos y totales del resultado."""
    P, totales = set(), []

    def agregar(v):
        try:
            v = abs(float(v))
        except (OverflowError, ValueError, TypeError):
            return
        if math.isfinite(v):
            P.add(v)

    def recorrer(x, clave, hondo=0):
        if hondo > 60 or isinstance(x, bool) or x is None:
            return
        if isinstance(x, (int, float)):
            agregar(x)
        elif isinstance(x, str):
            if clave in TEXTOS_DE_HERRAMIENTA:
                for v in cifras_de_herramienta(x):
                    agregar(v)
        elif isinstance(x, list):
            agregar(len(x))
            for v in x:
                recorrer(v, clave, hondo + 1)
        elif isinstance(x, dict):
            agregar(len(x))
            for k, v in x.items():
                if k not in SALTAR:
                    recorrer(v, k, hondo + 1)

    def es_numero(v):
        try:
            return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))
        except OverflowError:
            return False

    for nombre, datos in artefactos:
        recorrer(datos, None)
        if nombre == "informe.json":
            filas = [f for f in (datos.get("resultado_oficial") or []) if isinstance(f, dict)]
            for col in sorted({k for f in filas for k, v in f.items() if es_numero(v)}):
                t = sum(float(f[col]) for f in filas if es_numero(f.get(col)))
                totales.append((col, t))
                agregar(t)
    return sorted(P), totales


def respaldada(x, tol, P):
    tol = tol + 1e-9 * max(1.0, abs(x))
    i = bisect_left(P, x - tol)
    return i < len(P) and P[i] <= x + tol


def destino_es_archivo(ruta, carpeta):
    """El destino de un enlace es un archivo que existe junto al whitepaper, dentro de su carpeta o del repositorio
    («../../agentes/13-documentador.md»): el número de su nombre no es una cifra. Sin carpeta (la autoprueba), ninguno."""
    if carpeta is None or not ruta or ruta.startswith(("/", "~", "\\")) or ":" in ruta:
        return False
    try:
        base = Path(carpeta).resolve()
        real = (base / ruta).resolve()
        return real.is_file() and (real.is_relative_to(base) or real.is_relative_to(AQUI.parent.resolve()))
    except (OSError, ValueError):
        return False


def sin_destinos(texto, carpeta=None):
    """Quita el destino de cada enlace que no es una cifra: una dirección web (sus números no se comprueban: límite) o
    un archivo que existe (el ancla «#…» queda). Cualquier otro destino se imprime al lado del texto y sus números se
    buscan como los de la prosa: «[la tabla](total-real-30.000.000.000.000-pesos)» ya no esconde una cifra (L119)."""
    def cambiar(m):
        dest = m.group(1)
        if re.match(r"https?://", dest, re.I):
            return " " * len(m.group(0))
        ruta, _, ancla = dest.partition("#")
        if destino_es_archivo(ruta, carpeta):
            return " " * (2 + len(ruta) + (1 if _ else 0)) + ancla + " "
        return "  " + dest + " "
    return ENLACE.sub(cambiar, texto)


def sin_permitidos(texto, carpeta=None):
    t = sin_destinos(texto, carpeta)
    t = re.sub(r"(?m)^([ \t]*#{1,6}[ \t]+)(\d{1,2}[ \t]*[.)·:-][ \t]*)", lambda m: m.group(1) + " " * len(m.group(2)), t)
    t = re.sub(r"(?m)^([ \t]*)(\d{1,2}[.)][ \t]+)", lambda m: m.group(1) + " " * len(m.group(2)), t)   # listas numeradas
    for rx in PERMITIDOS:
        t = rx.sub(lambda m: " " * len(m.group(0)), t)
    return t


MOTIVOS = {"invalida": "formato no válido: punto para miles y coma para decimales",
           "espacios": "formato no válido: los miles van con punto (12.000.000), sin espacios",
           "pegada": "formato no válido: una cifra pegada a letras (30k, 2,5M, 2do) no se puede comprobar",
           "rara": "formato no válido: caracteres numéricos que no son los dígitos del 0 al 9",
           "palabras": "cifra con palabras: las cifras van con dígitos, en formato colombiano"}


def cifras_del_texto(texto, cuerpos, carpeta=None):
    """Cada cifra del whitepaper con su valor, su tolerancia de redondeo y si su formato es válido."""
    t = sin_permitidos(texto, carpeta)
    inicios = [0] + [m.end() for m in re.finditer("\n", texto)]
    hallados = []

    def apartar(rx, motivo, cuenta=None):   # lo que no tiene una forma comprobable: cifra no válida, y se quita del texto
        nonlocal t
        for m in rx.finditer(t):
            if cuenta is None or cuenta(m.group(0)):
                hallados.append((m.start(), m.end(), m.group(0), motivo, None))
        t = rx.sub(lambda m: " " * len(m.group(0)) if cuenta is None or cuenta(m.group(0)) else m.group(0), t)
    apartar(re.compile(r"[^\x00-\x7f]"), "rara", lambda ch: unicodedata.numeric(ch, None) is not None)   # ⁶ ½ ٣ ❹
    apartar(AGRUPADA, "espacios")
    for m in CIENTIFICA.finditer(t):
        dec, exp = len(m.group(2) or ""), int(m.group(3))
        if abs(exp) <= 30:
            v = float(m.group(1) + "." + (m.group(2) or "0")) * 10.0 ** exp
            hallados.append((m.start(), m.end(), m.group(0), v, 0.5 * 10.0 ** (exp - dec)))
        else:
            hallados.append((m.start(), m.end(), m.group(0), "invalida", None))
    t = CIENTIFICA.sub(lambda m: " " * len(m.group(0)), t)
    apartar(PEGADA, "pegada")
    for m in TOKEN.finditer(t):
        hallados.append((m.start(), m.end(), m.group(0), None, None))
    out, tramos = [], []
    for ini, fin, tok, v, tol in sorted(hallados, key=lambda h: h[0]):
        c = {"cifra": tok, "linea": bisect_right(inicios, ini), "seccion": de_que_seccion(ini, cuerpos), "valida": True}
        if v in MOTIVOS or (v is None and not ES_NUMERO.fullmatch(tok)):
            c.update(valida=False, motivo=MOTIVOS.get(v, MOTIVOS["invalida"]))
            out.append((ini, c))
            continue
        if v is None:
            entero, _, dec = tok.partition(",")
            v, f = float(entero.replace(".", "") + ("." + dec if dec else "")), 1.0
            mag = MAGNITUD.match(t, fin)
            if mag:
                f = factor(mag.group(1))
                c["cifra"], fin = tok + " " + mag.group(1), mag.end()
            v, tol = v * f, 0.5 * 10.0 ** (-len(dec)) * f
        c.update(valor=v, tol=tol, porcentaje=bool(PORCENTAJE.match(t, fin)))
        if c["porcentaje"]:
            c["cifra"] += " %"
        out.append((ini, c))
        tramos.append((ini, fin))
    # cifras con palabras, fuera de las cifras con dígitos y su magnitud («17,2 billones» no es «billones» suelto)
    for ini, fin in tramos:
        t = t[:ini] + " " * (fin - ini) + t[fin:]
    for ini, fin, palabras in numeros_con_palabras(t):
        porcentaje = bool(PORCENTAJE.match(t, fin))
        if not porcentaje and (all(CARDINAL.fullmatch(w) for w in palabras) or all(UNIDAD_SOLA.fullmatch(w) for w in palabras)):
            continue
        out.append((ini, {"cifra": " ".join(t[ini:fin].split())[:60] + (" por ciento" if porcentaje else ""),
                          "linea": bisect_right(inicios, ini), "seccion": de_que_seccion(ini, cuerpos),
                          "valida": False, "motivo": MOTIVOS["palabras"]}))
    return [c for _, c in sorted(out, key=lambda x: x[0])]


def numeros_con_palabras(t):
    """[(inicio, fin, palabras)] de cada número escrito con palabras: palabras de número seguidas, separadas por
    espacios o por «y» («noventa y siete», «treinta billones», «dos mil millones»)."""
    palabras = [(m.group(0), m.start(), m.end()) for m in re.finditer(r"[^\W\d_]+", t)]

    def es_numero(k):   # «ciento» después de «por» es el porcentaje, no un número
        return k < len(palabras) and PALABRA_NUMERO.fullmatch(palabras[k][0]) and not (
            k > 0 and palabras[k][0].lower() == "ciento" and palabras[k - 1][0].lower() == "por")
    out, i = [], 0
    while i < len(palabras):
        if not es_numero(i):
            i += 1
            continue
        j = i
        while True:
            k = j + 2 if j + 2 < len(palabras) and palabras[j + 1][0].lower() == "y" else j + 1
            if not (es_numero(k) and ENTRE_PALABRAS.fullmatch(t, palabras[j][2], palabras[k][1])):
                break
            j = k
        out.append((palabras[i][1], palabras[j][2], [w.lower() for w, _, _ in palabras[i:j + 1] if w.lower() != "y"]))
        i = j + 1
    return out


# ---------------- validación ----------------
def validar(texto, artefactos, faltan=(), utf8=True, carpeta=None):
    """texto: el whitepaper; artefactos: [(nombre, json)] candidatos (solo cuentan los aprobados); carpeta: la del
    whitepaper (el nombre de un archivo enlazado que existe ahí no es una cifra). Devuelve (chequeos, cifras)."""
    chequeos = []

    def chequeo(nombre, ok, detalle):
        chequeos.append({"chequeo": nombre, "ok": bool(ok), "detalle": detalle})

    if len(texto.encode("utf-8", errors="replace")) > MAX_BYTES:
        for nombre in CHEQUEOS:
            chequeo(nombre, False, f"no se revisó: el whitepaper pasa de {MAX_BYTES // 1000} KB (un whitepaper es prosa breve)")
        return chequeos, []
    lineas = texto.splitlines()
    largas = [i for i, l in enumerate(lineas, 1) if len(l) > LINEA_MAX]
    if largas:   # el resto se revisa con esas líneas recortadas: W1 ya falla
        texto = "\n".join(l[:LINEA_MAX] for l in lineas)
    titulos, cuerpos = secciones(texto)
    # W1
    problemas, posiciones = [], []
    if not texto.strip():
        problemas.append("el whitepaper está vacío")
    if not utf8:
        problemas.append("el archivo no es UTF-8 válido")
    if largas:
        problemas.append(f"{len(largas)} línea(s) de más de {LINEA_MAX} caracteres (desde la {largas[0]}): no es prosa")
    for nombre, patron in SECCIONES:
        i = next((k for k, (norm, _, _) in enumerate(cuerpos) if re.match(patron, norm)), None)
        if i is None:
            problemas.append(f"falta «{nombre}»")
            continue
        _, ini, fin = cuerpos[i]
        cuerpo = re.sub(r"(?m)^[ \t]*#{1,6}[ \t].*$", "", texto[ini:fin])
        if not re.search(r"[^\W\d_]", cuerpo):
            problemas.append(f"«{nombre}» está vacía")
        posiciones.append(i)
    if posiciones != sorted(posiciones):
        problemas.append("las secciones no van en el orden de la ficha")
    chequeo(CHEQUEOS[0], not problemas, "; ".join(problemas) or f"las {len(SECCIONES)} secciones, en orden y con contenido")

    # W2
    usados, sin_aprobar = aprobados(artefactos)
    P, totales = pozo(usados)
    cifras = cifras_del_texto(texto, cuerpos, carpeta)
    for c in cifras:
        c["respaldada"] = c["valida"] and (respaldada(c["valor"], c["tol"], P) or (
            c["porcentaje"] and respaldada(c["valor"] / 100, c["tol"] / 100, P)))
    problemas = []
    if not any(n == "informe.json" for n, _ in usados):
        problemas.append("no hay cifra verificada: informe.json falta o no está aprobado")
    malas = [c for c in cifras if not c["respaldada"]]
    if malas:
        problemas.append(f"{len(malas)} cifra(s) sin respaldo en los artefactos verificados: " + "; ".join(
            f"«{c['cifra'][:30]}» (línea {c['linea']}{', ' + c['motivo'] if c.get('motivo') else ''})" for c in malas[:8]))
    palabras = sorted({re.sub(r"\s+", " ", m.group(0).lower()) for m in MAGNITUD_EN_PALABRAS.finditer(texto)})
    if palabras:
        problemas.append("magnitudes con palabras que no se pueden comprobar: " + ", ".join(f"«{p}»" for p in palabras[:6]))
    if totales:
        en_cifra = [c for c in cifras if c["seccion"] == CIFRA and c["valida"]]
        if not any(abs(c["valor"] - t) <= c["tol"] + 1e-9 * max(1.0, abs(t)) for c in en_cifra for _, t in totales):
            problemas.append(f"«{CIFRA}» no cita ningún total del resultado aprobado ({', '.join(col for col, _ in totales)})")
    nota = (f" · artefactos: {', '.join(n for n, _ in usados) or 'ninguno'}"
            + (f" · no cuentan: {', '.join(sin_aprobar)}" if sin_aprobar else "")
            + (f" · no están: {', '.join(faltan)}" if faltan else ""))
    chequeo(CHEQUEOS[1], not problemas,
            ("; ".join(problemas) if problemas else f"{len(cifras)} cifra(s), todas en los artefactos verificados") + nota)

    # W3
    plano = re.sub(r"\s+", " ", texto)
    frases = sorted(set(buscar_d15(texto)))   # también con énfasis de Markdown o letras disfrazadas (L117)
    malos_titulos = [t for _, t, _, _ in titulos if TITULO_DE_ANALISIS.match(normalizar(latinizar(forma_canonica(t))))
                     and not re.match(SECCIONES[7][1], normalizar(t))]
    problemas = []
    if frases:
        problemas.append("frases de conclusión, recomendación, causa o juicio: " + ", ".join(f"«{f[:40]}»" for f in frases[:6]))
    if malos_titulos:
        problemas.append("títulos de análisis: " + ", ".join(f"«{t[:40]}»" for t in malos_titulos[:3]))
    chequeo(CHEQUEOS[2], not problemas, "; ".join(problemas) or "describe lo hecho y lo medido; el análisis queda para las personas")

    # W4
    sec = next(((ini, fin) for norm, ini, fin in cuerpos if re.match(SECCIONES[7][1], norm)), None)
    problemas, tipos, items = [], set(), []
    if sec:
        for linea in texto[sec[0]:sec[1]].splitlines():
            m = re.match(r"\s*(?:[-*+]|\d{1,2}[.)])\s+(.*)", linea)
            if m:
                items.append(m.group(1).strip())
    for k, it in enumerate(items, 1):
        if "¿" not in it or "?" not in it or it.find("¿") > it.rfind("?"):
            problemas.append(f"la pregunta {k} no lleva «¿» y «?»")
        tipo = re.match(r"(costo|calidad|impacto)\b", normalizar(it))
        if tipo:
            tipos.add(tipo.group(1))
        else:
            problemas.append(f"la pregunta {k} no empieza con su tipo (Costo, Calidad o Impacto)")
    if len(items) < 3:
        problemas.append(f"hay {len(items)} pregunta(s); se piden al menos 3")
    faltan_tipos = [t for t in TIPOS if t not in tipos]
    if faltan_tipos:
        problemas.append(f"falta al menos una pregunta de: {', '.join(faltan_tipos)}")
    chequeo(CHEQUEOS[3], not problemas, "; ".join(problemas[:6]) or f"{len(items)} preguntas, de costo, calidad e impacto")

    # W5 (sobre el texto con los espacios colapsados: así ningún patrón se traba con miles de espacios seguidos)
    problemas = []
    comentarios = plano.count(ABRE_COMENTARIO)
    if comentarios <= 50 and parece_instruccion(plano):
        problemas.append("trae un texto con forma de instrucción para una IA (no se copia aquí)")
    canonico = forma_canonica(plano)   # la arroba o las cifras de ancho completo y un invisible no esconden un dato (L116)
    for nombre, rx in PATRONES.items():
        if nombre == "correo":   # solo alrededor de cada «@»: sin «@» no hay correo, y así no hay retroceso cuadrático
            hallados = sorted({x.group(0) for m in re.finditer("@", canonico)
                               for x in rx.finditer(canonico[max(0, m.start() - 80):m.end() + 260])})
        else:
            hallados = [m.group(0) for m in rx.finditer(canonico)]
        if hallados:
            problemas.append(f"{nombre}: {len(hallados)} ({enmascarar(hallados[0])})")
    if comentarios:
        problemas.append("comentario HTML (texto que no se ve al leer)")
    invisibles = INVISIBLES.findall(texto)
    if invisibles:
        problemas.append(f"{len(invisibles)} carácter(es) invisibles o de control (p. ej. U+{ord(invisibles[0]):04X})")
    disfrazadas = letras_disfrazadas(texto)   # «concluye» con la «o» cirílica: se lee latina y ninguna lista la ve (L117)
    if disfrazadas:
        problemas.append(f"{len(disfrazadas)} palabra(s) con letras de otro alfabeto que se leen como latinas "
                         f"(p. ej. {disfrazadas[0]})")
    etiquetas = sorted({m.group(1).lower() for m in ETIQUETA.finditer(texto)})
    if etiquetas:
        problemas.append("marcado HTML: " + ", ".join(etiquetas[:5]))
    chequeo(CHEQUEOS[4], not problemas, "; ".join(problemas) or "ninguno")
    return chequeos, cifras


class _Tiempo(Exception):
    pass


def _alarma(*_):
    raise _Tiempo()


def validar_con_tope(texto, artefactos, faltan=(), utf8=True, tope=TIEMPO_MAX, carpeta=None):
    """validar() con un tope de tiempo: si un texto hecho para trabar las expresiones regulares lo excede, falla cerrado."""
    usar = hasattr(signal, "SIGALRM")
    if usar:
        anterior = signal.signal(signal.SIGALRM, _alarma)
        signal.alarm(tope)
    try:
        return validar(texto, artefactos, faltan, utf8, carpeta)
    except _Tiempo:
        return [{"chequeo": "W0 la validación termina a tiempo", "ok": False,
                 "detalle": f"tardó más de {tope} s: el whitepaper no parece prosa (posible ataque de rendimiento)"}], []
    finally:
        if usar:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, anterior)


def procedencias(c):
    """Las procedencias de la ingesta: en la corrida, en datos/ o junto al dato crudo (como en informe_final.py). Solo
    archivos de la corrida o de este repositorio: una procedencia de otra carpeta (la copia del dueño, otro clon) no
    respalda una cifra que quien lee el whitepaper no puede ver (L123)."""
    from rutas import RAIZ, resolver
    candidatos = sorted(c.glob("procedencia*.json")) + sorted((c / "datos").glob("procedencia*.json"))
    spec = leer(c / "spec.json") or {}
    for r in list((spec.get("datos_crudos") or {}).values()) + list((spec.get("datos") or {}).values()):
        candidatos += sorted(Path(resolver(r)).parent.glob("procedencia*.json"))
    vistas, out = set(), []
    for p in candidatos:
        real = p.resolve()
        if real in vistas or not p.is_file() or not (real.is_relative_to(c.resolve()) or real.is_relative_to(RAIZ)):
            continue
        vistas.add(real)
        try:
            nombre = str(real.relative_to(c.resolve()))
        except ValueError:
            nombre = f"{p.name} (junto al dato crudo)"
        out.append((nombre, p))
    return out


def artefactos_de(c):
    """Los artefactos candidatos de una corrida [(nombre, json)] y los que no están."""
    candidatos, faltan = [], []
    for nombre in ("informe.json", "gobernanza.json", "grafico_verificacion.json"):
        if (c / nombre).exists():
            candidatos.append((nombre, leer(c / nombre)))
        else:
            faltan.append(nombre)
    procs = procedencias(c)
    candidatos += [(nombre, leer(p)) for nombre, p in procs]
    limpiezas = sorted(c.glob("limpieza_*.json"))
    candidatos += [(p.name, leer(p)) for p in limpiezas]
    faltan += (["procedencia*.json"] if not procs else []) + (["limpieza_*.json"] if not limpiezas else [])
    return candidatos, faltan


def validar_corrida(c):
    ruta = c / "whitepaper.md"
    if ruta.exists():
        crudo = ruta.read_bytes()
        try:
            texto, utf8 = crudo.decode("utf-8"), True
        except UnicodeDecodeError:
            texto, utf8 = crudo.decode("utf-8", errors="replace"), False
        candidatos, faltan = artefactos_de(c)
        chequeos, cifras = validar_con_tope(texto, candidatos, faltan, utf8, carpeta=c)
        huella = hashlib.sha256(crudo).hexdigest()
    else:
        chequeos, cifras, huella = [{"chequeo": "W0 existe whitepaper.md", "ok": False,
                                     "detalle": "el documentador no escribió whitepaper.md"}], [], None
    fallas = [x for x in chequeos if not x["ok"]]
    out = {"whitepaper": "whitepaper.md", "sha256": huella, "estado": "aprobado" if not fallas else "revisar",
           "chequeos": chequeos,
           "cifras": [{k: x[k] for k in ("cifra", "linea", "seccion", "respaldada") if k in x} for x in cifras[:400]]}
    (c / "whitepaper_verificacion.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for x in chequeos:
        print(f"  {'✓' if x['ok'] else '✗'} {x['chequeo']}: {x['detalle']}")
    print("RESUMEN " + json.dumps({"estado": out["estado"], "chequeos": len(chequeos), "fallas": len(fallas),
                                   "cifras": len(cifras)}, ensure_ascii=False))
    return 1 if fallas else 0


# ---------------- autoprueba ----------------
def autoprueba():
    """Whitepapers ficticios buenos y malos (sin red ni archivos de una corrida): cada chequeo atrapa lo suyo."""
    informe = {"estado": "aprobado", "preguntas_abiertas": 1,
               "resultado_oficial": [{"region": "Norte", "ventas_netas": 1250000.5}, {"region": "Sur", "ventas_netas": 830000.0},
                                     {"region": "Centro", "ventas_netas": 419999.5}],
               "reglas": [{"id": f"R{i}"} for i in range(1, 5)],
               "implementaciones": {"a": {"conciliacion": {"filas_leidas": 1520, "usadas": 1508, "excluidas": {"anulada": 12}},
                                          "reglas": [{"id": "R1", "mensaje": "resultado 2,500,000.00 · fuente 2,500,000.00"}],
                                          "caso_conocido": {"obtenido": [{"region": "Norte", "ventas_netas": 4321.0}]}}},
               "anticipo": {"minimo": 2000000, "maximo": 3000000, "total": 2500000.0,
                            "razon": "Se esperan unas 7.777 facturas y entre 2 y 3 millones."}}
    procedencia = {"estado": "aprobada", "filas": 1520, "conteo_fuente": 1520, "licencia": "CC BY-SA 4.0",
                   "consultado_legible": "06-11-2026 05:29", "cita": "Ventas ficticias, consultado el 06-11-2026. 1.520 filas."}
    limpieza = {"estado": "aprobada", "filas": 1520, "filas_ok": 1490, "marcas": {"anulada": 12, "atipico": 18},
                "calidad_despues": {"valor": {"completitud": 0.98}},
                "pruebas": [{"prueba": "filas marcadas «atipico» ≤ 40", "ok": True, "detalle": "18"}]}
    gobernanza = {"estado": "aprobado", "tablas": {"ventas": {"filas": 1520}}, "k_anonimato": {"aplica": False},
                  "custodio": {"hay_custodio": True, "columnas_fuente": 9, "ia_no_vio": []}, "problemas": []}
    grafico = {"estado": "aprobado", "comprobaciones": [
        {"comprobacion": "cuenta de control", "ok": True, "detalle": "gráfico 2,500,000.00 + fuera 0.00 · tabla 2,500,000.00"},
        {"comprobacion": "título", "ok": True, "detalle": "Ventas netas por región: 3 regiones, 2,5 millones; Norte 50,0 %"}]}
    base = [("informe.json", informe), ("procedencia_ventas.json", procedencia), ("limpieza_ventas.json", limpieza),
            ("gobernanza.json", gobernanza), ("grafico_verificacion.json", grafico)]
    pregunta = "## Pregunta\n¿Cuánto vendió cada región en el primer semestre de 2026, en ventas netas?\n\n"
    bueno = "# Whitepaper · Ventas netas por región (ejemplo ficticio)\n\n" \
            "Resumen de lo desarrollado, para que las personas hagan el análisis.\n\n" + pregunta + """## Datos y procedencia
Ventas ficticias consultadas el 06-11-2026 05:29: 1.520 filas, igual al conteo de la fuente. Licencia CC BY-SA 4.0; la huella SHA-256 del archivo está en la procedencia.

## Limpieza
De 1.520 filas, 1.490 quedaron sin marcas: 12 facturas anuladas (se excluyen) y 18 valores atípicos (solo avisan). Nada se borró.

## Cifra verificada y cómo se verificó
Ventas netas del semestre: 2.500.000 pesos (2,5 millones) en 3 regiones. Dos implementaciones independientes dieron lo mismo y pasaron las 4 reglas (R1 a R4); la conciliación cierra: 1.520 filas leídas = 1.508 usadas + 12 excluidas.

## Gráfico
Barras desde cero con las 3 regiones; según el título, la región Norte suma el 50,0 %. Ver [grafico.html](grafico.html).

## Gobernanza
El barrido no encontró datos personales. El custodio clasificó las 9 columnas de la fuente; el k-anonimato no aplica porque el resultado solo publica agregados (Ley 1581 de 2012).

## Límites
Queda 1 pregunta abierta (P1): la cifra usa su valor por defecto.

## Preguntas para el análisis de las personas
- **Costo.** ¿Qué parte de las ventas netas se va en devoluciones en cada región?
- **Calidad.** ¿Qué tienen en común las 18 facturas con valores atípicos?
- **Impacto.** ¿A qué clientes y municipios llegan las ventas de cada región?
"""
    limites = "Queda 1 pregunta abierta (P1): la cifra usa su valor por defecto."
    impacto = "- **Impacto.** ¿A qué clientes y municipios llegan las ventas de cada región?\n"
    casos = []

    def caso(nombre, esperado, reemplazos=(), artefactos=None, texto=None, carpeta=None):
        texto = bueno if texto is None else texto
        for viejo, nuevo in reemplazos:
            if viejo not in texto:
                raise SystemExit(f"autoprueba mal armada en «{nombre}»: no está {viejo!r}")
            texto = texto.replace(viejo, nuevo, 1)
        casos.append((nombre, texto, base if artefactos is None else artefactos, esperado, carpeta))

    def mas(frase):
        return [(limites, limites + " " + frase)]

    caso("whitepaper bueno", set())
    caso("redondeo bien hecho y porcentaje de una fracción", set(),
         mas("El total, redondeado, es de 2,50 millones; la completitud del valor quedó en el 98 %."))
    caso("falta una sección", {"W1"}, [("## Gráfico\n", "## Figura\n")])
    caso("sección vacía", {"W1"}, [(limites, "")])
    caso("secciones fuera de orden", {"W1"}, [(pregunta, ""), ("## Preguntas para", pregunta + "## Preguntas para")])
    caso("línea que no es prosa", {"W1"}, mas("x" * (LINEA_MAX + 1)))
    caso("cifra inventada", {"W2"}, mas("Hay 3.217 clientes en la base."))
    caso("cifra de la prosa de la IA (razón del anticipo)", {"W2"}, mas("Se esperaban unas 7.777 facturas."))
    caso("cifra del caso conocido (datos ficticios)", {"W2"}, mas("El caso conocido dio 4.321 pesos."))
    caso("redondeo mal hecho", {"W2"}, [("(2,5 millones)", "(2,6 millones)")])
    caso("formato en inglés", {"W2"}, [("2.500.000 pesos", "2,500,000 pesos")])
    caso("porcentaje inventado", {"W2"}, [("suma el 50,0 %", "suma el 55 %")])
    caso("notación científica enorme", {"W2"}, mas("Escala 1e9999."))
    caso("magnitud con palabras", {"W2"}, mas("La mitad de las ventas sale del Norte."))
    # cifras que W2 no veía (L119): agrupadas con espacios, con palabras, en el destino de un enlace o pegadas a letras
    caso("cifra agrupada con espacios", {"W2"}, mas("Las regiones vendieron 2 000 000 pesos."))
    caso("cifra agrupada con espacios de no separación", {"W2"}, mas("Las regiones vendieron 12\u00a0000\u00a0000 pesos."))
    caso("cifra con palabras", {"W2"}, mas("Las regiones vendieron treinta billones de pesos."))
    caso("porcentaje con palabras", {"W2"}, mas("Noventa y siete por ciento de las ventas sale del Norte."))
    caso("cardinales del método y unidades con palabras (pasa)", set(),
         mas("Se calculó dos veces, con una sola consulta, y las ventas van en millones de pesos."))
    caso("id de un conjunto de datos.gov.co que empieza con cifras (pasa)", set(), mas("El conjunto es el 3k7f-xp2m."))
    caso("cifra en el destino de un enlace (se imprime al lado)", {"W2"},
         mas("Detalle en [la tabla](total-real-30.000.000.000.000-pesos)."))
    caso("enlace a un archivo que existe: el número de su nombre no es una cifra (pasa)", set(),
         mas("Ver la [ficha del documentador](../agentes/13-documentador.md)."), carpeta=AQUI)
    caso("enlace a un archivo que no existe: el número de su nombre es una cifra", {"W2"},
         mas("Ver la [ficha del documentador](../agentes/13-inventada.md)."), carpeta=AQUI)
    caso("cifra pegada a letras", {"W2"}, mas("Se revisaron 30k facturas y 2,5M de pesos."))
    caso("carácter numérico que no es un dígito del 0 al 9", {"W2"}, mas("Las ventas crecieron 10\u2076 veces."))
    caso("la cifra verificada no cita el total", {"W2"},
         [("Ventas netas del semestre: 2.500.000 pesos (2,5 millones) en 3 regiones.", "Ventas netas del semestre en 3 regiones.")])
    caso("informe sin aprobar: no hay cifra verificada", {"W2"},
         artefactos=[("informe.json", {**informe, "estado": "revisar"})] + base[1:])
    caso("gobernanza sin aprobar: sus cifras no cuentan", {"W2"},
         artefactos=base[:3] + [("gobernanza.json", {**gobernanza, "estado": "revisar"})] + base[4:])
    caso("un archivo que no es artefacto verificado no cuenta", {"W2"}, mas("El gráfico deja 38 entidades en «Otras»."),
         artefactos=base + [("grafico.json", {"estado": "aprobado", "otras": {"entidades": 38}})])
    caso("conclusión", {"W3"}, mas("Esto demuestra que el Norte vende mejor."))
    caso("recomendación", {"W3"}, mas("Se recomienda cerrar la región Centro."))
    caso("«debería»", {"W3"}, mas("La región Sur debería vender más."))
    caso("causa", {"W3"}, mas("La diferencia se debe a la temporada."))
    caso("ahorro", {"W3"}, mas("Con menos devoluciones se ahorra dinero."))
    caso("título de conclusiones", {"W3"}, [("## Límites\n", "## Conclusiones\nSin conclusiones.\n\n## Límites\n")])
    for frase in FRASES_D15:   # la misma lista de frases que prueban la presentación y las fichas
        caso(f"D15: «{frase[:48]}»", {"W3"} | ({"W5"} if letras_disfrazadas(frase) else set()), mas(frase))
    caso("título de conclusiones con una letra de otro alfabeto", {"W3", "W5"},
         [("## Límites\n", "## C\u043enclusiones\nSin conclusiones.\n\n## Límites\n")])
    caso("palabra con una letra de otro alfabeto, sin frase de la lista", {"W5"}, mas("El N\u043erte suma lo de la tabla."))
    caso("letra suelta de otro alfabeto en una fórmula (pasa)", set(), mas("La correlación \u03c1 no se calculó."))
    caso("énfasis que no esconde nada (pasa)", set(), mas("La cifra es *exacta* y se **validó** sin IA."))
    caso("menos de tres preguntas", {"W4"}, [("- **Calidad.** ¿Qué tienen en común las 18 facturas con valores atípicos?\n", "")])
    caso("pregunta sin signos", {"W4"}, [("¿Qué parte de las ventas netas se va en devoluciones en cada región?",
                                          "Qué parte de las ventas netas se va en devoluciones en cada región.")])
    caso("falta un tipo de pregunta", {"W4"}, [("- **Impacto.** ¿A qué", "- **Costo.** ¿A qué")])
    caso("pregunta sin rótulo de tipo", {"W4"},
         [(impacto, impacto.replace("**Impacto.** ", "") + "- **Impacto.** ¿Cómo cambia la llegada por municipio?\n")])
    caso("dato personal", {"W5"}, mas("Dudas: " + "ana.perez" + "@" + "ejemplo.invalid" + "."))
    caso("comentario HTML", {"W5"}, mas(ABRE_COMENTARIO + " nota interna --" + ">"))
    caso("carácter invisible", {"W5"}, [("valor por defecto", "valor por" + "​" + " defecto")])
    caso("dato personal con la arroba de ancho completo", {"W5"}, mas("Dudas: " + "ana.perez" + "\uff20" + "ejemplo.invalid" + "."))
    caso("marcado HTML", {"W5"}, mas("<span>texto</span>"))
    caso("más de 200 KB: no se revisa y falla", {"W1", "W2", "W3", "W4", "W5"}, texto=bueno + ("Relleno. " * 30_000))
    errores = 0
    for nombre, texto, artefactos, esperado, carpeta in casos:
        chequeos, _ = validar(texto, artefactos, carpeta=carpeta)
        obtenido = {x["chequeo"].split()[0] for x in chequeos if not x["ok"]}
        ok = obtenido == esperado
        errores += not ok
        print(f"  {'✓' if ok else '✗'} {nombre}: " + ("pasa" if not obtenido else "atrapado por " + ", ".join(sorted(obtenido)))
              + ("" if ok else f" (se esperaba {', '.join(sorted(esperado)) or 'que pasara'}) · "
                 + " | ".join(x["detalle"][:200] for x in chequeos if not x["ok"])))
    # cada texto-instrucción de la batería de inyección, puesto en el whitepaper, lo atrapa W5
    maliciosos = [l for l in (AQUI.parent / "baterias" / "inyeccion" / "maliciosos.txt").read_text(encoding="utf-8").splitlines()
                  if l.strip()]
    no_atrapados = 0
    for linea in maliciosos:
        chequeos, _ = validar(bueno.replace(limites, limites + "\n\n" + linea), base)
        no_atrapados += not any(x["chequeo"].startswith("W5") and not x["ok"] for x in chequeos)
    errores += bool(no_atrapados or not maliciosos)
    print(f"  {'✓' if maliciosos and not no_atrapados else '✗'} textos-instrucción de baterias/inyeccion: W5 atrapa "
          f"{len(maliciosos) - no_atrapados} de {len(maliciosos)}")
    # cada frase que las fichas le nombran a la IA como prohibida está en la lista (L118); control positivo: se leen
    # las listas de las fichas 09, 12 y 13 y del encargo de las fichas (si la lectura se rompe, no se lee ninguna)
    ejemplos = ejemplos_de_las_fichas()
    fuera = [f"{a}: «{e}»" for a, e in ejemplos if not buscar_d15(e)]
    leidas = {a for a, _ in ejemplos}
    faltan_fichas = sorted({"agentes/09-graficador.md", "agentes/12-presentador.md", "agentes/13-documentador.md",
                            "plantillas/encargo_fichas.md"} - leidas)
    errores += bool(fuera or faltan_fichas)
    print(f"  {'✓' if not fuera and not faltan_fichas else '✗'} las {len(ejemplos)} frases prohibidas que nombran "
          f"{len(leidas)} fichas están en la lista D15" + (f" · fuera de la lista: {', '.join(fuera[:6])}" if fuera else "")
          + (f" · no se leyó la lista de: {', '.join(faltan_fichas)}" if faltan_fichas else ""))
    # textos hechos para trabar las expresiones regulares: todos terminan rápido (nunca cuelgan el pipeline), y los
    # que traen algo que las reglas rechazan, fallan
    hostiles = [("cifras pegadas", "1." * 2_000, True),
                ("cédula con miles de espacios", "cédula" + " " * 1_990 + ":" + " " * 1_990 + "1", False),
                ("línea larga de espacios", "cc" + " " * 9_000 + "1", True),
                ("puntos sin arroba", ("a." * 1_900 + "\n") * 40, False),
                ("puntos con una arroba al final", ("1." * 1_900 + "@\n") * 40, False),
                ("comentarios sin cerrar", ABRE_COMENTARIO * 999, True),
                ("etiquetas sin cerrar", ("<a " + "x" * 190 + "\n") * 300, False),
                ("cifras con espacios y con palabras", ("1 000 dos y treinta " * 180 + "\n") * 30, True)]
    malos = []
    for nombre, relleno, debe_fallar in hostiles:
        t0 = time.perf_counter()
        chequeos, _ = validar_con_tope(bueno.replace(limites, limites + "\n\n" + relleno), base, tope=20)
        seg = time.perf_counter() - t0
        if seg > 10 or (debe_fallar and all(x["ok"] for x in chequeos)):
            malos.append(f"{nombre} ({seg:.1f} s)")
    errores += bool(malos)
    print(f"  {'✓' if not malos else '✗'} textos hostiles: los {len(hostiles)} terminan en menos de 10 s"
          + (f" · no: {', '.join(malos)}" if malos else ""))
    # el pozo de W2 solo toma procedencias de la corrida o de este repositorio (L123): la que está junto a un dato de
    # otra carpeta (la copia del dueño, otro clon) no respalda cifras. Control positivo (L27): la lista de candidatos
    # de antes, la carpeta de cada dato de la spec, sí la encontraba
    import shutil
    import tempfile
    from rutas import resolver
    tmp = Path(tempfile.mkdtemp(prefix="wp-procedencias-"))
    try:
        c, afuera = tmp / "corrida", tmp / "afuera"
        (c / "datos").mkdir(parents=True)
        afuera.mkdir()
        (afuera / "ventas.csv").write_text("id\n1\n", encoding="utf-8")
        (afuera / "procedencia_ventas.json").write_text('{"estado": "aprobada", "filas": 987654}', encoding="utf-8")
        (c / "datos" / "procedencia_ventas.json").write_text('{"estado": "aprobada", "filas": 1520}', encoding="utf-8")
        (c / "spec.json").write_text(json.dumps({"datos": {"ventas": str(afuera / "ventas.csv")}}), encoding="utf-8")
        nombres = [n for n, _ in procedencias(c)]
        antes = sorted(Path(resolver(str(afuera / "ventas.csv"))).parent.glob("procedencia*.json"))
        ok_pozo = nombres == ["datos/procedencia_ventas.json"] and antes == [afuera / "procedencia_ventas.json"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    errores += not ok_pozo
    print(f"  {'✓' if ok_pozo else '✗'} W2 no toma la procedencia de otra carpeta, solo la de la corrida o del repositorio "
          f"(control positivo: la lista de antes la encontraba)" + ("" if ok_pozo else f" · tomó {nombres}"))
    print("RESUMEN " + json.dumps({"autoprueba": len(casos) + 4, "errores": errores}))
    return 1 if errores else 0


def main(argv):
    if argv[:1] == ["--autoprueba"]:
        return autoprueba()
    if not argv:
        raise SystemExit(__doc__)
    return validar_corrida(Path(argv[0]).resolve())


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
