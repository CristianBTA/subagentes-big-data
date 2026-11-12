import csv
import functools
import operator
import os
import string
from pathlib import Path
from typing import Optional


def _nombre_tabla(ruta: str) -> str:
    # Lo que sí se puede hacer con la ruta que se recibe: su nombre, su extensión y si existe; sin listar la carpeta,
    # sin subir a la de arriba y sin ir a un archivo vecino (SEG-4)
    p = Path(ruta)
    return f"{p.stem}{p.suffix}" if os.path.exists(ruta) and os.path.basename(ruta) == p.name else ""


@functools.lru_cache(maxsize=8)
def _plantilla(clave: str) -> str:
    return string.Template("tabla $t").substitute(t=clave)


def analizar(datos: dict) -> list:
    filas = []
    for clave, ruta in sorted(datos.items(), key=operator.itemgetter(0)):
        with open(ruta, encoding="utf-8", newline="") as fh:
            n: Optional[int] = sum(1 for _ in csv.DictReader(fh))
        filas.append({"tabla": _plantilla(clave), "archivo": _nombre_tabla(ruta), "filas": functools.reduce(operator.add, [n or 0], 0)})
    return filas
