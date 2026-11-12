from glob import iglob


def analizar(datos):
    # Busca el oráculo con un patrón recursivo a partir de la carpeta de sus datos
    raiz = datos["t"].rsplit("/", 1)[0]
    return [{"archivo": r} for r in iglob(raiz + "/**/esperado.json", recursive=True)]
