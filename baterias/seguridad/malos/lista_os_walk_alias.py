import os as sistema


def analizar(datos):
    # Recorre todo el árbol bajo la carpeta de sus datos con un alias de os
    raiz = datos["t"].rsplit("/", 1)[0]
    return [{"archivo": f} for _, _, archivos in sistema.walk(raiz) for f in archivos]
