#!/usr/bin/env python3
"""Reglas por debilidad (CWE) de la compuerta de seguridad, sin IA.

seguridad.py prohíbe lo que se sale del contrato de la función pura (red, escritura, comandos). Este módulo busca la
debilidad en sí, para que la compuerta también sirva con código que sí usa red y archivos (perfil «usuario»):
  CWE-89   SQL armado con datos                    CWE-79   HTML armado con datos sin escapar
  CWE-798  secretos escritos en el código          CWE-327  criptografía o hash débil, también al seudonimizar
  CWE-502  deserialización que ejecuta código      CWE-330  azar predecible para secretos
  CWE-295  verificación de TLS apagada             CWE-532  datos personales o secretos en mensajes y registros
  CWE-78   comandos armados con datos              CWE-1333 expresiones regulares con retroceso catastrófico
  CWE-22   rutas armadas con datos, sin contención
CWE-79 y CWE-532 aplican solo en el perfil «usuario»: en la función pura ya los cubren controles al ejecutar (mensajes saneados, L17;
HTML de los datos en verificar_grafico.py, L23).

Es análisis estático: no ejecuta el código. Sigue el dato dentro de cada función, no entre funciones, así que lo que
no atrape aquí lo tiene que atrapar otra capa. Cada hallazgo dice qué se hace para corregirlo y nunca copia el valor.
"""
import ast
import json
import math
import re
import warnings
import string
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

try:
    from re import _constants as sre_c, _parser as sre_parse   # Python 3.11 o más
except ImportError:  # pragma: no cover
    import sre_constants as sre_c
    import sre_parse

FUNCS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
NADA = object()


# ---------------- ayudas ----------------
def _nombre_func(call):
    f = call.func
    return f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else "")


def _punteado(n):
    partes = []
    while isinstance(n, ast.Attribute):
        partes.append(n.attr)
        n = n.value
    if isinstance(n, ast.Name):
        partes.append(n.id)
        return ".".join(reversed(partes))
    return ""


def _kw(call, nombre):
    for k in call.keywords:
        if k.arg == nombre:
            return k.value
    return None


def _propios(nodo):
    """Nodos de este ámbito, en orden de lectura, sin entrar a las funciones anidadas."""
    pila, salida = list(ast.iter_child_nodes(nodo)), []
    while pila:
        n = pila.pop()
        salida.append(n)
        if not isinstance(n, FUNCS):
            pila.extend(ast.iter_child_nodes(n))
    clave = lambda n: (getattr(n, "lineno", getattr(getattr(n, "target", None), "lineno", 0)),
                       getattr(n, "col_offset", getattr(getattr(n, "target", None), "col_offset", 0)))
    return sorted(salida, key=clave)


def _formato_numerico(spec):
    if spec is None:
        return False
    t = "".join(v.value for v in spec.values if isinstance(v, ast.Constant))
    return bool(re.search(r"[deEfFgGn%bxXo,_]$", t))


def _sin_tildes(t):
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def _partes(nombre):
    n = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", nombre)
    return [p for p in re.split(r"[^a-z0-9]+", _sin_tildes(n).lower()) if p]


# ---------------- CWE-798: nombres y valores de secretos ----------------
NOMBRE_SECRETO = re.compile(
    r"(?i)(password|passwd|contrase[nñ]a|contrasenia|apitoken|authtoken|accesstoken|clientsecret|dbpass|dbpwd|(?:^|[^a-z0-9])(pwd|pw|passphrase|pass|secrets?|secretos?|tokens?|api[-_. ]?key|apikey|access[-_. ]?key|"
    r"private[-_. ]?key|account[-_. ]?key|credencial(?:es)?|bearer|authorization|salt|sal|pepper|sas|iv|nonce)(?:[^a-z0-9]|$))")
NOMBRE_DEBIL = re.compile(r"(?i)(?:^|[^a-z0-9])(clave|llave|key|auth|firma|signature|appid|j?sessionid|phpsessid)(?:[^a-z0-9]|$)")
NOMBRE_CREDENCIAL = re.compile(r"(?i)(auth|autentic|credencial|credential|login|basic|(?:^|[^a-z0-9])creds?(?:[^a-z0-9]|$))")
NOMBRE_NO_SECRETO = re.compile(
    r"(?i)(?:^|[^a-z0-9])(url|uri|endpoint|env|var|variable|name|nombre|field|campo|col|columna|column|header|encabezado|path|ruta|file|archivo|"
    r"type|tipo|prefix|prefijo|regex|patron|pattern|msg|mensaje|label|etiqueta|hint|ayuda|id|length|longitud|expira\w*|expires?|ttl|scope|"
    r"algoritmo|algorithm|formato|format|version|count|conteo|total)(?:[^a-z0-9]|$)")
MARCADOR = re.compile(r"(?i)^(tu|your|su|mi|my)[-_ ]|aqu[ií]$|here$|^x+$|^\*+$|example|ejemplo|placeholder|^none$|^null$|^<.*>$|^\$(?:\{|[A-Z_]+$)|^\{.*\}$|^%")
CADENAS_SECRETAS = [
    (re.compile(r"\b[a-zA-Z][a-zA-Z0-9+.-]*://[^/\s:@'\"]*:(?![{<%]|\$\{|\$[A-Z_]+@)[^/\s@'\"{}]{2,}@"), "clave dentro de una URL o cadena de conexión"),
    (re.compile(r"(?i)(?:^|;)\s*(?:pwd|password)\s*=\s*\{(?=[^}]*[^A-Za-z_}])(?![$\s])[^}\s{]{4,}\}"), "clave en la cadena de conexión"),
    (re.compile(r"(?is)\binsert\b[^;]*\bvalues\s*\(\s*'(?:admin|root|administrador)[^']*'\s*,\s*'(?![{$<%?])[^'{}]{4,}'"), "cuenta de administrador con clave escrita en SQL"),
    (re.compile(r"(?i)jdbc:oracle:thin:[^/\s:@'\"]+/(?![{$<%])[^\s@'\"{}]{4,}@"), "clave dentro de una URL o cadena de conexión"),
    (re.compile(r"(?i)\b(?:curl|wget)\b[^\n]*\s(?:-u|--user)[= ]\s*[^\s:'\"]+:(?![{$<%])[^\s'\"{}]{4,}"), "clave en un comando"),
    (re.compile(r"(?im)^\s*[\"']?(?:password|passwd|pwd|secret|secret_key|api_key|apikey|token|access_token)[\"']?\s*:\s*[\"']?(?=[^\s\"'{}]*\d)(?![{$<%])[^\s\"'{}]{6,}[\"']?,?\s*$"), "clave escrita en una configuración embebida"),
    (re.compile(r"(?i)://(?=[^/\s:@'\"{}]*\d)[^/\s:@'\"{}]{8,}@"), "token como usuario dentro de una URL"),
    (re.compile(r"(?i)[?&](?:key|subscription[_-]?key|auth[_-]?key)=(?=[^&\s'\"]*\d)[^&\s'\"{}]{12,}"), "llave en los parámetros de la URL"),
    (re.compile(r"(?i)(?:^|[\s;&?,(])(?:password|passwd|pwd|secret|token|api[_-]?key)\s*=\s*(?:\\?[\"'])(?![{$<%?]|tu[-_ ]|your|su[-_ ]|mi[-_ ]|my[-_ ]|x{3}|\*{3}|example|ejemplo|placeholder)[^\s\"'{}\\]{4,}(?:\\?[\"'])"), "clave entre comillas en la cadena de conexión"),
    (re.compile(r"(?is)\bcreate\s+(?:or\s+replace\s+)?(?:persistent\s+|temporary\s+)?secret\b.*?\b(?:secret|key_id|password|token)\s+'(?![{$<%?]|tu[-_ ]|your|example|ejemplo|placeholder)[^'{}]{4,}'"), "clave escrita en un CREATE SECRET de SQL"),
    (re.compile(r"(?i)\bs3_(?:secret_access_key|access_key_id|session_token)\s*=\s*'(?![{$<%?]|tu[-_ ]|your|example|ejemplo|placeholder)[^'{}]{4,}'"), "llave de S3 escrita en SQL"),
    (re.compile(r"(?is)\b(?:create|alter)\s+(?:user|role)\b.*?\b(?:password|identified\s+by)\s+'(?![{$<%?]|tu[-_ ]|your|example|ejemplo|placeholder)[^'{}]{4,}'"), "clave escrita en un CREATE USER de SQL"),
    (re.compile(r"(?i)(?:^|[\s;&?])(password|passwd|pwd|pass|accountkey|sharedaccesskey|sharedaccesssignature|access[_-]?token|access[_-]?key|client[_-]?secret|api[_-]?key|app[_-]?token|"
                r"\$\$app_token|auth[_-]?token|token|sig|secret)\s*=\s*(?![{$<%])[^\s;&'\"{}]{4,}"), "clave en la cadena de conexión o en la URL"),
    (re.compile(r"(?i)\b(bearer\s+[a-z0-9._~+/-]{12,}|basic\s+[a-z0-9+/]{8,}={0,2})"), "token escrito en un encabezado"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "llave privada escrita en el código"),
    (re.compile(r"(?i)--(password|passwd|token|api-key|apikey|secret)[= ](?![{$<%])\S{4,}"), "clave en un comando"),
    (re.compile(r"(sk-[A-Za-z0-9_-]{20,}|sk_live_[A-Za-z0-9]{16,}|rk_live_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{16,}|\b(?:tok|tkn|token|apikey|api_key)_(?:[a-z]+_)?(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{16,}|\bbot\d{6,}:[A-Za-z0-9_-]{30,}|/services/T[A-Z0-9]{6,}/B[A-Z0-9]{6,}/[A-Za-z0-9]{16,}|/api/webhooks/\d{6,}/[A-Za-z0-9_-]{30,}|github_pat_[A-Za-z0-9_]{30,}|"
                r"glpat-[A-Za-z0-9_-]{16,}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{30,}|ya29\.[A-Za-z0-9_-]{20,}|SG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}|"
                r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,})"), "llave con formato conocido"),
]
FUERTES_DE_LINEA = CADENAS_SECRETAS[-1][0]


def nivel_secreto(nombre):
    n = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", nombre or "")
    if not n or NOMBRE_NO_SECRETO.search(n):
        return None
    if NOMBRE_SECRETO.search(n):
        return "fuerte"
    return "debil" if NOMBRE_DEBIL.search(n) else None


def _entropia(v):
    c = Counter(v)
    return -sum(k / len(v) * math.log2(k / len(v)) for k in c.values())


def valor_secreto(v, nivel):
    if isinstance(v, bytes):
        v = v.decode("latin-1")
    if not isinstance(v, str):
        return False
    v = re.sub(r"(?i)^(bearer|basic|token)\s+", "", v.strip())
    if len(v) < 4 or MARCADOR.search(v) or re.fullmatch(r"[A-Z][A-Z_]+|[A-Z][A-Z0-9_]*_[A-Z0-9_]*", v):
        return False
    if re.fullmatch(r"[A-Z][A-Z0-9]+", v) and nivel != "fuerte":
        return False
    extension = r"\.(?:csv|tsv|json|txt|pem|key|env|ya?ml|toml|ini|cfg|conf|crt|cer|pub|p12|pfx|jks|enc|gpg|age|bin|secret)$" if nivel == "fuerte" else r"\.[a-z]{2,5}$"
    if re.match(r"(?i)^[a-z][a-z0-9+.-]*://", v) or v.startswith(("/", "./", "../", "~")) or re.search(extension, v):
        return False
    if nivel == "fuerte":
        return len(re.findall(r"\s", v)) < 3
    if re.search(r"\s", v) or re.fullmatch(r"[a-z]+([_.-][a-z0-9]+)*", v):
        return False
    return len(v) >= 6 and bool(re.search(r"\d", v) and re.search(r"[A-Za-z]", v)) or _entropia(v) >= 3.8


def _es_alfabeto(v):
    """Cadena hecha de tramos en orden (ABCDEFGH...): es un alfabeto, no una llave."""
    return sum(0 < ord(b) - ord(a) <= 2 for a, b in zip(v, v[1:])) / max(len(v) - 1, 1) >= 0.8


def alta_entropia(v):
    if not isinstance(v, str) or len(v) < 20 or not re.fullmatch(r"[A-Za-z0-9+/_=.~-]+", v) or _es_alfabeto(v):
        return False
    if re.fullmatch(r"[0-9a-fA-F]{32}|[0-9a-fA-F]{40}|[0-9a-fA-F]{64}|[0-9a-fA-F-]{36}", v) or re.search(r"\.[a-zA-Z0-9]{2,5}$", v) or "/" in v[:3]:
        return False
    mayus, minus, digito = bool(re.search(r"[A-Z]", v)), bool(re.search(r"[a-z]", v)), bool(re.search(r"\d", v))
    if not digito or _entropia(v) < 3.6:
        return False
    if re.search(r"[_.-]", v) and all(re.fullmatch(r"[A-Z]?[a-z]{2,}\d{0,3}|[A-Z]{2,}|\d+", t) for t in re.split(r"[_./-]+", v)):
        return False   # palabras y años unidos: Presupuesto_Ejecutado_2024 es un nombre, no una llave
    if mayus and minus:
        return True
    separadores = len(re.findall(r"[_.-]", v))
    return separadores == 0 and len(v) >= 24 and sum(c.isdigit() for c in v) / len(v) >= 0.2


# ---------------- CWE-532: datos personales ----------------
PERSONALES = {"rut", "patrimonio", "remuneracion", "cedula", "cc", "documento", "identificacion", "nuip", "pasaporte", "correo", "email", "mail", "telefono", "celular", "movil",
              "direccion", "direccione", "domicilio", "apellido", "tarjeta", "cvv", "iban", "salario", "sueldo", "ssn", "dni", "password", "passwd",
              "pwd", "contrasena", "secret", "secreto", "token", "apikey", "representante", "paciente"}
CAMPOS_DE_FILA = {"nombre", "nombres", "firstname", "lastname", "first_name", "last_name"}   # solo si vienen de una fila de datos
PERSONALES_EXACTOS = {"ingreso_anual", "ingreso_mensual", "llave_privada", "llave_privada_pem", "private_key_pem", "clave_privada", "nombre_completo", "nombre_persona", "nombre_contratista", "nombre_proveedor", "proveedor_adjudicado",
                      "representante_legal", "numero_cuenta", "cuenta_bancaria", "api_key", "access_key", "secret_key", "private_key", "headers", "encabezados", "cabeceras", "cookies",
                      "credenciales", "credentials", "payload", "clave", "clave_acceso", "clave_api", "clave_secreta", "clave_usuario", "clave_db", "clave_bd",
                      "database_url", "database_uri", "db_url", "db_uri", "url_bd", "url_db", "uri_bd", "dsn", "pg_dsn", "conn_str", "conn_string", "connection_string", "cadena_conexion", "cadena_de_conexion",
                      "sqlalchemy_database_uri", "sqlalchemy_url", "mongo_uri", "mongodb_uri", "mongo_url", "redis_url", "postgres_url", "broker_url"}
OBJETOS_ENTEROS = {"registro", "fila", "row", "record", "persona", "usuario", "cliente", "ciudadano", "contratista", "empleado", "titular", "beneficiario", "contacto",
                   "afiliado", "proveedor", "paciente"}   # el objeto completo lleva sus datos; un campo suelto se juzga por su nombre
DATOS_DE = re.compile(r"(?i)^datos_(de_|del_)?(pago|personal(es)?|cliente|usuario|persona|contratista|proveedor|titular|beneficiario|paciente|bancarios?|tarjeta|contacto)")
NO_PERSONAL = {"total", "conteo", "cantidad", "count", "n", "len", "longitud", "tipo", "type", "col", "columna", "columnas", "campo", "field", "name",
               "valido", "invalido", "valida", "faltante", "nulos", "vacio", "vacios", "hay", "tiene", "es", "sin", "con", "ruta", "path", "url", "uri", "env",
               "var", "variable", "header", "encabezado", "hash", "hasheado", "enmascarado", "masked", "oculto", "anonimo", "seudonimo", "pseudonimo",
               "sha256", "prefijo", "ultimos", "mascara", "mask", "cifrado", "cifrada", "oculta", "enmascarada", "anonima", "seudonima", "hasheada", "truncado", "truncada", "parcial", "invalida",
               "ofuscado", "ofuscada", "protegido", "protegida", "digito", "sufijo", "regex", "patron", "pattern", "nombre_archivo", "expira", "expires", "ttl",
               "existe", "presente", "ok", "formato", "id", "de_entidad", "entidad"}
_ruta_secop = Path(__file__).resolve().parent.parent / "baterias" / "privacidad" / "columnas_secop.json"
try:
    # la lista de columnas también trae nombres genéricos («nombre», «nombres»): como columna identifican a personas, pero
    # en el código son variables corrientes y solo cuentan si vienen de una fila de datos (CAMPOS_DE_FILA, L59)
    PERSONALES_EXACTOS |= set(json.loads(_ruta_secop.read_text(encoding="utf-8")).get("personal", [])) - CAMPOS_DE_FILA
except (OSError, ValueError):
    pass
ENMASCARA = re.compile(r"(?i)(mask|enmascar|ofusc|ocult|redact|anonim|seudonim|pseudonim|hash|sha\d|^len$|(?<!value_)count|^sum$|nunique|notna|isna|isnull|notnull|^bool$|^type$|"
                       r"isinstance|^shape$|^mean$|^median$|^std$|^var$|^size$)")


def es_sensible(nombre):
    if not isinstance(nombre, str) or len(nombre) > 60 or re.search(r"\s", nombre):
        return False
    bajo = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", nombre)
    bajo = re.sub(r"[^a-z0-9]+", "_", _sin_tildes(bajo).lower()).strip("_")
    if bajo in PERSONALES_EXACTOS or DATOS_DE.match(bajo):
        return True
    partes = [p[:-1] if len(p) > 4 and p.endswith("s") else p for p in bajo.split("_") if p]
    if any(p in NO_PERSONAL for p in partes):
        return False
    return any(p in PERSONALES for p in partes)


# ---------------- CWE-1333: expresiones regulares ----------------
UNIVERSO = frozenset(range(129))
DIGITOS = frozenset(range(48, 58))
ESPACIOS = frozenset(b" \t\n\r\f\v")
PALABRA = frozenset(c for c in range(128) if chr(c).isalnum() or c == 95) | {128}
CATEGORIAS = {sre_c.CATEGORY_DIGIT: DIGITOS, sre_c.CATEGORY_NOT_DIGIT: UNIVERSO - DIGITOS, sre_c.CATEGORY_SPACE: ESPACIOS,
              sre_c.CATEGORY_NOT_SPACE: UNIVERSO - ESPACIOS, sre_c.CATEGORY_WORD: PALABRA, sre_c.CATEGORY_NOT_WORD: UNIVERSO - PALABRA}
REPETICIONES = (sre_c.MAX_REPEAT, sre_c.MIN_REPEAT)
SIN_ANCHO = (sre_c.AT, sre_c.ASSERT, sre_c.ASSERT_NOT)


_GRUPOS_REGEX = {}   # grupo -> caracteres que captura, para que una referencia \1 no cuente como «cualquier cosa»
TOPE_CONST = 200_000  # una constante armada por sumas no pasa de aquí
TOPE_REGEX = 5000    # un patrón más largo no se revisa: se bloquea por tamaño


def _chars(seq):
    out = set()
    for op, av in seq:
        if op is sre_c.LITERAL:
            out.add(min(av, 128))
        elif op is sre_c.NOT_LITERAL:
            out |= UNIVERSO - {min(av, 128)}
        elif op is sre_c.ANY:
            out |= UNIVERSO - {10}
        elif op is sre_c.IN:
            dentro, negado = set(), False
            for o, a in av:
                if o is sre_c.NEGATE:
                    negado = True
                elif o is sre_c.LITERAL:
                    dentro.add(min(a, 128))
                elif o is sre_c.RANGE:
                    dentro |= set(range(min(a[0], 128), min(a[1], 128) + 1))
                elif o is sre_c.CATEGORY:
                    dentro |= CATEGORIAS.get(a, UNIVERSO)
            out |= (UNIVERSO - dentro) if negado else dentro
        elif op is sre_c.SUBPATTERN:
            out |= _chars(av[3])
        elif op is sre_c.BRANCH:
            for r in av[1]:
                out |= _chars(r)
        elif op in REPETICIONES or op is getattr(sre_c, "POSSESSIVE_REPEAT", None):
            out |= _chars(av[2])
        elif op is getattr(sre_c, "ATOMIC_GROUP", None):
            out |= _chars(av)
        elif op is sre_c.GROUPREF:
            out |= _GRUPOS_REGEX.get(av, UNIVERSO)
    return out


def _anulable(seq):
    for op, av in seq:
        if op in SIN_ANCHO:
            continue
        if op in REPETICIONES or op is getattr(sre_c, "POSSESSIVE_REPEAT", None):
            if av[0] != 0 and not _anulable(av[2]):
                return False
        elif op is sre_c.SUBPATTERN:
            if not _anulable(av[3]):
                return False
        elif op is sre_c.BRANCH:
            if not any(_anulable(r) for r in av[1]):
                return False
        else:
            return False
    return True


def _primeros(seq):
    out = set()
    for it in seq:
        op, av = it
        if op in SIN_ANCHO:
            continue
        if op is sre_c.SUBPATTERN:
            out |= _primeros(av[3])
        elif op is sre_c.BRANCH:
            for r in av[1]:
                out |= _primeros(r)
        elif op in REPETICIONES:
            out |= _primeros(av[2])
        else:
            out |= _chars([it])
        if not _anulable([it]):
            break
    return out


def _variable(it):
    op, av = it
    if op in REPETICIONES:
        return av[1] > av[0] or any(_variable(x) for x in av[2])
    if op is sre_c.SUBPATTERN:
        return any(_variable(x) for x in av[3])
    if op is sre_c.BRANCH:
        ramas = av[1]
        if any(_anulable(r) for r in ramas) or any(_variable(x) for r in ramas for x in r):
            return True
        vistos = set()
        for r in ramas:
            p = _primeros(r)
            if vistos & p:
                return True
            vistos |= p
    return False


def _aplanar(seq):
    out = []
    for it in seq:
        if it[0] is sre_c.SUBPATTERN:
            out.extend(_aplanar(it[1][3]))
        else:
            out.append(it)
    return out


class _NoDeterminista(Exception):
    pass


def _ci(cs):
    return set(cs) | {ord(chr(c).swapcase()) for c in cs if c < 128 and chr(c).isalpha()}


def _codigo_prefijo(ramas):
    """Alternativas de solo letras fijas, sin que una sea inicio de otra: el texto decide cuál es."""
    textos = []
    for r in ramas:
        if not r or any(op is not sre_c.LITERAL for op, _ in r):
            return None
        textos.append(tuple(av for _, av in r))
    if any(a[:len(b)] == b for i, a in enumerate(textos) for j, b in enumerate(textos) if i != j):
        return None
    return {min(t[0], 128) for t in textos}


def _g_seq(seq, pos, sig):
    nula, pri, ult = True, set(), set()
    for it in seq:
        n2, p2, u2 = _g_item(it, pos, sig)
        for x in ult:
            _g_enlaza(x, p2, sig)
        if nula:
            pri |= p2
        ult = (ult | u2) if n2 else u2
        nula = nula and n2
    return nula, pri, ult


def _g_enlaza(x, destinos, sig):
    for y in destinos:
        if y in sig[x]:   # dos caminos al mismo sitio: (a+)+
            raise _NoDeterminista
        sig[x].add(y)


def _g_item(it, pos, sig):
    op, av = it
    prefijo = _codigo_prefijo(av[1]) if op is sre_c.BRANCH else None
    if op in (sre_c.LITERAL, sre_c.NOT_LITERAL, sre_c.ANY, sre_c.IN) or prefijo:
        pos.append(_ci(prefijo or _chars([it])))
        sig.append(set())
        i = len(pos) - 1
        return False, {i}, {i}
    if op is sre_c.AT:
        return True, set(), set()
    if op is sre_c.SUBPATTERN:
        return _g_seq(av[3], pos, sig)
    if op in REPETICIONES:
        nula, pri, ult = _g_seq(av[2], pos, sig)
        if av[1] > 1:
            for x in ult:
                _g_enlaza(x, pri, sig)
        return nula or av[0] == 0, pri, ult
    if op is sre_c.BRANCH:
        nula, pri, ult = False, set(), set()
        for r in av[1]:
            n2, p2, u2 = _g_seq(r, pos, sig)
            nula, pri, ult = nula or n2, pri | p2, ult | u2
        return nula, pri, ult
    raise _NoDeterminista


def _determinista(cuerpo):
    """Autómata de Glushkov del cuerpo repetido: si en cada paso el siguiente carácter decide el camino, no hay retroceso que multiplicar."""
    pos, sig = [], []
    try:
        nula, pri, ult = _g_seq(cuerpo, pos, sig)
        if nula:
            return False
        for x in ult:
            _g_enlaza(x, pri, sig)
    except _NoDeterminista:
        return False

    def sin_cruce(conjunto):
        vistos = set()
        for i in conjunto:
            if vistos & pos[i]:
                return False
            vistos |= pos[i]
        return True
    return sin_cruce(pri) and all(sin_cruce(s) for s in sig)


def _ambigua(cuerpo):
    """¿Una repetición de este cuerpo puede partir el mismo texto de muchas maneras?"""
    if _determinista(cuerpo):
        return False
    items = _aplanar(cuerpo)
    for it in items:
        if it[0] is sre_c.BRANCH:
            ramas = [str(list(r)) for r in it[1][1]]
            if len(set(ramas)) < len(ramas):
                return True
    for i, it in enumerate(items):
        if not _variable(it):
            continue
        c = _chars([it])
        otros = items[:i] + items[i + 1:]
        if all(_anulable([o]) or (_chars([o]) & c) for o in otros):
            return True
        # dos tramos variables seguidos que aceptan lo mismo: cada vuelta se puede partir de varias maneras, aunque haya un separador fijo
        for o in items[i + 1:]:
            if _variable(o) and (_chars([o]) & c):
                return True
            if not _anulable([o]):
                break
    return False


def _pocas_formas(cuerpo, total):
    """(?:\\d{1,2}){1,10}: tope corto de tramos cortos; se puede partir de pocas maneras en total, no cuelga a nadie."""
    if total == sre_c.MAXREPEAT:
        return False
    formas = 1
    for op, av in _aplanar(cuerpo):
        if op in REPETICIONES:
            if av[1] == sre_c.MAXREPEAT or any(o not in (sre_c.LITERAL, sre_c.IN, sre_c.ANY, sre_c.NOT_LITERAL) for o, _ in av[2]):
                return False
            formas *= av[1] - av[0] + 1
        elif op not in (sre_c.LITERAL, sre_c.IN, sre_c.ANY, sre_c.NOT_LITERAL, sre_c.AT):
            return False
    return formas ** total < 5000


def _hijos_regex(op, av):
    if op in REPETICIONES or op is getattr(sre_c, "POSSESSIVE_REPEAT", None):
        return [av[2]]
    if op is sre_c.SUBPATTERN:
        return [av[3]]
    if op is sre_c.BRANCH:
        return list(av[1])
    if op in (sre_c.ASSERT, sre_c.ASSERT_NOT):
        return [av[1]]
    if op is getattr(sre_c, "ATOMIC_GROUP", None):
        return [av]
    if op is sre_c.GROUPREF_EXISTS:
        return [r for r in av[1:] if r is not None]
    return []


def _anota_grupos(seq):
    for op, av in seq:
        if op is sre_c.SUBPATTERN and av[0] is not None:
            _GRUPOS_REGEX[av[0]] = frozenset(_chars(av[3]))
        for h in _hijos_regex(op, av):
            _anota_grupos(h)


def _recorre_regex(seq, veces=1):
    """veces = cuántas repeticiones envuelven a seq: ((x){7}){7} repite 49 aunque cada tope sea corto."""
    planos = _aplanar(seq)
    for a, b in zip(planos, planos[1:]):
        if a[0] in REPETICIONES and b[0] in REPETICIONES and a[1][1] == sre_c.MAXREPEAT and b[1][1] == sre_c.MAXREPEAT and _chars([a]) == _chars([b]):
            return True
    for op, av in seq:
        if op in REPETICIONES:
            mn, mx, cuerpo = av
            total = sre_c.MAXREPEAT if mx == sre_c.MAXREPEAT else min(veces * mx, sre_c.MAXREPEAT)
            if (total == sre_c.MAXREPEAT or total >= 8) and _ambigua(cuerpo) and not _pocas_formas(cuerpo, total):
                return True
            if _recorre_regex(cuerpo, total):
                return True
        else:
            if any(_recorre_regex(h, veces) for h in _hijos_regex(op, av)):
                return True
    return False


def _revisa_regex(patron, banderas=0):
    try:
        arbol = sre_parse.parse(patron, banderas)
        _GRUPOS_REGEX.clear()
        _anota_grupos(arbol)
        return _recorre_regex(arbol)
    except (RecursionError, MemoryError):   # demasiado anidado para revisarlo: falla cerrada
        return True
    except Exception:   # un patrón que no compila no es asunto de esta regla
        return False


def regex_catastrofica(patron, verbose=False):
    if isinstance(patron, bytes):
        patron = patron.decode("latin-1")
    if len(patron) > TOPE_REGEX:
        return True
    # un patrón en varias líneas casi siempre va con re.VERBOSE, aunque la bandera esté en otra variable
    return _revisa_regex(patron) or ((verbose or "\n" in patron) and _revisa_regex(patron, re.VERBOSE))


SQL_REGEX = re.compile(r"""(?i)(?:\b(?:regexp|rlike|similar\s+to)\s+|~\*?\s*|\b(?:regexp_\w+|rlike)\s*\([^,'"]*,\s*)(?:'([^']*)'|"([^"]*)")""")


def regex_en_sql(texto):
    """Patrón dentro del propio SQL: REGEXP, RLIKE, ~, regexp_replace(col, '...')."""
    for m in SQL_REGEX.finditer(texto):
        p = m.group(1) if m.group(1) is not None else m.group(2)
        if regex_catastrofica(p) or ("\\\\" in p and regex_catastrofica(p.replace("\\\\", "\\"))):
            return True
    return False


# ---------------- tablas de las reglas ----------------
DESERIALIZA = {"pickle", "_pickle", "cPickle", "dill", "cloudpickle", "jsonpickle", "joblib", "shelve", "marshal"}
SUMIDEROS_SQL = {"execute", "executemany", "executescript", "sql", "query", "read_sql", "read_sql_query", "raw", "exec_driver_sql", "run_query"}
SUMIDEROS_EXPR = {"filter", "where", "expr", "selectExpr", "having"}
SANEADORES_SQL = {"int", "float", "bool", "len", "round", "abs", "quote_identifier", "quote_ident", "Identifier", "Literal", "escape_identifier"}
SANEADORES_CMD = {"quote", "int", "float", "len", "abs", "round"}
SANEADORES_HTML = {"escape", "escape_html", "quote", "quote_plus", "clean", "sanitize", "sanitizar", "urlencode", "int", "float", "len", "round", "abs",
                   "sum", "count", "mean", "max", "min", "nunique", "format_html", "conditional_escape", "to_html", "isoformat", "strftime", "date"}
SANEADORES_DATO = {"int", "float", "bool", "len", "basename", "secure_filename", "escape", "quote", "quote_plus", "abs", "round", "sum", "count", "isoformat",
                   "strftime", "mean", "max", "min", "nunique", "hexdigest"}
FUENTES = {"input", "parse_args", "namelist", "getnames", "getmembers", "json", "iterrows", "itertuples", "DictReader", "reader", "fetchall", "fetchone",
           "fetchmany", "read_csv", "read_json", "read_excel", "read_parquet", "read_table", "readline", "readlines", "read", "load", "loads", "safe_load",
           "get_json", "getlist", "recv"}
FILAS = {"iterrows", "itertuples", "DictReader", "reader", "fetchall", "fetchmany", "fetchone", "collect", "to_dict", "toLocalIterator"}
GUARDAS_RUTA = {"is_relative_to", "commonpath", "commonprefix", "relative_to", "safe_join", "secure_filename"}
SUMIDEROS_RUTA = {"open", "read_csv", "read_parquet", "read_json", "read_excel", "read_table", "read_xml", "read_feather", "read_orc", "read_fwf", "to_csv",
                  "to_parquet", "to_json", "to_excel", "remove", "unlink", "rmtree", "copy", "copy2", "copyfile", "copytree", "move", "send_file", "csv", "parquet",
                  "orc", "save", "ZipFile", "TarFile", "listdir", "scandir"}
SUMIDEROS_RUTA |= {"read_pickle", "read_hdf", "read_stata", "read_sas", "read_spss", "read_ndjson", "read_ipc", "read_avro", "read_delta", "scan_csv", "scan_parquet", "scan_ndjson",
                   "scan_ipc", "write_csv", "write_parquet", "write_json", "write_ndjson", "to_pickle", "to_feather", "to_hdf", "to_orc", "to_stata", "loadtxt", "genfromtxt",
                   "textFile", "wholeTextFiles", "saveAsTextFile"}
LECTOR_SPARK = {"json", "text", "avro", "xml"}   # solo con spark.read / df.write delante: json y text a secas significan otra cosa
RESUELVE_RUTA = {"resolve", "realpath", "abspath", "normpath"}   # estas sí colapsan los ..
SQL_LEE_ARCHIVO = re.compile(r"(?is)\b(read_\w+|parquet_scan|sniff_csv|glob)\s*\(\s*(\[\s*)?(\?|\$|%s|:\w)|\b(copy|attach)\b.*(\?|\$\d|%s|:\w)")
METODOS_RUTA = {"read_text", "read_bytes", "write_text", "write_bytes", "open", "unlink", "rmdir", "touch"}
CLAVES_RUTA = ("path", "ruta", "filepath", "file", "fname", "filename", "path_or_buf", "src", "dst", "name")
SUBPROCESO = {"run", "call", "check_call", "check_output", "Popen"}
DE_RED = {"get", "post", "put", "patch", "delete", "head", "options", "request", "Session", "Client", "AsyncClient", "PoolManager", "urlopen", "connect", "create_engine", "download",
          "Elasticsearch", "OpenSearch", "stream", "ClientSession", "TCPConnector"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "cmd", "cmd.exe", "powershell", "pwsh", "/bin/sh", "/bin/bash", "/usr/bin/bash"}
RE_FUNCS = {"compile", "match", "search", "fullmatch", "findall", "finditer", "sub", "subn", "split"}
STR_REGEX = {"contains", "match", "fullmatch", "extract", "extractall", "findall", "count"}
NOMBRE_PATRON = re.compile(r"(?i)(patron|regex|regexp|pattern|expresion|^er_|_er$|^re_)")
NOMBRE_TIEMPO = re.compile(r"(?i)(expir|vence|vencim|ttl|tiempo|inicio|fin$|fecha|timestamp|creado|emitido|duracion|edad|segundos)")
CONTEXTO_SECRETO = re.compile(r"(?i)(token|clave|contrase|passw|pwd|secret|sesion|session|otp|(?:^|_)pin(?:_|$)|nonce|salt|(?:^|_)sal(?:_|$)|api_?key|reset|csrf|acceso|"
                              r"verificaci|activaci|invitaci|recuper|seudonim|pseudonim|anonim|cupon|voucher|credencial|llave|(?:^|_)key(?:_|$)|"
                              r"codigos?+(?!_?(?:de_)?(?:postal|dane|municip|depart|divipola|ciiu|unspsc|barras|pais|ciudad|area|producto|item|sku|contrato|proceso|entidad|cliente|empleado|segmento|categoria|tipo|banco|moneda|error|estado|cuenta|agencia|sucursal|region|zona|vereda|barrio))|"
                              r"(?<!puntos_)canje|ticket(?!_?(?:promedio|medio|valor|monto|total|precio))|enlace|invit(?!ados?)|identificador|"
                              r"(?:verification|confirmation)(?!_(?:sample|set|split|data))|(?:verify|sms|mfa|auth|login|confirm|redeem|promo|gift|coupon|discount|invite|access|activation)_?codes?(?:_|$)|"
                              r"activation_(?:link|token|key)|one_?time|magic_?link|passcode|credential|coupon)")
TLS_KW = {"verify": False, "verify_ssl": False, "ssl_verify": False, "verify_certs": False, "validate_certs": False, "check_hostname": False, "ssl": False,
          "verify_tls": False, "tls_verify": False, "assert_hostname": False, "use_ssl": False, "insecure": True, "ssl_verify_cert": False}
TLS_FALSO = re.compile(r"(?i)^(verify|ssl|use_ssl|assert_hostname|ssl_match_hostname)$|(verif|valid|check).*(ssl|tls|cert|hostname)|(ssl|tls|cert|hostname).*(verif|valid|check)")
TLS_CIERTO = re.compile(r"(?i)(allow|accept|trust|ignore|skip|disable|no).{0,12}(invalid|insecure|cert|ssl|tls|verif)|insecure|danger.*(cert|ssl|tls)")


def apaga_tls(nombre, valor):
    if not isinstance(nombre, str):
        return False
    return (valor is False and bool(TLS_FALSO.search(nombre))) or (valor is True and bool(TLS_CIERTO.search(nombre)))


TLS_ATTR = {"_create_unverified_context", "_create_stdlib_context", "CERT_NONE", "CERT_OPTIONAL", "InsecureRequestWarning", "disable_warnings", "PROTOCOL_SSLv2", "PROTOCOL_SSLv3",
            "PROTOCOL_TLSv1", "PROTOCOL_TLSv1_1"}
TLS_TEXTO = re.compile(r"(?i)(sslmode=(disable|allow|prefer|require|no-verify)\b|trustservercertificate=(true|yes|1)\b|usessl=false|encrypt=(false|no)\b|\bssl=false|sslverify=false|ssl_verify_cert=false|"
                       r"(?-i:\bcurl\b[^|;&\n]*\s-[a-zA-Z]*k[a-zA-Z]*(?=\s|$))|"
                       r"--insecure\b|--no-check-certificate\b|CERT_NONE\b|tls(allowinvalid\w+|insecure)=true)")
TLS_OPCION = {"sslmode": {"disable", "allow", "prefer", "require", "no-verify"}, "trustservercertificate": {"true", "yes", "1"}, "ssl": {"false"}, "usessl": {"false"}, "encrypt": {"false", "no"}, "sslverify": {"false"},
              "spark.ssl.enabled": {"false"}}
TLS_ENTORNO = {"PYTHONHTTPSVERIFY", "CURL_CA_BUNDLE", "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE", "NODE_TLS_REJECT_UNAUTHORIZED", "GIT_SSL_NO_VERIFY"}
CRIPTO_DEBIL = {"MODE_ECB", "ECB", "ARC4", "ARC2", "DES", "DES3", "TripleDES", "Blowfish", "RC4", "RC2", "MD5", "MD4", "SHA1", "IDEA", "SEED", "CAST5"}
HASH_DEBIL = {"md5", "sha1", "md4", "md2", "sha"}
HASH_SIN_SAL = {"sha224", "sha256", "sha384", "sha512", "sha3_256", "sha3_512", "blake2b", "blake2s", "sha2", "xxhash", "crc32", "adler32", "hash_pandas_object", "hash_array",
                "b64encode", "urlsafe_b64encode", "hash"}
CONTEXTO_SEUDONIMO = re.compile(r"(?i)(seudonim|pseudonim|anonim|ofusc|enmascar|proteg|cifr|encript|encrypt)")
HUELLA_INTEGRIDAD = re.compile(r"(?i)(checksum|suma|huella|fingerprint|etag|integridad|dedup|cache|particion|shard|bucket)")
CON_SAL = re.compile(r"(?i)(^|[^a-z])(sal|salt|pepper|llave|key|secret|secreto|hmac)([^a-z]|$)")
SQL_HASH = re.compile(r"(?i)\b(md5|sha1|sha256|sha2|hash)\s*\(\s*[\w.]*(cedula|documento|identificaci|correo|email|telefono|celular|nombre_|proveedor_adj)[\w.]*\s*[,)]")
SQL_HASH_NORMALIZADO = re.compile(r"(?is)\b(?:md5|sha1|sha256|sha512|sha2|hash)\s*\(\s*(?:(?:lower|upper|trim|ltrim|rtrim|cast|try_cast|to_varchar|strip_accents)\s*\(\s*)*[\w.\"]*(?:cedula|documento|identificaci|correo|email|telefono|celular|nombre_|paciente|nuip)[\w.\"]*\s*(?:(?:::|\bAS\b)\s*\w+\s*)?\)(?:\s*\))*+(?!\s*(?:\|\||\+|,(?!\s*\d+\s*\))))")
SQL_AZAR = re.compile(r"(?im)\b(?:random|rand|randomblob)\s*\(\s*\d*\s*\)[^\n;]{0,80}?\bAS\s+[\"'`]?(\w+)[\"'`]?\s*(?:,|$|\bFROM\b)")
ES_HTML = re.compile(r"(?i)</?(html|head|body|div|span|p|a|td|tr|th|table|tbody|thead|ul|ol|li|h[1-6]|b|i|u|em|strong|img|script|style|br|hr|form|input|button|select|option|code|pre|section|article|nav|header|footer|small|label|link|meta|title|iframe|svg|line|rect|circle|path|text|textarea|center|font|blockquote|dl|dt|dd|main|aside|details|summary|caption|col|colgroup)(\s[^<>]*)?/?>|<[a-zA-Z]+\s+[a-zA-Z-]+=")
LOG_NIVELES = {"debug", "info", "warning", "warn", "error", "critical", "exception", "log"}
HTML_SUMIDEROS = {"HTML", "displayHTML", "Markup", "mark_safe", "render_template_string", "make_response"}


CONSERVAN_DATO = {"value_counts", "unique", "drop_duplicates", "to_string", "astype", "fillna", "dropna", "sort_values", "explode", "filter", "where", "str", "repr", "format", "strip", "lower", "upper", "title", "replace", "join", "get", "pop", "select", "col", "column", "to_dict", "to_json", "dict", "vars", "asdict",
                  "_asdict", "items", "values", "tolist", "to_list", "dumps", "list", "tuple", "head", "tail", "sample", "copy", "getenv", "first", "collect", "take", "fetchone", "fetchall"}


class Ambito:
    def __init__(self, nodo, padre=None):
        self.nodo, self.padre = nodo, padre
        self.locales, self.no_constantes = set(), set()
        self.constantes = {}
        self.s = defaultdict(set)
        self.nodos = _propios(nodo)


class Analisis:
    """Recorre un archivo una vez: primero sigue los datos en cada ámbito y luego aplica las reglas."""

    def __init__(self, texto, perfil="pura"):
        self.texto, self.perfil = texto, perfil
        self.hallazgos, self._vistos = [], set()
        self.exentas = defaultdict(set)       # línea -> reglas de Bandit que este análisis ya resolvió (solo perfil usuario)
        self.arbol = ast.parse(texto)
        self._crecen = None
        self.padres = {h: p for p in ast.walk(self.arbol) for h in ast.iter_child_nodes(p)}
        self.imports = {}
        for n in ast.walk(self.arbol):
            if isinstance(n, ast.Import):
                for a in n.names:
                    self.imports[a.asname or a.name.split(".")[0]] = a.name if a.asname else a.name.split(".")[0]
            elif isinstance(n, ast.ImportFrom) and n.module:
                for a in n.names:
                    self.imports[a.asname or a.name] = f"{n.module}.{a.name}"
        self.sanea_html = {f.name for f in ast.walk(self.arbol) if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))
                           and any(isinstance(x, ast.Call) and _nombre_func(x) in ("escape", "clean", "sanitize") for x in ast.walk(f))}
        self.ambitos = {}
        self._crear(self.arbol, None)
        for amb in self.ambitos.values():
            self._flujo(amb)
        self._reglas()

    # ---- ámbitos y flujo de datos ----
    def _crear(self, nodo, padre):
        amb = Ambito(nodo, padre)
        self.ambitos[nodo] = amb
        for n in amb.nodos:
            if isinstance(n, FUNCS):
                self._crear(n, amb)

    def ambito_de(self, n):
        while n not in self.ambitos:
            n = self.padres[n]
        return self.ambitos[n]

    def completo(self, f):
        p = _punteado(f)
        if not p:
            return ""
        raiz, _, resto = p.partition(".")
        base = self.imports.get(raiz, raiz)
        return f"{base}.{resto}" if resto else base

    def _en(self, amb, clave, nombre):
        while amb is not None:
            if nombre in amb.s[clave]:
                return True
            if nombre in amb.locales:
                return False
            amb = amb.padre
        return False

    def _const_nombre(self, amb, nombre):
        while amb is not None:
            if nombre in amb.locales:
                if nombre in amb.no_constantes or nombre not in amb.constantes:
                    return NADA
                return amb.constantes[nombre]
            amb = amb.padre
        return NADA

    def _const(self, e, amb):
        if isinstance(e, ast.Constant):
            return e.value
        if isinstance(e, ast.Name):
            return self._const_nombre(amb, e.id)
        if isinstance(e, ast.BinOp) and isinstance(e.op, ast.Add):
            a, b = self._const(e.left, amb), self._const(e.right, amb)
            if a is not NADA and b is not NADA and type(a) is type(b) and isinstance(a, (str, bytes)):
                return a + b if len(a) + len(b) <= TOPE_CONST else NADA      # bomba de constantes: a = b + b no crece sin límite
            return NADA
        if isinstance(e, ast.BinOp) and isinstance(e.op, ast.Mult):
            a, b = self._const(e.left, amb), self._const(e.right, amb)
            if isinstance(b, bytes):
                a, b = b, a
            if isinstance(a, bytes) and type(b) is int and 0 <= b <= 4096:
                return a * b
            return NADA
        if isinstance(e, ast.Call) and isinstance(e.func, ast.Name) and e.func.id == "bytes" and len(e.args) == 1 and not e.keywords:
            t = self._const(e.args[0], amb)
            if type(t) is int and 0 <= t <= 4096:
                return bytes(t)
            return NADA
        if isinstance(e, ast.JoinedStr):
            partes = []
            for v in e.values:
                c = self._const(v.value, amb) if isinstance(v, ast.FormattedValue) else v.value
                if c is NADA:
                    return NADA
                partes.append(str(c))
            return "".join(partes) if sum(map(len, partes)) <= TOPE_CONST else NADA
        if isinstance(e, ast.Call) and isinstance(e.func, ast.Attribute) and e.args:
            r = self._const(e.func.value, amb)
            if e.func.attr == "join" and isinstance(r, str) and isinstance(e.args[0], (ast.List, ast.Tuple)):
                piezas = [self._const(x, amb) for x in e.args[0].elts]
                if all(isinstance(p, str) for p in piezas) and sum(map(len, piezas)) + len(r) * len(piezas) <= TOPE_CONST:
                    return r.join(piezas)
        if isinstance(e, ast.Call) and isinstance(e.func, ast.Attribute) and e.func.attr == "encode":
            r = self._const(e.func.value, amb)
            if isinstance(r, str):
                return r.encode("utf-8", "ignore")
        if isinstance(e, ast.Call) and not e.args and not e.keywords and isinstance(e.func, ast.Attribute) and e.func.attr in ("strip", "lstrip", "rstrip"):
            r = self._const(e.func.value, amb)
            if isinstance(r, str):
                return getattr(r, e.func.attr)()
        if isinstance(e, ast.Call) and len(e.args) == 1 and _nombre_func(e) == "dedent":
            r = self._const(e.args[0], amb)
            if isinstance(r, str):
                return r
        return NADA

    def _texto(self, e, amb):
        """Parte literal de una cadena, con {} en los huecos."""
        if isinstance(e, ast.Constant):
            return e.value if isinstance(e.value, str) else ""
        if isinstance(e, ast.JoinedStr):
            return "".join(v.value if isinstance(v, ast.Constant) else "{}" for v in e.values)
        if isinstance(e, ast.BinOp) and isinstance(e.op, (ast.Add, ast.Mod)):
            return self._texto(e.left, amb) + (self._texto(e.right, amb) if isinstance(e.op, ast.Add) else "")
        if isinstance(e, ast.Call) and isinstance(e.func, ast.Attribute) and e.func.attr == "format":
            return self._texto(e.func.value, amb)
        if isinstance(e, ast.Name):
            c = self._const(e, amb)
            return c if isinstance(c, str) else ""
        if isinstance(e, ast.Call):
            c = self._const(e, amb)
            return c if isinstance(c, str) else ""
        return ""

    def _textual(self, e, amb):
        if isinstance(e, ast.JoinedStr):
            return True
        if isinstance(e, ast.BinOp) and isinstance(e.op, ast.Add):
            return self._textual(e.left, amb) or self._textual(e.right, amb)
        if isinstance(e, ast.Call) and isinstance(e.func, ast.Attribute) and e.func.attr in ("format", "join"):
            return isinstance(self._const(e.func.value, amb), str)
        return isinstance(self._const(e, amb), str)

    def _interpolaciones(self, e, amb):
        """Piezas que se insertan en una cadena armada; None si e no es una cadena armada."""
        if isinstance(e, ast.JoinedStr):
            vals = [v for v in e.values if isinstance(v, ast.FormattedValue)]
            return vals or None
        if isinstance(e, ast.BinOp) and isinstance(e.op, ast.Add):
            if not self._textual(e, amb):
                return None
            partes = []
            for lado in (e.left, e.right):
                i = self._interpolaciones(lado, amb)
                if i is not None:
                    partes += i
                elif self._const(lado, amb) is NADA:
                    partes.append(lado)
            return partes or None
        if isinstance(e, ast.BinOp) and isinstance(e.op, ast.Mod) and (isinstance(self._const(e.left, amb), str) or isinstance(e.left, (ast.JoinedStr, ast.Subscript))):
            d = e.right
            return list(d.elts) if isinstance(d, ast.Tuple) else (list(d.values) if isinstance(d, ast.Dict) else [d])
        if isinstance(e, ast.Call) and isinstance(e.func, ast.Attribute):
            if e.func.attr == "format" and (isinstance(self._const(e.func.value, amb), str) or self._plantilla_variable(e.func.value)):
                return list(e.args) + [k.value for k in e.keywords]
            if e.func.attr == "join" and isinstance(self._const(e.func.value, amb), str) and self._const(e, amb) is NADA:
                return [e]
            if e.func.attr == "replace" and isinstance(self._const(e.func.value, amb), str) and len(e.args) >= 2:
                return [e.args[1]]
            if e.func.attr in ("substitute", "safe_substitute"):
                return list(e.args) + [k.value for k in e.keywords]
        return None

    def _plantilla_variable(self, e):
        """Plantilla que no es un literal: de un dict (PLANTILLAS[k], .get(k)) o de una variable. spark.read.format(...) no entra: es un atributo."""
        return isinstance(e, (ast.Subscript, ast.Name)) or (isinstance(e, ast.Call) and _nombre_func(e) == "get")

    def _lista_const(self, e, amb):
        if isinstance(e, (ast.List, ast.Tuple, ast.Set)):
            return all(self._const(x, amb) is not NADA for x in e.elts)
        if isinstance(e, ast.Name):
            return self._en(amb, "listas_limpias", e.id) and not self._en(amb, "listas_sucias", e.id)
        if isinstance(e, ast.Call) and _nombre_func(e) in ("sorted", "list", "tuple", "set") and e.args:
            return self._lista_const(e.args[0], amb)
        return False

    def _es_marcas(self, e, amb):
        if isinstance(e, ast.BinOp) and isinstance(e.op, ast.Mult):
            c = self._const(e.left, amb)
            return isinstance(c, str) and bool(re.fullmatch(r"[?,\s]+|(%s[,\s]*)+", c))
        if isinstance(e, ast.Call) and _nombre_func(e) == "join" and e.args:
            lit = [c.value for c in ast.walk(e.args[0]) if isinstance(c, ast.Constant) and isinstance(c.value, str)]
            return bool(lit) and all(re.fullmatch(r"\s*(\?|%s|:\w*|\$\d*)\s*,?\s*", x) for x in lit)
        return False

    def _segura(self, v, amb, saneadores):
        """¿La pieza insertada no puede traer datos de afuera?"""
        if isinstance(v, ast.FormattedValue):
            if _formato_numerico(v.format_spec):
                return True
            v = v.value
        if self._const(v, amb) is not NADA:
            return True
        if isinstance(v, ast.Call):
            nf = _nombre_func(v)
            if nf in saneadores:
                return True
            if nf == "join" and v.args:
                a = v.args[0]
                if self._lista_const(a, amb) or self._es_marcas(v, amb):
                    return True
                if isinstance(a, (ast.GeneratorExp, ast.ListComp)):
                    ok_iter = all(self._lista_const(g.iter, amb) or (isinstance(g.iter, ast.Name) and self._en(amb, "seguras", g.iter.id)) for g in a.generators)
                    pz = self._interpolaciones(a.elt, amb)
                    return ok_iter and (pz is None or all(self._segura(p, amb, saneadores) for p in pz))
        if isinstance(v, ast.Name):
            return self._en(amb, "seguras", v.id) or self._en(amb, "validadas", v.id)
        if isinstance(v, ast.IfExp):
            return self._segura(v.body, amb, saneadores) and self._segura(v.orelse, amb, saneadores)
        if isinstance(v, ast.Subscript) and isinstance(v.value, ast.Name) and v.value.id.isupper():
            return self._mayus_fija(v.value.id)
        return False

    def _mayus_fija(self, nombre):
        """Una constante en MAYÚSCULAS solo es de fiar si está escrita en el código; si sale de un archivo (yaml, json, entorno) es dato de afuera. Importada: no se puede ver, se respeta."""
        for x in ast.walk(self.arbol):
            if isinstance(x, (ast.Assign, ast.AnnAssign)) and getattr(x, "value", None) is not None:
                objetivos = x.targets if isinstance(x, ast.Assign) else [x.target]
                if any(isinstance(t, ast.Name) and t.id == nombre for t in objetivos):
                    v = x.value
                    if not isinstance(v, (ast.Dict, ast.List, ast.Tuple, ast.Set)):
                        return False
                    if not (v.keys if isinstance(v, ast.Dict) else v.elts):
                        return False
                    if any(isinstance(h, ast.Subscript) or (isinstance(h, ast.Call) and _nombre_func(h) not in ("Path", "PurePath")) for h in ast.walk(v)):
                        return False
        return True

    def _patron_entero(self, x, amb):
        """¿Esta llamada exige un texto entero y limitado? match() sin $ ni \\Z solo mira el comienzo, y ., [^...] o \\S dejan pasar ; | y $( ). Lo demás pasa sin revisar."""
        f = x.func
        p, extra = None, list(x.args[2:]) + [k.value for k in x.keywords]
        if self.completo(f) in ("re.match", "re.fullmatch") and x.args:
            p = x.args[0]
        elif isinstance(f, ast.Attribute):
            p = f.value
        if isinstance(p, ast.Call) and self.completo(p.func) == "re.compile" and p.args:
            extra += list(p.args[1:]) + [k.value for k in p.keywords]
            p = p.args[0]
        elif isinstance(p, (ast.Name, ast.Attribute)):
            nombre = p.id if isinstance(p, ast.Name) else p.attr
            for a in ast.walk(self.arbol):
                if isinstance(a, ast.Assign) and isinstance(a.value, ast.Call) and self.completo(a.value.func) == "re.compile" and a.value.args and \
                        any((t.id if isinstance(t, ast.Name) else getattr(t, "attr", None)) == nombre for t in a.targets):
                    extra += list(a.value.args[1:]) + [k.value for k in a.value.keywords]
                    p = a.value.args[0]
                    break
        c = self._const(p, amb) if p is not None else NADA
        if not isinstance(c, str):
            return True     # el patrón no se ve aquí (importado o calculado): no se puede afirmar nada
        sin_clases = re.sub(r"\[(?!\^)(?:\\.|[^\]\\])*\]", "", re.sub(r"\\[^SDW]", "", c))
        if "." in sin_clases or "[^" in sin_clases or re.search(r"\\[SDW]", sin_clases):
            return False
        if _nombre_func(x) == "fullmatch":
            return True
        multilinea = re.match(r"\(\?[a-zA-Z]*m", c) or any(isinstance(h, ast.Attribute) and h.attr in ("M", "MULTILINE") for e in extra for h in ast.walk(e))
        return bool(re.search(r"(?<!\\)(\$|\\Z)$", c)) and not multilinea

    def _sql_ok(self, v, amb):
        return self._segura(v, amb, SANEADORES_SQL)

    def _cmd_ok(self, v, amb):
        return self._segura(v, amb, SANEADORES_CMD)

    def _plantilla_interna(self, a, amb):
        """Un patrón armado solo con parámetros de una función del archivo es una plantilla interna, no un patrón que llega de afuera."""
        f = amb.nodo
        if not isinstance(a, (ast.JoinedStr, ast.BinOp)) or not isinstance(f, FUNCS) or not hasattr(f, "name"):
            return False
        if any(isinstance(x, ast.Call) and (_nombre_func(x) in FUENTES or _punteado(x.func).startswith(("requests.", "httpx."))) for x in ast.walk(a)):
            return False
        parametros = {p.arg for p in f.args.posonlyargs + f.args.args + f.args.kwonlyargs}
        return {x.id for x in ast.walk(a) if isinstance(x, ast.Name) and self._en(amb, "contaminadas", x.id)} <= parametros

    def _contamina(self, e, amb):
        if e is None or isinstance(e, ast.Constant):
            return False
        if isinstance(e, ast.Name):
            return e.id in ("request", "flask_request") or (self._en(amb, "contaminadas", e.id) and not self._en(amb, "validadas", e.id))
        if isinstance(e, ast.Attribute):
            if e.attr in ("name", "stem", "suffix"):
                return False
            if _punteado(e) == "sys.argv":
                return True
        if isinstance(e, ast.FormattedValue) and _formato_numerico(e.format_spec):
            return False
        if isinstance(e, ast.Call):
            nf = _nombre_func(e)
            if nf in SANEADORES_DATO or nf == "escape":
                return False
            comp = self.completo(e.func)
            if nf in FUENTES or comp.startswith(("requests.", "httpx.", "urllib.request.")):
                return True
        return any(self._contamina(h, amb) for h in ast.iter_child_nodes(e))

    def _parametros(self, amb):
        f = amb.nodo
        if not isinstance(f, FUNCS):
            return
        a = f.args
        posicion = a.posonlyargs + a.args
        defectos = dict(zip(reversed([p.arg for p in posicion]), reversed(a.defaults)))
        for p, d in zip(a.kwonlyargs, a.kw_defaults):
            if d is not None:
                defectos[p.arg] = d
        todos = posicion + a.kwonlyargs + ([a.vararg] if a.vararg else []) + ([a.kwarg] if a.kwarg else [])
        for p in todos:
            amb.locales.add(p.arg)
            if p.arg in ("self", "cls"):
                continue
            tipo = p.annotation.id if isinstance(p.annotation, ast.Name) else ""
            d = defectos.get(p.arg)
            if tipo in ("int", "float", "bool") or (isinstance(d, ast.Constant) and isinstance(d.value, (int, float, bool))):
                amb.s["seguras"].add(p.arg)
            else:
                amb.s["contaminadas"].add(p.arg)

    def _flujo(self, amb):
        self._parametros(amb)
        def apunta(t):
            for x in ast.walk(t):
                if isinstance(x, ast.Name):
                    amb.locales.add(x.id)
        for n in amb.nodos:
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    apunta(t)
            elif isinstance(n, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr, ast.For, ast.AsyncFor, ast.comprehension)):
                apunta(n.target)
            elif isinstance(n, (ast.With, ast.AsyncWith)):
                for it in n.items:
                    if it.optional_vars is not None:
                        apunta(it.optional_vars)
        for _ in range(2):
            for n in amb.nodos:
                if isinstance(n, ast.Assign):
                    for t in n.targets:
                        self._asigna(t, n.value, amb)
                elif isinstance(n, (ast.AnnAssign, ast.NamedExpr)) and n.value is not None:
                    self._asigna(n.target, n.value, amb)
                elif isinstance(n, ast.AugAssign):
                    self._asigna(n.target, n.value, amb, aumento=True)
                elif isinstance(n, (ast.For, ast.AsyncFor, ast.comprehension)):
                    self._itera(n.target, n.iter, amb)
                    if isinstance(n, ast.comprehension):
                        for c in n.ifs:
                            self._valida(c, amb)
                elif isinstance(n, (ast.With, ast.AsyncWith)):
                    for it in n.items:
                        if it.optional_vars is not None:
                            self._con(it.optional_vars, it.context_expr, amb)
                elif isinstance(n, (ast.If, ast.IfExp)):
                    self._valida(n.test, amb, n)
                elif isinstance(n, (ast.While, ast.Assert)):
                    self._valida(n.test, amb)
                elif isinstance(n, ast.Call):
                    self._llamada_flujo(n, amb)

    @staticmethod
    def _rama_lo_usa(rama, nombre):
        """Comparar y solo elegir otra cosa (clase = "ok" if estado in LISTA else "alerta") no valida el valor."""
        if rama is None:
            return True
        partes = [rama.body, rama.orelse] if isinstance(rama, ast.IfExp) else list(rama.body) + list(rama.orelse)
        for p in partes:
            for y in ast.walk(p):
                if isinstance(y, (ast.Raise, ast.Return, ast.Continue, ast.Break)) or (isinstance(y, ast.Name) and y.id == nombre):
                    return True
        return False

    def _valida(self, test, amb, rama=None):
        for x in ast.walk(test):
            if isinstance(x, ast.Compare) and isinstance(x.left, ast.Name) and any(isinstance(o, (ast.In, ast.NotIn)) for o in x.ops):
                comp = x.comparators[0]
                if not self._rama_lo_usa(rama, x.left.id):
                    continue
                if not (isinstance(comp, ast.Name) and (self._en(amb, "contaminadas", comp.id) or comp.id in self._coleccion_que_crece())):
                    amb.s["validadas"].add(x.left.id)
            elif isinstance(x, ast.Call):
                nf = _nombre_func(x)
                if nf in ("fullmatch", "match") and self._patron_entero(x, amb):
                    for a in x.args:
                        if isinstance(a, ast.Name):
                            amb.s["validadas"].add(a.id)
                elif nf in ("isdigit", "isalnum", "isidentifier", "isnumeric", "isdecimal", "isalpha") and isinstance(x.func, ast.Attribute) and isinstance(x.func.value, ast.Name):
                    amb.s["validadas"].add(x.func.value.id)

    def _coleccion_que_crece(self):
        """Colecciones que reciben claves variables (cachés, vistos): estar en ellas no valida nada."""
        if self._crecen is None:
            self._crecen = set()
            for x in ast.walk(self.arbol):
                if isinstance(x, ast.Subscript) and isinstance(x.ctx, ast.Store) and isinstance(x.value, ast.Name) and not isinstance(x.slice, ast.Constant):
                    self._crecen.add(x.value.id)
                elif (isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) and isinstance(x.func.value, ast.Name) and x.func.attr in ("add", "append", "setdefault", "update", "extend")
                        and x.args and not isinstance(x.args[0], (ast.Constant, ast.List, ast.Tuple, ast.Set, ast.Dict))):
                    self._crecen.add(x.func.value.id)
        return self._crecen

    def _llamada_flujo(self, n, amb):
        amb.s["llamadas"].add(_nombre_func(n))
        f = n.func
        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.attr in ("append", "extend", "add", "insert") and n.args:
            lista, a = f.value.id, n.args[-1]
            if self._ruta_armada(a, amb):
                amb.s["rutas"].add(lista)
            if self._const(a, amb) is NADA and not self._lista_const(a, amb):
                pz = self._interpolaciones(a, amb)
                if pz is None or not all(self._sql_ok(p, amb) for p in pz):
                    amb.s["listas_sucias"].add(lista)
            if self._html_ok(a, amb):
                amb.s["html"].add(lista)
            if self._sensible_en(a, amb):
                amb.s["sensibles"].add(lista)
        if isinstance(f, ast.Attribute) and f.attr in ("update", "setdefault") and isinstance(f.value, ast.Name):
            if any(self._sensible_en(a, amb) for a in n.args):
                amb.s["sensibles"].add(f.value.id)

    def _con(self, t, ctx, amb):
        if not isinstance(t, ast.Name) or not isinstance(ctx, ast.Call):
            return
        comp, nf = self.completo(ctx.func), _nombre_func(ctx)
        if comp.startswith("tarfile."):
            amb.s["tarfiles"].add(t.id)
        if comp.startswith("zipfile."):
            amb.s["zipfiles"].add(t.id)
        if nf == "open" or self._contamina(ctx, amb):
            amb.s["contaminadas"].add(t.id)
        if nf == "open" and ctx.args:
            texto = self._texto(ctx.args[0], amb)
            nombres = " ".join(y.id if isinstance(y, ast.Name) else y.attr for y in ast.walk(ctx.args[0]) if isinstance(y, (ast.Name, ast.Attribute)))
            if re.search(r"(?i)(\.log\b|log|bitacora|registro)", texto) or re.search(r"(?i)(^|[_\s])(logs?|bitacoras?|registro|audit|auditoria|trazas?)($|[_\s])", nombres):
                amb.s["archivos_log"].add(t.id)

    def _itera(self, t, it, amb):
        nombres = [x.id for x in ast.walk(t) if isinstance(x, ast.Name)]
        if self._lista_const(it, amb) or (isinstance(it, ast.Name) and it.id.isupper() and self._en(amb, "listas_limpias", it.id)):
            amb.s["seguras"].update(nombres)
            return
        if self._contamina(it, amb):
            amb.s["contaminadas"].update(nombres)
        if isinstance(it, ast.Name) and self._en(amb, "rutas", it.id):
            amb.s["rutas"].update(nombres)
        es_fila = (isinstance(it, ast.Call) and _nombre_func(it) in FILAS) or (isinstance(it, ast.Name) and self._en(amb, "iterables_fila", it.id))
        if es_fila:
            ultimo = t.elts[-1] if isinstance(t, ast.Tuple) and t.elts else t
            if isinstance(ultimo, ast.Name):
                amb.s["filas"].add(ultimo.id)
        if isinstance(it, ast.Name) and self._en(amb, "sensibles", it.id):
            amb.s["sensibles"].update(nombres)

    def _asigna(self, t, v, amb, aumento=False):
        s = amb.s
        if isinstance(t, (ast.Tuple, ast.List)):
            if isinstance(v, (ast.Tuple, ast.List)) and len(v.elts) == len(t.elts):
                for a, b in zip(t.elts, v.elts):
                    self._asigna(a, b, amb)
            elif self._contamina(v, amb):
                s["contaminadas"].update(x.id for x in t.elts if isinstance(x, ast.Name))
            return
        if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and isinstance(t.slice, ast.Constant) and es_sensible(t.slice.value) and any((isinstance(x, ast.Call) and ENMASCARA.search(_nombre_func(x))) or (isinstance(x, ast.Name) and ENMASCARA.search(x.id)) for x in ast.walk(v)):
            s["df_enmascarado"].add(t.value.id)
        if not isinstance(t, ast.Name):
            return
        n = t.id
        if self._frame_personal(v, amb):
            s["df_personales"].add(n)
        elif not aumento:
            s["df_personales"].discard(n)
        c = self._const(v, amb)
        if aumento or c is NADA:
            amb.no_constantes.add(n)
            amb.constantes.pop(n, None)
        elif n in amb.constantes and amb.constantes[n] != c:
            amb.no_constantes.add(n)
        else:
            amb.constantes[n] = c
        if self._contamina(v, amb):
            s["contaminadas"].add(n)
        elif not aumento:
            s["contaminadas"].discard(n)
        if self._es_styler(v, amb):
            s["stylers"].add(n)
        elif not aumento:
            s["stylers"].discard(n)
        if isinstance(v, ast.Subscript) and isinstance(v.value, ast.Name) and v.value.id.isupper() and self._mayus_fija(v.value.id):
            s["validadas"].add(n)
        if isinstance(v, ast.Call) and _nombre_func(v) == "get" and isinstance(v.func, ast.Attribute) and isinstance(v.func.value, ast.Name) and v.func.value.id.isupper() and self._mayus_fija(v.func.value.id):
            s["validadas"].add(n)
        if isinstance(v, (ast.List, ast.Tuple, ast.Set)) and self._lista_const(v, amb):
            s["listas_limpias"].add(n)
        if self._es_marcas(v, amb):
            s["seguras"].add(n)
        pz = self._interpolaciones(v, amb)
        dinamica = pz is not None and not all(self._sql_ok(i, amb) for i in pz)
        if dinamica or (isinstance(v, ast.Name) and self._en(amb, "dinamicas", v.id)):
            s["dinamicas"].add(n)
        elif not aumento:
            s["dinamicas"].discard(n)
        if pz is not None and all(self._cmd_ok(i, amb) for i in pz):
            s["comandos_ok"].add(n)
        if self._ruta_armada(v, amb):
            s["rutas"].add(n)
        elif not aumento:
            s["rutas"].discard(n)
        if self._html_ok(v, amb):
            s["html"].add(n)
        elif not aumento:
            s["html"].discard(n)
        # el dato sigue sensible al copiarse o darle formato; lo que devuelve una función cualquiera (un conteo, un resumen) ya es otra cosa
        if self._sensible_en(v, amb) and not (isinstance(v, ast.Call) and _nombre_func(v) not in CONSERVAN_DATO):
            s["sensibles"].add(n)
        if isinstance(v, ast.Call):
            nf, comp = _nombre_func(v), self.completo(v.func)
            if ENMASCARA.search(nf):
                s["enmascaradas"].add(n)
                s["sensibles"].discard(n)
            if comp.startswith("tarfile."):
                s["tarfiles"].add(n)
            if comp.startswith("hashlib."):
                s["hashes"].add(n)
            if comp.startswith("zipfile."):
                s["zipfiles"].add(n)
            if comp in ("random.Random", "numpy.random.default_rng", "numpy.random.RandomState"):
                s["generadores"].add(n)
            if nf in FILAS:
                s["iterables_fila"].add(n)

    # ---- CWE-22: rutas ----
    def _pieza_ruta(self, partes, amb):
        for i, p in enumerate(partes):
            if isinstance(p, ast.Constant) or self._const(p, amb) is not NADA:
                continue
            siguiente = partes[i + 1] if i + 1 < len(partes) else None
            texto = self._const(siguiente, amb) if siguiente is not None else None
            if i == 0 and isinstance(texto, str) and texto.startswith(("/", "\\")):
                continue   # es la carpeta base: lo que manda es lo que va después
            if self._contamina(p, amb):
                return True
        return False

    def _aplanar_suma(self, e):
        if isinstance(e, ast.BinOp) and isinstance(e.op, ast.Add):
            return self._aplanar_suma(e.left) + self._aplanar_suma(e.right)
        return [e]

    def _huecos_de_format(self, e, amb):
        """Lo que entra a los huecos de una plantilla constante con .format, sin el hueco inicial (la carpeta base) ni los numéricos. None si no aplica."""
        if not (isinstance(e, ast.Call) and isinstance(e.func, ast.Attribute) and e.func.attr == "format"):
            return None
        plantilla = self._const(e.func.value, amb)
        if not isinstance(plantilla, str):
            return None
        por_nombre, piezas, siguiente = {k.arg: k.value for k in e.keywords if k.arg}, [], 0
        try:
            campos = list(string.Formatter().parse(plantilla))
        except ValueError:
            return None
        for i, (literal, campo, espec, _) in enumerate(campos):
            if campo is None:
                continue
            raiz = re.split(r"[.\[]", campo)[0]
            if raiz == "":
                raiz, siguiente = siguiente, siguiente + 1
            elif raiz.isdigit():
                raiz = int(raiz)
            pieza = por_nombre.get(raiz) if isinstance(raiz, str) else (e.args[raiz] if raiz < len(e.args) else None)
            es_base = i == 0 and not literal and len(campos) > 1 and campos[1][0].startswith(("/", "\\"))
            if pieza is None or es_base or re.search(r"[bcdoxXneEfFgG%]$", espec or ""):
                continue
            piezas.append(pieza)
        return piezas

    def _ruta_armada(self, e, amb):
        if isinstance(e, ast.Name):
            return self._en(amb, "rutas", e.id)
        if isinstance(e, ast.Starred):
            return self._ruta_armada(e.value, amb)
        if isinstance(e, (ast.List, ast.Tuple, ast.Set)):
            return any(self._ruta_armada(x, amb) for x in e.elts)
        if isinstance(e, (ast.ListComp, ast.GeneratorExp, ast.SetComp)):
            return self._ruta_armada(e.elt, amb)
        huecos = self._huecos_de_format(e, amb)
        if huecos is not None:
            return any(self._contamina(p, amb) for p in huecos)
        if isinstance(e, ast.BinOp) and isinstance(e.op, ast.Mod) and isinstance(self._const(e.left, amb), str) and not self._const(e.left, amb).startswith("%"):
            return self._contamina(e.right, amb)
        if isinstance(e, ast.JoinedStr):
            return self._pieza_ruta(list(e.values), amb)
        if isinstance(e, ast.BinOp) and isinstance(e.op, ast.Add) and self._textual(e, amb):
            return self._pieza_ruta(self._aplanar_suma(e), amb)
        if isinstance(e, ast.BinOp) and isinstance(e.op, ast.Div):
            return self._contamina(e.right, amb) or self._ruta_armada(e.left, amb)
        pz = self._interpolaciones(e, amb)
        if pz is not None and isinstance(e, (ast.BinOp, ast.Call)) and _nombre_func(e) != "join" if isinstance(e, ast.Call) else pz is not None:
            return any(self._contamina(p, amb) for p in pz[1:]) or (len(pz) == 1 and self._contamina(pz[0], amb))
        if isinstance(e, ast.Call):
            comp, nf = self.completo(e.func), _nombre_func(e)
            if comp in ("os.path.join", "posixpath.join", "ntpath.join", "pathlib.Path", "pathlib.PurePath", "Path", "PurePath") or nf == "joinpath":
                args = list(e.args)
                if nf == "joinpath":
                    return any(self._contamina(a, amb) or self._ruta_armada(a, amb) for a in args) or self._ruta_armada(e.func.value, amb)
                return any(self._ruta_armada(a, amb) for a in args) or any(self._contamina(a, amb) for a in args[1:])
            if nf in ("resolve", "absolute", "expanduser") and isinstance(e.func, ast.Attribute):
                return self._ruta_armada(e.func.value, amb)
            if comp in ("os.path.abspath", "os.path.normpath", "os.path.realpath", "os.path.expanduser", "str") and e.args:
                return self._ruta_armada(e.args[0], amb)
        return False

    def _ruta_resuelta(self, e, amb, vistos=frozenset()):
        """¿e ya tiene los .. colapsados? Sin eso, comparar rutas es comparar texto."""
        if isinstance(e, ast.Name):
            if e.id in vistos:
                return False
            vistos = vistos | {e.id}
            a = amb
            while a is not None:
                for x in a.nodos:
                    if isinstance(x, ast.Assign) and any(isinstance(t, ast.Name) and t.id == e.id for t in x.targets) and self._ruta_resuelta(x.value, amb, vistos):
                        return True
                    if isinstance(x, ast.NamedExpr) and x.target.id == e.id and self._ruta_resuelta(x.value, amb, vistos):
                        return True
                a = a.padre
            return False
        if isinstance(e, ast.Call):
            nf = _nombre_func(e)
            if nf in RESUELVE_RUTA:
                return True
            if nf in ("str", "Path", "PurePath", "fspath", "normcase") and e.args:
                return self._ruta_resuelta(e.args[0], amb, vistos)
            if nf in ("as_posix", "lower", "casefold") and isinstance(e.func, ast.Attribute):
                return self._ruta_resuelta(e.func.value, amb, vistos)
        return False

    def _ruta_protegida(self, amb, por_ayudante=True):
        a = amb
        while a is not None:
            for x in a.nodos:
                if not isinstance(x, ast.Call):
                    continue
                nf = _nombre_func(x)
                if nf in ("safe_join", "secure_filename"):
                    return True
                if por_ayudante and isinstance(x.func, ast.Name):
                    # la comprobación puede vivir en una función propia del archivo
                    for d in self.ambitos:
                        if isinstance(d, (ast.FunctionDef, ast.AsyncFunctionDef)) and d.name == x.func.id and self._ruta_protegida(self.ambitos[d], False):
                            return True
                if nf in ("is_relative_to", "relative_to", "startswith") and isinstance(x.func, ast.Attribute) and self._ruta_resuelta(x.func.value, amb):
                    return True
                if nf in ("commonpath", "commonprefix") and x.args:
                    piezas = x.args[0].elts if isinstance(x.args[0], (ast.List, ast.Tuple)) else [x.args[0]]
                    if any(self._ruta_resuelta(p, amb) for p in piezas):
                        return True
            a = a.padre
        return False

    # ---- CWE-79: HTML ----
    def _html_ok(self, v, amb):
        if isinstance(v, ast.FormattedValue):
            if _formato_numerico(v.format_spec):
                return True
            v = v.value
        if self._const(v, amb) is not NADA:
            return True
        if isinstance(v, ast.Call):
            nf = _nombre_func(v)
            if nf == "to_html":
                k = _kw(v, "escape")
                return not (isinstance(k, ast.Constant) and k.value is False)
            if nf in SANEADORES_HTML or nf in self.sanea_html:
                return True
            if nf == "join" and v.args:
                a = v.args[0]
                if isinstance(a, (ast.GeneratorExp, ast.ListComp)):
                    return self._html_ok(a.elt, amb) or self._es_html_armado(a.elt, amb)
                return self._html_ok(a, amb) or self._lista_const(a, amb)
        if isinstance(v, ast.Name):
            return any(self._en(amb, k, v.id) for k in ("html", "seguras", "validadas"))
        if isinstance(v, ast.IfExp):
            return self._html_ok(v.body, amb) and self._html_ok(v.orelse, amb)
        if isinstance(v, ast.Attribute) and v.attr in ("shape", "size"):
            return True
        if isinstance(v, ast.Subscript) and isinstance(v.value, ast.Attribute) and v.value.attr == "shape":
            return True
        if isinstance(v, ast.BinOp) and isinstance(v.op, (ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Pow)):
            return True
        return self._es_html_armado(v, amb)   # se revisa aparte, en su propia línea

    def _es_html_armado(self, e, amb):
        return self._interpolaciones(e, amb) is not None and bool(ES_HTML.search(self._texto(e, amb) or ""))

    # ---- CWE-532 ----
    def _comprension_filtrada(self, e):
        """{k: ("***" if k in SENSIBLES else v) ...} o {k: v ... if k not in SENSIBLES}: lo que queda ya se limpió."""
        for g in e.generators:
            if any(isinstance(x, ast.Compare) and any(isinstance(o, ast.NotIn) for o in x.ops) for c in g.ifs for x in ast.walk(c)):
                return True
        for x in ast.walk(e.value if isinstance(e, ast.DictComp) else e.elt):
            if isinstance(x, ast.IfExp):
                for rama in (x.body, x.orelse):
                    if isinstance(rama, ast.Constant) and isinstance(rama.value, str) and re.search(r"(?i)(\*{2,}|x{3,}|reservad|ocult|redact|mask|enmasc|\[.*\])", rama.value):
                        return True
        return False

    # Tablas con columnas personales: print(df.head()) solo se marca si el mismo programa muestra que la tabla las tiene.
    def _listas_modulo(self):
        if not hasattr(self, "_listas_cache"):
            self._listas_cache = {}
            for x in ast.walk(self.arbol):
                if isinstance(x, ast.Assign) and isinstance(x.value, (ast.List, ast.Tuple)):
                    for t in x.targets:
                        if isinstance(t, ast.Name):
                            self._listas_cache[t.id] = x.value
        return self._listas_cache

    def _columnas(self, e):
        if isinstance(e, ast.Name):
            e = self._listas_modulo().get(e.id)
        if isinstance(e, ast.Constant):
            return [e.value]
        if isinstance(e, (ast.List, ast.Tuple)):
            return [x.value for x in e.elts if isinstance(x, ast.Constant)]
        return []

    def _frame_personal(self, e, amb):
        """¿Esta expresión es una tabla que conserva columnas personales?"""
        if isinstance(e, ast.Name):
            if self._en(amb, "df_enmascarado", e.id):
                return False
            if self._en(amb, "df_personales", e.id):
                return True
            usa = False
            for x in amb.nodos:
                if isinstance(x, ast.Call) and _nombre_func(x) == "drop" and isinstance(x.func, ast.Attribute) and isinstance(x.func.value, ast.Name) and x.func.value.id == e.id:
                    return False
                if isinstance(x, ast.Subscript) and isinstance(x.value, ast.Name) and x.value.id == e.id and isinstance(x.ctx, ast.Load) and isinstance(x.slice, ast.Constant) and es_sensible(x.slice.value):
                    usa = True
            if not usa or re.fullmatch(r"(?i)(df|df_\w+|\w+_df|tabla|frame)", e.id):
                return usa
            # nulos = df.isna().sum(); nulos["cedula"] no dice que «nulos» tenga datos personales: debe venir de una lectura
            return any(isinstance(x, ast.Assign) and isinstance(x.value, ast.Call) and any(isinstance(t, ast.Name) and t.id == e.id for t in x.targets) and
                       (_nombre_func(x.value).startswith("read_") or _nombre_func(x.value) in ("DataFrame", "parquet", "csv", "table", "sql", "orc")) for x in amb.nodos)
        if isinstance(e, ast.Call):
            nf = _nombre_func(e)
            if nf.startswith("read_"):
                return any(es_sensible(c) for k in ("usecols", "names", "columns") for c in self._columnas(_kw(e, k)))
            if not isinstance(e.func, ast.Attribute):
                return False
            if nf == "select":
                return any(es_sensible(c) for a in e.args for c in self._columnas(a))
            if nf in ("dropna", "fillna", "query", "sort_values", "drop_duplicates", "dropDuplicates", "copy", "reset_index", "filter", "where", "astype", "assign", "orderBy", "sort",
                      "limit", "withColumn", "toPandas", "head", "tail", "sample", "nlargest", "nsmallest", "to_string", "to_markdown", "to_dict", "to_json", "rename"):
                return self._frame_personal(e.func.value, amb)
            return False
        if isinstance(e, ast.Attribute) and e.attr in ("iloc", "loc"):
            return self._frame_personal(e.value, amb)
        if isinstance(e, ast.Subscript):
            cols = self._columnas(e.slice) if isinstance(e.slice, (ast.List, ast.Name)) else None
            if cols:
                return any(es_sensible(c) for c in cols)
            if isinstance(e.slice, (ast.Constant, ast.List, ast.Tuple)) and not isinstance(e.value, ast.Attribute):
                return False
            if isinstance(e.slice, ast.Tuple):
                return False
            return self._frame_personal(e.value, amb)
        return False

    def _excepcion_con_secreto(self, n, amb):
        """logger.error("...", e) con requests: el mensaje de la excepción trae la URL completa, con sus parámetros."""
        p = n
        while p in self.padres and not isinstance(p, ast.ExceptHandler):
            p = self.padres[p]
        if not isinstance(p, ast.ExceptHandler) or not isinstance(self.padres.get(p), ast.Try):
            return False
        usa = _nombre_func(n) == "exception" or self._const(_kw(n, "exc_info"), amb) is True
        for a in n.args:
            for b in ([v.value for v in a.values if isinstance(v, ast.FormattedValue)] if isinstance(a, ast.JoinedStr) else [a]):
                if isinstance(b, ast.Call) and _nombre_func(b) in ("str", "repr") and b.args:
                    b = b.args[0]
                if isinstance(b, ast.Name) and p.name and b.id == p.name:
                    usa = True
        if not usa:
            return False
        for st in self.padres[p].body:
            for c in ast.walk(st):
                if not (isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr in ("get", "post", "put", "patch", "delete", "head", "request")):
                    continue
                if not (self.completo(c.func).startswith(("requests.", "httpx.")) or re.search(r"(?i)(session|sesion|client)", _punteado(c.func.value) or "")):
                    continue
                url = c.args[0] if c.args else _kw(c, "url")
                if self._sensible_en(_kw(c, "params"), amb) or self._sensible_en(url, amb):
                    return True
                if url is not None and re.search(r"(?i)(token|key|secret|password|clave)=", self._texto(url, amb) or ""):
                    return True
        return False

    def _es_objeto(self, e, amb):
        return isinstance(e, ast.Name) and (e.id in OBJETOS_ENTEROS or self._en(amb, "filas", e.id))

    def _nombre_inocuo(self, nombre, amb):
        """Solo nombres que parecen sensibles pero que el código ata a algo sin datos: encabezados = df.columns.tolist(), número de enumerate, llave de un dict literal."""
        if not (nombre in OBJETOS_ENTEROS or es_sensible(nombre) or self._en(amb, "sensibles", nombre)):
            return False
        visto = False
        for x in ast.walk(amb.nodo):
            if isinstance(x, ast.Assign) and any(isinstance(t, ast.Name) and t.id == nombre for t in x.targets):
                v = x.value
                if isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute) and v.func.attr == "tolist":
                    v = v.func.value
                if not (isinstance(v, ast.Attribute) and v.attr == "columns"):
                    return False
                visto = True
            elif isinstance(x, ast.Assign) and any(isinstance(t, ast.Tuple) and any(isinstance(y, ast.Name) and y.id == nombre for y in t.elts) for t in x.targets):
                return False
            elif isinstance(x, (ast.For, ast.comprehension)):
                t = x.target
                if isinstance(t, ast.Name) and t.id == nombre:
                    return False
                if isinstance(t, ast.Tuple) and any(isinstance(y, ast.Name) and y.id == nombre for y in t.elts):
                    primero = isinstance(t.elts[0], ast.Name) and t.elts[0].id == nombre
                    it = x.iter
                    if not (primero and isinstance(it, ast.Call) and self._iter_de_llaves(it, amb)):
                        return False
                    visto = True
            elif isinstance(x, ast.arg) and x.arg == nombre:
                return False
        return visto

    def _iter_de_llaves(self, it, amb):
        if isinstance(it.func, ast.Name) and it.func.id == "enumerate":
            return True
        if isinstance(it.func, ast.Attribute) and it.func.attr == "items" and isinstance(it.func.value, ast.Name):
            valores = [x.value for x in ast.walk(amb.nodo) if isinstance(x, ast.Assign) and any(isinstance(t, ast.Name) and t.id == it.func.value.id for t in x.targets)]
            return bool(valores) and all(isinstance(v, ast.Dict) and all(isinstance(k, ast.Constant) for k in v.keys) for v in valores)
        return False

    def _sensible_en(self, e, amb):
        if e is None or isinstance(e, (ast.Constant, ast.Compare)):
            return None
        if isinstance(e, ast.IfExp):   # 'sí' if LLAVE else 'no': la condición no se imprime, solo las ramas
            return self._sensible_en(e.body, amb) or self._sensible_en(e.orelse, amb)
        if isinstance(e, (ast.DictComp, ast.ListComp, ast.SetComp, ast.GeneratorExp)) and self._comprension_filtrada(e):
            return None
        if isinstance(e, ast.Attribute) and e.attr in ("is_unique", "dtype", "dtypes", "hasnans", "columns", "ndim", "empty"):
            return None   # metadatos de la columna, no sus valores
        if isinstance(e, ast.Name):
            if self._en(amb, "enmascaradas", e.id) or self._en(amb, "seguras", e.id) or self._nombre_inocuo(e.id, amb):
                return None
            if e.id in OBJETOS_ENTEROS or self._en(amb, "filas", e.id):
                return e.id
            return e.id if es_sensible(e.id) or self._en(amb, "sensibles", e.id) else None
        if isinstance(e, ast.Call):
            nf = _nombre_func(e)
            if ENMASCARA.search(nf) or nf in ("len", "sum", "count", "nunique", "size") or _punteado(e.func).startswith("secrets."):
                return None   # enmascarado, un conteo o una llave recién generada que la herramienta entrega a quien la pidió
            recv = e.func.value if isinstance(e.func, ast.Attribute) else (e.args[0] if e.args else None)
            if nf in ("to_dict", "to_json", "dict", "vars", "asdict", "_asdict", "items", "values", "tolist", "to_list") and self._es_objeto(recv, amb):
                return recv.id
            if nf == "value_counts" and (any(isinstance(x, ast.Attribute) and x.attr == "str" for x in ast.walk(recv)) or
                                         (isinstance(recv, ast.Call) and _nombre_func(recv) in ("duplicated", "isin", "between", "eq", "ne", "gt", "lt", "ge", "le"))):
                return None   # conteos de una propiedad derivada, no de los valores
            if nf in ("max", "min", "mean", "median", "std") and isinstance(recv, ast.Call) and _nombre_func(recv) == "value_counts":
                return None
            if nf in ("get", "getenv", "pop", "select", "col", "column") and e.args:
                for a in e.args:
                    if isinstance(a, ast.Constant) and es_sensible(a.value):
                        return a.value
                if isinstance(e.func, ast.Attribute) and _punteado(e.func.value) == "os.environ" and isinstance(e.args[0], ast.Constant):
                    return None   # una variable de entorno de nombre neutro, como REGION
        if isinstance(e, ast.Subscript):
            if isinstance(e.slice, ast.Slice):
                return None
            if isinstance(e.value, ast.Name) and self._en(amb, "enmascaradas", e.value.id):
                return None
            de_fila = isinstance(e.value, ast.Name) and self._en(amb, "filas", e.value.id)
            for c in ast.walk(e.slice):
                if isinstance(c, ast.Constant) and (es_sensible(c.value) or (de_fila and c.value in CAMPOS_DE_FILA)):
                    return c.value
            if self._es_objeto(e.value, amb) or _punteado(e.value) == "os.environ":
                return None   # un campo suelto de una fila: ya se juzgó por su nombre
            return self._sensible_en(e.value, amb)
        if isinstance(e, ast.Attribute):
            if e.attr in ("shape", "size", "empty", "dtype", "dtypes", "columns", "hostname", "port", "scheme"):
                return None
            if self._es_objeto(e.value, amb):
                if e.attr in CAMPOS_DE_FILA or es_sensible(e.attr):
                    return e.attr
                return None
            if _punteado(e) == "os.environ":
                return "os.environ"
            return e.attr if es_sensible(e.attr) else self._sensible_en(e.value, amb)
        if isinstance(e, ast.Dict):
            for k, val in zip(e.keys, e.values):
                if isinstance(k, ast.Constant) and es_sensible(k.value) and not (isinstance(val, ast.Call) and ENMASCARA.search(_nombre_func(val))):
                    return k.value
        if isinstance(e, ast.FormattedValue):
            return self._sensible_en(e.value, amb)
        for h in ast.iter_child_nodes(e):
            r = self._sensible_en(h, amb)
            if r:
                return r
        return None

    # ---- hallazgos ----
    def _h(self, n, regla, detalle):
        linea = getattr(n, "lineno", 0)
        if (linea, regla) not in self._vistos:
            self._vistos.add((linea, regla))
            self.hallazgos.append({"linea": linea, "regla": regla, "detalle": detalle})

    def _exime(self, n, *reglas):
        p = n
        while p in self.padres and not isinstance(p, ast.stmt):
            p = self.padres[p]
        for x in range(getattr(p, "lineno", 0), getattr(p, "end_lineno", getattr(p, "lineno", 0)) + 1):
            self.exentas[x].update(reglas)

    def _contexto_secreto(self, n):
        """Nombre de lo que recibe el valor: la variable, la llave, el parámetro o la función."""
        nombres, p = [], n
        while p in self.padres:
            q = self.padres[p]
            if isinstance(q, ast.keyword) and q.arg:
                nombres.append(q.arg)
            elif isinstance(q, ast.Dict):
                for k, val in zip(q.keys, q.values):
                    if val is p and isinstance(k, ast.Constant) and isinstance(k.value, str):
                        nombres.append(k.value)
            elif isinstance(q, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
                objetivos = q.targets if isinstance(q, ast.Assign) else [q.target]
                for t in objetivos:
                    for x in ast.walk(t):
                        if isinstance(x, ast.Name):
                            nombres.append(x.id)
                        elif isinstance(x, ast.Attribute):
                            nombres.append(x.attr)
                        elif isinstance(x, ast.Constant) and isinstance(x.value, str):
                            nombres.append(x.value)
            elif isinstance(q, (ast.FunctionDef, ast.AsyncFunctionDef)):
                nombres.append(q.name)
                break
            elif isinstance(q, ast.ClassDef):
                nombres.append(q.name)
            p = q
        return nombres

    # ---- reglas ----
    def _reglas(self):
        for n in ast.walk(self.arbol):
            amb = self.ambito_de(n) if n is not self.arbol else self.ambitos[self.arbol]
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                self._r_import(n)
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._r_parametros(n, amb)
                self._r_cifrado_casero(n)
                self._r_token_predecible(n)
                if n.name in ("__reduce__", "__reduce_ex__", "__setstate__"):
                    self._h(n, "CWE-502 · deserialización", "define cómo se reconstruye un objeto al deserializarlo. Qué se hace: guardar datos en JSON, CSV o Parquet")
            elif isinstance(n, ast.Constant) and isinstance(n.value, (str, bytes)):
                self._r_cadena(n, amb)
            elif isinstance(n, ast.JoinedStr):
                self._r_cadena_texto(n, self._texto(n, amb))
                self._r_url_con_constante(n, amb)
            elif isinstance(n, (ast.Assign, ast.AnnAssign, ast.NamedExpr, ast.AugAssign)):
                self._r_asignacion(n, amb)
            elif isinstance(n, ast.Dict):
                self._r_dict(n, amb)
            elif isinstance(n, ast.Compare) and isinstance(n.left, ast.Name) and re.search(r"(?i)clave|contrase|password|passwd|pwd", n.left.id) and len(n.ops) == 1 and isinstance(n.ops[0], (ast.Eq, ast.NotEq)):
                c_cmp = self._const(n.comparators[0], amb)
                if isinstance(c_cmp, str) and len(c_cmp) >= 6 and re.search(r"\d", c_cmp) and re.search(r"[A-Za-z]", c_cmp) and not MARCADOR.search(c_cmp):
                    self._h(n, "CWE-798 · secreto en el código", "una clave se compara contra un valor escrito. Qué se hace: leerla de una variable de entorno o comparar su hash")
            elif isinstance(n, ast.Call):
                self._r_llamada(n, amb)
            elif isinstance(n, (ast.Attribute, ast.Name)):
                self._r_atributo(n)
            elif isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitXor) and any(isinstance(x, ast.Call) and _nombre_func(x) in ("ord", "bytes", "bytearray") for x in ast.walk(n)):
                self._h(n, "CWE-327 · criptografía débil", "un cifrado casero con XOR no protege nada. Qué se hace: cifrado autenticado (AES-GCM) o HMAC con llave")
            elif isinstance(n, ast.Raise) and isinstance(n.exc, ast.Call) and self.perfil == "usuario":
                for a in n.exc.args:
                    if self._sensible_en(a, amb):
                        self._h(n, "CWE-532 · dato sensible en un mensaje", "un error lleva un dato personal o un secreto. Qué se hace: decir la fila o el conteo, no el valor")
            if isinstance(n, (ast.JoinedStr, ast.BinOp)) or (isinstance(n, ast.Call) and _nombre_func(n) in ("format", "substitute", "safe_substitute", "replace")):
                if not isinstance(self.padres.get(n), ast.BinOp) and not isinstance(self.padres.get(n), ast.FormattedValue):
                    self._r_cadena_armada(n, amb)

    def _r_import(self, n):
        nombres = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module or ""]
        for m in nombres:
            if set(m.split(".")) & DESERIALIZA:
                self._h(n, "CWE-502 · deserialización", f"importa {m.split('.')[0]}, que ejecuta código al cargar. Qué se hace: usar JSON, CSV o Parquet")

    def _r_cadena(self, n, amb):
        padre = self.padres.get(n)
        if isinstance(padre, ast.Expr) or isinstance(padre, ast.JoinedStr):
            return   # docstring, o ya se revisa la f-string completa
        v = n.value.decode("latin-1") if isinstance(n.value, bytes) else n.value
        self._r_cadena_texto(n, v)
        if isinstance(v, str) and self._literal_regex(n, padre, v):
            self._h(n, "CWE-1333 · regex catastrófica", "repeticiones anidadas que pueden colgar el proceso. Qué se hace: acotar el patrón o cambiarlo por uno sin repetición dentro de repetición")
        if alta_entropia(v):
            self._h(n, "CWE-798 · secreto en el código", "una cadena tiene forma de llave. Qué se hace: leerla de una variable de entorno o una bóveda")
        if isinstance(padre, (ast.Assign, ast.AnnAssign)):
            objetivos = padre.targets if isinstance(padre, ast.Assign) else [padre.target]
            if any(isinstance(t, ast.Name) and NOMBRE_PATRON.search(t.id) for t in objetivos) and isinstance(v, str) and regex_catastrofica(v):
                self._h(n, "CWE-1333 · regex catastrófica", "repeticiones anidadas que pueden colgar el proceso. Qué se hace: acotar el patrón o cambiarlo por uno sin repetición dentro de repetición")

    def _literal_regex(self, n, padre, v):
        """Un patrón guardado aparte (diccionario de reglas, constante que luego se pasa a una función) no pasa por _r_regex."""
        if len(v) > TOPE_REGEX or "(" not in v or not regex_catastrofica(v):
            return False
        if isinstance(padre, (ast.Dict, ast.List, ast.Tuple, ast.Set)):
            return True
        if not re.search(r"(?m)^\s*(import|from)\s+(re|regex)\b", self.texto):
            return False
        if isinstance(padre, ast.Call):   # un texto de ayuda que muestra un patrón no lo usa
            f = padre.func
            nombre = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
            return nombre != "print" and nombre not in LOG_NIVELES
        return isinstance(padre, (ast.Assign, ast.AnnAssign, ast.keyword))

    def _r_cadena_texto(self, n, v):
        if not isinstance(v, str):
            return
        if regex_en_sql(v):
            self._h(n, "CWE-1333 · regex catastrófica", "el SQL trae un patrón con repeticiones anidadas que puede colgar el proceso. Qué se hace: acotar el patrón o cambiarlo por uno sin repetición dentro de repetición")
        for rx, motivo in CADENAS_SECRETAS:
            if rx.search(v):
                self._h(n, "CWE-798 · secreto en el código", f"{motivo}. Qué se hace: leerlo de una variable de entorno o una bóveda")
                break
        if TLS_TEXTO.search(v):
            self._h(n, "CWE-295 · TLS sin verificar", "una opción apaga la verificación del certificado. Qué se hace: dejarla activa y configurar la autoridad certificadora")
        if SQL_HASH.search(v) or SQL_HASH_NORMALIZADO.search(v):
            self._h(n, "CWE-327 · hash débil", "una consulta seudonimiza un dato personal con hash sin sal o débil. Qué se hace: HMAC con llave, o hash fuerte con sal secreta")
        for m in SQL_AZAR.finditer(v):
            if CONTEXTO_SECRETO.search(_sin_tildes(m.group(1))) and not NOMBRE_TIEMPO.search(_sin_tildes(m.group(1))):
                self._h(n, "CWE-330 · azar predecible", "una consulta arma un valor secreto con el azar del motor, que es predecible. Qué se hace: generarlo con el módulo secrets y cargarlo como parámetro")
                break

    def _r_parametros(self, f, amb):
        a = f.args
        posicion = a.posonlyargs + a.args
        pares = list(zip(reversed(posicion), reversed(a.defaults))) + [(p, d) for p, d in zip(a.kwonlyargs, a.kw_defaults) if d is not None]
        for p, d in pares:
            c, nivel = self._const(d, amb), nivel_secreto(p.arg)
            if nivel and c is not NADA and valor_secreto(c, nivel):
                self._h(f, "CWE-798 · secreto en el código", f"el valor por defecto de «{p.arg}» es un secreto escrito. Qué se hace: leerlo de una variable de entorno o una bóveda")
            if isinstance(c, bool):
                self._r_defecto_tls(f, p.arg, c)

    def _r_defecto_tls(self, f, parametro, defecto):
        """def bajar(url, verify=False): requests.get(url, verify=verify): quien no pase el parámetro descarga sin validar el certificado."""
        def efectivo(e):
            if isinstance(e, ast.Name) and e.id == parametro:
                return defecto
            if isinstance(e, ast.UnaryOp) and isinstance(e.op, ast.Not) and isinstance(e.operand, ast.Name) and e.operand.id == parametro:
                return not defecto
            return NADA
        propias = {d.name for d in ast.walk(self.arbol) if isinstance(d, FUNCS) and hasattr(d, "name")}
        for x in ast.walk(f):
            pares = []
            if isinstance(x, ast.Call):
                # una función del mismo archivo, o «verify» en algo que no conecta, no dice nada de TLS
                nf = _nombre_func(x)
                if nf in propias:
                    continue
                de_red = nf in DE_RED or self.completo(x.func).split(".")[0] in ("requests", "httpx", "urllib3", "aiohttp")
                pares = [(k.arg, k.value) for k in x.keywords if isinstance(k.arg, str) and (de_red or re.search(r"(?i)ssl|tls|cert|hostname", k.arg))]
            elif isinstance(x, ast.Assign):
                pares = [(t.attr, x.value) for t in x.targets if isinstance(t, ast.Attribute)]
            for nombre, valor in pares:
                if apaga_tls(nombre, efectivo(valor)):
                    self._h(f, "CWE-295 · TLS sin verificar", f"el valor por defecto de «{parametro}» apaga la verificación. Qué se hace: dejarla activa por defecto")
                    return

    def _r_asignacion(self, n, amb):
        objetivos = n.targets if isinstance(n, ast.Assign) else [n.target]
        v = getattr(n, "value", None)
        if v is None:
            return
        for t in objetivos:
            if isinstance(t, (ast.Tuple, ast.List)) and isinstance(v, (ast.Tuple, ast.List)) and len(t.elts) == len(v.elts):
                for a, b in zip(t.elts, v.elts):
                    if isinstance(a, ast.Name):
                        nivel, c = nivel_secreto(a.id), self._const(b, amb)
                        if nivel and c is not NADA and valor_secreto(c, nivel):
                            self._h(n, "CWE-798 · secreto en el código", f"«{a.id}» tiene el valor escrito. Qué se hace: leerlo de una variable de entorno o una bóveda")
            nombre_t = t.id if isinstance(t, ast.Name) else (t.attr if isinstance(t, ast.Attribute) else None)
            if nombre_t and NOMBRE_CREDENCIAL.search(nombre_t) and isinstance(v, (ast.Tuple, ast.List)) and len(v.elts) == 2:
                c2 = self._const(v.elts[1], amb)
                if isinstance(c2, str) and c2 and not MARCADOR.search(c2):
                    self._h(n, "CWE-798 · secreto en el código", f"«{nombre_t}» tiene usuario y clave escritos. Qué se hace: leerlos de una variable de entorno o una bóveda")
        c = self._const(v, amb)
        for t in objetivos:
            nombre = t.id if isinstance(t, ast.Name) else (t.attr if isinstance(t, ast.Attribute) else None)
            if isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant) and isinstance(t.slice.value, str):
                nombre = t.slice.value
                if nombre in TLS_ENTORNO and c is not NADA and str(c) in ("", "0", "false", "False"):
                    self._h(n, "CWE-295 · TLS sin verificar", f"apaga la verificación por medio de {nombre}. Qué se hace: quitar esa línea")
            nivel = nivel_secreto(nombre) if nombre else None
            if nivel and c is not NADA and valor_secreto(c, nivel):
                self._h(n, "CWE-798 · secreto en el código", f"«{nombre}» tiene el valor escrito. Qué se hace: leerlo de una variable de entorno o una bóveda")
            if c is NADA and self._respaldo_escrito(v, amb, nivel):
                self._h(n, "CWE-798 · secreto en el código", f"«{nombre or 'la variable'}» tiene un valor de respaldo escrito. Qué se hace: leerlo solo del entorno y fallar si no está")
            if isinstance(v, (ast.List, ast.Tuple, ast.Set)) and (nivel == "fuerte" or (nombre and re.search(r"(?i)api[-_. ]?keys|(llaves|claves)[-_. ](de[-_. ])?(api|acceso|secretas?)", nombre))):
                piezas = [self._const(x, amb) for x in v.elts]
                if any(isinstance(p, str) and len(p) >= 8 and re.search(r"\d", p) and re.search(r"[A-Za-z]", p) and valor_secreto(p, "fuerte") for p in piezas):
                    self._h(n, "CWE-798 · secreto en el código", f"«{nombre}» tiene valores escritos. Qué se hace: leerlos de una variable de entorno o una bóveda")
            if isinstance(t, ast.Attribute):
                if apaga_tls(t.attr, c):
                    self._h(n, "CWE-295 · TLS sin verificar", f"apaga .{t.attr}. Qué se hace: dejarlo activo y configurar la autoridad certificadora")
                if t.attr == "_create_default_https_context":
                    self._h(n, "CWE-295 · TLS sin verificar", "cambia el contexto de HTTPS de todo el proceso. Qué se hace: quitar esa línea")

    def _respaldo_escrito(self, e, amb, nivel):
        """¿Una clave literal entra por «or», por un if/else, por quote_plus o como default del entorno?"""
        literales = []

        def rec(x):
            nonlocal nivel
            if isinstance(x, ast.BoolOp) and isinstance(x.op, ast.Or):
                for y in x.values:
                    rec(y)
            elif isinstance(x, ast.IfExp):
                rec(x.body)
                rec(x.orelse)
            elif isinstance(x, ast.Call):
                nf = _nombre_func(x)
                entorno = nf == "getenv" or (nf == "get" and isinstance(x.func, ast.Attribute) and isinstance(x.func.value, (ast.Attribute, ast.Name))
                                             and getattr(x.func.value, "attr", getattr(x.func.value, "id", "")) == "environ")
                if entorno and x.args:
                    k0 = self._const(x.args[0], amb)
                    n0 = nivel_secreto(k0) if isinstance(k0, str) else None
                    if n0 == "fuerte" or (n0 and not nivel):
                        nivel = n0
                    for d in x.args[1:2] + [k.value for k in x.keywords if k.arg == "default"]:
                        rec(d)
                elif nf in ("quote", "quote_plus", "SecretStr") and x.args:
                    rec(x.args[0])
            else:
                c = self._const(x, amb)
                if isinstance(c, str):
                    literales.append(c)

        if isinstance(e, (ast.BoolOp, ast.IfExp, ast.Call)):
            rec(e)
        return bool(nivel) and any(valor_secreto(c, nivel) for c in literales)

    def _r_url_con_constante(self, n, amb):
        """f"postgresql://{U}:{CLAVE}@{HOST}/..." con la clave en una constante del archivo."""
        for a, b, d in zip(n.values, n.values[1:], n.values[2:]):
            if not (isinstance(a, ast.Constant) and isinstance(b, ast.FormattedValue) and isinstance(d, ast.Constant)):
                continue
            previo, siguiente = str(a.value), str(d.value)
            if (previo.endswith(":") and siguiente.startswith("@")) or re.search(r"(?i)(?:password|passwd|pwd|pass|token|secret|api[_-]?key|access[_-]?key)\s*=\s*['\"]?$", previo):
                c = self._const(b.value, amb)
                if isinstance(c, str) and len(c) >= 4 and not MARCADOR.search(c):
                    self._h(n, "CWE-798 · secreto en el código", "una clave escrita en una constante entra a la cadena de conexión. Qué se hace: leerla de una variable de entorno o una bóveda")

    def _r_dict(self, n, amb):
        for k, val in zip(n.keys, n.values):
            if not (isinstance(k, ast.Constant) and isinstance(k.value, str)):
                continue
            c = self._const(val, amb)
            nivel = nivel_secreto(k.value)
            if c is NADA and self._respaldo_escrito(val, amb, nivel):
                self._h(val, "CWE-798 · secreto en el código", f"la llave «{k.value}» tiene un valor de respaldo escrito. Qué se hace: leerlo solo del entorno y fallar si no está")
            if nivel and c is not NADA and valor_secreto(c, nivel):
                self._h(val, "CWE-798 · secreto en el código", f"la llave «{k.value}» tiene el valor escrito. Qué se hace: leerlo de una variable de entorno o una bóveda")
            if apaga_tls(k.value, c) or (isinstance(c, str) and c.lower() in TLS_OPCION.get(k.value.lower(), ())):
                self._h(val, "CWE-295 · TLS sin verificar", f"«{k.value}» apaga la verificación. Qué se hace: dejarla activa")

    def _r_atributo(self, n):
        nombre = n.attr if isinstance(n, ast.Attribute) else n.id
        if nombre in TLS_ATTR:
            comp = self.completo(n)
            if isinstance(n, ast.Attribute) or "." in comp:
                self._h(n, "CWE-295 · TLS sin verificar", f"usa {nombre}. Qué se hace: contexto por defecto, con verificación")
        if nombre in CRIPTO_DEBIL or nombre in HASH_DEBIL:
            comp = self.completo(n)
            raiz = comp.split(".")[0]
            if nombre in CRIPTO_DEBIL and (raiz in ("Crypto", "Cryptodome", "cryptography") or (isinstance(n, ast.Attribute) and _punteado(n).split(".")[0] in ("hashes", "modes", "algorithms", "AES"))):
                self._h(n, "CWE-327 · criptografía débil", f"usa {nombre}. Qué se hace: AES-GCM o ChaCha20, y SHA-256 o más")
            if nombre in HASH_DEBIL and comp == f"hashlib.{nombre}" and not isinstance(self.padres.get(n), ast.Call):
                self._h(n, "CWE-327 · criptografía débil", f"usa {nombre}. Qué se hace: SHA-256 o más; para seudonimizar, HMAC con llave")

    def _r_cadena_armada(self, n, amb):
        pz = self._interpolaciones(n, amb)
        nf = _nombre_func(n) if isinstance(n, ast.Call) else ""
        if nf in ("substitute", "safe_substitute", "replace") and isinstance(n.func, ast.Attribute):
            if self.perfil != "usuario":
                return
            recv = n.func.value
            texto = self._const(recv, amb)
            if isinstance(recv, ast.Call) and _nombre_func(recv) == "Template" and recv.args:
                texto = self._const(recv.args[0], amb)
            if isinstance(texto, str) and ES_HTML.search(texto):
                piezas = (list(n.args[1:]) if nf == "replace" else list(n.args)) + [k.value for k in n.keywords]
                if not all(self._html_ok(p, amb) for p in piezas):
                    self._h(n, "CWE-79 · HTML sin escapar", "una plantilla HTML recibe datos sin escapar. Qué se hace: html.escape() antes de insertar")
            return
        if pz is None:
            return
        if all(self._sql_ok(p, amb) for p in pz):
            self._exime(n, "B608")
        if self.perfil == "usuario" and (ES_HTML.search(self._texto(n, amb) or "") or "</{}>" in (self._texto(n, amb) or "")) and not all(self._html_ok(p, amb) for p in pz):
            self._h(n, "CWE-79 · HTML sin escapar", "se arma HTML con datos sin escapar. Qué se hace: html.escape() antes de insertar")

    def _r_llamada(self, n, amb):
        nf, comp = _nombre_func(n), self.completo(n.func)
        self._r_secreto_llamada(n, nf, comp, amb)
        self._r_tls_llamada(n, nf, comp, amb)
        self._r_sql(n, nf, comp, amb)
        self._r_comando(n, nf, comp, amb)
        self._r_deserializa(n, nf, comp, amb)
        self._r_ruta(n, nf, comp, amb)
        self._r_html_sumidero(n, nf, comp, amb)
        self._r_log(n, nf, comp, amb)
        self._r_azar(n, nf, comp, amb)
        self._r_hash(n, nf, comp, amb)
        self._r_vector_fijo(n, nf, comp, amb)
        self._r_regex(n, nf, comp, amb)

    def _r_cifrado_casero(self, f):
        """Una función que dice cifrar u ofuscar y desplaza caracteres o solo codifica no protege nada."""
        if not re.search(r"(?i)cifr|encript|encrypt|ofusc|obfusc|cipher", f.name) or re.search(r"(?i)descifr|decrypt|desencript", f.name):
            return
        nombres = {_nombre_func(x) for x in ast.walk(f) if isinstance(x, ast.Call)}
        if {"chr", "ord"} <= nombres or nombres & {"b64encode", "urlsafe_b64encode", "b32encode", "rot13", "hexlify"} or (any(isinstance(x, ast.Call) and _punteado(x.func) == "codecs.encode" for x in ast.walk(f))):
            if not nombres & {"new", "encrypt", "Fernet", "AESGCM", "ChaCha20Poly1305", "update"}:
                self._h(f, "CWE-327 · criptografía débil", "desplazar caracteres o codificar no es cifrar: cualquiera lo revierte. Qué se hace: cifrado autenticado de una librería, como Fernet o AES-GCM")

    def _r_token_predecible(self, f):
        """Un token, una sesión o una clave que sale de la hora, del proceso o de una fórmula propia se puede adivinar."""
        verbo, objeto = r"(crear|generar|nuev|emitir|armar|make|generate|new|create|issue)", r"(token|sesion|session|clave|key|secret|sid)"
        if not re.search(rf"(?i){verbo}.*{objeto}|{objeto}.*{verbo}", _sin_tildes(f.name)):
            return
        completos = {_punteado(x.func) for x in ast.walk(f) if isinstance(x, ast.Call)}
        cortos = {_nombre_func(x) for x in ast.walk(f) if isinstance(x, ast.Call)}
        if any(c.startswith(("secrets.", "os.urandom", "uuid.uuid4", "hmac.", "jwt.")) for c in completos) or cortos & {"token_hex", "token_urlsafe", "token_bytes", "urandom", "uuid4", "encode_jwt", "SystemRandom"}:
            return
        tiempo = {"time.time", "time.time_ns", "time.monotonic", "time.perf_counter", "datetime.now", "datetime.utcnow", "datetime.datetime.now", "datetime.datetime.utcnow", "os.getpid", "uuid.uuid1", "uuid1", "getpid", "time_ns"}
        de_tiempo = {t.id for x in ast.walk(f) if isinstance(x, ast.Assign) and isinstance(x.value, ast.Call) and _punteado(x.value.func) in tiempo for t in x.targets if isinstance(t, ast.Name)}
        for r in ast.walk(f):
            if isinstance(r, ast.Return) and r.value is not None and any(
                    (isinstance(x, ast.Call) and _punteado(x.func) in tiempo) or (isinstance(x, ast.Name) and x.id in de_tiempo) for x in ast.walk(r.value)):
                self._h(f, "CWE-330 · azar predecible", "el valor sale de la hora o del proceso y se puede adivinar. Qué se hace: secrets.token_urlsafe()")
                return
        formula = [x for x in ast.walk(f) if isinstance(x, ast.BinOp) and isinstance(x.op, (ast.Mod, ast.BitAnd)) and any(isinstance(y, ast.BinOp) and isinstance(y.op, ast.Mult) for y in ast.walk(x.left))]
        if formula:
            self._h(f, "CWE-330 · azar predecible", "una fórmula propia con semilla no es azar criptográfico. Qué se hace: secrets.token_urlsafe()")

    def _en_demostracion(self, n):
        """Valores de ejemplo pasados a una función del mismo archivo en el bloque principal o en una función de demostración."""
        while n in self.padres:
            n = self.padres[n]
            if isinstance(n, ast.If) and "__main__" in ast.unparse(n.test):
                return True
            if isinstance(n, FUNCS) and hasattr(n, "name") and re.fullmatch(r"(?i)_?(main|demo\w*|ejemplo\w*|prueba\w*|test_\w*)", n.name):
                return True
        return False

    def _r_secreto_llamada(self, n, nf, comp, amb):
        if re.fullmatch(r"(?i).*credentials?|.*credenciales?|.*basicauth|.*digestauth", nf) and len(n.args) >= 2:
            ultimo = self._const(n.args[-1], amb)
            if isinstance(ultimo, str) and valor_secreto(ultimo, "debil"):
                self._h(n, "CWE-798 · secreto en el código", "la credencial tiene el valor escrito. Qué se hace: leerla de una variable de entorno o una bóveda")
        for k in n.keywords:
            if not k.arg:
                continue
            nivel = nivel_secreto(k.arg)
            c = self._const(k.value, amb)
            if nivel and c is not NADA and valor_secreto(c, nivel):
                self._h(n, "CWE-798 · secreto en el código", f"el parámetro «{k.arg}» tiene el valor escrito. Qué se hace: leerlo de una variable de entorno o una bóveda")
            if c is NADA and self._respaldo_escrito(k.value, amb, nivel):
                self._h(n, "CWE-798 · secreto en el código", f"el parámetro «{k.arg}» tiene un valor de respaldo escrito. Qué se hace: leerlo solo del entorno y fallar si no está")
            if k.arg == "auth" and isinstance(k.value, ast.Name):
                for m in self.padres:
                    if isinstance(m, ast.Assign) and isinstance(m.value, (ast.Tuple, ast.List)) and len(m.value.elts) == 2 and any(isinstance(t, ast.Name) and t.id == k.value.id for t in m.targets):
                        c2 = self._const(m.value.elts[1], amb)
                        if isinstance(c2, str) and c2 and not MARCADOR.search(c2):
                            self._h(n, "CWE-798 · secreto en el código", "la autenticación tiene la clave escrita. Qué se hace: leerla de una variable de entorno o una bóveda")
                            break
            if k.arg == "auth" and isinstance(k.value, (ast.Tuple, ast.List)) and len(k.value.elts) == 2:
                c2 = self._const(k.value.elts[1], amb)
                if isinstance(c2, str) and c2:
                    self._h(n, "CWE-798 · secreto en el código", "la autenticación tiene la clave escrita. Qué se hace: leerla de una variable de entorno o una bóveda")
        if nf in ("HTTPBasicAuth", "HTTPDigestAuth", "BasicAuth", "login") and len(n.args) >= 2:
            c2 = self._const(n.args[1], amb)
            if isinstance(c2, str) and c2:
                self._h(n, "CWE-798 · secreto en el código", "la autenticación tiene la clave escrita. Qué se hace: leerla de una variable de entorno o una bóveda")
        if nf == "add_argument" and n.args:
            k0 = self._const(n.args[0], amb)
            d = _kw(n, "default")
            cd = self._const(d, amb) if d is not None else NADA
            if isinstance(k0, str) and cd is not NADA and nivel_secreto(k0.lstrip("-")) and valor_secreto(cd, nivel_secreto(k0.lstrip("-"))):
                self._h(n, "CWE-798 · secreto en el código", "el valor por defecto del argumento es un secreto escrito. Qué se hace: leerlo de una variable de entorno o una bóveda")
        if nf in ("get", "getint") and len(n.args) >= 1 and _kw(n, "fallback") is not None:
            k0, cd = self._const(n.args[-1], amb), self._const(_kw(n, "fallback"), amb)
            if isinstance(k0, str) and cd is not NADA and nivel_secreto(k0) and valor_secreto(cd, nivel_secreto(k0)):
                self._h(n, "CWE-798 · secreto en el código", "el respaldo de la configuración es un secreto escrito. Qué se hace: leerlo de una variable de entorno o una bóveda")
        if nf == "format" and isinstance(n.func, ast.Attribute) and len(n.args) >= 2:
            plantilla = self._const(n.func.value, amb)
            c1 = self._const(n.args[1], amb)
            if isinstance(plantilla, str) and re.search(r"://\{\}:\{\}@", plantilla) and isinstance(c1, str) and len(c1) >= 4 and not MARCADOR.search(c1):
                self._h(n, "CWE-798 · secreto en el código", "una clave escrita entra a la cadena de conexión. Qué se hace: leerla de una variable de entorno o una bóveda")
        if nf == "setAll" and n.args and isinstance(n.args[0], (ast.List, ast.Tuple)):
            for par in n.args[0].elts:
                if isinstance(par, ast.Tuple) and len(par.elts) == 2:
                    k0, k1 = self._const(par.elts[0], amb), self._const(par.elts[1], amb)
                    if isinstance(k0, str) and k1 is not NADA and nivel_secreto(k0) and valor_secreto(k1, nivel_secreto(k0)):
                        self._h(n, "CWE-798 · secreto en el código", f"«{k0}» tiene el valor escrito. Qué se hace: leerlo de una variable de entorno o una bóveda")
        if nf in ("run", "Popen", "call", "check_call", "check_output") and n.args and isinstance(n.args[0], (ast.List, ast.Tuple)):
            piezas = [self._const(x, amb) for x in n.args[0].elts]
            for a, b in zip(piezas, piezas[1:]):
                if a in ("-u", "--user") and isinstance(b, str) and re.fullmatch(r"[^\s:]+:[^\s{$<%]{4,}", b):
                    self._h(n, "CWE-798 · secreto en el código", "un comando lleva usuario y clave escritos. Qué se hace: leerla de una variable de entorno")
        if isinstance(n.func, ast.Name) and n.args:
            for m in self.padres:
                if isinstance(m, ast.FunctionDef) and m.name == n.func.id:
                    params = m.args.posonlyargs + m.args.args
                    for p, a in zip(params, n.args):
                        ca, niv = self._const(a, amb), nivel_secreto(p.arg)
                        if niv and isinstance(a, ast.Constant) and ca is not NADA and valor_secreto(ca, niv) and not self._en_demostracion(n):
                            self._h(n, "CWE-798 · secreto en el código", f"el argumento «{p.arg}» se pasa escrito. Qué se hace: leerlo de una variable de entorno o una bóveda")
                    break
        if nf in ("get", "getenv") and n.args and self._respaldo_escrito(n, amb, None):
            self._h(n, "CWE-798 · secreto en el código", "el valor por defecto de la variable de entorno es un secreto escrito. Qué se hace: leerlo solo del entorno y fallar si no está")
        if nf in ("option", "config", "set", "setdefault", "get", "getenv", "add_header", "putheader", "header") and len(n.args) >= 2:
            k0, k1 = self._const(n.args[0], amb), self._const(n.args[1], amb)
            if isinstance(k0, str) and k1 is not NADA:
                nivel = nivel_secreto(k0)
                if nivel and valor_secreto(k1, nivel):
                    self._h(n, "CWE-798 · secreto en el código", f"«{k0}» tiene el valor escrito. Qué se hace: leerlo de una variable de entorno o una bóveda")
                if isinstance(k1, str) and k1.lower() in TLS_OPCION.get(k0.lower(), ()):
                    self._h(n, "CWE-295 · TLS sin verificar", f"la opción «{k0}» apaga la verificación. Qué se hace: dejarla activa")
                if k0 in TLS_ENTORNO and str(k1) in ("", "0"):
                    self._h(n, "CWE-295 · TLS sin verificar", f"apaga la verificación por medio de {k0}. Qué se hace: quitar esa línea")
        llave_fija = None
        if (comp.startswith("jwt.") and nf in ("encode", "decode") and len(n.args) >= 2):
            llave_fija = n.args[1]
        elif comp == "hmac.new" and n.args or nf == "Fernet" and n.args:
            llave_fija = n.args[0]
        elif nf == "new" and comp.split(".")[0] in ("Crypto", "Cryptodome", "AES", "ChaCha20") and n.args:
            llave_fija = n.args[0]
        if llave_fija is not None and isinstance(self._const(llave_fija, amb), (str, bytes)):
            self._h(n, "CWE-798 · secreto en el código", "la llave de cifrado o de firma está escrita. Qué se hace: leerla de una variable de entorno o una bóveda")
        if nf in ("Socrata",) and len(n.args) >= 2 and isinstance(self._const(n.args[1], amb), str):
            self._h(n, "CWE-798 · secreto en el código", "el token de la aplicación está escrito. Qué se hace: leerlo de una variable de entorno")
        if nf in ("b64decode", "urlsafe_b64decode", "b64encode", "urlsafe_b64encode") and n.args:
            c0 = self._const(n.args[0], amb)
            texto = c0.decode("latin-1") if isinstance(c0, bytes) else c0
            if isinstance(texto, str) and (nf.endswith("b64decode") and len(texto) >= 8 or ":" in texto):
                self._h(n, "CWE-798 · secreto en el código", "una credencial va codificada dentro del código; base64 no la protege. Qué se hace: leerla de una variable de entorno o una bóveda")

    def _r_tls_llamada(self, n, nf, comp, amb):
        for k in n.keywords:
            if apaga_tls(k.arg, self._const(k.value, amb)):
                self._h(n, "CWE-295 · TLS sin verificar", f"{k.arg} apaga la verificación del certificado. Qué se hace: dejarla activa y configurar la autoridad certificadora")
            elif k.arg and isinstance(self._const(k.value, amb), str) and k.arg.lower() != "sslmode" and self._const(k.value, amb).lower() in TLS_OPCION.get(k.arg.lower(), ()):
                self._h(n, "CWE-295 · TLS sin verificar", f"{k.arg} apaga la verificación del certificado. Qué se hace: dejarla activa y configurar la autoridad certificadora")
            elif k.arg == "sslmode" and self._const(k.value, amb) in TLS_OPCION["sslmode"]:
                self._h(n, "CWE-295 · TLS sin verificar", "sslmode no exige TLS verificado. Qué se hace: sslmode=verify-full")
            elif k.arg in ("cert_reqs", "ssl_cert_reqs") and str(self._const(k.value, amb)).upper() in ("CERT_NONE", "NONE"):
                self._h(n, "CWE-295 · TLS sin verificar", f"{k.arg} apaga la verificación. Qué se hace: CERT_REQUIRED")
        if isinstance(n.func, ast.Attribute) or nf in SUBPROCESO:
            for a in n.args:
                if isinstance(a, (ast.List, ast.Tuple)):
                    textos = [self._const(x, amb) for x in a.elts]
                    if "curl" in textos and any(isinstance(t, str) and re.fullmatch(r"-[a-zA-Z]*k[a-zA-Z]*", t) for t in textos):
                        self._h(n, "CWE-295 · TLS sin verificar", "curl -k apaga la verificación. Qué se hace: quitar -k")
        if comp == "ssl.SSLContext" and (not n.args or (_punteado(n.args[0]) or "").rsplit(".", 1)[-1] in ("PROTOCOL_TLS", "PROTOCOL_SSLv23")) and \
                not any(isinstance(x, ast.Assign) and any(isinstance(t, ast.Attribute) and t.attr == "verify_mode" for t in x.targets) for x in ast.walk(self.arbol)):
            self._h(n, "CWE-295 · TLS sin verificar", "ese SSLContext no valida el certificado. Qué se hace: ssl.create_default_context()")
        # sin contexto, estas clases de la biblioteca estándar cifran pero no validan el certificado del servidor
        ctx = _kw(n, "context") or _kw(n, "ssl_context")
        sin_ctx = ctx is None or (isinstance(ctx, ast.Constant) and ctx.value is None)
        if comp in ("smtplib.SMTP_SSL", "imaplib.IMAP4_SSL", "poplib.POP3_SSL", "ftplib.FTP_TLS") and sin_ctx:
            self._h(n, "CWE-295 · TLS sin verificar", f"{nf} sin context no valida el certificado. Qué se hace: context=ssl.create_default_context()")
        elif nf in ("starttls", "stls") and isinstance(n.func, ast.Attribute) and sin_ctx and not n.args and \
                any(str(m).split(".")[0] in ("smtplib", "imaplib", "poplib") for m in self.imports.values()):
            self._h(n, "CWE-295 · TLS sin verificar", f"{nf}() sin context no valida el certificado. Qué se hace: {nf}(context=ssl.create_default_context())")

    def _r_sql(self, n, nf, comp, amb):
        msg = "la consulta se arma pegando valores. Qué se hace: marcadores (? o :nombre) y los valores aparte; para nombres de tabla o columna, una lista permitida"
        def armada(x):
            pz = self._interpolaciones(x, amb)
            return (pz is not None and not all(self._sql_ok(p, amb) for p in pz)) or (isinstance(x, ast.Name) and self._en(amb, "dinamicas", x.id))
        if nf == "option" and len(n.args) >= 2 and str(self._const(n.args[0], amb)).lower() in ("query", "dbtable") and armada(n.args[1]):
            self._h(n, "CWE-89 · SQL armado con datos", msg)
        if nf == "jdbc":
            for x in list(n.args[1:2]) + [k.value for k in n.keywords if k.arg in ("table", "query")]:
                if armada(x):
                    self._h(n, "CWE-89 · SQL armado con datos", msg)
        a = n.args[0] if n.args else (_kw(n, "sql") or _kw(n, "query") or _kw(n, "sql_query"))
        if a is None:
            return
        es_texto_sql = nf == "text" and (comp == "text" or comp.endswith("sqlalchemy.text") or comp.endswith("sql.text") or comp.startswith("sqlalchemy"))
        if (nf in SUMIDEROS_SQL and isinstance(n.func, ast.Attribute)) or nf == "read_sql_query" or nf == "read_sql" or es_texto_sql:
            pz = self._interpolaciones(a, amb)
            if (pz is not None and not all(self._sql_ok(p, amb) for p in pz)) or (isinstance(a, ast.Name) and self._en(amb, "dinamicas", a.id)):
                self._h(n, "CWE-89 · SQL armado con datos", "la consulta se arma pegando valores. Qué se hace: marcadores (? o :nombre) y los valores aparte; para nombres de tabla o columna, una lista permitida")
        elif nf in SUMIDEROS_EXPR:
            pz = self._interpolaciones(a, amb)
            if (pz is not None and any(self._contamina(p, amb) and not self._sql_ok(p, amb) for p in pz)) or (isinstance(a, ast.Name) and self._en(amb, "dinamicas", a.id) and self._contamina(a, amb)):
                self._h(n, "CWE-89 · SQL armado con datos", "una expresión de Spark se arma con datos de afuera. Qué se hace: usar col() == valor, no texto")

    @staticmethod
    def _shell_con_datos(textos):
        """["bash", "-lc", f"..."], también tras env o sudo: el texto que sigue a la bandera -c es un guion, y los datos pegados ahí se ejecutan."""
        for i, t in enumerate(textos):
            base = t.rsplit("/", 1)[-1] if isinstance(t, str) else ""
            bandera = None
            if t in SHELLS or base in SHELLS:
                bandera = r"-[a-zA-Z]*c|/[cC]|(?i:-command|-encodedcommand)"
            elif re.fullmatch(r"python[0-9.]*", base):
                bandera = r"-c"
            elif base in ("perl", "ruby", "node", "php"):
                bandera = r"-[a-zA-Z]*e|-r"
            if bandera:
                for j in range(i + 1, len(textos) - 1):
                    b = textos[j]
                    if isinstance(b, str) and re.fullmatch(bandera, b):
                        return textos[j + 1] is NADA
                return False
        return False

    def _r_comando(self, n, nf, comp, amb):
        shell = _kw(n, "shell")
        hay_shell = shell is not None and self._const(shell, amb) is not False
        if not n.args:
            return
        a = n.args[0]
        if comp == "asyncio.create_subprocess_exec" and self._shell_con_datos([self._const(x, amb) for x in n.args]):
            self._h(n, "CWE-78 · comando armado", "el comando se arma con datos. Qué se hace: lista de argumentos, sin shell")
        es_sub = comp.startswith("subprocess.") and nf in SUBPROCESO or (nf in SUBPROCESO and hay_shell)
        msg = "el comando se arma con datos. Qué se hace: lista de argumentos, sin shell"
        pz = self._interpolaciones(a, amb)
        if es_sub or hay_shell:
            if hay_shell and self._const(a, amb) is NADA:
                if pz is not None and all(self._cmd_ok(p, amb) for p in pz):
                    self._exime(n, "B602", "B604", "B605", "B607")
                elif isinstance(a, ast.Name) and self._en(amb, "comandos_ok", a.id):
                    self._exime(n, "B602", "B604", "B605", "B607")
                else:
                    self._h(n, "CWE-78 · comando armado", msg)
            if pz is not None and not all(self._cmd_ok(p, amb) for p in pz):
                self._h(n, "CWE-78 · comando armado", msg)
            if isinstance(a, ast.Call) and _nombre_func(a) == "split":
                dentro = a.args[0] if a.args and self.completo(a.func) == "shlex.split" else (a.func.value if isinstance(a.func, ast.Attribute) else None)
                if dentro is not None and self._const(dentro, amb) is NADA:
                    self._h(n, "CWE-78 · comando armado", msg)
            if isinstance(a, (ast.List, ast.Tuple)) and a.elts:
                textos = [self._const(x, amb) for x in a.elts]
                if self._shell_con_datos(textos):
                    self._h(n, "CWE-78 · comando armado", msg)
                for x in a.elts:
                    if isinstance(x, ast.Name) and self._en(amb, "dinamicas", x.id) and textos[0] in SHELLS:
                        self._h(n, "CWE-78 · comando armado", msg)
            if isinstance(a, ast.Name) and self._en(amb, "dinamicas", a.id) and not self._en(amb, "comandos_ok", a.id):
                self._h(n, "CWE-78 · comando armado", msg)
        elif comp in ("subprocess.getoutput", "subprocess.getstatusoutput", "commands.getoutput", "asyncio.create_subprocess_shell", "pexpect.spawn", "pexpect.run") or \
                (nf in ("system", "getoutput") and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Call) and _nombre_func(n.func.value) == "get_ipython") or \
                nf in ("exec_command", "pipe") and pz is not None:
            if self._const(a, amb) is NADA and not (pz is not None and all(self._cmd_ok(p, amb) for p in pz)):
                self._h(n, "CWE-78 · comando armado", msg)

    def _r_deserializa(self, n, nf, comp, amb):
        msg = "carga un archivo de una forma que puede ejecutar código. Qué se hace: JSON, CSV o Parquet"
        if nf in ("read_pickle", "pickleFile", "read_hdf", "unsafe_load", "unsafe_load_all", "full_load", "full_load_all"):
            self._h(n, "CWE-502 · deserialización", msg)
        elif comp in ("numpy.load", "np.load"):
            ap = _kw(n, "allow_pickle")
            if ap is not None and self._const(ap, amb) is not False:
                self._h(n, "CWE-502 · deserialización", "np.load con allow_pickle ejecuta código al cargar. Qué se hace: dejarlo en False")
        elif comp in ("torch.load",):
            w = _kw(n, "weights_only")
            if w is None or self._const(w, amb) is not True:
                self._h(n, "CWE-502 · deserialización", "torch.load sin weights_only=True ejecuta código al cargar. Qué se hace: weights_only=True")
        elif comp in ("yaml.load", "yaml.load_all"):
            cargador = _kw(n, "Loader") or (n.args[1] if len(n.args) > 1 else None)
            if not (cargador is not None and "Safe" in _punteado(cargador)):
                self._h(n, "CWE-502 · deserialización", "yaml.load sin cargador seguro ejecuta código. Qué se hace: yaml.safe_load")
        elif nf == "load_model" and comp.split(".")[0] in ("keras", "tensorflow", "tf", "mlflow"):
            self._h(n, "CWE-502 · deserialización", "cargar un modelo ajeno puede ejecutar código. Qué se hace: solo modelos propios firmados, o formatos sin ejecución")

    def _r_ruta(self, n, nf, comp, amb):
        msg = "la ruta se arma con un dato de afuera y sin comprobar que quede dentro de la carpeta base. Qué se hace: resolver la ruta y exigir is_relative_to(base)"
        candidatos = []
        if nf in SUMIDEROS_RUTA:
            candidatos = list(n.args[:2]) + [k.value for k in n.keywords if k.arg in CLAVES_RUTA]
        if nf in LECTOR_SPARK and isinstance(n.func, ast.Attribute) and any(isinstance(x, ast.Attribute) and x.attr in ("read", "write", "readStream", "writeStream") for x in ast.walk(n.func.value)):
            candidatos = list(n.args[:1]) + [k.value for k in n.keywords if k.arg in CLAVES_RUTA]
        if nf in SUMIDEROS_SQL and isinstance(n.func, ast.Attribute) and n.args:
            sql, par = self._const(n.args[0], amb), n.args[1] if len(n.args) > 1 else (_kw(n, "parameters") or _kw(n, "params"))
            if isinstance(sql, str) and par is not None and SQL_LEE_ARCHIVO.search(sql):
                candidatos = list(par.values) if isinstance(par, ast.Dict) else [par]
        if nf in ("glob", "iglob") or comp == "sqlite3.connect" or (nf == "load" and isinstance(n.func, ast.Attribute) and (comp == "numpy.load" or "read" in _punteado(n.func.value).split(".") or "format" in {_nombre_func(x) for x in ast.walk(n.func.value) if isinstance(x, ast.Call)})):
            candidatos = list(n.args[:1])
        malo = any(self._ruta_armada(a, amb) for a in candidatos)
        if not malo and nf in SUMIDEROS_RUTA:
            malo = any(isinstance(x, ast.Name) and x.id in ("request", "flask_request") or (isinstance(x, ast.Call) and _nombre_func(x) == "input") for a in candidatos for x in ast.walk(a))
        if not malo and isinstance(n.func, ast.Attribute) and nf in METODOS_RUTA:
            malo = self._ruta_armada(n.func.value, amb)
        if malo and not self._ruta_protegida(amb):
            self._h(n, "CWE-22 · ruta sin contención", msg)
        if nf in ("extractall", "extract") and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) and self._en(amb, "tarfiles", n.func.value.id):
            filtro = _kw(n, "filter")
            if filtro is None:
                self._h(n, "CWE-22 · ruta sin contención", "un .tar puede escribir fuera de la carpeta. Qué se hace: extractall(filter=\"data\")")
            else:
                self._exime(n, "B202")
        if nf in ("extractall", "extract") and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) and self._en(amb, "zipfiles", n.func.value.id) and not self._ruta_protegida(amb):
            self._h(n, "CWE-22 · ruta sin contención", "se extrae un archivo ajeno sin revisar sus miembros. Qué se hace: comprobar cada nombre contra la carpeta destino antes de extraer")
        if comp == "shutil.unpack_archive" and _kw(n, "filter") is None:
            self._h(n, "CWE-22 · ruta sin contención", "un archivo comprimido puede escribir fuera de la carpeta. Qué se hace: unpack_archive(..., filter=\"data\")")

    def _es_styler(self, e, amb):
        """df.style...; escape="html" en .format lo deja limpio."""
        hay = False
        for x in ast.walk(e):
            if isinstance(x, ast.Call) and _nombre_func(x) == "format" and self._const(_kw(x, "escape"), amb) in ("html", "latex", "xml"):
                return False
            if isinstance(x, ast.Attribute) and x.attr == "style":
                hay = True
            if isinstance(x, ast.Name) and self._en(amb, "stylers", x.id):
                hay = True
        return hay

    def _r_html_sumidero(self, n, nf, comp, amb):
        if self.perfil != "usuario":
            return
        if comp in ("markdown.markdown", "markdown2.markdown", "mistune.html", "commonmark.commonmark", "markdown") and n.args and self._const(n.args[0], amb) is NADA:
            if not re.search(r"(?i)bleach|nh3|sanitize|sanear", self.texto):
                self._h(n, "CWE-79 · HTML sin escapar", "el Markdown deja pasar HTML incrustado de los datos. Qué se hace: limpiar el resultado con bleach o nh3")
        if nf in ("substitute", "safe_substitute") and isinstance(n.func, ast.Attribute):
            r = n.func.value
            plantilla = r.args[0] if isinstance(r, ast.Call) and _nombre_func(r) == "Template" and r.args else None
            if isinstance(r, ast.Name):
                for x in ast.walk(self.arbol):
                    if isinstance(x, ast.Assign) and isinstance(x.value, ast.Call) and _nombre_func(x.value) == "Template" and x.value.args and any(isinstance(t, ast.Name) and t.id == r.id for t in x.targets):
                        plantilla = x.value.args[0]
            texto = self._const(plantilla, amb) if plantilla is not None else NADA
            if isinstance(texto, str) and ES_HTML.search(texto):
                valores = list(n.args) + [k.value for k in n.keywords]
                if any(self._const(v, amb) is NADA and not (isinstance(v, ast.Call) and _nombre_func(v) in ("escape", "quote", "clean", "int", "float", "len")) for v in valores):
                    self._h(n, "CWE-79 · HTML sin escapar", "la plantilla HTML recibe datos sin escapar. Qué se hace: html.escape() en cada valor")
        if nf == "to_html":
            k = _kw(n, "escape")
            if k is not None and self._const(k, amb) is False:
                self._h(n, "CWE-79 · HTML sin escapar", "to_html(escape=False) deja pasar HTML de los datos. Qué se hace: quitar escape=False")
            k = _kw(n, "render_links")
            if k is not None and self._const(k, amb) is True:
                self._h(n, "CWE-79 · HTML sin escapar", "to_html(render_links=True) pone la URL de los datos sin escapar en el enlace. Qué se hace: quitar render_links y armar el enlace con html.escape()")
        if nf in ("to_html", "render") and isinstance(n.func, ast.Attribute) and self._es_styler(n.func.value, amb):
            self._h(n, "CWE-79 · HTML sin escapar", "df.style no escapa los textos por defecto. Qué se hace: agregar .format(escape=\"html\") a la tabla con estilo")
        unsafe = _kw(n, "unsafe_allow_html")
        es_sumidero = nf in HTML_SUMIDEROS or (unsafe is not None and self._const(unsafe, amb) is True)
        if es_sumidero and n.args:
            a = n.args[0]
            if self._const(a, amb) is NADA and not self._html_ok(a, amb):
                self._h(n, "CWE-79 · HTML sin escapar", "se muestra como HTML un texto con datos. Qué se hace: html.escape() antes de insertar")
        if comp in ("jinja2.Template",) and self._const(_kw(n, "autoescape"), amb) is not True:
            self._h(n, "CWE-79 · HTML sin escapar", "jinja2.Template no escapa por defecto. Qué se hace: Environment(autoescape=True)")

    def _r_log(self, n, nf, comp, amb):
        if self.perfil != "usuario":
            return
        f = n.func
        es_log = nf in ("print", "pprint", "pp", "display") and isinstance(f, ast.Name)
        if isinstance(f, ast.Attribute):
            raiz = _punteado(f.value)
            if nf in LOG_NIVELES and (comp.startswith("logging.") or re.search(r"(?i)log", raiz or "") or (isinstance(f.value, ast.Call) and _nombre_func(f.value) == "getLogger")):
                es_log = True
            if comp in ("sys.stdout.write", "sys.stderr.write", "warnings.warn", "pprint.pprint", "st.write", "streamlit.write"):
                es_log = True
            if nf in ("write", "writelines") and isinstance(f.value, ast.Name) and self._en(amb, "archivos_log", f.value.id):
                es_log = True
            if nf == "show":
                for c in ast.walk(f.value):
                    if isinstance(c, ast.Constant) and es_sensible(c.value):
                        self._h(n, "CWE-532 · dato sensible en un mensaje", "se imprimen filas con datos personales. Qué se hace: mostrar conteos o valores enmascarados")
                        break
                if self._frame_personal(f.value, amb):
                    self._h(n, "CWE-532 · dato sensible en un mensaje", "se imprimen filas con datos personales. Qué se hace: mostrar conteos o valores enmascarados")
        if not es_log:
            return
        muestra = [b.value if isinstance(b, ast.FormattedValue) else b for a in n.args for b in (a.values if isinstance(a, ast.JoinedStr) else [a])]
        if any(self._frame_personal(b, amb) for b in muestra):
            self._h(n, "CWE-532 · dato sensible en un mensaje", "se imprimen filas de una tabla con columnas personales. Qué se hace: mostrar conteos, o quitar o enmascarar esas columnas antes")
        if self._excepcion_con_secreto(n, amb):
            self._h(n, "CWE-532 · dato sensible en un mensaje", "el mensaje de la excepción trae la URL con sus parámetros secretos. Qué se hace: registrar el tipo de error y el código HTTP, no la excepción completa")
        for a in list(n.args) + [k.value for k in n.keywords]:
            if self._sensible_en(a, amb) or (isinstance(a, ast.Name) and self._en(amb, "filas", a.id)):
                self._h(n, "CWE-532 · dato sensible en un mensaje", "un mensaje o registro lleva un dato personal o un secreto. Qué se hace: conteos, o el valor enmascarado")
                break

    def _usa_alfabeto(self, e):
        """¿El argumento es, o se arma con, un alfabeto escrito (ABCDEF...)? Sigue un nombre hasta su asignación."""
        def literal(x):
            return any(isinstance(y, ast.Constant) and isinstance(y.value, str) and len(y.value) >= 20 and _es_alfabeto(y.value) for y in ast.walk(x))
        if literal(e):
            return True
        nombres = {x.id for x in ast.walk(e) if isinstance(x, ast.Name)}
        return any(isinstance(m, ast.Assign) and any(isinstance(t, ast.Name) and t.id in nombres for t in m.targets) and literal(m.value) for m in self.padres)

    def _r_vector_fijo(self, n, nf, comp, amb):
        msg = "el cifrado usa un vector inicial o un nonce fijo, y mensajes iguales quedan expuestos. Qué se hace: uno nuevo con os.urandom en cada cifrado"
        partes = comp.split(".")
        candidatos = []
        if nf == "new" and len(partes) >= 2 and partes[-2] in ("AES", "DES3", "ChaCha20", "ChaCha20_Poly1305", "Salsa20", "Blowfish", "CAST", "ARC2"):
            candidatos = list(n.args[2:3]) + [k.value for k in n.keywords if k.arg in ("iv", "IV", "nonce")]
        elif nf in ("CBC", "CTR", "GCM", "OFB", "CFB", "CFB8") and (partes[0] == "cryptography" or (len(partes) >= 2 and partes[-2] == "modes")):
            candidatos = list(n.args[:1]) + [k.value for k in n.keywords if k.arg in ("initialization_vector", "nonce", "tweak")]
        elif nf == "encrypt" and len(n.args) == 3:
            candidatos = list(n.args[:1])
        if any(isinstance(self._const(c, amb), bytes) for c in candidatos):
            self._h(n, "CWE-327 · criptografía débil", msg)

    def _usa_alfabeto(self, e):
        if any(isinstance(x, ast.Attribute) and self.completo(x).startswith("string.") for x in ast.walk(e)):
            return True
        if isinstance(e, ast.Name):
            for a in ast.walk(self.arbol):
                if isinstance(a, ast.Assign) and any(isinstance(t, ast.Name) and t.id == e.id for t in a.targets):
                    if any(isinstance(x, ast.Attribute) and self.completo(x).startswith("string.") for x in ast.walk(a.value)):
                        return True
        return False

    def _r_azar_spark(self, n, nf, comp):
        msg = "un valor secreto sale de un azar predecible. Qué se hace: el módulo secrets"
        secreto = lambda x: isinstance(x, str) and CONTEXTO_SECRETO.search(_sin_tildes(x)) and not NOMBRE_TIEMPO.search(_sin_tildes(x))
        if nf == "withColumn" and len(n.args) > 1 and isinstance(n.args[0], ast.Constant) and secreto(n.args[0].value):
            if any(isinstance(c, ast.Constant) and isinstance(c.value, str) and re.search(r"(?i)\brandn?\s*\(", c.value) for c in ast.walk(n.args[1])):
                self._h(n, "CWE-330 · azar predecible", msg)
        es_rand = nf in ("rand", "randn") and (comp.split(".")[0] == "pyspark" or (isinstance(n.func, ast.Attribute) and _punteado(n.func.value) in ("F", "f", "fn", "funcs", "sf")))
        if not es_rand:
            return
        nombres, p = list(self._contexto_secreto(n)), n
        while p in self.padres:
            q = self.padres[p]
            if isinstance(q, ast.Call) and isinstance(q.func, ast.Attribute) and q.func.attr == "withColumn" and len(q.args) > 1 and p is q.args[1] and isinstance(q.args[0], ast.Constant):
                nombres.append(q.args[0].value)
            if isinstance(q, ast.Attribute) and q.attr == "alias" and isinstance(self.padres.get(q), ast.Call):
                for a in self.padres[q].args[:1]:
                    if isinstance(a, ast.Constant):
                        nombres.append(a.value)
            p = q
        if any(secreto(x) for x in nombres):
            self._h(n, "CWE-330 · azar predecible", msg)

    def _r_azar_funcion_local(self, n):
        if not isinstance(n.func, ast.Name):
            return
        p, propias = n, set()
        while p in self.padres:
            p = self.padres[p]
            if isinstance(p, (ast.FunctionDef, ast.AsyncFunctionDef)):
                propias.add(p.name)
        nombres = [x for x in self._contexto_secreto(n) if isinstance(x, str) and x not in propias]
        if not any(CONTEXTO_SECRETO.search(_sin_tildes(x)) and not NOMBRE_TIEMPO.search(_sin_tildes(x)) for x in nombres):
            return
        for f in ast.walk(self.arbol):
            if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)) and f.name == n.func.id:
                comps = {self.completo(c.func) for c in ast.walk(f) if isinstance(c, ast.Call)}
                if any("SystemRandom" in c for c in comps):
                    return
                if any(c.startswith(("random.", "numpy.random.", "np.random.")) for c in comps):
                    self._h(n, "CWE-330 · azar predecible", "un valor secreto sale de una función que usa un azar predecible. Qué se hace: el módulo secrets")
                    return

    def _destino_secreto(self, objetivos, valor, usados, es_tiempo):
        limpios = [_sin_tildes(x) for x in objetivos if isinstance(x, str)]
        fuertes = [x for x in limpios if CONTEXTO_SECRETO.search(x) and not NOMBRE_TIEMPO.search(x)]
        if not es_tiempo:
            fuertes = [x for x in fuertes if not re.search(r"(?i)(clave|llave|key|acceso)", x) or re.search(r"(?i)(api_?key|clave_(api|acceso|secreta)|secret)", x)]
        fuertes = [x for x in fuertes if not re.search(r"(?i)(por_|total|conteo|cantidad|(?:^|_)nu?m?_|usados|promedio|media|sesiones)", x)]
        if not fuertes:
            return False
        comps = {self.completo(c.func) for c in ast.walk(valor) if isinstance(c, ast.Call)}
        if any(c.startswith("secrets.") for c in comps):
            return False
        if es_tiempo:
            if not any(c.startswith("hashlib.") for c in comps) or any(CON_SAL.search(x) for x in usados) or any(HUELLA_INTEGRIDAD.search(x) for x in limpios):
                return False
        return True

    def _r_azar_flujo(self, n, es_tiempo):
        """El azar o la hora llegan al secreto por una variable intermedia."""
        st = n
        while st in self.padres and not isinstance(st, ast.stmt):
            st = self.padres[st]
        if not isinstance(st, ast.Assign):
            return False
        marcados = {t.id for t in st.targets if isinstance(t, ast.Name)}
        if not marcados:
            return False
        alcance = st
        while alcance in self.padres and not isinstance(alcance, (ast.FunctionDef, ast.AsyncFunctionDef)):
            alcance = self.padres[alcance]
        pasos = [a for a in ast.walk(alcance) if isinstance(a, (ast.Assign, ast.Return)) and a is not st and a.value is not None]
        for _ in range(4):
            for a in pasos:
                usados = {x.id for x in ast.walk(a.value) if isinstance(x, ast.Name)}
                if not usados & marcados or isinstance(a.value, ast.Compare):
                    continue
                if isinstance(a.value, ast.Subscript) and any(isinstance(x, ast.Name) and x.id in marcados for x in ast.walk(a.value.slice)):
                    continue
                if isinstance(a, ast.Return):
                    objetivos = [alcance.name] if isinstance(alcance, (ast.FunctionDef, ast.AsyncFunctionDef)) else []
                else:
                    objetivos = []
                    for t in a.targets:
                        if isinstance(t, ast.Name):
                            objetivos.append(t.id)
                            marcados.add(t.id)
                        elif isinstance(t, ast.Attribute):
                            objetivos.append(t.attr)
                        elif isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant):
                            objetivos.append(t.slice.value)
                if self._destino_secreto(objetivos, a.value, usados, es_tiempo):
                    return True
        return False

    def _r_azar(self, n, nf, comp, amb):
        self._r_azar_spark(n, nf, comp)
        self._r_azar_funcion_local(n)
        es_azar = (comp.startswith("random.") and nf not in ("seed", "SystemRandom")) or comp.startswith(("numpy.random.", "np.random."))
        if isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) and self._en(amb, "generadores", n.func.value.id):
            es_azar = True
        es_tiempo = comp in ("uuid.uuid1", "time.time", "time.time_ns", "datetime.now", "datetime.datetime.now")
        if not es_azar and not es_tiempo:
            return
        msg = "un valor secreto sale de un azar predecible. Qué se hace: el módulo secrets"
        nombres = [x for x in self._contexto_secreto(n) if isinstance(x, str)]
        if self.perfil == "usuario" and nf not in ("default_rng", "Random", "RandomState", "SeedSequence", "PCG64", "Generator") and self._r_azar_flujo(n, es_tiempo):
            self._h(n, "CWE-330 · azar predecible", msg)
            return
        if es_tiempo and any(NOMBRE_TIEMPO.search(_sin_tildes(x)) for x in nombres):
            return   # es la fecha de vencimiento del token, no el token
        if any(CONTEXTO_SECRETO.search(_sin_tildes(x)) for x in nombres):
            self._h(n, "CWE-330 · azar predecible", msg)
            return
        if es_azar:
            if nf in ("getrandbits", "randbytes"):
                self._h(n, "CWE-330 · azar predecible", msg)
            if nf in ("choice", "choices", "sample") and n.args and self._usa_alfabeto(n.args[0]):
                self._h(n, "CWE-330 · azar predecible", "se arma un identificador o una clave con random. Qué se hace: el módulo secrets")
            elif nf in ("choice", "choices", "sample") and n.args and self._usa_alfabeto(n.args[0]):
                self._h(n, "CWE-330 · azar predecible", "se arma un identificador o una clave con random. Qué se hace: el módulo secrets")
            if self.perfil == "pura" and "random.seed" not in {self.completo(x.func) for x in ast.walk(self.arbol) if isinstance(x, ast.Call)} and nf not in ("Random", "default_rng", "RandomState") :
                self._h(n, "azar sin semilla", "el resultado no se puede repetir. Qué se hace: fijar la semilla")

    def _lista_personal(self, it):
        if isinstance(it, ast.Name):
            if re.search(r"(?i)(personal|(?:^|_)pii(?:_|$))", it.id) and not re.search(r"(?i)(?:^|_)no_", it.id):
                return True
            for a in ast.walk(self.arbol):
                if isinstance(a, ast.Assign) and any(isinstance(t, ast.Name) and t.id == it.id for t in a.targets) and not isinstance(a.value, ast.Name):
                    return self._lista_personal(a.value)
            return False
        if isinstance(it, (ast.List, ast.Tuple, ast.Set)):
            return any(isinstance(x, ast.Constant) and es_sensible(x.value) for x in it.elts)
        return isinstance(it, ast.Subscript) and isinstance(it.slice, ast.Constant) and es_sensible(it.slice.value)

    def _receptor_personal(self, r, usados):
        while isinstance(r, ast.Call) or (isinstance(r, ast.Attribute) and not es_sensible(r.attr)):
            r = r.func if isinstance(r, ast.Call) else r.value
        if isinstance(r, ast.Attribute) and es_sensible(r.attr):
            return True
        if isinstance(r, ast.Subscript):
            if isinstance(r.slice, ast.Constant) and es_sensible(r.slice.value):
                return True
            if isinstance(r.slice, ast.Name):
                usados.add(r.slice.id)
        return False

    def _viene_de_columna_personal(self, args, n):
        """El valor llega de una columna personal por un lambda, una función de map o una lista de columnas."""
        usados = {x.id for a in args for x in ast.walk(a) if isinstance(x, ast.Name)}
        METODOS = ("apply", "map", "transform", "applymap")
        p = n
        while p in self.padres:
            q = self.padres[p]
            if isinstance(q, ast.Lambda):
                c = self.padres.get(q)
                if {a.arg for a in q.args.args} & usados and isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr in METODOS:
                    if self._receptor_personal(c.func.value, usados):
                        return True
            elif isinstance(q, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if {a.arg for a in q.args.args} & usados:
                    for c in ast.walk(self.arbol):
                        if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr in METODOS and c.args and isinstance(c.args[0], ast.Name) and c.args[0].id == q.name:
                            if self._receptor_personal(c.func.value, set()):
                                return True
            elif isinstance(q, ast.For):
                if isinstance(q.target, ast.Name) and q.target.id in usados and self._lista_personal(q.iter):
                    return True
            elif isinstance(q, (ast.ListComp, ast.GeneratorExp, ast.SetComp, ast.DictComp)):
                if any(isinstance(g.target, ast.Name) and g.target.id in usados and self._lista_personal(g.iter) for g in q.generators):
                    return True
            p = q
        return False

    def _sal_vacia(self, nombre):
        """La sal o la llave quedan vacías si falta la variable de entorno, y nadie lo revisa."""
        vacia = False
        for a in ast.walk(self.arbol):
            if isinstance(a, (ast.If, ast.Assert, ast.IfExp)) and any(isinstance(x, ast.Name) and x.id == nombre for x in ast.walk(a.test)):
                return False
            if isinstance(a, ast.Assign) and any(isinstance(t, ast.Name) and t.id == nombre for t in a.targets):
                for c in ast.walk(a.value):
                    if isinstance(c, ast.Constant) and c.value in ("", b"") and c is a.value:
                        vacia = True
                    if isinstance(c, ast.Call) and self.completo(c.func) in ("os.getenv", "os.environ.get") and len(c.args) > 1 and isinstance(c.args[1], ast.Constant) and c.args[1].value in ("", b""):
                        vacia = True
                    if isinstance(c, ast.BoolOp) and isinstance(c.op, ast.Or) and isinstance(c.values[-1], ast.Constant) and c.values[-1].value in ("", b""):
                        vacia = True
        return vacia

    def _r_hash(self, n, nf, comp, amb):
        debil = comp.split(".")[-1] if comp.startswith("hashlib.") else ""
        uso = _kw(n, "usedforsecurity")
        para_integridad = uso is not None and self._const(uso, amb) is False
        if debil in HASH_DEBIL and not para_integridad:
            self._h(n, "CWE-327 · criptografía débil", f"usa {debil}. Qué se hace: SHA-256 o más; para seudonimizar, HMAC con llave")
        if comp in ("hashlib.new", "hmac.new", "hashlib.pbkdf2_hmac") or nf == "HMAC":
            for a in list(n.args) + [k.value for k in n.keywords if k.arg in ("digestmod", "name", "hash_name")]:
                c = self._const(a, amb)
                if isinstance(c, str) and c.lower() in HASH_DEBIL and not para_integridad:
                    self._h(n, "CWE-327 · criptografía débil", f"usa {c}. Qué se hace: SHA-256 o más")
        if comp == "hashlib.pbkdf2_hmac":
            it = n.args[3] if len(n.args) > 3 else _kw(n, "iterations")
            c = self._const(it, amb) if it is not None else NADA
            if isinstance(c, int) and c < 100000:
                self._h(n, "CWE-327 · criptografía débil", "muy pocas iteraciones para derivar una clave. Qué se hace: 100.000 o más")
        if comp in ("crypt.crypt",):
            self._h(n, "CWE-327 · criptografía débil", "crypt es débil. Qué se hace: hashlib.scrypt")
        args = list(n.args)
        if not args:
            return
        nombres_salida = [x for x in self._contexto_secreto(n) if isinstance(x, str)]
        spark_debil = nf in HASH_DEBIL and comp.split(".")[0] == "pyspark" or (nf in HASH_DEBIL and isinstance(n.func, ast.Attribute) and _punteado(n.func.value) in ("F", "f", "fn", "funcs", "sf"))
        sensible = next((self._sensible_en(a, amb) for a in args if self._sensible_en(a, amb)), None)
        if not sensible and (nf in HASH_DEBIL or nf in HASH_SIN_SAL or comp in ("uuid.uuid5", "uuid.uuid3") or comp.split(".")[-1] in HASH_SIN_SAL) and self._viene_de_columna_personal(args, n):
            sensible = "columna personal"
        if comp == "hmac.new" and any(isinstance(x, ast.Name) and self._sal_vacia(x.id) for x in ast.walk(args[0])):
            self._h(n, "CWE-327 · criptografía débil", "si falta la variable de entorno la llave queda vacía y el HMAC no protege nada. Qué se hace: leerla con os.environ[...] para que falle sin ella")
        if debil in HASH_DEBIL and para_integridad and sensible:
            nombres_arg = {x.id for a in args for x in ast.walk(a) if isinstance(x, ast.Name)}
            if not any(CON_SAL.search(x) for x in nombres_arg):
                self._h(n, "CWE-327 · criptografía débil", f"usa {debil} sobre un dato personal, aunque se marque como no criptográfico. Qué se hace: HMAC con llave, o hash fuerte con sal secreta")
        if spark_debil and not any(HUELLA_INTEGRIDAD.search(x) for x in nombres_salida):
            if sensible or any(re.search(r"(?i)(seudonim|pseudonim|anonim|hash_doc|hash_ced)", x) for x in nombres_salida) or any(isinstance(c, ast.Constant) and es_sensible(c.value) for a in args for c in ast.walk(a)):
                self._h(n, "CWE-327 · criptografía débil", f"seudonimiza con {nf}. Qué se hace: HMAC con llave, o hash fuerte con sal secreta")
        base = nf if nf in HASH_SIN_SAL else (comp.split(".")[-1] if comp.split(".")[-1] in HASH_SIN_SAL else "")
        if comp in ("uuid.uuid5", "uuid.uuid3"):
            base = "uuid"
        if (base or (comp.startswith(("zlib.", "binascii.")) and nf in HASH_SIN_SAL)) and not (nf in ("b64encode", "urlsafe_b64encode", "b32encode", "hexlify") and re.search(r"AESGCM|Fernet|ChaCha20|\.encrypt\(", self.texto)):
            con_constante = any(isinstance(c, ast.Constant) and es_sensible(c.value) for a in args for c in ast.walk(a))
            para_seudonimizar = any(CONTEXTO_SEUDONIMO.search(_sin_tildes(x)) for x in nombres_salida) and not any(HUELLA_INTEGRIDAD.search(x) for x in nombres_salida)
            if (sensible or con_constante or para_seudonimizar) and not _kw(n, "key") and not _kw(n, "salt") and not self._de_secrets(args, amb):
                nombres_arg = {x.id for a in args for x in ast.walk(a) if isinstance(x, ast.Name)} | {c.value for a in args for c in ast.walk(a) if isinstance(c, ast.Constant) and isinstance(c.value, str)}
                if not any(CON_SAL.search(x) for x in nombres_arg):
                    self._h(n, "CWE-327 · criptografía débil", "un dato personal se seudonimiza sin sal ni llave y se puede revertir por diccionario. Qué se hace: HMAC con llave, o hash fuerte con sal secreta")
                elif any(CON_SAL.search(x) and self._sal_vacia(x) for x in nombres_arg):
                    self._h(n, "CWE-327 · criptografía débil", "si falta la variable de entorno la sal queda vacía y el dato se revierte por diccionario. Qué se hace: leerla con os.environ[...] para que falle sin ella")
        if nf == "update" and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) and self._en(amb, "hashes", n.func.value.id) and sensible:
            nombres = {x.id for x in ast.walk(amb.nodo) if isinstance(x, ast.Name)}
            if not any(CON_SAL.search(x) for x in nombres):
                self._h(n, "CWE-327 · criptografía débil", "un dato personal se seudonimiza sin sal ni llave. Qué se hace: HMAC con llave, o hash fuerte con sal secreta")
        if nf == "encode" and comp.startswith("codecs.") and len(args) > 1 and str(self._const(args[1], amb)).lower().startswith("rot"):
            self._h(n, "CWE-327 · criptografía débil", "rot13 no protege nada. Qué se hace: cifrado autenticado o HMAC")
        if comp.split(".")[-1] in ("b64encode", "urlsafe_b64encode") and any(re.search(r"(?i)(cifr|encript|encrypt|ofusc|seudonim|pseudonim|anonim)", x) for x in nombres_salida):
            self._h(n, "CWE-327 · criptografía débil", "base64 no cifra: cualquiera lo revierte. Qué se hace: cifrado autenticado o HMAC")

    def _regex_escapada(self, a, amb, prof=0):
        """El propio consejo de la regla: re.escape() de cada parte, también unidas con "|".join(...)."""
        if prof > 6:
            return False
        if isinstance(a, ast.Constant):
            return True
        if isinstance(a, ast.Call):
            f = _punteado(a.func) if isinstance(a.func, ast.Attribute) else ""
            if f == "re.escape" or (isinstance(a.func, ast.Name) and a.func.id == "escape" and self.imports.get("escape", "").startswith("re")):
                return True
            if isinstance(a.func, ast.Attribute) and a.func.attr == "join" and isinstance(a.func.value, ast.Constant) and len(a.args) == 1:
                d = a.args[0]
                if isinstance(d, (ast.GeneratorExp, ast.ListComp)):
                    return self._regex_escapada(d.elt, amb, prof + 1)
                return isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == "map" and bool(d.args) and _punteado(d.args[0]) == "re.escape"
            return False
        if isinstance(a, ast.BinOp) and isinstance(a.op, ast.Add):
            return self._regex_escapada(a.left, amb, prof + 1) and self._regex_escapada(a.right, amb, prof + 1)
        if isinstance(a, ast.JoinedStr):
            return all(self._regex_escapada(v.value if isinstance(v, ast.FormattedValue) else v, amb, prof + 1) for v in a.values)
        if isinstance(a, ast.Name):
            valores = [x.value for x in ast.walk(amb.nodo) if isinstance(x, ast.Assign) and any(isinstance(t, ast.Name) and t.id == a.id for t in x.targets)]
            return bool(valores) and all(self._regex_escapada(v, amb, prof + 1) for v in valores)
        return False

    def _de_secrets(self, args, amb):
        """Un token que acaba de salir de secrets ya trae todo su azar: guardar su huella es lo correcto y la sal no aporta."""
        nombres = {x.id for a in args for x in ast.walk(a) if isinstance(x, ast.Name)}
        if not nombres:
            return False
        for nombre in nombres:
            valores = [x.value for x in ast.walk(amb.nodo) if isinstance(x, ast.Assign) and any(isinstance(t, ast.Name) and t.id == nombre for t in x.targets)]
            if not valores or not all(isinstance(v, ast.Call) and _nombre_func(v) in ("token_urlsafe", "token_hex", "token_bytes") for v in valores):
                return False
        return True

    def _r_regex(self, n, nf, comp, amb):
        es_re = comp.startswith(("re.", "regex.")) and nf in RE_FUNCS
        es_str = nf in STR_REGEX and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Attribute) and n.func.value.attr == "str"
        es_spark = nf in ("rlike", "regexp_extract", "regexp_replace", "regexp_like")
        patrones = list(n.args[:2]) if es_re or es_spark or nf in ("split", "rsplit", "str_matches", "str_contains", "colRegex") else (list(n.args[:1]) if es_str else [])
        rx = _kw(n, "pat") or _kw(n, "pattern") or _kw(n, "regex")
        if rx is not None:
            patrones.append(rx)
        if nf == "replace":   # Series.str.replace y DataFrame.replace
            es_regex = _kw(n, "regex")
            destino = n.args[0] if n.args else _kw(n, "to_replace")
            if es_regex is not None and self._const(es_regex, amb) is True and destino is not None:
                patrones.append(destino)
        verbose = any(isinstance(x, ast.Attribute) and x.attr in ("VERBOSE", "X") or isinstance(x, ast.Name) and x.id in ("VERBOSE", "X")
                      for a in list(n.args[1:]) + [k.value for k in n.keywords] for x in ast.walk(a))
        for p in patrones:
            c = self._const(p, amb)
            if isinstance(c, (str, bytes)) and regex_catastrofica(c, verbose):
                self._h(n, "CWE-1333 · regex catastrófica", "repeticiones anidadas que pueden colgar el proceso. Qué se hace: acotar el patrón o cambiarlo por uno sin repetición dentro de repetición")
                return
        if es_re or es_str or nf == "rlike":
            if es_str:
                k = _kw(n, "regex")
                if k is not None and self._const(k, amb) is False:
                    return
            a = n.args[0] if n.args else None
            if a is not None and self.perfil == "usuario" and self._const(a, amb) is NADA and self._contamina(a, amb) and not self._regex_escapada(a, amb) and not self._plantilla_interna(a, amb):
                self._h(n, "CWE-1333 · regex catastrófica", "el patrón viene de afuera y puede colgar el proceso. Qué se hace: re.escape() o regex=False")


def analizar(texto, perfil="pura"):
    with warnings.catch_warnings():   # avisos del analizador de regex de Python sobre el patrón revisado: no son hallazgos
        warnings.simplefilter("ignore", FutureWarning)
        return Analisis(texto, perfil)
