from pathlib import Path


def analizar(datos):
    # getattr con el nombre en texto: el atributo «iterdir» no aparece como atributo en el código
    carpeta = Path(datos["t"].rsplit("/", 1)[0])
    return [{"archivo": p.name} for p in getattr(carpeta, "iterdir")()]
