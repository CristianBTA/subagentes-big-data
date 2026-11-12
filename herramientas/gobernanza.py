#!/usr/bin/env python3
"""Gobernanza determinista (sin IA): datos personales, salidas limpias y k-anonimato.

Uso:
  python gobernanza.py <corrida>        barre los datos de spec.json y las salidas de la corrida; escribe gobernanza.json
  python gobernanza.py --columnas a.csv muestra cómo se clasifica cada columna por su nombre

Qué hace:
  1. Clasifica cada columna por su nombre (y por su descripción en los metadatos, si la hay): identificador personal,
     cuasi-identificador, texto libre o sin marca. Los datos sensibles (Ley 1581, art. 5) cuentan como cuasi y la
     ingesta además les pide base legal. Una clave publicada que identifica a personas es un problema, con o sin k.
  2. Barre el texto libre con expresiones regulares (cédulas con contexto, correos, celulares,
     nombres con tratamiento) y entrega SOLO conteos y ejemplos enmascarados, nunca valores. Barre el texto en su forma
     canónica (forma_canonica: NFKC y sin caracteres de formato), así la arroba o las cifras de ancho completo, un
     espacio de ancho cero o un guion suave no esconden un dato; y de una página, también el texto sin etiquetas
     (L116). Límites: un nombre sin tratamiento, una cédula sin contexto, un celular de 10 cifras pegado, un correo
     escrito con palabras («arroba») o una letra invisible que no es de formato (U+3164) no tienen la forma que buscan
     las expresiones.
  3. Barre las salidas que se van a publicar (informe, resultado, gráfico, whitepaper y presentación, también en su
     versión impresa): deben salir en cero, y ninguna trae un texto con forma de instrucción para una IA. La orden se
     busca también en como la lee una persona: en su forma canónica y con las letras de otro alfabeto que se leen como
     latinas vueltas latinas (latinizar), así «Ignora» con la «o» cirílica no se esconde (L117).
  4. Calcula el k-anonimato del resultado si publica columnas de personas.
  5. Compara la clasificación de la IA (custodio.json) con la del barrido: lo que la IA no vio.
"""
import csv
import html
import json
import re
import sys
import unicodedata
from pathlib import Path

ROLES = r"(representante|ordenador|supervisor|persona|contacto|funcionario|proveedor|contratista|beneficiario|titular|usuario|paciente|afiliado|ciudadano)"
PERSONAL = re.compile(
    rf"(nombre_{ROLES}|nombre_del_{ROLES}|nombre_completo|^nombres?$|^apellidos?$|nombres?_y_apellidos|representante_legal|"
    r"contratista|raz[oó_]n_social|"
    r"identificaci|identidad|c[ée]dula|^documento(?!s_tipo)|documento_(proveedor|persona|representante|identidad|de_identidad)|"
    r"doc_identidad|n_mero_de_documento|n[uú]mero_de_documento|numero_documento|num_documento|"
    r"proveedor_adjudicado|codigo_proveedor|nit_proveedor|^nit$|nit_(contratista|persona|beneficiario|titular)|"
    r"correo|e_?mail|(^|_)mail($|_)|tel[ée]fono|celular|(^|_)m[oó]vil($|_)|whatsapp|direcci|domicilio|"
    r"cuenta|banco|tarjeta|placa)", re.I)
CUASI = re.compile(r"(g[ée_]nero|sexo|edad|nacimiento|nacionalidad|estrato|tipodocproveedor|tipo_de_documento_|"
                   r"latitud|longitud|coordenada)", re.I)
# Datos sensibles (Ley 1581 de 2012, art. 5; los de niños, niñas y adolescentes, art. 7): cuentan como cuasi para todo
# lo demás y, además, la ingesta los rechaza si el contrato no registra la base legal (base_legal_sensibles).
SENSIBLE = re.compile(r"(etni|[ée]tnic|(^|_)raza($|_)|racial|ind[ií]gena|afrocolombian|afrodescendient|discapacidad|"
                      r"(^|_)salud|enfermedad|diagn[oó]stic|(^|_)vih($|_)|orientaci[oó]n_sexual|vida_sexual|sexualidad|"
                      r"biom[ée]tric|huella_dactilar|religi|creencia|afiliaci[oó]n_pol|partido_pol|sindica|"
                      r"menor(es)?_de_edad|^es_menor)", re.I)
TEXTO_LIBRE = re.compile(r"(objeto|descripcion_del_proceso|observaci|comentari|^detalle|_detalle|^notas?$|_notas?$|mensaje)", re.I)
# La descripción de la columna en los metadatos (Socrata: /api/views/<id>.json) delata lo que el nombre esconde
PERSONAL_DESC = re.compile(rf"(c[ée]dula|documento de identidad|n[uú]mero de (identificaci[oó]n|documento)|nombres? y apellidos|"
                           rf"nombre completo|apellidos|nombre del {ROLES}|correo electr[oó]nico|tel[ée]fono|celular|"
                           rf"direcci[oó]n de (residencia|domicilio|notificaci[oó]n)|domicilio|n[uú]mero de cuenta)", re.I)
CUASI_DESC = re.compile(r"(fecha de nacimiento|\bg[ée]nero\b|\bsexo\b|\bedad\b|nacionalidad|\bestrato\b|tipo de (documento|identificaci[oó]n))", re.I)
SENSIBLE_DESC = re.compile(r"(\betnia|[ée]tnic|\braza\b|racial|discapacidad|orientaci[oó]n sexual|vida sexual|biom[ée]tric|"
                           r"huella dactilar|religi[oó]n|afiliaci[oó]n pol[ií]tica|partido pol[ií]tico|sindica|menor(es)? de edad)", re.I)
PATRONES = {
    "cédula con contexto": re.compile(
        # cada parte opcional consume sus propios espacios: con tres «\s*» seguidos, una nota con miles de espacios
        # tardaba decenas de segundos (retroceso cúbico, hallado por la revisión ciega del verificador de la presentación)
        r"\b(?:c\.\s?c\.?|cc|c[ée]dula(?:\s+de\s+ciudadan[ií]a)?|identificad[oa]\s+con)(?:\s*(?:no\.?|n[°º.]|n[úu]mero))?(?:\s*[:#])?\s*"
        r"(\d{1,3}(?:[.\s]?\d{3}){1,3})\b", re.I),
    "correo": re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"),
    # con contexto (cel., teléfono…) o con separadores; un número suelto de 10 dígitos puede ser un valor en pesos
    "celular": re.compile(
        r"(?i:(?:cel(?:ular)?|tel(?:[ée]fono)?|m[óo]vil|whatsapp|contacto)\.?(?:\s*:)?\s*(?:\+?57\s?)?3\d{2}[\s-]?\d{3}[\s-]?\d{4})"
        r"|\+57\s?3\d{9}(?!\d)|(?<![\d.,])3\d{2}[\s-]\d{3}[\s-]?\d{4}(?![\d.,])"),
    "nombre con tratamiento": re.compile(
        r"\b(?i:señor|señora|sr\.|sra\.|don|doña)\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3}"),
}
K_MINIMO = 5
INSTRUCCION = re.compile(
    r"(ignor[ae]\w*\s+(las\s+|todas\s+las\s+|tus\s+)?(instrucciones|reglas|indicaciones)|ignore\s+(all\s+|the\s+|any\s+)?(previous|prior|above)?\s*instructions"
    r"|olvida\w*\s+(las|tus|todas)|forget\s+(all|your|previous)|you\s+are\s+now|ahora\s+eres|act[uú]a\s+como|\bact\s+as\b"
    r"|nota\s+para\s+(la\s+)?(ia|ai|el\s+agente|el\s+asistente|el\s+modelo)|instrucci[oó]n\s+para\s+(la\s+ia|el\s+(agente|graficador|especificador|generador|revisor))"
    r"|(system|sistema)\s*prompt|instrucciones\s+del\s+sistema|<\|im_start\|>|\[/?INST\]"
    r"|apru[eé]ba\w*\s+(este|el|la|esta)\s+(aporte|corrida|cambio|pull)|approve\s+this|merge\s+this|aprobad[oa]\s+por\s+auditor"
    r"|(salta|saltar|desactiva|desactivar|omite|omitir|disable|bypass|skip)\s+(la\s+|el\s+|the\s+)?(compuerta|filtro|verificaci[oó]n|gate|filter|check)"
    r"|sin\s+correr\s+el\s+filtro|ya\s+no\s+aplica"
    r"|(debe|deben|tiene\s+que|tienen\s+que)\s+(leer|abrir|consultar|copiar)\s+(el\s+|la\s+|los\s+)?(reglas\.py|caso_conocido|esperado\.json|sellos))", re.I)
COMENTARIO_OCULTO = re.compile(r"<!--(.*?)-->", re.S)


def parece_instruccion(texto):
    """Texto que da órdenes a una IA, escondido en los datos o en un aporte (inyección de instrucciones). Se busca en
    el texto tal cual y en como lo lee una persona (forma canónica y letras de otro alfabeto vueltas latinas): una
    «o» cirílica (U+043E) o las letras de ancho completo no esconden la orden (L117)."""
    t = str(texto or "")
    for forma in ((t,) if t.isascii() else (t, latinizar(forma_canonica(t)))):
        if INSTRUCCION.search(forma):
            return True
        if any(re.search(r"\b(agente|ia|ai|assistant|asistente|claude|gpt|modelo|llm|aprueba|approve|merge)\b", c, re.I)
               for c in COMENTARIO_OCULTO.findall(forma)):
            return True
    return False


def clasificar_columna(nombre, descripcion=None):
    """personal: identifica a una persona; cuasi: combinada puede identificarla (los datos sensibles también son
    cuasi, ver es_sensible); texto_libre: puede traer nombres o cédulas escritos a mano (en SECOP, cerca de 1 de cada
    1.000 filas). Todas piden justificación en la ingesta. Con la descripción de los metadatos, si el nombre no dice
    nada, decide la descripción («campo_7: Número de cédula del beneficiario» es personal)."""
    if PERSONAL.search(nombre):
        return "personal"
    if es_sensible(nombre, descripcion) or CUASI.search(nombre):
        return "cuasi"
    if TEXTO_LIBRE.search(nombre):
        return "texto_libre"
    if descripcion and PERSONAL_DESC.search(descripcion):
        return "personal"
    if descripcion and CUASI_DESC.search(descripcion):
        return "cuasi"
    return None


def es_sensible(nombre, descripcion=None):
    """Dato sensible (Ley 1581 de 2012, art. 5: origen racial o étnico, salud, vida sexual, biométricos, convicciones,
    afiliación sindical o política; art. 7: menores de edad). La ingesta lo rechaza sin base legal registrada."""
    return bool(SENSIBLE.search(nombre) or (descripcion and SENSIBLE_DESC.search(descripcion)))


def enmascarar(texto):
    t = re.sub(r"\d", "•", texto)
    return t[:3] + "•" * max(0, min(len(t) - 3, 8)) if len(t) > 3 else "•••"


_FORMATO = []


def forma_canonica(texto):
    """El texto como lo lee una persona, para barrerlo: en NFKC (la arroba «＠» y las cifras de ancho completo, las
    ligaduras) y sin los caracteres de formato (categoría Cf: el espacio de ancho cero, la unión invisible, el guion
    suave, las marcas de dirección), que no se ven y parten un correo o una cédula para que ninguna expresión los
    encuentre (L116)."""
    t = str(texto or "")
    if t.isascii():
        return t
    if not _FORMATO:
        _FORMATO.append(re.compile("[" + "".join(re.escape(chr(c)) for c in range(sys.maxunicode + 1)
                                                 if unicodedata.category(chr(c)) == "Cf") + "]"))
    return _FORMATO[0].sub("", unicodedata.normalize("NFKC", t))


# Letras de otros alfabetos que una persona lee como latinas: la «o» cirílica (U+043E) en «concluye», la omicrón
# griega, la «o» armenia, la «A» cheroqui. Se escriben como \u para que este archivo no las traiga (L117).
_CONFUNDIBLES = {
    # cirílico
    "\u0430": "a", "\u0435": "e", "\u043e": "o", "\u0440": "p", "\u0441": "c", "\u0443": "y", "\u0445": "x", "\u0456": "i",
    "\u0458": "j", "\u0455": "s", "\u0501": "d", "\u04bb": "h", "\u051b": "q", "\u051d": "w", "\u04cf": "l", "\u043a": "k",
    "\u04af": "y", "\u0410": "A", "\u0412": "B", "\u0415": "E", "\u041a": "K", "\u041c": "M", "\u041d": "H", "\u041e": "O",
    "\u0420": "P", "\u0421": "C", "\u0422": "T", "\u0423": "Y", "\u0425": "X", "\u0406": "I", "\u0408": "J", "\u0405": "S",
    "\u051a": "Q", "\u051c": "W", "\u04ae": "Y", "\u04c0": "I",
    # griego
    "\u03b1": "a", "\u03b9": "i", "\u03ba": "k", "\u03bd": "v", "\u03bf": "o", "\u03c1": "p", "\u03c5": "u", "\u03c7": "x",
    "\u03f3": "j", "\u0391": "A", "\u0392": "B", "\u0395": "E", "\u0396": "Z", "\u0397": "H", "\u0399": "I", "\u039a": "K",
    "\u039c": "M", "\u039d": "N", "\u039f": "O", "\u03a1": "P", "\u03a4": "T", "\u03a5": "Y", "\u03a7": "X",
    # armenio y cheroqui
    "\u0585": "o", "\u057d": "u", "\u0570": "h", "\u0578": "n", "\u13aa": "A", "\u13f4": "B", "\u13df": "C", "\u13ac": "E",
    "\u13bb": "H", "\u13ab": "J", "\u13e6": "K", "\u13b7": "M", "\u13e2": "P", "\u13da": "S", "\u13a2": "T", "\u13b3": "W",
    "\u13c3": "Z",
    # latinas fuera de ASCII que se leen como otra (no son de otro alfabeto: se leen como latinas, no se marcan)
    "\u0131": "i", "\u0251": "a", "\u0261": "g",
}
_A_LATINAS = str.maketrans(_CONFUNDIBLES)
_OTROS_ALFABETOS = ("CYRILLIC", "GREEK", "ARMENIAN", "CHEROKEE")


def latinizar(texto):
    """El texto con las letras de otro alfabeto que se leen como latinas vueltas latinas (también con su tilde: la
    omicrón griega con tilde se lee «ó»). Para buscar las listas (D15 e instrucciones) en lo que lee una persona (L117)."""
    t = str(texto or "")
    if t.isascii():
        return t
    return unicodedata.normalize("NFC", unicodedata.normalize("NFD", t).translate(_A_LATINAS))


def letras_disfrazadas(texto):
    """Las palabras que se leen como latinas pero traen letras de otro alfabeto: las que mezclan letras latinas con una
    de otro alfabeto que se confunde con una latina («concluye» con la «o» cirílica, U+043E) y las de dos o más letras hechas
    solo de esas letras («se» escrito con la «s» y la «e» cirílicas). Devuelve el punto de código de la primera letra disfrazada de cada
    palabra, nunca la palabra (puede ser una orden). Una letra suelta de otro alfabeto (la rho, la mu o la alfa de una fórmula) no
    cuenta (L117)."""
    t = str(texto or "")
    if t.isascii():
        return []
    out = []
    for m in re.finditer(r"[^\W\d_]+", t):
        palabra = m.group(0)
        if palabra.isascii():
            continue
        disfrazadas, latinas, otras = [], 0, 0
        for ch in palabra:
            base = unicodedata.normalize("NFD", ch)[0]
            alfabeto = unicodedata.name(base, "").split(" ")[0]
            if base in _CONFUNDIBLES and alfabeto in _OTROS_ALFABETOS:
                disfrazadas.append(ch)
            elif alfabeto == "LATIN":
                latinas += 1
            elif ch.isalpha():
                otras += 1
        if disfrazadas and not otras and (latinas or len(disfrazadas) >= 2):
            out.append(f"U+{ord(disfrazadas[0]):04X}")
    return out


def texto_de_marcado(t):
    """De una página, un SVG o un XML: el texto con las entidades resueltas y, aparte, sin etiquetas (ni <script> ni
    <style>): «juana&#64;…» o «juana<span>@</span>…» no esconden un correo (L114, L116)."""
    sin_codigo = re.sub(r"(?is)<(script|style)\b.*?</\1\s*>", " ", t)
    return [html.unescape(t), html.unescape(re.sub(r"<[^>]*>", "", sin_codigo))]


def escanear_texto(texto):
    out = {}
    texto = forma_canonica(texto)
    for nombre, rx in PATRONES.items():
        hallados = rx.findall(texto) if texto else []
        if hallados:
            out[nombre] = len(hallados)
    return out


def leer_csv(ruta):
    with open(ruta, newline="", encoding="utf-8-sig") as fh:
        lector = csv.DictReader(fh, strict=True)
        return lector.fieldnames or [], list(lector)


def barrer_tabla(ruta):
    cols, filas = leer_csv(ruta)
    res = {"ruta": str(ruta), "filas": len(filas), "columnas": {}}
    for c in cols:
        clase = clasificar_columna(c)
        valores = [f.get(c) or "" for f in filas]
        largo = sum(len(v) for v in valores) / max(1, len(valores))
        info = {"clase_por_nombre": clase, "texto_libre": largo > 40}
        if not clase and not any(v and not v.replace(".", "").replace("-", "").isdigit() for v in valores[:500]):
            res["columnas"][c] = info
            continue
        conteo, filas_con = {}, 0
        ejemplos = []
        for v in valores:
            h = escanear_texto(v)
            if h:
                filas_con += 1
                for k, n in h.items():
                    conteo[k] = conteo.get(k, 0) + n
                if len(ejemplos) < 3:
                    for nombre, rx in PATRONES.items():
                        m = rx.search(forma_canonica(v))
                        if m:
                            ejemplos.append(f"{nombre}: {enmascarar(m.group(0))}")
                            break
        if conteo:
            info.update({"hallazgos": conteo, "filas_con_hallazgos": filas_con,
                         "por_cada_mil_filas": round(1000 * filas_con / max(1, len(filas)), 2),
                         "ejemplos_enmascarados": ejemplos})
        res["columnas"][c] = info
    return res


# Lo que se publica de una corrida. El whitepaper y la presentación ya los revisan W5 (validar_whitepaper.py) y
# verificar_presentacion.py; aquí se barren igual, con las mismas reglas que el resto, para que gobernanza.json diga
# de todas las salidas y no dependa de que esos dos se hayan corrido (L87).
SALIDAS = ("informe.md", "informe_final.md", "informe_final.html", "grafico.html", "presentacion.html", "informe.json",
           "hipotesis_resultado.json", "whitepaper.md", "WHITEPAPER.html", "presentacion.json")
CON_INSTRUCCIONES = ("informe.md", "informe_final.md", "whitepaper.md", "WHITEPAPER.html", "presentacion.json",
                     "presentacion.html")


def texto_publicado(p):
    """El texto que se publica de una salida: las cadenas de un JSON (no los números: un valor en pesos no es un dato
    personal; de informe.json, solo el resultado oficial); de un HTML, sin el paquete de Plotly, con las entidades
    resueltas (un «&#64;» no esconde un correo) y, aparte, sin etiquetas (un «<span>@</span>» tampoco, L116)."""
    texto = p.read_text(encoding="utf-8", errors="ignore")
    if p.suffix == ".json":
        def cadenas(x):
            if isinstance(x, dict):
                return " ".join(cadenas(v) for v in x.values())
            if isinstance(x, list):
                return " ".join(cadenas(v) for v in x)
            return x if isinstance(x, str) else ""
        try:
            datos = json.loads(texto)
            texto = cadenas(datos.get("resultado_oficial") if p.name == "informe.json" else datos)
        except Exception:
            pass
    if p.name == "grafico.html":
        texto = re.sub(r"<script[^>]*plotly[^>]*>.*?</script>", " ", texto, flags=re.S)[:2_000_000]
    if p.suffix == ".html":
        texto = "\n".join(texto_de_marcado(texto))
    return texto


def barrer_salidas(c):
    archivos = [c / n for n in SALIDAS if (c / n).exists()]
    out = {}
    for p in archivos:
        out[p.name] = escanear_texto(texto_publicado(p))
    return out


def k_anonimato(resultado, claves):
    personales = [k for k in claves if clasificar_columna(k) in ("personal", "cuasi")]
    if not personales:
        return {"aplica": False, "motivo": "el resultado no publica columnas de personas (son agregados)"}
    grupos = {}
    for f in resultado:
        g = tuple(str(f.get(k)) for k in personales)
        grupos[g] = grupos.get(g, 0) + 1
    k = min(grupos.values()) if grupos else 0
    return {"aplica": True, "columnas": personales, "k": k, "k_minimo": K_MINIMO, "ok": k >= K_MINIMO}


def comparar_custodio(c, tablas):
    """La IA clasifica TODAS las columnas de la fuente (con metadatos, sin filas); el código clasifica las mismas
    por su nombre y barre el texto de las que se ingirieron. Se reporta en qué no coinciden."""
    ruta = c / "custodio.json"
    if not ruta.exists():
        return {"hay_custodio": False}
    ia = json.loads(ruta.read_text(encoding="utf-8"))
    clase_ia = {x["columna"]: x.get("clase") for x in ia.get("columnas", [])}
    marcadas_ia = {k for k, v in clase_ia.items() if v in ("personal", "cuasi")}
    marcadas_codigo = {k for k in clase_ia if clasificar_columna(k)}
    for t in tablas.values():
        for col, info in t["columnas"].items():
            if info.get("clase_por_nombre") or info.get("hallazgos"):
                marcadas_codigo.add(col)
    ingeridas = {col for t in tablas.values() for col in t["columnas"]}
    return {"hay_custodio": True, "columnas_fuente": len(clase_ia), "ia_no_vio": sorted(marcadas_codigo - marcadas_ia),
            "solo_la_ia": sorted(marcadas_ia - marcadas_codigo), "coinciden": sorted(marcadas_ia & marcadas_codigo),
            "personales_que_la_ingesta_dejo_fuera": sorted((marcadas_ia | marcadas_codigo) - ingeridas)}


def gobernar(c):
    from rutas import faltan_datos, resolver_datos
    spec = resolver_datos(json.loads((c / "spec.json").read_text(encoding="utf-8")))
    # un dato que este clon no tiene no se barre en otra carpeta (L123): la gobernanza queda en «revisar» con el motivo,
    # sin traceback, y no deja en pie un gobernanza.json «aprobado» de otra corrida
    sin_dato = faltan_datos(spec, crudos=False)
    if sin_dato:
        out = {"tablas": {}, "salidas": {}, "problemas": sin_dato, "estado": "revisar"}
        (c / "gobernanza.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Gobernanza: revisar (sin el dato no se barre)")
        for p in sin_dato:
            print(f"  - {p}")
        print("RESUMEN " + json.dumps({"estado": "revisar", "problemas": sin_dato}, ensure_ascii=False))
        return 1
    tablas = {t: barrer_tabla(r) for t, r in spec["datos"].items()}
    salidas = barrer_salidas(c)
    inf = json.loads((c / "informe.json").read_text(encoding="utf-8")) if (c / "informe.json").exists() else {}
    k = k_anonimato(inf.get("resultado_oficial") or [], spec["salida"]["claves"])
    custodio = comparar_custodio(c, tablas)
    problemas = [f"{n}: {h}" for n, h in salidas.items() if h]
    for p in [c / n for n in CON_INSTRUCCIONES]:
        if p.exists() and parece_instruccion(re.sub(r"(?s)<!--.*?-->", "", texto_publicado(p))):
            problemas.append(f"{p.name}: trae un texto con forma de instrucción para una IA (posible inyección en los datos)")
    if k.get("aplica") and not k.get("ok"):
        problemas.append(f"k-anonimato {k['k']} < {K_MINIMO} en {k['columnas']}")
    # una clave que identifica (nombre, documento, NIT de persona, contacto) o un dato sensible no se publica ni con k alto
    identifican = [x for x in spec["salida"]["claves"] if clasificar_columna(x) == "personal" or es_sensible(x)]
    if identifican:
        problemas.append(f"el resultado publica columnas que identifican a personas o son datos sensibles: {identifican}")
    if custodio.get("ia_no_vio"):
        problemas.append(f"la IA no marcó como personales: {custodio['ia_no_vio']} (el barrido sí)")
    usadas = set(spec.get("columnas_usadas") or [])
    personales_usadas = sorted(col for t in tablas.values() for col, i in t["columnas"].items()
                               if col in usadas and i.get("clase_por_nombre") == "personal")
    if personales_usadas:
        problemas.append(f"el análisis usa columnas personales: {personales_usadas}")
    out = {"tablas": tablas, "salidas": salidas, "k_anonimato": k, "custodio": custodio,
           "personales_usadas": personales_usadas, "claves_que_identifican": identifican, "problemas": problemas,
           "estado": "aprobado" if not problemas else "revisar"}
    (c / "gobernanza.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Gobernanza: {out['estado']}")
    for p in problemas:
        print(f"  - {p}")
    for t, info in tablas.items():
        for col, i in info["columnas"].items():
            if i.get("clase_por_nombre") or i.get("hallazgos"):
                print(f"  · {t}.{col}: {i.get('clase_por_nombre') or ''} {i.get('hallazgos') or ''} "
                      f"{i.get('ejemplos_enmascarados') or ''}".rstrip())
    print("RESUMEN " + json.dumps({"estado": out["estado"], "problemas": problemas}, ensure_ascii=False))
    return 0 if not problemas else 1


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    if argv[0] == "--columnas":
        cols, _ = leer_csv(argv[1])
        for col in cols:
            print(f"{col}: {clasificar_columna(col) or '—'}")
        return 0
    return gobernar(Path(argv[0]).resolve())


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
