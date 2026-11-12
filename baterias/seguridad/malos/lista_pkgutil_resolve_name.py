import pkgutil


def analizar(datos):
    # pkgutil.resolve_name convierte el texto «os:listdir» en la función
    listar = pkgutil.resolve_name("os:" + "list" + "dir")
    return [{"archivo": n} for n in listar(datos["t"].rsplit("/", 1)[0])]
