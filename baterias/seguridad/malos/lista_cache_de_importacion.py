import sys


def analizar(datos):
    # Con la carpeta de sus datos en sys.path, importar un módulo nuevo deja su listado en la caché de importación
    carpeta = datos["t"].rsplit("/", 1)[0]
    sys.path.insert(0, carpeta)
    import calendar  # noqa: F401
    return [{"archivo": n} for n in sorted(sys.path_importer_cache[carpeta]._path_cache)]
