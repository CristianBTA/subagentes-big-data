from pathlib import Path


def analizar(datos):
    # Path.rglob y Path.iterdir: recorren la carpeta de sus datos sin subir con .parent
    carpeta = Path(datos["t"].rsplit("/", 1)[0])
    hallados = [p.name for p in carpeta.rglob("*.json")] + [p.name for p in carpeta.iterdir()]
    return [{"archivo": n} for n in hallados]
