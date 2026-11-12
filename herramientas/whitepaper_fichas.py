#!/usr/bin/env python3
"""Whitepaper de tres hojas tamaño carta con el resumen para que el ESTUDIANTE haga el análisis (sin IA).

Uso: python herramientas/whitepaper_fichas.py <carpeta de trabajo del agente masivo> [--titulo "…"]

El resumen lo puede escribir la IA (<trabajo>/RESUMEN_IA.md); el análisis lo hace el estudiante con su propio conocimiento.
El resumen de la IA entra solo si pasa una comprobación sin IA: sin conclusiones, recomendaciones ni causas (la lista D15 de
validar_whitepaper.py, la misma del whitepaper del pipeline, la presentación, el gráfico y las fichas; su autoprueba está en
la de validar_ficha.py), sin cifras fuera de las medidas (años y normas se permiten), sin datos personales ni
instrucciones, y corto (hasta 230 palabras). Si no pasa, el documento sale igual y
dice por qué quedó fuera. Lo demás se arma solo con lo que ya está escrito y validado:
  - las fichas (<trabajo>/fichas/<id>.json), que escribió la IA y comprobó validar_ficha.py;
  - el tamaño medido (<id>.dictamen.json);
  - el resultado de la validación (<id>.log): chequeos, fallas y cruces medidos.
Hoja 1: panorama (qué datos, el método, la tabla de conjuntos y cómo leerlo). Hojas 2 y 3: una ficha por conjunto (lo que
se puede afirmar, las preguntas para el análisis del estudiante, los cruces medidos, la gobernanza y el procesamiento) y una
guía corta para su análisis. Se imprime a PDF tamaño carta con Chrome y se CUENTAN las páginas (el armador común,
carta.py, el mismo de whitepaper_corrida.py): si pasa de tres, se ajustan la letra (nunca por debajo de 8,5 pt) y lo que
se muestra; si aun así no cabe, salen las últimas fichas y el documento las nombra. Escribe WHITEPAPER.html y
WHITEPAPER.pdf en la carpeta.
"""
import html
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import carta  # noqa: E402
from gobernanza import PATRONES, forma_canonica, parece_instruccion  # noqa: E402
from validar_ficha import PERMITIDOS_NUM  # noqa: E402
from validar_whitepaper import buscar_d15  # noqa: E402  D15: la lista única

E = html.escape


def cargar(trabajo):
    fichas = []
    for f in sorted((trabajo / "fichas").glob("*.json")):
        if f.name.endswith((".dictamen.json", ".verificacion.json")):
            continue
        ficha = json.loads(f.read_text(encoding="utf-8"))
        d = f.with_name(f"{ficha.get('id')}.dictamen.json")
        dic = json.loads(d.read_text(encoding="utf-8")) if d.exists() else {}
        log = f.with_suffix(".log")
        texto = log.read_text(encoding="utf-8") if log.exists() else ""
        fallas = [l.strip()[2:] for l in texto.splitlines() if l.strip().startswith("✗")]
        cruces = [re.sub(r"^\s*[✓✗]\s*", "", l) for l in texto.splitlines() if "V5 cruce" in l]
        m = re.search(r'"chequeos":\s*(\d+),\s*"fallas":\s*(\d+)', texto)
        fichas.append({"f": ficha, "dic": dic, "fallas": fallas, "cruces": cruces,
                       "chequeos": int(m.group(1)) if m else None, "n_fallas": int(m.group(2)) if m else None})
    return fichas


def comprobar_resumen(texto, fichas):
    """Sin IA: el resumen describe lo desarrollado; no concluye, no inventa cifras, no trae datos personales ni órdenes."""
    medidas = set()
    for x in fichas:
        med = x["dic"].get("medidas", {})
        for v in (med.get("filas"), med.get("columnas"), x["dic"].get("memoria_pandas_gb"), x["dic"].get("csv_gb"), x["dic"].get("nivel")):
            if v is not None:
                medidas |= {str(v), num(v) if isinstance(v, int) else str(v).replace(".", ",")}
    medidas |= {str(len(fichas))}
    problemas = []
    palabras = len(re.findall(r"\w+", texto))
    if palabras > 230:
        problemas.append(f"tiene {palabras} palabras (máximo 230)")
    m = buscar_d15(texto)   # también con énfasis de Markdown o letras disfrazadas (L117)
    if m:
        problemas.append(f"concluye, recomienda o busca causas («{m[0]}»): el análisis es del estudiante")
    sueltas = [n for n in re.findall(r"\d[\d.,]*", PERMITIDOS_NUM.sub("", texto)) if n.rstrip(".,") not in medidas]
    if sueltas:
        problemas.append(f"cifras que no están en las mediciones: {', '.join(sueltas[:5])}")
    if parece_instruccion(texto):
        problemas.append("trae una instrucción dirigida a agentes")
    personales = [n for n, pat in PATRONES.items() if pat.search(forma_canonica(texto))]   # L116
    if personales:
        problemas.append(f"trae datos personales ({', '.join(personales)})")
    return problemas


def num(x):
    return f"{x:,}".replace(",", ".") if isinstance(x, int) else str(x)


def armar(fichas, titulo, fuente, base_pt, max_preg, max_decir, ficha_tope, salto_guia, resumen_html="", autorizadas=None):
    nivel_txt = {1: "No es big data", 2: "Frontera", 3: "Big data"}
    filas_tabla = []
    for x in fichas:
        med = x["dic"].get("medidas", {})
        val = ("sin validar" if x["chequeos"] is None else
               f"{x['chequeos'] - x['n_fallas']} de {x['chequeos']} chequeos" + (" ✓" if x["n_fallas"] == 0 else ""))
        filas_tabla.append(f"<tr><td><b>{E(x['f'].get('id', ''))}</b><br>{E(str(med.get('titulo') or '')[:70])}</td>"
                           f"<td>{num(med.get('filas', '—'))}</td><td>{x['dic'].get('memoria_pandas_gb', '—')} GB</td>"
                           f"<td>{nivel_txt.get(x['dic'].get('nivel'), '—')}</td><td>{E(val)}</td></tr>")
    bloques = []
    for x in fichas[:ficha_tope]:
        f = x["f"]
        med = x["dic"].get("medidas", {})
        decir = "".join(f"<li>{E(d.get('plantilla', ''))}</li>" for d in f.get("que_se_puede_decir", [])[:max_decir])
        preg = "".join(f"<li><span class='tipo'>{E(p.get('tipo', ''))}</span> {E(p.get('pregunta', ''))}</li>"
                       for p in f.get("preguntas", [])[:max_preg])
        cruces = "; ".join(E(c) for c in x["cruces"][:2]) or "sin cruce declarado"
        gob = f.get("gobernanza", {})
        excl = len(gob.get("excluir", [])) + len(gob.get("seudonimizar", []))
        aviso = (f"<p class='aviso'>La validación marcó: {E('; '.join(x['fallas'][:2])[:220])}</p>" if x["fallas"] else "")
        bloques.append(
            f"<section class='ficha'><h3>{E(str(med.get('titulo') or f.get('id', '')))} <small>{E(f.get('id', ''))} · "
            f"{num(med.get('filas', '—'))} filas · {nivel_txt.get(x['dic'].get('nivel'), '—')}</small></h3>"
            f"<p class='r'>Qué se puede afirmar de cada unidad:</p><ul>{decir}</ul>"
            f"<p class='r'>Preguntas para tu análisis:</p><ol>{preg}</ol>"
            f"<p class='m'><b>Cruces medidos:</b> {cruces}</p>"
            f"<p class='m'><b>Gobernanza:</b> {excl} columnas personales o sensibles quedan fuera · k mínimo {E(str(gob.get('k_minimo', '—')))} · "
            f"{E(str(gob.get('base_legal', '')))}</p>"
            f"<p class='m'><b>Procesamiento:</b> {E(str(f.get('procesamiento', {}).get('estrategia', ''))[:240])}</p>{aviso}</section>")
    omitidas = [x["f"].get("id") for x in fichas[ficha_tope:]]
    nota_omit = (f"<p class='m'>Por espacio, sin ficha en este documento: {E(', '.join(omitidas))} (están en la carpeta de trabajo).</p>"
                 if omitidas else "")
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><title>{E(titulo)}</title><style>
@page {{ size: letter; margin: 0.55in 0.6in; }}
* {{ box-sizing: border-box; }}
body {{ font-family: "Source Sans 3", "Segoe UI", Arial, sans-serif; font-size: {base_pt}pt; line-height: 1.32; color: #1a1f27; margin: 0; }}
h1 {{ font-size: {base_pt * 2.0:.1f}pt; margin: 0 0 2pt; color: #0b3d91; }}
h2 {{ font-size: {base_pt * 1.3:.1f}pt; margin: 10pt 0 4pt; color: #0b3d91; border-bottom: 1.5pt solid #b47b18; padding-bottom: 2pt; }}
h3 {{ font-size: {base_pt * 1.12:.1f}pt; margin: 0 0 3pt; color: #071f4a; }}
h3 small {{ font-weight: 400; color: #4a5568; font-size: {base_pt * 0.85:.1f}pt; }}
.sub {{ color: #4a5568; margin: 0 0 8pt; }}
.caja {{ border-left: 3pt solid #b47b18; background: #fcf6e8; padding: 5pt 8pt; margin: 6pt 0; }}
table {{ width: 100%; border-collapse: collapse; font-size: {base_pt * 0.92:.1f}pt; }}
th, td {{ border-bottom: 0.6pt solid #cbd5e1; padding: 3pt 4pt; text-align: left; vertical-align: top; }}
th {{ background: #edf3fc; }}
.ficha {{ border: 0.8pt solid #cbd5e1; border-radius: 4pt; padding: 5pt 7pt; margin: 0 0 6pt; break-inside: avoid; }}
ul, ol {{ margin: 1pt 0 3pt 14pt; padding: 0; }} li {{ margin: 0 0 1pt; }}
.r {{ margin: 3pt 0 1pt; font-weight: 600; }} .m {{ margin: 2pt 0; font-size: {base_pt * 0.92:.1f}pt; }}
.tipo {{ display: inline-block; font-size: {base_pt * 0.78:.1f}pt; text-transform: uppercase; letter-spacing: .04em; color: #fff; background: #0b3d91; border-radius: 3pt; padding: 0 3pt; }}
.aviso {{ color: #b3261e; font-size: {base_pt * 0.88:.1f}pt; margin: 2pt 0; }}
.salto {{ break-before: page; }} .pie {{ color: #4a5568; font-size: {base_pt * 0.8:.1f}pt; margin-top: 8pt; }}
</style></head><body>
<h1>{E(titulo)}</h1>
<p class="sub">Resumen para el análisis del estudiante · {E(fuente)} · {date.today().isoformat()}</p>
<div class="caja"><b>Cómo leer este documento.</b> Es un resumen de lo que dejó listo el agente masivo, no un análisis: no trae
conclusiones. Las fichas las propuso una IA y una prueba sin IA las comprobó contra la fuente real (columnas, consultas, cruces,
gobernanza). <b>El análisis lo haces tú:</b> elige una pregunta, plantea tu hipótesis antes de mirar, compruébala con una
consulta y concluye con evidencia.</div>
{resumen_html}<h2>Panorama</h2>
<p>{"El agente trabajó solo con las fuentes que autorizó el dueño (" + E(", ".join(autorizadas)) + "): no se conectó a ningún otro conjunto." if autorizadas else "El agente recorrió el catálogo del portal con permiso del dueño y eligió los conjuntos que permiten decir de cada unidad en qué estado está, dónde está y a qué toca."}
Para cada conjunto midió sin IA si es big data: nivel 1, cabe en pandas en una máquina; nivel 2, frontera, cabe solo con la
herramienta adecuada; nivel 3, una sola máquina no alcanza y hay que agregar en la fuente o distribuir. La referencia es la RAM
de Colab, 12,7 GB.</p>
<table><tr><th>Conjunto</th><th>Filas</th><th>En pandas</th><th>Tamaño</th><th>Validación sin IA</th></tr>{''.join(filas_tabla)}</table>
<div class="caja"><b>Reglas para tu análisis.</b> Ninguna cifra sin su consulta. Ningún dato personal, aunque el dato sea
público (Ley 1712 de 2014 y Ley 1581 de 2012): trabaja con agregados y no publiques grupos pequeños. Di qué es una fila antes de
contar. Toda pregunta de costo compara contra una referencia.</div>
<h2 class="salto">Fichas: lo que puedes analizar</h2>
{''.join(bloques)}{nota_omit}
<h2 class="{'salto' if salto_guia else ''}">Guía para tu análisis</h2>
<ol>
<li><b>Elige una pregunta</b> de las fichas y escribe tu hipótesis antes de mirar los datos.</li>
<li><b>Escribe la consulta</b> agregada que la prueba (SoQL en el portal, o DuckDB sobre una muestra en Parquet).</li>
<li><b>Mide</b>: filas leídas, usadas y excluidas con su motivo; compara con una línea base.</li>
<li><b>Concluye solo con evidencia</b> y escribe los límites: sesgos, vacíos, cambios de definición.</li>
<li><b>Revisa la gobernanza</b> antes de mostrar: sin columnas personales y sin grupos con menos de k registros.</li>
</ol>
<p class="pie">Generado sin IA por herramientas/whitepaper_fichas.py a partir de fichas validadas por validar_ficha.py ·
agente-solicitudes (curso «Big Data con IA», NODO · EAFIT).</p>
</body></html>"""


def main(argv):
    if not argv or argv[0].startswith("--"):
        raise SystemExit(__doc__)
    trabajo = Path(argv[0]).resolve()
    titulo = argv[argv.index("--titulo") + 1] if "--titulo" in argv else "Oportunidades en datos públicos grandes"
    fichas = cargar(trabajo)
    if not fichas:
        raise SystemExit(f"No hay fichas en {trabajo / 'fichas'}")
    fuente = fichas[0]["f"].get("dominio", "datos abiertos")
    fa = trabajo / "fuentes_autorizadas.json"
    autorizadas = None
    if fa.exists():
        autorizadas = json.loads(fa.read_text(encoding="utf-8")).get("conjuntos", [])
        fuente += f" · fuentes autorizadas por el dueño: {', '.join(autorizadas)}"
    h, pdf = trabajo / "WHITEPAPER.html", trabajo / "WHITEPAPER.pdf"
    resumen_html = ""
    ria = trabajo / "RESUMEN_IA.md"
    if ria.exists():
        texto = ria.read_text(encoding="utf-8").strip()
        problemas = comprobar_resumen(texto, fichas)
        if problemas:
            print("El resumen de la IA no entra: " + "; ".join(problemas))
            resumen_html = (f"<p class='aviso'>El resumen que escribió la IA no pasó la comprobación sin IA y quedó fuera: "
                            f"{E('; '.join(problemas))}.</p>")
        else:
            parrafos = "".join(f"<p>{E(p.strip())}</p>" for p in re.split(r"\n\s*\n", re.sub(r"^#.*\n", "", texto)) if p.strip())
            resumen_html = f"<h2>Resumen</h2><div class='resumen'>{parrafos}<p class='pie'>Escrito por IA y comprobado sin IA: sin conclusiones, sin cifras fuera de las mediciones y sin datos personales.</p></div>"
    # la letra no baja de carta.LETRA_MINIMA (8,5 pt): se lee en papel. Con letra más chica caben menos preguntas.
    intentos = list(zip(carta.PASOS_LETRA, ((4, 3), (3, 3), (3, 2), (3, 2))))
    # en cada paso, primero la guía a continuación y, si queda corto, la guía en su propia hoja
    pasos = [[(base, mp, md, salto) for salto in (False, True)] for base, (mp, md) in intentos]
    tope = len(fichas)
    while True:
        r = carta.ajustar(pasos, lambda v: armar(fichas, titulo, fuente, v[0], v[1], v[2], tope, v[3], resumen_html, autorizadas), h, pdf)
        n, base = r["paginas"], r["variante"][0]
        if r["estado"] == "sin_chrome":
            print("Sin Chrome: quedó WHITEPAPER.html; imprímelo en tamaño carta.")
            print("RESUMEN " + json.dumps({"html": str(h), "pdf": None}))
            return 0
        if r["estado"] == "exacto":
            print(f"WHITEPAPER.pdf: 3 hojas carta · {tope} de {len(fichas)} fichas · letra base {base} pt")
            print("RESUMEN " + json.dumps({"paginas": 3, "fichas": tope, "letra_pt": base, "pdf": str(pdf)}, ensure_ascii=False))
            return 0
        if r["estado"] == "corto":
            print(f"WHITEPAPER.pdf: {n} hojas (el contenido no alcanza para tres)")
            print("RESUMEN " + json.dumps({"paginas": n, "fichas": tope, "pdf": str(pdf)}))
            return 0
        if tope <= 1:
            print(f"No cupo en tres hojas: {n} páginas con una sola ficha")
            print("RESUMEN " + json.dumps({"paginas": n, "fichas": tope, "pdf": str(pdf)}))
            return 1
        tope -= 1             # «largo»: sale una ficha menos y el documento nombra las que quedaron fuera


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
