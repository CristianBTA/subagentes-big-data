import string
from pathlib import Path


def analizar(datos):
    # string.Formatter.get_field resuelve «0.iterdir» y devuelve el método: es un getattr por texto
    carpeta = Path(datos["t"].rsplit("/", 1)[0])
    metodo = string.Formatter().get_field("0.iterdir", (carpeta,), {})[0]
    return [{"archivo": p.name} for p in metodo()]
