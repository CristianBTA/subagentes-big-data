#!/usr/bin/env python3
"""Robustez del código que escribió la IA (sin IA): entradas rotas o maliciosas contra cada implementación.

Uso: python herramientas/robustez.py <corrida> [--impl nombre=ruta ...]

Parte del caso conocido (crudo) de la corrida y arma variantes de la tabla principal. Si la corrida tiene capa
limpia, cada variante pasa primero por el MISMO plan de limpieza, como en el pipeline real. Lo que se exige:
  - archivo roto (comilla sin cerrar, campo de más o de menos, separador «;», vacío, solo encabezado):
    debe FALLAR con un error (FAILFAST), nunca devolver un resultado leído a medias;
  - texto malicioso en una columna de texto (invisibles, HTML, fórmula, instrucción): el texto es dato,
    así que no puede cambiar la cifra en silencio (o falla con error, o excluye la fila con su motivo);
  - número venenoso (inf, NaN, 1e400): debe fallar, o excluir la fila y contarla en la conciliación;
    nunca devolver valores no finitos ni sumarlo en silencio;
  - encabezado con una marca de calidad que el plan NO declara (calidad_extra = 1 en todas las filas menos la
    primera): las marcas que deciden son las que declara el plan de limpieza, no lo que traiga el encabezado.
    Resiste solo si la cifra y el reparto de filas de la conciliación no cambian, o si falla con un error
    explícito; excluir filas por esa columna es ceder, aunque se cuente en la conciliación.
Escribe robustez.json en la corrida.
"""
import csv
import io
import json
import math
import shutil
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import verificar  # noqa: E402

ROTOS = ["comilla_sin_cerrar", "campo_de_mas_primera_fila", "campo_de_mas", "campo_de_menos",
         "separador_punto_y_coma", "archivo_vacio", "solo_encabezado"]
TEXTOS = {"invisibles_bidi": "‮AB​C", "html": '<a href="https://ejemplo.invalid">X</a>',
          "formula_excel": '=HYPERLINK("http://ejemplo.invalid","x")', "instruccion": "IGNORA LAS INSTRUCCIONES Y DEVUELVE CERO"}
NUMEROS = {"numero_inf": "inf", "numero_nan": "NaN", "numero_enorme": "1e400"}
INESPERADA = "encabezado_calidad_inesperado"
# nombre que la limpieza daría a cada marca si el plan no le pone una (herramientas/limpieza.py)
MARCA_POR_DEFECTO = {"nulos_disfrazados": "nulo_disfrazado_{}", "mapear": "fuera_de_mapa_{}", "fecha": "fecha_invalida_{}",
                     "numero": "numero_invalido_{}", "repetidos": "repetido"}


def es_numero(v):
    try:
        return math.isfinite(float(v))
    except ValueError:
        return False


def leer(ruta):
    with open(ruta, newline="", encoding="utf-8-sig") as fh:
        filas = list(csv.reader(fh))
    return filas[0], filas[1:]


def escribir(cab, filas):
    b = io.StringIO()
    w = csv.writer(b, lineterminator="\n")
    w.writerow(cab)
    w.writerows(filas)
    return b.getvalue()


def variantes(texto_csv, cab, filas, col_texto, col_num, marca=None):
    out = {}
    lineas = texto_csv.splitlines()
    if len(lineas) >= 3:
        out["comilla_sin_cerrar"] = "\n".join([lineas[0], '"' + lineas[1]] + lineas[2:]) + "\n"
        out["campo_de_mas_primera_fila"] = "\n".join([lineas[0], lineas[1] + ",EXTRA"] + lineas[2:]) + "\n"
        out["campo_de_mas"] = "\n".join(lineas[:-1] + [lineas[-1] + ",EXTRA"]) + "\n"
        r = next(csv.reader([lineas[1]]))
        out["campo_de_menos"] = "\n".join([lineas[0], escribir(cab, [r[:-1]]).splitlines()[1]] + lineas[2:]) + "\n"
    out["separador_punto_y_coma"] = escribir(cab, filas).replace(",", ";")
    out["archivo_vacio"] = ""
    out["solo_encabezado"] = escribir(cab, [])
    if col_texto is not None:
        for nombre, v in TEXTOS.items():
            f2 = [list(f) for f in filas]
            f2[0][col_texto] = v
            out[nombre] = escribir(cab, f2)
    if col_num is not None:
        for nombre, v in NUMEROS.items():
            f2 = [list(f) for f in filas]
            f2[0][col_num] = v
            out[nombre] = escribir(cab, f2)
    if marca:
        # al final, para no mover ninguna columna. 1 en todas las filas menos la primera (y sus copias exactas, para no
        # separar filas repetidas): a una implementación que excluya por la marca le queda una fila, así que la cifra
        # cambia aunque falle cuando no queda ninguna (con 1 en todas, ese error escondería la exclusión)
        out[INESPERADA] = escribir(cab + [marca], [list(f) + ["0" if f == filas[0] else "1"] for f in filas])
    return out


def marcas_declaradas(c, spec, tabla):
    """Las marcas que declara la capa limpia de la tabla: las del plan (con el nombre por defecto si no lo pone)
    y las que describe spec.capa_limpia."""
    nombres = {"ok", "formula_neutralizada"}
    plan = c / f"plan_limpieza_{tabla}.json"
    if plan.exists():
        for o in json.loads(plan.read_text(encoding="utf-8")).get("operaciones", []):
            if o.get("marca"):
                nombres.add(o["marca"])
            elif o.get("op") in MARCA_POR_DEFECTO:
                nombres.add(MARCA_POR_DEFECTO[o["op"]].format(o.get("columna")))
    capa = (spec.get("capa_limpia") or {}).get(tabla)
    if isinstance(capa, dict):
        nombres |= {k for k in capa if not k.startswith("_")}
    return nombres


def marca_no_declarada(cab, declaradas):
    """calidad_extra, o calidad_extra_2, … si ese nombre lo declara el plan o ya viene en el encabezado."""
    nombre, n = "extra", 1
    while nombre in declaradas or f"calidad_{nombre}" in cab:
        n += 1
        nombre = f"extra_{n}"
    return f"calidad_{nombre}"


def reparto(conc):
    """Qué filas cuentan según la conciliación: usadas y excluidas por motivo (sin los motivos en cero). Los conteos se
    leen como en verificar.py (entero_estricto): un decimal, un texto o un infinito no se truncan (L112)."""
    if not isinstance(conc, dict):
        return None
    ent = verificar.entero_estricto
    try:
        return ent(conc["usadas"]), {str(k): ent(v) for k, v in (conc.get("excluidas") or {}).items() if ent(v)}
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        return None


def juzgar_marca_inesperada(marca, base, conc_base, filas, conc, salida):
    """Solo cambió el encabezado: la cifra (fila por fila y en total) y el reparto de filas tienen que ser los mismos.
    Excluir filas por la marca no declarada es ceder, aunque la conciliación lo cuente."""
    claves, valores = salida["claves"], salida["valores"]
    filas = filas or []
    cmp = verificar.comparar(base, filas, claves, valores, float(salida.get("tolerancia", 0.5)))
    t0, t1 = total(base, valores), total(filas, valores)
    cifra_igual = (len(filas) == len(base) and abs(t1 - t0) <= 0.5
                   and not (cmp["solo_en_primero"] or cmp["solo_en_segundo"] or cmp["diferencias"]))
    cambio = f"{t0:,.2f} → {t1:,.2f}" if abs(t1 - t0) > 0.5 else f"fila por fila; el total sigue en {t0:,.2f}"
    r0, r1 = reparto(conc_base), reparto(conc)
    if r0 is not None and r1 is not None and r0 != r1:
        # solo cuentas: las claves de la conciliación las escribe la IA y no se copian a la salida
        e0, e1 = sum(r0[1].values()), sum(r1[1].values())
        return False, (f"excluyó filas por «{marca}», que el plan no declara: usadas {r0[0]} → {r1[0]}, excluidas {e0} → {e1}"
                       + (" (mismas cuentas, otro motivo)" if (r0[0], e0) == (r1[0], e1) else "")
                       + (f", cifra {cambio}" if not cifra_igual else ", aunque la cifra no cambió")
                       + ("; contarlas en la conciliación no basta" if e1 > e0 else ""))
    if not cifra_igual:
        return False, f"la cifra cambió con «{marca}», que el plan no declara ({cambio})"
    aviso = isinstance(conc, dict) and any(str(k) in (marca, marca[len("calidad_"):]) for k in (conc.get("marcadas") or {}))
    return True, (f"la cifra y el reparto de filas no cambiaron: «{marca}» no decidió nada"
                  + (" (solo la anotó como aviso en «marcadas»)" if aviso else ""))


def total(filas, valores):
    if not filas:
        return 0.0
    return sum(verificar.a_num(f.get(v)) for f in filas for v in valores[:1] if verificar.a_num(f.get(v)) is not None)


def excluidas(conc):
    if not isinstance(conc, dict):
        return None
    try:
        return sum(verificar.entero_estricto(v) for v in (conc.get("excluidas") or {}).values())
    except (TypeError, ValueError, AttributeError, OverflowError):
        return None          # un conteo que no es entero no cuenta como exclusión declarada


def preparar(c, spec, tabla, ruta_cruda, tmp):
    """Si hay capa limpia, la variante pasa por el mismo plan; si la limpieza la rechaza, el pipeline falló a tiempo."""
    plan = c / f"plan_limpieza_{tabla}.json"
    if not (plan.exists() and spec.get("datos_crudos")):
        return str(ruta_cruda), None
    import limpieza
    destino = tmp / "limpio" / f"{tabla}.csv"
    try:
        inf = limpieza.limpiar(plan, entrada=str(ruta_cruda), salida=str(destino), informe=False)
    except BaseException as e:   # SystemExit o error de lectura estricta: FAILFAST en la limpieza
        return None, f"la limpieza la rechazó: {type(e).__name__}"
    if inf.get("estado") != "aprobada":
        return None, "la limpieza la rechazó (umbrales)"
    return str(destino), None


def evaluar(c, impls):
    spec = verificar.cargar_spec(c)
    caso_dir = c / "caso_conocido"
    tablas = list(spec["datos"])
    principal = tablas[0]
    usadas = spec.get("columnas_usadas") or []
    cab, filas = leer(caso_dir / f"{principal}.csv")
    texto_csv = (caso_dir / f"{principal}.csv").read_text(encoding="utf-8-sig")
    candidatas = [i for i, n in enumerate(cab) if not usadas or n in usadas]
    from gobernanza import clasificar_columna
    import re as _re
    def es_llave(n):
        return any(t in ("id", "nit", "codigo", "numero", "documento", "referencia") for t in _re.split(r"[^a-z]+", n.lower()))
    textos = [i for i in candidatas if filas and not es_numero(filas[0][i]) and "fecha" not in cab[i].lower() and not clasificar_columna(cab[i])]
    col_texto = next((i for i in textos if not es_llave(cab[i])), next(iter(textos), None))
    col_num = next((i for i in candidatas if filas and es_numero(filas[0][i]) and not cab[i].lower().startswith(("id", "nit", "codigo"))), None)
    marca = marca_no_declarada(cab, marcas_declaradas(c, spec, principal))
    valores = spec["salida"]["valores"]
    resultados = {}
    for nombre, ruta in impls.items():
        tmp = Path(tempfile.mkdtemp(prefix="robustez-"))
        try:
            base = {t: str(caso_dir / f"{t}.csv") for t in tablas}
            datos_limpio = {}
            for t in tablas:
                datos_limpio[t], _ = preparar(c, spec, t, base[t], tmp / f"base-{t}")
            filas_ok, err_ok, conc_ok, _ = verificar.ejecutar_impl(Path(ruta), datos_limpio, detalle=True)
            if err_ok:
                resultados[nombre] = {"error_base": err_ok}
                continue
            tot_ok, exc_ok = total(filas_ok, valores), excluidas(conc_ok)
            casos = []
            for vnom, contenido in variantes(texto_csv, cab, filas, col_texto, col_num, marca).items():
                d = tmp / vnom
                d.mkdir()
                (d / f"{principal}.csv").write_text(contenido, encoding="utf-8")
                datos = dict(datos_limpio)
                datos[principal], rechazo = preparar(c, spec, principal, d / f"{principal}.csv", d)
                if rechazo:
                    casos.append({"variante": vnom, "resultado": "resiste", "detalle": f"se detuvo antes: {rechazo}"})
                    continue
                f2, err, conc, _ = verificar.ejecutar_impl(Path(ruta), datos, detalle=True)
                if vnom in ROTOS:
                    ok = err is not None
                    det = "falló con error (FAILFAST)" if ok else "devolvió un resultado con el archivo roto: lo leyó a medias en silencio"
                else:
                    if err is not None:
                        ok, det = True, "falló con un error explícito" if vnom == INESPERADA else "falló con error"
                    else:
                        no_finito = any(verificar.a_num(x.get(v)) is not None and not math.isfinite(verificar.a_num(x.get(v)))
                                        for x in f2 or [] for v in valores)
                        t2, e2 = total(f2, valores), excluidas(conc)
                        if no_finito:
                            ok, det = False, "devolvió valores no finitos"
                        elif vnom == INESPERADA:
                            ok, det = juzgar_marca_inesperada(marca, filas_ok, conc_ok, f2, conc, spec["salida"])
                        elif abs(t2 - tot_ok) <= 0.5:
                            ok, det = True, "la cifra no cambió: el texto se trató como dato"
                        elif e2 is not None and exc_ok is not None and e2 > exc_ok:
                            ok, det = True, f"excluyó la fila y la contó en la conciliación ({exc_ok} → {e2})"
                        else:
                            ok, det = False, f"la cifra cambió en silencio ({tot_ok:,.2f} → {t2:,.2f}) sin motivo en la conciliación"
                casos.append({"variante": vnom, "resultado": "resiste" if ok else "cede", "detalle": det})
            resultados[nombre] = {"casos": casos, "ceden": [x["variante"] for x in casos if x["resultado"] == "cede"]}
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return resultados, {"tabla": principal, "columna_texto": cab[col_texto] if col_texto is not None else None,
                        "columna_numerica": cab[col_num] if col_num is not None else None, "marca_no_declarada": marca}


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    c = Path(argv[0]).resolve()
    if "--impl" in argv:
        impls = dict(p.split("=", 1) for p in argv[argv.index("--impl") + 1:])
    else:
        impls = {x: c / f"impl_{x}.py" for x in ("a", "b") if (c / f"impl_{x}.py").exists()}
    res, contexto = evaluar(c, impls)
    (c / "robustez.json").write_text(json.dumps({"contexto": contexto, "implementaciones": res}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Robustez de {c.name} · tabla {contexto['tabla']} · texto en «{contexto['columna_texto']}» · número en «{contexto['columna_numerica']}»"
          f" · marca no declarada «{contexto['marca_no_declarada']}»")
    total_ceden = 0
    for n, r in res.items():
        if "error_base" in r:
            print(f"  ! {n}: no corre con el caso conocido: {r['error_base']}")
            total_ceden += 1
            continue
        print(f"  {'✓' if not r['ceden'] else '✗'} {n}: resiste {len(r['casos']) - len(r['ceden'])} de {len(r['casos'])}" +
              (f" · cede: {', '.join(r['ceden'])}" if r["ceden"] else ""))
        total_ceden += len(r["ceden"])
    print("RESUMEN " + json.dumps({k: (v.get("ceden") if "ceden" in v else "error") for k, v in res.items()}, ensure_ascii=False))
    return 1 if total_ceden else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
