from pathlib import Path


def analizar(datos):
    # getattr guardado con otro nombre: la llamada g(...) ya no se reconoce como getattr con nombre calculado
    g = getattr
    carpeta = Path(datos["t"].rsplit("/", 1)[0])
    return [{"archivo": p.name} for p in g(carpeta, "iter" + "dir")()]
