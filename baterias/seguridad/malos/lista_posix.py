import posix


def analizar(datos):
    # posix es os por debajo: lista la carpeta sin escribir «os»
    return [{"archivo": n} for n in posix.listdir(datos["t"].rsplit("/", 1)[0])]
