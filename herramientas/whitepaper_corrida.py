#!/usr/bin/env python3
"""El whitepaper del pipeline en tres hojas tamaño carta (sin IA): maqueta el texto validado, sin cambiarlo.

Uso:
  python herramientas/whitepaper_corrida.py <corrida>       escribe <corrida>/WHITEPAPER.html y <corrida>/WHITEPAPER.pdf
  python herramientas/whitepaper_corrida.py --autoprueba    casos buenos y malos, sin Chrome

El documentador (agentes/13-documentador.md) escribe <corrida>/whitepaper.md, y validar_whitepaper.py lo valida sin IA
(W1 a W5) y deja whitepaper_verificacion.json con la huella (sha256) del texto validado y su estado. Esta herramienta
solo arma la versión impresa, y solo si:
  - la verificación existe, dice «aprobado» y todos sus chequeos pasaron;
  - su huella es la del whitepaper.md de hoy (un texto que cambió después de validarse no vale);
  - ni el whitepaper ni la verificación son enlaces simbólicos, el texto es UTF-8 y prosa breve (hasta 200 KB y
    líneas de hasta 4.000 caracteres, como en la validación) y no trae caracteres invisibles ni bidireccionales ni
    palabras disfrazadas con letras de otro alfabeto (W5 ya los rechaza: si aparecen, la verificación no es de este
    texto).
Si algo falla, falla cerrado: no arma nada, borra el WHITEPAPER.html y el WHITEPAPER.pdf anteriores (eran de otro texto),
dice por qué y sale con 1.

No cambia ni una palabra ni una cifra: pasa el Markdown a HTML escapando todo, porque el texto lo escribió una IA. Ningún
marcado HTML del texto se interpreta (sale como texto), no hay enlaces (<a>), imágenes ni scripts, y el HTML declara una
política de contenido que no carga nada. Un enlace queda como su texto con el destino al lado, en gris y sin abrir (un
enlace externo tampoco se abre): Chrome escribe un enlace relativo en el PDF como file:///ruta/local/completa, y el PDF
que se comparte filtraría la ruta y el usuario de quien lo imprimió (L84). Los números de una lista numerada se
muestran como están escritos. Antes de imprimir comprueba, sin IA:
  - que cada palabra y cada cifra del texto validado está en el HTML (se cuentan una por una);
  - que el HTML solo trae las etiquetas y atributos del armador (nada de a, img, script, iframe ni eventos);
  - el barrido de datos personales e instrucciones de gobernanza.py sobre el texto que se ve;
  - la lista D15 (buscar_d15 de validar_whitepaper.py) sobre el texto que se ve: una verificación vieja que dejó pasar
    «Esto *demuestra* que…» no imprime «Esto demuestra que…» (L117).
Después de imprimir, comprueba que el PDF es carta (612 × 792 pt) y que no trae enlaces.

Hoja 1: el título, el sello de la validación y Pregunta · Datos y procedencia · Limpieza. Hoja 2: Cifra verificada y
cómo se verificó · Gráfico · Gobernanza. Hoja 3: Límites · Preguntas para el análisis de las personas. Se imprime con
el armador común (carta.py, el mismo de whitepaper_fichas.py): en cada paso de letra (de 10 a 8,5 pt), primero con un
salto de hoja antes de «Cifra verificada» y otro antes de «Límites» (una parte por hoja) y, si así no da tres hojas, el
texto seguido. Si con 8,5 pt no cabe en tres hojas, sale completo en las hojas que necesite, con la letra más grande con
la que quepa en tres o, si no cabe, con 8,5 pt (nunca se recorta texto validado), lo dice y sale con 1: el whitepaper es
más largo que lo pedido y el documentador debe acortarlo. Sin Chrome deja el HTML y lo dice. El informe final
(informe_final.py) no le cree a esta herramienta: mide el PDF por su cuenta y lo enlaza «en tres hojas carta» solo si
tiene tres, en carta y sin enlaces; con más hojas no lo enlaza y deja el análisis sin aprobar (L113).
Última línea: RESUMEN {json}.
"""
import contextlib
import hashlib
import io
import json
import re
import shutil
import sys
import tempfile
import time
import unicodedata
from collections import Counter
from html import escape
from html.parser import HTMLParser
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import carta  # noqa: E402
from gobernanza import escanear_texto, letras_disfrazadas, parece_instruccion  # noqa: E402
from validar_whitepaper import buscar_d15  # noqa: E402  D15: la lista única

MAX_BYTES, LINEA_MAX = 200_000, 4_000          # los mismos topes de validar_whitepaper.py
INVISIBLES = re.compile("[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f\u00ad\u200b-\u200f\u202a-\u202e"
                        "\u2060-\u2069\ufeff\U000e0000-\U000e007f]")
SALTOS = (r"(la )?cifra verificada\b", r"(los )?limites\b")     # antes de estas secciones empieza hoja
PALABRA = re.compile(r"[^\W_]+")
ETIQUETAS = {"html", "head", "meta", "title", "style", "body", "h1", "h2", "h3", "h4", "h5", "h6", "p", "div", "ul",
             "li", "span", "strong", "em", "code", "pre", "table", "thead", "tbody", "tr", "th", "td", "blockquote",
             "hr", "b"}
ATRIBUTOS = {"class", "lang", "charset", "http-equiv", "content"}
POLITICA = "default-src 'none'; style-src 'unsafe-inline'"

# ---------------- Markdown → HTML, escapando todo ----------------
INLINE = re.compile(
    r"(?P<cod>`{1,3})(?P<codt>[^`\n]{1,2000}?)(?P=cod)"                                   # `código`
    r"|(?P<img>!?)\[(?P<txt>[^\[\]\n]{0,500})\]\((?P<dest>[^()\s]{0,2000})\)"              # [texto](destino)
    r"|(?P<neg>\*\*|__)(?P<negt>[^\s*_](?:[^\n]{0,1000}?[^\s])?)(?P=neg)"                  # **negrita**
    r"|(?<![\w*])\*(?P<cur>[^\s*](?:[^*\n]{0,1000}[^\s*])?)\*(?![\w*])"                   # *cursiva*
    r"|(?<!\w)_(?P<cur2>[^\s_](?:[^_\n]{0,1000}[^\s_])?)_(?!\w)"                          # _cursiva_
    r"|\\(?P<esc>[!-/:-@\[-`{-~])")                                                        # \* y demás escapes
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
TITULO = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.*)$")
RAYA = re.compile(r"^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$")
ITEM = re.compile(r"^([ \t]*)([-*+]|\d{1,9}[.)])[ \t]+(.*)$")
CITA = re.compile(r"^ {0,3}> ?(.*)$")
SEPARADOR = re.compile(r"^\s*\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?\s*$")


def sin_rodeos(dest):
    return re.sub(r"^(?:\.{1,2}/)+", "", dest)


def inline(t, ocultos, prof=0):
    """Texto de una línea → HTML. Escapa todo lo que no es marca de Markdown; los enlaces e imágenes quedan como texto
    con su destino al lado (inerte). `ocultos` recibe lo que no se muestra (el destino igual al texto del enlace)."""
    if prof > 3:
        return escape(t)
    out, pos = [], 0
    for m in INLINE.finditer(t):
        out.append(escape(t[pos:m.start()]))
        pos = m.end()
        if m.group("cod"):
            out.append(f"<code>{escape(m.group('codt'))}</code>")
        elif m.group("dest") is not None:
            txt, dest = m.group("txt"), m.group("dest")
            if m.group("img"):
                out.append(f"{inline(txt, ocultos, prof + 1)} <span class=\"dest\">(imagen no incluida: {escape(dest)})</span>")
            elif dest and sin_rodeos(dest) != txt and not dest.endswith("/" + txt):
                out.append(f"{inline(txt, ocultos, prof + 1)} <span class=\"dest\">({escape(dest)})</span>")
            else:
                out.append(inline(txt, ocultos, prof + 1))
                ocultos.append(dest)
        elif m.group("neg"):
            out.append(f"<strong>{inline(m.group('negt'), ocultos, prof + 1)}</strong>")
        elif m.group("cur") is not None or m.group("cur2") is not None:
            out.append(f"<em>{inline(m.group('cur') or m.group('cur2'), ocultos, prof + 1)}</em>")
        else:
            out.append(escape(m.group("esc")))
    out.append(escape(t[pos:]))
    return "".join(out)


def es_inicio(linea):
    return bool(FENCE.match(linea) or TITULO.match(linea) or RAYA.match(linea) or ITEM.match(linea)
                or CITA.match(linea) or linea.lstrip().startswith("|"))


def celdas(fila):
    f = fila.strip()
    f = f[1:] if f.startswith("|") else f
    f = f[:-1] if f.endswith("|") and not f.endswith("\\|") else f
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", f)]


def lista(items, ocultos):
    pila, filas = [], []
    for sangria, marca, partes in items:
        while pila and sangria < pila[-1]:
            pila.pop()
        if not pila or sangria > pila[-1]:
            pila.append(sangria)
        nivel = min(len(pila) - 1, 3)
        m = "•" if marca in "-*+" else escape(marca)
        filas.append(f"<li class=\"n{nivel}\"><span class=\"m\">{m}</span><span>{inline(' '.join(partes), ocultos)}</span></li>")
    return "<ul class=\"lista\">" + "".join(filas) + "</ul>"


def bloques(md, ocultos, prof=0):
    """Markdown → [{"tipo", "html", "nivel", "titulo"}]. Lo que no reconoce queda como párrafo, con todo su texto."""
    L = md.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out, par, i = [], [], 0

    def cerrar():
        if par:
            out.append({"tipo": "p", "html": "<p>" + inline(" ".join(x.strip() for x in par), ocultos) + "</p>"})
            par.clear()

    while i < len(L):
        linea = L[i]
        if not linea.strip():
            cerrar()
            i += 1
            continue
        m = FENCE.match(linea)
        if m:
            cerrar()
            marca, info, cuerpo = m.group(1), m.group(2).strip(), []
            cierre = re.compile(r"^ {0,3}" + re.escape(marca[0]) + "{" + str(len(marca)) + r",}[ \t]*$")
            i += 1
            while i < len(L) and not cierre.match(L[i]):
                cuerpo.append(L[i])
                i += 1
            i += 1
            out.append({"tipo": "pre", "html": "<pre>" + (f"<span class=\"dest\">{escape(info)}</span>\n" if info else "")
                        + escape("\n".join(cuerpo)) + "</pre>"})
            continue
        m = TITULO.match(linea)
        if m:
            cerrar()
            titulo = m.group(2).rstrip(" \t#")
            out.append({"tipo": "h", "nivel": len(m.group(1)), "titulo": titulo, "html": inline(titulo, ocultos)})
            i += 1
            continue
        if RAYA.match(linea):
            cerrar()
            out.append({"tipo": "hr", "html": "<hr>"})
            i += 1
            continue
        if CITA.match(linea):
            cerrar()
            dentro = []
            while i < len(L) and CITA.match(L[i]):
                dentro.append(CITA.match(L[i]).group(1))
                i += 1
            sub = (bloques("\n".join(dentro), ocultos, prof + 1) if prof < 3
                   else [{"html": "<p>" + escape(" ".join(dentro)) + "</p>"}])
            dentro_html = "\n".join(f"<h{b['nivel']}>{b['html']}</h{b['nivel']}>" if b.get("tipo") == "h" else b["html"] for b in sub)
            out.append({"tipo": "cita", "html": "<blockquote>" + dentro_html + "</blockquote>"})
            continue
        if linea.lstrip().startswith("|") and i + 1 < len(L) and SEPARADOR.match(L[i + 1]) and "-" in L[i + 1]:
            cerrar()
            filas = [celdas(L[i])]
            i += 2
            while i < len(L) and L[i].lstrip().startswith("|"):
                filas.append(celdas(L[i]))
                i += 1
            cab = "".join(f"<th>{inline(c, ocultos)}</th>" for c in filas[0])
            cuerpo = "".join("<tr>" + "".join(f"<td>{inline(c, ocultos)}</td>" for c in f) + "</tr>" for f in filas[1:])
            out.append({"tipo": "tabla", "html": f"<table><thead><tr>{cab}</tr></thead><tbody>{cuerpo}</tbody></table>"})
            continue
        if ITEM.match(linea):
            cerrar()
            items = []
            while i < len(L):
                linea = L[i]
                m = ITEM.match(linea)
                if m and not RAYA.match(linea):
                    items.append((len(m.group(1).expandtabs(4)), m.group(2), [m.group(3)]))
                    i += 1
                    continue
                if not linea.strip():
                    # una línea en blanco: la lista sigue si viene otro ítem o un párrafo con sangría
                    j = i + 1
                    while j < len(L) and not L[j].strip():
                        j += 1
                    if j < len(L) and ((ITEM.match(L[j]) and not RAYA.match(L[j]))
                                       or (L[j][:2] == "  " and not es_inicio(L[j]))):
                        i = j
                        continue
                    break
                if es_inicio(linea):
                    break
                items[-1][2].append(linea.strip())          # el ítem sigue en la línea de abajo
                i += 1
            out.append({"tipo": "lista", "html": lista(items, ocultos)})
            continue
        par.append(linea)
        i += 1
    cerrar()
    return out


# ---------------- comprobaciones sin IA ----------------
class _Lector(HTMLParser):
    """El texto que se ve (sin <title> ni <style>) y las etiquetas con sus atributos."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes, self.etiquetas, self.dentro = [], [], 0

    def handle_starttag(self, tag, attrs):
        self.etiquetas.append((tag, [a for a, _ in attrs]))
        self.dentro += tag in ("title", "style")

    def handle_startendtag(self, tag, attrs):
        self.etiquetas.append((tag, [a for a, _ in attrs]))

    def handle_endtag(self, tag):
        self.dentro -= tag in ("title", "style") and self.dentro > 0

    def handle_data(self, data):
        if not self.dentro:
            self.partes.append(data)


def leer_html(doc):
    lector = _Lector()
    lector.feed(doc)
    lector.close()
    return " ".join(lector.partes), lector.etiquetas


def fragmento(blq):
    """El HTML de los bloques, uno por línea (dos títulos seguidos no se pegan en una sola palabra)."""
    return "\n".join(b["html"] for b in blq)


def fidelidad(md, fragmento, ocultos):
    """Las palabras y cifras del texto validado que NO están en el HTML (lista vacía = no falta ninguna)."""
    faltan = (Counter(PALABRA.findall(md)) - Counter(PALABRA.findall(leer_html(fragmento)[0]))
              - Counter(PALABRA.findall(" ".join(ocultos))))
    return sorted(faltan.elements())


def revisar_html(doc):
    """Lo que el HTML trae y el armador no pone: etiquetas, atributos o más de una hoja de estilo."""
    _, etiquetas = leer_html(doc)
    raras = sorted({t for t, _ in etiquetas if t not in ETIQUETAS})
    attrs = sorted({a for _, aa in etiquetas for a in aa if a not in ATRIBUTOS})
    problemas = ([f"etiquetas que el armador no pone: {', '.join(raras)}"] if raras else []) + \
                ([f"atributos que el armador no pone: {', '.join(attrs)}"] if attrs else [])
    if sum(1 for t, _ in etiquetas if t == "style") != 1:
        problemas.append("más de una hoja de estilo")
    if f'content="{POLITICA}"' not in doc:
        problemas.append("falta la política de contenido que no carga nada")
    return problemas


def normalizar(t):
    t = "".join(ch for ch in unicodedata.normalize("NFD", str(t).lower()) if unicodedata.category(ch) != "Mn")
    t = re.sub(r"^\s*\d{1,2}\s*[.)·:-]?\s*", "", t)
    t = re.sub(r"[*_`:¿?¡!]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def leer(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def preparar(c):
    """(motivos, datos). Sin motivos, el texto se puede maquetar."""
    md_p, v_p = c / "whitepaper.md", c / "whitepaper_verificacion.json"
    if not c.is_dir():
        return [f"no existe la carpeta de la corrida: {c}"], None
    for p in (md_p, v_p):
        if p.is_symlink():
            return [f"{p.name} es un enlace simbólico: no se sigue"], None
    if not md_p.is_file():
        return ["falta whitepaper.md: el documentador no lo escribió"], None
    if not v_p.is_file():
        return ["falta whitepaper_verificacion.json: primero corre validar_whitepaper.py"], None
    crudo = md_p.read_bytes()
    if len(crudo) > MAX_BYTES:
        return [f"whitepaper.md pesa {len(crudo)} bytes: no es prosa breve (máximo {MAX_BYTES})"], None
    wpv = leer(v_p)
    if not isinstance(wpv, dict):
        return ["whitepaper_verificacion.json no se puede leer"], None
    motivos = []
    if wpv.get("estado") != "aprobado":
        motivos.append(f"la verificación dice «{wpv.get('estado')}», no «aprobado»")
    chequeos = wpv.get("chequeos")
    if not isinstance(chequeos, list) or not chequeos or not all(isinstance(x, dict) and x.get("ok") is True for x in chequeos):
        motivos.append("la verificación no trae sus chequeos o alguno no pasó")
    huella = hashlib.sha256(crudo).hexdigest()
    if wpv.get("sha256") != huella:
        motivos.append(f"whitepaper.md cambió después de validarse (huella validada {str(wpv.get('sha256'))[:12]}…, "
                       f"la de hoy {huella[:12]}…)")
    try:
        texto = crudo.decode("utf-8")
    except UnicodeDecodeError:
        return motivos + ["whitepaper.md no es UTF-8"], None
    if INVISIBLES.search(texto):
        motivos.append("trae caracteres invisibles o bidireccionales: W5 no los deja pasar, la verificación no es de este texto")
    if letras_disfrazadas(texto):
        motivos.append("trae palabras con letras de otro alfabeto que se leen como latinas: W5 no las deja pasar, la "
                       "verificación no es de este texto")
    if any(len(x) > LINEA_MAX for x in texto.splitlines()):
        motivos.append(f"trae líneas de más de {LINEA_MAX} caracteres: no es prosa")
    return motivos, {"texto": texto, "huella": huella, "wpv": wpv}


# ---------------- el documento ----------------
def sello(c, d):
    wpv = d["wpv"]
    ids = [str(x.get("chequeo", "")).split(" ")[0] for x in wpv.get("chequeos", [])]
    cifras = [x for x in (wpv.get("cifras") or []) if isinstance(x, dict)]
    resp = sum(1 for x in cifras if x.get("respaldada"))
    return (f"<p class=\"sub\">Resumen para el análisis de las personas · corrida {escape(c.name)}</p>"
            f"<div class=\"sello\"><b>Texto validado, sin cambios.</b> Lo escribió la IA (el documentador) y lo comprobó sin IA "
            f"validar_whitepaper.py: {len(ids)} de {len(ids)} chequeos ({escape(', '.join(ids))})"
            + (f", {resp:d} de {len(cifras)} cifras en los artefactos verificados" if cifras else "")
            + ". Esta hoja solo lo maqueta: no agrega ni quita palabras ni cifras. El análisis lo hacen las personas.</div>")


def documento(blq, titulo, cabecera, pie, base, saltos):
    cuerpo, puesto = [], False
    for b in blq:
        if b["tipo"] == "h":
            n = b["nivel"]
            clase = (" class=\"salto\"" if saltos and n == 2 and any(re.match(p, normalizar(b["titulo"])) for p in SALTOS) else "")
            cuerpo.append(f"<h{n}{clase}>{b['html']}</h{n}>")
            if n == 1 and not puesto:
                cuerpo.append(cabecera)
                puesto = True
        else:
            cuerpo.append(b["html"])
    if not puesto:
        cuerpo.insert(0, f"<h1>{escape(titulo)}</h1>{cabecera}")
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{POLITICA}">
<title>{escape(titulo)}</title><style>
@page {{ size: letter; margin: 0.55in 0.6in; }}
* {{ box-sizing: border-box; }}
body {{ font-family: "Source Sans 3", "Segoe UI", Arial, sans-serif; font-size: {base:g}pt; line-height: 1.32; color: #1a1f27; margin: 0; }}
h1 {{ font-size: {base * 1.7:.1f}pt; margin: 0 0 2pt; color: #0b3d91; line-height: 1.15; }}
h2 {{ font-size: {base * 1.3:.1f}pt; margin: 9pt 0 3pt; color: #0b3d91; border-bottom: 1.5pt solid #b47b18; padding-bottom: 2pt; break-after: avoid; }}
h3, h4, h5, h6 {{ font-size: {base * 1.1:.1f}pt; margin: 6pt 0 2pt; color: #071f4a; break-after: avoid; }}
p {{ margin: 0 0 4pt; orphans: 2; widows: 2; }}
.sub {{ color: #4a5568; margin: 0 0 4pt; }}
.sello {{ border-left: 3pt solid #b47b18; background: #fcf6e8; padding: 4pt 8pt; margin: 4pt 0 8pt; font-size: {base * 0.92:.1f}pt; }}
.lista {{ list-style: none; margin: 1pt 0 4pt; padding: 0; }}
.lista li {{ display: flex; gap: 4pt; margin: 0 0 1.5pt; break-inside: avoid; }}
.lista .n1 {{ margin-left: 12pt; }} .lista .n2 {{ margin-left: 24pt; }} .lista .n3 {{ margin-left: 36pt; }}
.lista .m {{ flex: none; min-width: 8pt; color: #0b3d91; }}
table {{ width: 100%; border-collapse: collapse; font-size: {base * 0.92:.1f}pt; margin: 2pt 0 5pt; }}
th, td {{ border-bottom: 0.6pt solid #cbd5e1; padding: 2pt 4pt; text-align: left; vertical-align: top; }}
th {{ background: #edf3fc; }}
code, pre {{ font-family: Menlo, Consolas, monospace; font-size: {base * 0.86:.1f}pt; }}
code {{ background: #f1f4f8; padding: 0 1pt; border-radius: 2pt; }}
pre {{ background: #f1f4f8; padding: 4pt 6pt; white-space: pre-wrap; overflow-wrap: anywhere; }}
blockquote {{ margin: 3pt 0; padding: 0 8pt; border-left: 2pt solid #cbd5e1; }}
.dest {{ color: #5b6573; font-size: {base * 0.85:.1f}pt; overflow-wrap: anywhere; }}
hr {{ border: 0; border-top: 0.6pt solid #cbd5e1; }}
.salto {{ break-before: page; }} .pie {{ color: #4a5568; font-size: {base * 0.8:.1f}pt; margin-top: 8pt; }}
</style></head><body>
{''.join(cuerpo)}
{pie}
</body></html>"""


def borrar_salidas(*rutas):
    borradas = []
    for p in rutas:
        if p.is_symlink() or p.exists():
            p.unlink()                      # un enlace simbólico se quita, nunca se sigue
            borradas.append(p.name)
    return borradas


def rechazar(c, motivos):
    borradas = borrar_salidas(c / "WHITEPAPER.html", c / "WHITEPAPER.pdf")
    for x in motivos:
        print(f"  ✗ {x}")
    print("No se armó el whitepaper en carta: solo se maqueta un whitepaper.md aprobado por validar_whitepaper.py y sin "
          "cambios desde entonces." + (f" Se borró lo anterior ({', '.join(borradas)}): era de otro texto." if borradas else ""))
    print("RESUMEN " + json.dumps({"estado": "rechazado", "motivos": motivos, "borrados": borradas}, ensure_ascii=False))
    return 1


def armar_corrida(c, imprimir=True):
    c = Path(c).resolve()
    h, pdf = c / "WHITEPAPER.html", c / "WHITEPAPER.pdf"
    motivos, d = preparar(c)
    if motivos or d is None:
        return rechazar(c, motivos)
    ocultos = []
    blq = bloques(d["texto"], ocultos)
    titulo = next((b["titulo"] for b in blq if b["tipo"] == "h" and b["nivel"] == 1), f"Whitepaper de la corrida {c.name}")
    pie = (f"<p class=\"pie\">Maquetado sin IA por herramientas/whitepaper_corrida.py a partir de whitepaper.md, validado por "
           f"validar_whitepaper.py · huella SHA-256 del texto validado: {escape(d['huella'])} · agente-solicitudes (curso «Big Data "
           f"con IA», NODO · EAFIT).</p>")
    cabecera = sello(c, d)
    faltan = fidelidad(d["texto"], fragmento(blq), ocultos)
    if faltan:
        motivos.append(f"al pasar a HTML faltarían {len(faltan)} palabra(s) o cifra(s) del texto validado: {', '.join(faltan[:8])}")
    doc = documento(blq, titulo, cabecera, pie, carta.PASOS_LETRA[0], True)
    motivos += revisar_html(doc)
    visible = leer_html(doc)[0]
    personales = escanear_texto(visible)
    if personales:
        motivos.append(f"el barrido de gobernanza.py encuentra posibles datos personales: {personales}")
    if parece_instruccion(visible):
        motivos.append("el barrido de gobernanza.py encuentra texto con forma de instrucción para agentes")
    analisis = buscar_d15(visible)
    if analisis:   # lo que se imprime, sin las marcas de Markdown: «Esto *demuestra* que» se lee «Esto demuestra que» (L117)
        motivos.append("el texto que se imprime trae frases de conclusión, recomendación, causa o juicio (D15): "
                       + ", ".join(f"«{x[:40]}»" for x in analisis[:4]))
    if motivos:
        return rechazar(c, motivos)
    borrar_salidas(h, pdf)                  # si eran enlaces simbólicos, se escribe un archivo nuevo, nunca a través de ellos
    con_saltos = sum(1 for b in blq if b["tipo"] == "h" and b["nivel"] == 2
                     and any(re.match(p, normalizar(b["titulo"])) for p in SALTOS)) > 0
    if not imprimir:
        h.write_text(doc, encoding="utf-8")
        print("Sin imprimir (autoprueba): quedó WHITEPAPER.html")
        print("RESUMEN " + json.dumps({"estado": "sin_imprimir", "html": str(h), "pdf": None}))
        return 0
    variantes = (True, False) if con_saltos else (False,)       # primero una parte por hoja; si no, el texto seguido
    pasos = [[(base, s) for s in variantes] for base in carta.PASOS_LETRA]
    r = carta.ajustar(pasos, lambda v: documento(blq, titulo, cabecera, pie, v[0], v[1]), h, pdf)
    if r["estado"] == "sin_chrome":
        print("Sin Chrome (o Chrome no imprimió): quedó WHITEPAPER.html; imprímelo en tamaño carta.")
        print("RESUMEN " + json.dumps({"estado": "sin_chrome", "html": str(h), "pdf": None}))
        return 0
    base, saltos = r["variante"]
    if r["estado"] == "largo":              # el texto completo y seguido: la letra más grande con la que cabe, o la mínima
        saltos = False
        for base in carta.PASOS_LETRA:
            h.write_text(documento(blq, titulo, cabecera, pie, base, saltos), encoding="utf-8")
            if not carta.imprimir(h, pdf):
                print("Chrome no imprimió la versión completa: quedó WHITEPAPER.html.")
                print("RESUMEN " + json.dumps({"estado": "sin_chrome", "html": str(h), "pdf": None}))
                return 1
            if carta.paginas(pdf) <= carta.HOJAS:
                break
    n, tam, enl = carta.paginas(pdf), carta.tamano(pdf), carta.enlaces(pdf)
    problemas = ([] if tam == carta.CARTA_PT else [f"el PDF no salió en carta: {tam} pt"]) + \
                ([f"el PDF trae enlaces: {', '.join(enl)[:200]}"] if enl else [])
    if problemas:
        pdf.unlink()
        for x in problemas:
            print(f"  ✗ {x}")
        print("Se borró WHITEPAPER.pdf; quedó WHITEPAPER.html.")
        print("RESUMEN " + json.dumps({"estado": "pdf_rechazado", "problemas": problemas, "html": str(h), "pdf": None}, ensure_ascii=False))
        return 1
    forma = "una parte del whitepaper en cada hoja" if saltos else "texto seguido"
    if n == carta.HOJAS:
        print(f"WHITEPAPER.pdf: 3 hojas carta (612 × 792 pt) · letra base {base} pt · {forma} · texto validado sin cambios "
              f"(huella {d['huella'][:12]}…)")
    elif n < carta.HOJAS:
        print(f"WHITEPAPER.pdf: {n} hojas carta (el texto no alcanza para tres) · letra base {base} pt · sin cambios")
    else:
        print(f"WHITEPAPER.pdf: {n} hojas carta. El texto validado no cabe en tres ni con letra de {str(carta.LETRA_MINIMA).replace('.', ',')} pt, "
              "y no se recorta: el documento sale completo y el whitepaper debe acortarse.")
    print("RESUMEN " + json.dumps({"estado": "armado", "paginas": n, "tres_hojas": n == carta.HOJAS, "letra_pt": base,
                                   "saltos": saltos, "tamano_pt": list(tam), "sha256": d["huella"], "html": str(h),
                                   "pdf": str(pdf)}, ensure_ascii=False))
    return 0 if n <= carta.HOJAS else 1


# ---------------- autoprueba ----------------
BUENO = """# Whitepaper · Ventas ficticias del semestre

Resumen para las personas del curso, con la [plantilla del análisis](../../plantillas/analisis_humano.md).

## Pregunta

Ventas netas por región en el semestre, según _ventas_ficticias.csv_.

## Datos y procedencia

- Fuente: ventas ficticias, con licencia CC BY-SA 4.0.
- Consulta: 06-11-2026 05:29. Se cargaron 1.520 filas.
  - Minimización: entraron 6 columnas (`id_factura`, `region`, `valor`).

## Limpieza

1. Marcas que avisan: 12 anuladas.
1. Atípicos: 18.
7. Sin filas repetidas.

| Marca | Filas |
|---|---|
| anulada | 12 |
| atípico \\| revisado | 18 |

## Cifra verificada y cómo se verificó

**2.500.000 pesos** (unos 2,5 millones) en 3 regiones; la tabla está en el [informe final](informe_final.html).

## Gráfico

[grafico.html](grafico.html): barras desde cero.

## Gobernanza

Sin datos personales (Ley 1581 de 2012).

> El k-anonimato no aplica: solo hay agregados.

## Límites

Queda 1 pregunta abierta (P1).

```
consulta de ejemplo: SELECT region, SUM(valor)
```

## Preguntas para el análisis de las personas

- **Costo.** ¿Qué parte de las ventas se va en devoluciones?
- **Calidad.** ¿Qué tienen en común las 18 facturas atípicas?
- **Impacto.** ¿A qué municipios llegan las ventas de cada región?
"""
ABRE_COMENTARIO = "<" + "!--"   # armado aquí: este archivo no trae un comentario HTML literal (el filtro de aportes los lee)


def _con(texto, viejo, nuevo):
    if viejo not in texto:
        raise SystemExit(f"autoprueba mal armada: no está {viejo!r}")
    return texto.replace(viejo, nuevo, 1)


def _corrida(base, nombre, texto, estado="aprobado", huella=None, chequeos=None, verificacion=True):
    c = (base / nombre).resolve()
    if not c.is_relative_to(base.resolve()):
        raise SystemExit(f"autoprueba mal armada: {nombre} queda fuera de la carpeta temporal")
    c.mkdir(parents=True)
    crudo = texto.encode("utf-8")
    (c / "whitepaper.md").write_bytes(crudo)
    if verificacion:
        ver = {"whitepaper": "whitepaper.md", "sha256": huella or hashlib.sha256(crudo).hexdigest(), "estado": estado,
               "chequeos": chequeos if chequeos is not None else [{"chequeo": f"W{i} x", "ok": True, "detalle": ""} for i in range(1, 6)],
               "cifras": [{"cifra": "1.520", "respaldada": True}]}
        (c / "whitepaper_verificacion.json").write_text(json.dumps(ver, ensure_ascii=False), encoding="utf-8")
    return c


def _correr(c):
    salida = io.StringIO()
    with contextlib.redirect_stdout(salida):
        rc = armar_corrida(c, imprimir=False)
    h = c / "WHITEPAPER.html"
    return rc, salida.getvalue(), (h.read_text(encoding="utf-8") if h.is_file() and not h.is_symlink() else "")


def autoprueba():
    """Casos buenos y malos, sin Chrome (no imprime): la puerta de la validación, el escape y el armador común."""
    tmp = Path(tempfile.mkdtemp(prefix="whitepaper-corrida-"))
    resultados = []

    def caso(nombre, ok, detalle=""):
        resultados.append((nombre, bool(ok), detalle))

    try:
        # control positivo: el whitepaper bueno, aprobado y con su huella, se maqueta completo
        c = _corrida(tmp, "bueno", BUENO)
        rc, out, doc = _correr(c)
        visible = leer_html(doc)[0]
        caso("control positivo: aprobado y con su huella, se maqueta", rc == 0 and doc and not revisar_html(doc)
             and "2.500.000 pesos" in visible and "Texto validado, sin cambios." in visible, out[-300:])
        ocultos = []
        frag = fragmento(bloques(BUENO, ocultos))
        caso("control positivo: cada palabra y cifra del texto está en el HTML",
             ocultos == ["grafico.html"] and not fidelidad(BUENO, frag, ocultos) and all(t in visible for t in ("1.520", "2,5", "1581", "P1", "06-11-2026 05:29")))
        caso("control positivo: los números de la lista son los del texto (1, 1, 7), sin renumerar",
             re.search(r'class="m">1\.</span>.*class="m">1\.</span>.*class="m">7\.</span>', doc) is not None)
        caso("control positivo: los enlaces quedan como texto con su destino, sin <a>",
             "<a" not in doc and "(../../plantillas/analisis_humano.md)" in visible and "(informe_final.html)" in visible
             and "grafico.html (grafico.html)" not in visible)
        caso("control positivo: hoja 2 desde «Cifra verificada» y hoja 3 desde «Límites» (variante con saltos)",
             len(re.findall(r'<h2 class="salto">', documento(bloques(BUENO, []), "t", "", "", 10.0, True))) == 2
             and 'class="salto"' not in documento(bloques(BUENO, []), "t", "", "", 10.0, False))

        # la puerta: falla cerrado y borra lo anterior
        c = _corrida(tmp, "huella", BUENO, huella="0" * 64)
        (c / "WHITEPAPER.pdf").write_bytes(b"%PDF viejo")
        (c / "WHITEPAPER.html").write_text("viejo", encoding="utf-8")
        rc, out, _ = _correr(c)
        caso("huella distinta (el texto cambió después de validarse): no arma y borra el PDF y el HTML viejos",
             rc == 1 and "cambió después de validarse" in out and not (c / "WHITEPAPER.pdf").exists()
             and not (c / "WHITEPAPER.html").exists(), out[-300:])
        rc, out, _ = _correr(_corrida(tmp, "revisar", BUENO, estado="revisar"))
        caso("estado «revisar»: no arma", rc == 1 and "no «aprobado»" in out, out[-200:])
        rc, out, _ = _correr(_corrida(tmp, "sin-verificacion", BUENO, verificacion=False))
        caso("falta la verificación: no arma", rc == 1 and "falta whitepaper_verificacion.json" in out, out[-200:])
        c = _corrida(tmp, "sin-whitepaper", BUENO)
        (c / "whitepaper.md").unlink()
        rc, out, _ = _correr(c)
        caso("falta whitepaper.md: no arma", rc == 1 and "falta whitepaper.md" in out, out[-200:])
        rc, out, _ = _correr(_corrida(tmp, "chequeo-falso", BUENO, chequeos=[{"chequeo": "W2 x", "ok": False}]))
        caso("«aprobado» con un chequeo que no pasó: no arma", rc == 1 and "alguno no pasó" in out, out[-200:])
        (tmp / "otra.json").write_text("{}", encoding="utf-8")
        c = _corrida(tmp, "verificacion-enlace", BUENO, verificacion=False)
        (c / "whitepaper_verificacion.json").symlink_to(tmp / "otra.json")
        rc, out, _ = _correr(c)
        caso("la verificación es un enlace simbólico: no se sigue", rc == 1 and "enlace simbólico" in out, out[-200:])
        rc, out, _ = _correr(_corrida(tmp, "invisible", _con(BUENO, "Sin datos personales", "Sin datos\u202e personales")))
        caso("carácter bidireccional (con una verificación que dice aprobado): no arma", rc == 1 and "invisibles" in out, out[-200:])
        correo = "ana.perez" + "@" + "ejemplo.invalid"
        rc, out, _ = _correr(_corrida(tmp, "personal", _con(BUENO, "Sin datos personales", f"Dudas a {correo}")))
        caso("dato personal (con una verificación que dice aprobado): el barrido no deja armar", rc == 1 and "datos personales" in out, out[-200:])
        rc, out, _ = _correr(_corrida(tmp, "enfasis", _con(BUENO, "Sin datos personales", "Esto *demuestra* que no hay datos personales")))
        caso("frase D15 con énfasis de Markdown (con una verificación vieja que dice aprobado): no arma",
             rc == 1 and "(D15)" in out and "«demuestra que»" in out, out[-200:])
        rc, out, _ = _correr(_corrida(tmp, "disfrazada", _con(BUENO, "Sin datos personales", "Sin datos pers\u043enales")))
        caso("letra de otro alfabeto disfrazada de latina (con una verificación que dice aprobado): no arma",
             rc == 1 and "otro alfabeto" in out, out[-200:])

        # el escape: el texto lo escribió una IA; aunque la verificación diga aprobado, nada se interpreta
        ataque = ("<script>alert(1)</script> <img src=x onerror=alert(2)> <iframe src=\"https://ejemplo.invalid\"></iframe> "
                  f"{ABRE_COMENTARIO} oculto --> <style>body{{display:none}}</style> <b onclick=\"x()\">negrita</b> &amp; listo")
        c = _corrida(tmp, "html", _con(_con(BUENO, "Queda 1 pregunta abierta (P1).", "Queda 1 pregunta abierta (P1). " + ataque),
            "barras desde cero.", "barras desde cero.\n\n<div onmouseover=\"y()\">bloque</div>"))
        rc, out, doc = _correr(c)
        visible = leer_html(doc)[0]
        caso("HTML y script en el markdown: salen escapados, como texto", rc == 0 and not revisar_html(doc)
             and "<script" not in doc and "&lt;script&gt;alert(1)&lt;/script&gt;" in doc and "onerror=alert(2)>" not in doc
             and "<script>alert(1)</script>" in visible and "&amp; listo" in visible, (out + " | " + "; ".join(revisar_html(doc)))[-300:])
        ext = ("Fuente: [portal](https://ejemplo.invalid/datos), logo ![logo](https://ejemplo.invalid/p.png), "
               "[clic](javascript:alert(3)) y <https://ejemplo.invalid/auto>.")
        rc, out, doc = _correr(_corrida(tmp, "externo", _con(BUENO, "Queda 1 pregunta abierta (P1).", ext)))
        visible = leer_html(doc)[0]
        caso("enlace externo, imagen remota y javascript: quedan como texto inerte (sin href ni src)",
             rc == 0 and not revisar_html(doc) and "href" not in doc and "src=" not in doc
             and "(https://ejemplo.invalid/datos)" in visible and "imagen no incluida" in visible, out[-300:])
        destino = tmp / "canario.txt"
        destino.write_text("intacto", encoding="utf-8")
        c = _corrida(tmp, "salida-enlace", BUENO)
        (c / "WHITEPAPER.html").symlink_to(destino)
        rc, out, doc = _correr(c)
        caso("WHITEPAPER.html previo como enlace simbólico: se quita el enlace y no se escribe a través de él",
             rc == 0 and destino.read_text(encoding="utf-8") == "intacto" and not (c / "WHITEPAPER.html").is_symlink(), out[-200:])

        # el comprobador de fidelidad no es de adorno: atrapa una palabra o una cifra que falte
        caso("fidelidad: atrapa una cifra que falta (control negativo)", fidelidad(BUENO, frag.replace("1.520", "1."), ocultos) == ["520"])
        caso("fidelidad: atrapa una palabra que falta (control negativo)",
             fidelidad(BUENO, frag.replace("municipios", ""), ocultos) == ["municipios"])
        seguidos = "## Uno\n### Dos\n#### Tres\n- cuatro\n> cinco\n> ## diez\n\n| seis |\n|---|\n| siete |\n```\nocho\n```\nnueve"
        oc = []
        caso("fidelidad: títulos y bloques seguidos no se pegan (sin falsas alarmas)",
             not fidelidad(seguidos, fragmento(bloques(seguidos, oc)), oc) and "<h2>diez</h2>" in fragmento(bloques(seguidos, [])))

        # textos hechos para trabar las expresiones regulares: el armado termina rápido
        hostiles = {"asteriscos": "**a" * 1300, "corchetes": "[" * 3900, "comillas invertidas": "`" * 3900,
                    "guiones bajos": "_a" * 1900, "imágenes": "![" * 1900, "escapes": "\\" * 3900,
                    "enlaces sin cerrar": "[a](" * 900, "listas": "- " * 1900}
        lentos = []
        for nombre, relleno in hostiles.items():
            t0 = time.perf_counter()
            oc = []
            fr = fragmento(bloques(BUENO + "\n" + relleno + "\n", oc))
            falta = fidelidad(BUENO + "\n" + relleno + "\n", fr, oc)
            seg = time.perf_counter() - t0
            if seg > 5 or falta:
                lentos.append(f"{nombre} ({seg:.1f} s, faltan {len(falta)})")
        caso(f"textos hostiles: los {len(hostiles)} se arman en menos de 5 s y sin perder texto", not lentos, ", ".join(lentos))

        # el armador común (carta.py) sin Chrome: imprimir y contar páginas se simulan
        viejo = carta.imprimir, carta.paginas
        try:
            def con_paginas(tabla, hay_chrome=True):
                carta.imprimir = lambda h, p: hay_chrome
                actual = {}
                carta.paginas = lambda p: actual["n"]

                def escribir(v):
                    actual["n"] = tabla.get(v, 4)
                    return "x"
                return carta.ajustar([[(b, s) for s in (False, True)] for b in carta.PASOS_LETRA], escribir,
                                     tmp / "a.html", tmp / "a.pdf")
            r = con_paginas({(10.0, False): 2, (10.0, True): 3})
            caso("armador: la primera variante queda corta → la segunda da 3 (exacto)", r["estado"] == "exacto" and r["variante"] == (10.0, True))
            r = con_paginas({(10.0, False): 4, (10.0, True): 5, (9.5, False): 3})
            caso("armador: largo con 10 pt → baja a 9,5 pt (exacto)", r["estado"] == "exacto" and r["variante"] == (9.5, False))
            r = con_paginas({(10.0, False): 2, (10.0, True): 2})
            caso("armador: todas las variantes cortas → para (corto), no baja la letra", r["estado"] == "corto" and r["variante"] == (10.0, True))
            r = con_paginas({(10.0, False): 2, (10.0, True): 4, (9.5, True): 3})
            caso("armador: una corta y otra larga → baja la letra (no es «corto»)", r["estado"] == "exacto" and r["variante"] == (9.5, True))
            r = con_paginas({})
            caso("armador: no cabe ni con 8,5 pt → largo (quien llama decide; nunca baja de 8,5)",
                 r["estado"] == "largo" and r["variante"] == (carta.LETRA_MINIMA, True) and min(carta.PASOS_LETRA) >= carta.LETRA_MINIMA)
            r = con_paginas({}, hay_chrome=False)
            caso("armador: sin Chrome → lo dice (sin_chrome)", r["estado"] == "sin_chrome")
        finally:
            carta.imprimir, carta.paginas = viejo

        # el informe final mide el PDF y no le cree a quien lo armó: «en tres hojas carta» solo si lo es (L113).
        # Las hojas, el tamaño y los enlaces se simulan; el PDF es del texto validado (su HTML lleva la huella).
        import informe_final
        c = _corrida(tmp, "impresa", BUENO)
        _correr(c)
        (c / "WHITEPAPER.pdf").write_bytes(b"%PDF simulado")
        wpv = json.loads((c / "whitepaper_verificacion.json").read_text(encoding="utf-8"))
        viejo = carta.paginas, carta.tamano, carta.enlaces
        try:
            def impresa(n, tam=carta.CARTA_PT, enl=(), corrida=c):
                carta.paginas, carta.tamano, carta.enlaces = (lambda p: n), (lambda p: tam), (lambda p: list(enl))
                return informe_final.version_impresa(corrida, wpv)
            linea, problema = impresa(3)
            caso("informe final (control positivo): tres hojas carta sin enlaces → se enlaza como «tres hojas carta»",
                 problema is None and linea and "En tres hojas carta" in linea and "(WHITEPAPER.pdf)" in linea, str(linea))
            linea, problema = impresa(4)
            caso("informe final: un PDF de 4 hojas no se enlaza como «tres hojas carta»: es un problema, y el análisis no se aprueba",
                 problema and "4 hojas" in problema and "acortar" in problema and "(WHITEPAPER.pdf)" not in linea, str(linea))
            linea, problema = impresa(2)
            caso("informe final: un PDF de 2 hojas se enlaza diciendo que tiene dos (no «tres»)",
                 problema is None and "En dos hojas carta" in linea and "tres hojas carta" not in linea, str(linea))
            linea, problema = impresa(3, tam=(595, 842))
            caso("informe final: tres hojas A4 no son carta: no se enlaza", problema and "no es tamaño carta" in problema, str(linea))
            linea, problema = impresa(3, enl=["file:///ruta/local/whitepaper.md"])
            caso("informe final: un PDF con enlaces no se enlaza", problema and "enlaces" in problema, str(linea))
            linea, problema = impresa(0, tam=None)
            caso("informe final: un PDF que no deja contar sus hojas no se enlaza", problema and "contar sus hojas" in problema, str(linea))
            otro = _corrida(tmp, "impresa-otra", BUENO)
            (otro / "WHITEPAPER.html").write_text("de otro texto", encoding="utf-8")
            (otro / "WHITEPAPER.pdf").write_bytes(b"%PDF simulado")
            caso("informe final: el PDF de otro texto (sin la huella en su HTML) no se enlaza ni se mide",
                 impresa(4, corrida=otro) == (None, None))
            (c / "WHITEPAPER.pdf").unlink()
            (c / "WHITEPAPER.pdf").symlink_to(tmp / "otra.json")
            caso("informe final: un WHITEPAPER.pdf que es un enlace simbólico no se sigue", impresa(3) == (None, None))
        finally:
            carta.paginas, carta.tamano, carta.enlaces = viejo
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    errores = 0
    for nombre, ok, detalle in resultados:
        errores += not ok
        print(f"  {'✓' if ok else '✗'} {nombre}" + ("" if ok or not detalle else f" · {detalle}"))
    print("RESUMEN " + json.dumps({"autoprueba": len(resultados), "errores": errores}))
    return 1 if errores else 0


def main(argv):
    if argv[:1] == ["--autoprueba"]:
        return autoprueba()
    if not argv or argv[0].startswith("--"):
        raise SystemExit(__doc__)
    return armar_corrida(Path(argv[0]))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
