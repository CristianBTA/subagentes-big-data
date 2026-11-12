#!/usr/bin/env python3
"""Informe final de una corrida: las cinco etapas en un documento (sin IA).

Uso: python informe_final.py <corrida>   escribe informe_final.md e informe_final.html

Junta lo que dejó cada etapa: procedencia (ingesta), informe.json (procesamiento), whitepaper_verificacion.json
(análisis: lo hacen las personas; la IA solo resume lo desarrollado en whitepaper.md, y las hipótesis de las
corridas anteriores al 6-nov-2026 salen aparte, como historial), grafico_verificacion.json (visualización),
gobernanza.json y custodio.json (gobernanza), la revisión de seguridad y las baterías, y la bitácora del copiloto
(bitacora/*.json).
La versión impresa del whitepaper (WHITEPAPER.pdf) se enlaza solo si es del texto validado de hoy, y su tamaño y sus
hojas se miden aquí: «en tres hojas carta» solo si tiene tres, en carta y sin enlaces. Si tiene más (el texto no cupo
y whitepaper_corrida.py pidió acortarlo), no es carta o trae enlaces, no se enlaza, se dice y el análisis no queda
aprobado (L113).
El HTML se arma escapando todo el texto: un nombre que traiga <script> se muestra, no se ejecuta.
"""
import hashlib
import html
import json
import re
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import carta  # noqa: E402
from verificar import fmt, tabla_md, a_num, revisar_limpiezas  # noqa: E402
from rutas import estado_ingesta, procedencias  # noqa: E402

ETAPAS = ["Ingesta", "Procesamiento", "Análisis", "Visualización", "Gobernanza"]
QUE_HACE_LA_IA = {
    "Ingesta": "escribe el lector (contrato de datos: fuente, columnas, tipos, llave, dominios)",
    "Procesamiento": "limpia y transforma (especificación, reglas y dos implementaciones)",
    "Análisis": "solo resume lo desarrollado en un whitepaper: el análisis lo hacen las personas",
    "Visualización": "genera el gráfico",
    "Gobernanza": "halla datos personales (con nombres, tipos y conteos; nunca filas)",
}
COMO_SE_PRUEBA = {
    "Ingesta": "conteo contra la fuente, llave única y sin nulos, tipos, rangos, dominios, minimización, correr dos veces",
    "Procesamiento": "reglas selladas, caso con respuesta conocida, A = B, conciliación, compuertas y caja de arena",
    "Análisis": "secciones obligatorias, cada cifra en los artefactos verificados, sin conclusiones ni recomendaciones, preguntas de costo, calidad e impacto",
    "Visualización": "cuenta de control, eje desde cero, título, unidades, fuente y fecha, sin datos personales",
    "Gobernanza": "barrido determinista, salidas limpias, k-anonimato, comparación con la IA",
}
RETIRO = "6-nov-2026"                               # desde ese día el análisis lo hacen las personas
PLANTILLA = "../../plantillas/analisis_humano.md"   # las corridas viven en corridas/<fecha-nombre>/
ENLACES_FIJOS = ("whitepaper.md", PLANTILLA, "WHITEPAPER.pdf")   # los únicos enlaces fuera de *.html: los escribe esta herramienta


def leer(p):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def icono(ok):
    return "✅" if ok is True else ("⚠️" if ok is False else ("historial" if ok == "historial" else "—"))


def estado_analisis(c, hip):
    """(estado, validación, vigente). El estado sale de la validación del whitepaper, y solo vale si la huella
    validada es la del whitepaper de hoy. «historial»: corrida anterior al cambio, con las hipótesis de la IA
    probadas y sin whitepaper. None: no hay ni lo uno ni lo otro."""
    wpv = leer(c / "whitepaper_verificacion.json")
    wp = c / "whitepaper.md"
    if wpv is not None:
        vigente = wp.exists() and wpv.get("sha256") == hashlib.sha256(wp.read_bytes()).hexdigest()
        return wpv.get("estado") == "aprobado" and vigente, wpv, vigente
    if wp.exists():
        return False, None, False
    if hip:
        return ("historial" if hip.get("estado") == "probadas" else False), None, None
    return None, None, None


def version_impresa(c, wpv):
    """(línea del informe o None, problema o None) de WHITEPAPER.pdf, medido aquí y no creído (regla de las tres hojas
    carta, L113). Solo cuenta el PDF del texto validado: su HTML lleva en el pie la huella de la validación. Un PDF de
    otro texto, o un enlace simbólico, no se enlaza ni se mide."""
    pdf, hoja = c / "WHITEPAPER.pdf", c / "WHITEPAPER.html"
    huella = wpv.get("sha256") if isinstance(wpv, dict) else None
    if (not isinstance(huella, str) or not huella or pdf.is_symlink() or hoja.is_symlink() or not pdf.is_file()
            or not hoja.is_file() or huella not in hoja.read_text(encoding="utf-8", errors="replace")):
        return None, None
    n, tam, enl = carta.paginas(pdf), carta.tamano(pdf), carta.enlaces(pdf)
    medida = f"{tam[0]} × {tam[1]} pt" if tam else "sin medida"
    problemas = ([f"tiene {n} hojas (el whitepaper validado no cabe en tres hojas carta y hay que acortarlo)"]
                 if n > carta.HOJAS else ["no deja contar sus hojas"] if n < 1 else []) \
        + ([] if tam == carta.CARTA_PT else [f"no es tamaño carta ({medida})"]) \
        + (["trae enlaces (filtrarían la ruta de quien lo imprimió, L84)"] if enl else [])
    if problemas:
        problema = "WHITEPAPER.pdf " + "; ".join(problemas)
        return f"- ⚠️ La versión impresa no se enlaza: {problema}.", problema
    hojas = {1: "una hoja carta (el texto no alcanza para tres)", 2: "dos hojas carta (el texto no alcanza para tres)",
             3: "tres hojas carta"}.get(n, f"{n} hojas carta")
    return (f"- En {hojas}, para imprimir: [WHITEPAPER.pdf](WHITEPAPER.pdf) "
            "(maquetado sin IA por `whitepaper_corrida.py` desde el texto validado)"), None


def seccion_ingesta(t, proc):
    """Lo que dejó la ingesta de UNA tabla: fuente, consulta exacta, versión, huella completa y sus pruebas."""
    if not proc:
        return [f"- Sin procedencia: la tabla «{t}» no pasó por la ingesta con contrato."]
    L = []
    if proc.get("estado") != "aprobada":
        L.append(f"- ⚠️ La carga de «{t}» fue **rechazada**" + (f": {proc['motivo']}" if proc.get("motivo") else "") + ".")
    if proc.get("fuente"):
        L += [f"- Fuente: {proc['fuente'].get('titulo')} · {proc.get('origen') or ''}",
              f"- Consultado: {proc.get('consultado_legible')} · filas {fmt(proc.get('filas'))} · conteo de la fuente {fmt(proc.get('conteo_fuente'))}",
              f"- Huella SHA-256 del archivo: `{proc.get('sha256') or '—'}`"
              + (" (sin cambios frente a la carga anterior)" if proc.get("sin_cambios") else "")]
    if proc.get("consulta"):
        q = proc["consulta"]
        L.append(f"- Consulta exacta: $select={q.get('select')} · $where={q.get('where')} · $order={q.get('order')} · "
                 f"{q.get('paginas')} página(s) de {fmt(q.get('limit_por_pagina'))} filas (la lista está en la procedencia)")
    if proc.get("version_fuente"):
        v = proc["version_fuente"]
        L.append("- Versión de la fuente: " + " · ".join(f"{k} {v[k + '_fecha']}" for k in ("rowsUpdatedAt", "dataUpdatedAt", "viewLastModified")
                                                       if k + "_fecha" in v))
    if proc.get("nota_de_publicacion"):
        L.append(f"- Nota: {proc['nota_de_publicacion']}")
    if proc.get("pruebas"):
        L += ["", "| Prueba de la carga | Resultado | Detalle |", "|---|---|---|"]
        L += [f"| {p['prueba']} | {icono(p['ok'])} | {p['detalle']} |" for p in proc["pruebas"]]
    L += [f"- Aviso: {a}" for a in proc.get("avisos", [])]
    return L


def seccion_procesamiento(c):
    md = (c / "informe.md").read_text(encoding="utf-8") if (c / "informe.md").exists() else ""
    i = md.find("## Lo que se entendió")
    cuerpo = md[i:] if i >= 0 else md
    return re.sub(r"^## ", "### ", cuerpo, flags=re.M)


def armar(c):
    from rutas import resolver_datos
    spec = resolver_datos(leer(c / "spec.json"))
    inf = leer(c / "informe.json") or {}
    procs = procedencias(c, spec)        # una por tabla: con dos tablas, la de la última ya no reemplaza a la otra
    hip = leer(c / "hipotesis_resultado.json")
    est_analisis, wpv, vigente = estado_analisis(c, hip)
    # la versión impresa se mide aquí: un PDF de 4 hojas no se enlaza como «tres hojas carta» ni deja el análisis en ✅
    impresa, problema_impresa = version_impresa(c, wpv) if est_analisis is True else (None, None)
    graf = leer(c / "grafico_verificacion.json")
    gob = leer(c / "gobernanza.json")
    cust = leer(c / "custodio.json")
    revs = leer(c / "revision_seguridad.json")
    bitac = [leer(p) for p in sorted((c / "bitacora").glob("*.json"))] if (c / "bitacora").exists() else []
    bat = subprocess.run([sys.executable, str(AQUI / "baterias.py")], capture_output=True, text=True)  # nosec B603
    bat_txt = [l for l in bat.stdout.splitlines() if not l.startswith("RESUMEN")]
    # la limpieza se mira aparte de informe.json: si quedó rechazada o su capa limpia cambió después de verificar, el
    # procesamiento no está aprobado aunque informe.json diga «aprobado» (L109)
    _, motivos_limpieza = revisar_limpiezas(c, spec)

    estado = {
        "Ingesta": estado_ingesta(procs),    # ✅ solo si TODAS las tablas tienen su procedencia aprobada
        "Procesamiento": (inf.get("estado") == "aprobado" and not motivos_limpieza) if inf or motivos_limpieza else None,
        "Análisis": False if problema_impresa else est_analisis,
        "Visualización": None if not graf else graf.get("estado") == "aprobado",
        "Gobernanza": None if not gob else gob.get("estado") == "aprobado",
    }
    L = [f"# {spec.get('peticion', 'Petición')}", ""]
    historial = est_analisis == "historial"
    todo_ok = all(v is True for e, v in estado.items() if not (e == "Análisis" and historial))
    L.append("**Estado: ✅ todas las etapas aprobadas.**" if todo_ok else
             "**Estado: ⚠️ hay etapas sin aprobar o sin correr; ver la tabla.**")
    if historial:
        L.append(f"\n> El análisis de esta corrida es historial: lo hacía la IA con hipótesis, un paso retirado el {RETIRO}. "
                 "Desde entonces lo hacen las personas (ver Análisis).")
    if inf.get("preguntas_abiertas"):
        L.append(f"\n> {inf['preguntas_abiertas']} pregunta(s) de negocio abiertas: la cifra usa el valor por defecto de cada una (ver Procesamiento).")
    L += ["", "## El pipeline", "| Etapa | La IA… | La prueba sin IA | Estado |", "|---|---|---|---|"]
    L += [f"| {e} | {QUE_HACE_LA_IA[e]} | {COMO_SE_PRUEBA[e]} | {icono(estado[e])} |" for e in ETAPAS]

    L += ["", "## Resultado"]
    if inf.get("resultado_oficial"):
        cols = spec["salida"]["claves"] + spec["salida"]["valores"]
        L.append(tabla_md(inf["resultado_oficial"], cols))
        tot = {v: sum(a_num(f.get(v)) or 0 for f in inf["resultado_oficial"]) for v in spec["salida"]["valores"]}
        L.append("\n**Total:** " + " · ".join(f"{v} {fmt(t)}" for v, t in tot.items()))
    citas = [f"{p['cita']} Licencia {p.get('licencia') or '—'}; atribución: {p.get('atribucion') or '—'}."
             for p in procs.values() if p and p.get("cita")]
    if citas:
        L += ["", "**Cita (R9):** " + " ".join(citas)]

    L += ["", "## 1 · Ingesta: la IA escribe el lector"]
    if any(procs.values()):
        for t, proc in procs.items():
            if len(procs) > 1:
                L += ["", f"### Tabla «{t}»"]
            L += seccion_ingesta(t, proc)
    else:
        L.append("Sin procedencia: los datos no pasaron por la ingesta con contrato.")

    L += ["", "## 2 · Procesamiento: la IA limpia y transforma"]
    L += [f"- ⚠️ {m}." for m in motivos_limpieza]
    for lp in sorted(c.glob("limpieza_*.json")):
        li = leer(lp)
        L += ["", f"### Limpieza de «{li.get('tabla')}»: {fmt(li.get('filas'))} filas, {fmt(li.get('filas_ok'))} sin marcas"]
        if li.get("estado") != "aprobada":
            L.append(f"- ⚠️ La limpieza quedó **{li.get('estado')}**" + (f": {li['motivo']}" if li.get("motivo") else "") + ".")
        L += ["| Operación | Columna | Filas cambiadas | Filas marcadas | Ejemplo |", "|---|---|---|---|---|"]
        for o in li.get("operaciones", []):
            col = o["columna"] if isinstance(o["columna"], str) else ", ".join(o["columna"]) if isinstance(o["columna"], list) else str(o["columna"])
            L.append(f"| {o['op']} | {col} | {fmt(o['filas_cambiadas'])} | {fmt(o['filas_marcadas'])} | {(o.get('ejemplos') or ['—'])[0]} |")
        L += ["", "| Prueba de la limpieza | Resultado | Detalle |", "|---|---|---|"]
        L += [f"| {p['prueba']} | {icono(p['ok'])} | {p['detalle']} |" for p in li.get("pruebas", [])]
        if li.get("marcas"):
            L.append("- Marcas (las filas no se borran; la spec dice cuáles se excluyen): " + " · ".join(f"{k} {fmt(v)}" for k, v in li["marcas"].items()))
    L.append(seccion_procesamiento(c))

    L += ["", "## 3 · Análisis: lo hacen las personas",
          "La IA no da el análisis: el documentador resume lo desarrollado en un whitepaper, y las personas del curso analizan, "
          "con su hipótesis escrita antes de mirar y su conclusión en la plantilla."]
    if wpv is not None:
        cifras = wpv.get("cifras") or []
        validacion = ("✅ aprobada" if est_analisis is True else
                      "⚠️ el whitepaper cambió después de validarse" if wpv.get("estado") == "aprobado" and not vigente else "⚠️ sin aprobar")
        L.append(f"- Whitepaper: [whitepaper.md](whitepaper.md) · validación sin IA (`validar_whitepaper.py`): {validacion}"
                 + (f" · {sum(1 for x in cifras if x.get('respaldada'))} de {len(cifras)} cifras en los artefactos verificados" if cifras else ""))
        # la versión impresa se enlaza solo si es del texto validado de hoy (la huella completa va en el pie del HTML) y
        # si de verdad tiene tres hojas carta sin enlaces: se mide aquí (version_impresa, L113)
        if impresa:
            L.append(impresa)
        L += ["", "| Comprobación | Resultado | Detalle |", "|---|---|---|"]
        L += [f"| {x.get('chequeo')} | {icono(x.get('ok'))} | {str(x.get('detalle')).replace('|', chr(92) + '|')} |"
              for x in wpv.get("chequeos", [])]
    elif (c / "whitepaper.md").exists():
        L.append("- Whitepaper: [whitepaper.md](whitepaper.md) · ⚠️ sin validar: falta correr `validar_whitepaper.py`.")
    else:
        L.append("- Whitepaper: no hay." + (f" La corrida es anterior al {RETIRO}: su análisis queda abajo, como historial." if hip else ""))
    L.append(f"- Plantilla para el análisis de las personas: [plantillas/analisis_humano.md]({PLANTILLA})")
    if hip:
        L += ["", f"### Historial: hipótesis de la IA (retirado el {RETIRO})",
              "| Hipótesis | Umbral | Valor | Línea base | Veredicto |", "|---|---|---|---|---|"]
        for h in hip["hipotesis"]:
            u = h.get("umbral", {})
            L.append(f"| **{h['id']}** {h['enunciado']} | {u.get('operador')} {u.get('valor')} | {fmt(a_num(h.get('valor')))} | "
                     f"{fmt(a_num(h.get('linea_base_valor')))} ({h.get('linea_base', '')}) | {h['veredicto']} |")
        L += [f"- {p}" for p in hip.get("problemas", [])]
        L.append(f"\n_Hasta el {RETIRO} la IA proponía hipótesis, las sellaba antes de probarlas y otro agente escribía la consulta "
                 "de cada una. Ese paso se retiró: el análisis lo hacen las personas. Se conserva como historial de esta corrida._")

    L += ["", "## 4 · Visualización: la IA genera el gráfico"]
    if graf:
        if graf.get("html"):
            L.append(f"Gráfico: [grafico.html](grafico.html)")
        L += ["", "| Comprobación | Resultado | Detalle |", "|---|---|---|"]
        L += [f"| {x['comprobacion']} | {icono(x['ok'])} | {x['detalle']} |" for x in graf["comprobaciones"]]
    else:
        L.append("No se corrió.")

    L += ["", "## 5 · Gobernanza: la IA halla datos personales"]
    if gob:
        marcadas = [(t, col, i) for t, info in gob["tablas"].items() for col, i in info["columnas"].items()
                    if i.get("clase_por_nombre") or i.get("hallazgos")]
        L.append(f"- Columnas con datos personales en los datos usados: {len(marcadas) or 'ninguna'}"
                 + ("" if not marcadas else ": " + "; ".join(f"{col} ({i.get('clase_por_nombre') or ''} {i.get('hallazgos') or ''})".strip() for _, col, i in marcadas)))
        for t, proc in procs.items():
            if proc and proc.get("columnas_personales_justificadas"):
                L.append(f"- Columnas personales justificadas en la ingesta de «{t}»: {proc['columnas_personales_justificadas']}")
            if proc and proc.get("base_legal_sensibles"):
                L.append(f"- Datos sensibles con base legal en la ingesta de «{t}»: {proc['base_legal_sensibles']}")
        L.append("- Salidas que se publican (informe, resultado, gráfico): "
                 + ("sin datos personales." if not any(gob["salidas"].values()) else f"**con hallazgos**: {gob['salidas']}"))
        k = gob.get("k_anonimato", {})
        L.append(f"- k-anonimato: {k.get('motivo') if not k.get('aplica') else ('k = ' + str(k['k']) + ' (mínimo ' + str(k['k_minimo']) + ')')}")
        cu = gob.get("custodio", {})
        if cu.get("hay_custodio"):
            L.append(f"- La IA (custodio) y el barrido coinciden en {len(cu['coinciden'])} columnas; la IA no vio: {cu['ia_no_vio'] or 'ninguna'}; "
                     f"solo la IA marcó: {cu['solo_la_ia'] or 'ninguna'}.")
        if cust and cust.get("recomendaciones"):
            L += [f"- Recomendación del custodio: {r}" for r in cust["recomendaciones"][:5]]
        L += [f"- ⚠️ {p}" for p in gob.get("problemas", [])]
    else:
        L.append("No se corrió.")

    integ = leer(c / "integridad_comprobacion.json")
    L += ["", "## Integridad del pipeline"]
    if integ:
        L.append("- Herramientas, fichas, flujo y dependencias: " + ("**sin cambios** durante la corrida." if integ["estado"] == "intacta" else "**alteradas**:"))
        L += [f"  - ⚠️ {a}" for a in integ.get("alertas", [])]
        if integ.get("casos_nuevos_en_baterias"):
            L.append(f"- Casos nuevos en las baterías (solo pueden crecer): {', '.join(integ['casos_nuevos_en_baterias'])}")
    else:
        L.append("- Sin manifiesto de integridad en esta corrida (se agregó después).")
    L += ["", "## Seguridad del código que escribió la IA"]
    archivos = sorted(p.name for p in c.glob("*.py") if p.name not in ("reglas.py",)) + ["reglas.py"]
    L.append(f"- Archivos de la IA revisados con compuertas (librerías permitidas, reglas propias y Bandit) antes de ejecutarse: {', '.join(archivos)}.")
    L.append("- Todo se ejecuta en caja de arena: sin red y sin poder escribir fuera de una carpeta temporal.")
    if revs:
        L.append(f"- Revisión ciega de vulnerabilidades: {len(revs.get('hallazgos', []))} hallazgo(s); "
                 f"{sum(1 for h in revs.get('hallazgos', []) if h.get('confirmado'))} confirmado(s) con prueba.")
        L += [f"  - {h.get('id')}: {h.get('descripcion')} — {'confirmado' if h.get('confirmado') else 'sin prueba que lo confirme'}"
              for h in revs.get("hallazgos", [])[:8]]
    L += ["- Baterías (lo que falló una vez, probado otra vez):"] + [f"  - {l}" for l in bat_txt]

    L += ["", "## Bitácora del copiloto"]
    if bitac:
        L += ["| Etapa | Qué se pidió | Qué devolvió | Cómo se probó | Qué se corrigió | Qué quedó sin verificar |", "|---|---|---|---|---|---|"]
        orden = {e: i for i, e in enumerate(ETAPAS)}
        for b in sorted([b for b in bitac if b], key=lambda b: orden.get(b.get("etapa"), 9)):
            celdas = [b.get(k, "—") for k in ("etapa", "que_se_pidio", "que_devolvio", "como_se_probo", "que_se_corrigio", "sin_verificar")]
            L.append("| " + " | ".join(str(x).replace("|", "\\|").replace("\n", " ") for x in celdas) + " |")
    else:
        L.append("Sin entradas.")
    return "\n".join(L) + "\n", todo_ok


def md_a_html(md, titulo):
    """Convierte el subconjunto de Markdown que usa este informe. Escapa primero: nada del texto se ejecuta."""
    def linea(t):
        t = re.sub(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f\u200b-\u200f\u202a-\u202e\u2060-\u2069\ufeff]", "", t)
        t = html.escape(t, quote=False)
        t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"(?<![\w*])_(.+?)_(?![\w*])", r"<em>\1</em>", t)
        t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        t = re.sub(r"\[([^\]]+)\]\(([\w.-]+\.html)\)", r'<a href="\2">\1</a>', t)   # sin «/»: solo archivos de la corrida
        # y los dos enlaces fijos que escribe esta herramienta (el whitepaper y la plantilla): nunca un destino de los datos
        t = re.sub(r"\[([^\]]+)\]\((" + "|".join(map(re.escape, ENLACES_FIJOS)) + r")\)", r'<a href="\2">\1</a>', t)
        return t
    out, en_tabla, en_lista = [], False, False
    for raw in md.splitlines():
        if raw.startswith("|"):
            celdas = [x.strip() for x in re.split(r"(?<!\\)\|", raw.strip()[1:-1])]
            if all(re.fullmatch(r"-{3,}", x) for x in celdas):
                continue
            if not en_tabla:
                out.append("<table><thead><tr>" + "".join(f"<th>{linea(x)}</th>" for x in celdas) + "</tr></thead><tbody>")
                en_tabla = True
            else:
                out.append("<tr>" + "".join(f"<td>{linea(x.replace(chr(92) + '|', '|'))}</td>" for x in celdas) + "</tr>")
            continue
        if en_tabla:
            out.append("</tbody></table>")
            en_tabla = False
        if raw.lstrip().startswith("- "):
            if not en_lista:
                out.append("<ul>")
                en_lista = True
            out.append(f"<li>{linea(raw.lstrip()[2:])}</li>")
            continue
        if en_lista:
            out.append("</ul>")
            en_lista = False
        m = re.match(r"^(#{1,4}) (.*)", raw)
        if m:
            n = len(m.group(1))
            out.append(f"<h{n}>{linea(m.group(2))}</h{n}>")
        elif raw.startswith("> "):
            out.append(f"<blockquote>{linea(raw[2:])}</blockquote>")
        elif raw.strip():
            out.append(f"<p>{linea(raw)}</p>")
    if en_tabla:
        out.append("</tbody></table>")
    if en_lista:
        out.append("</ul>")
    css = """
:root{--fondo:#ffffff;--texto:#1d2330;--suave:#5b6474;--borde:#d9dee7;--cabeza:#f2f4f8;--acento:#2f6fde}
@media (prefers-color-scheme: dark){:root{--fondo:#14181f;--texto:#e6e9ef;--suave:#a3acbb;--borde:#2c3340;--cabeza:#1c222c;--acento:#7aa7ff}}
body{background:var(--fondo);color:var(--texto);font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;margin:0;padding:24px 16px}
main{max-width:1100px;margin:0 auto}h1{font-size:1.6rem;line-height:1.25}h2{margin-top:2rem;border-bottom:1px solid var(--borde);padding-bottom:.3rem}
table{border-collapse:collapse;width:100%;margin:.6rem 0;font-size:.92rem;display:block;overflow-x:auto}
th,td{border:1px solid var(--borde);padding:.4rem .55rem;text-align:left;vertical-align:top}th{background:var(--cabeza)}
blockquote{margin:.8rem 0;padding:.5rem .9rem;border-left:4px solid var(--acento);background:var(--cabeza)}
code{font-size:.88em}a{color:var(--acento)}iframe{width:100%;height:620px;border:1px solid var(--borde);border-radius:8px}
"""
    cuerpo = "\n".join(out)
    if 'href="grafico.html"' in cuerpo:
        cuerpo = cuerpo.replace('<a href="grafico.html">grafico.html</a>', '<a href="grafico.html">abrir el gráfico aparte</a></p><iframe src="grafico.html" title="Gráfico"></iframe><p>')
    return (f"<!doctype html><html lang=\"es\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            f"<title>{html.escape(titulo)}</title><style>{css}</style></head><body><main>{cuerpo}</main></body></html>\n")


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    c = Path(argv[0]).resolve()
    md, ok = armar(c)
    (c / "informe_final.md").write_text(md, encoding="utf-8")
    spec = leer(c / "spec.json")
    (c / "informe_final.html").write_text(md_a_html(md, "Informe de la corrida"), encoding="utf-8")
    print(f"Informe final: {c / 'informe_final.html'} · {'todas las etapas aprobadas' if ok else 'hay etapas por revisar'}")
    print("RESUMEN " + json.dumps({"todas_aprobadas": ok, "peticion": spec.get("peticion")}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
