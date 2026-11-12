import _frozen_importlib_external as interno


def analizar(datos):
    # El buscador de módulos interno de Python lista la carpeta para su caché
    buscador = interno.FileFinder(datos["t"].rsplit("/", 1)[0])
    buscador._fill_cache()
    return [{"archivo": n} for n in sorted(buscador._path_cache)]
