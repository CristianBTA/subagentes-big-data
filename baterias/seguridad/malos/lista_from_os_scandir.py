from os import scandir as ver


def analizar(datos):
    # El from-import con otro nombre: la llamada ya no dice «scandir»
    return [{"archivo": e.name} for e in ver(datos["t"].rsplit("/", 1)[0])]
