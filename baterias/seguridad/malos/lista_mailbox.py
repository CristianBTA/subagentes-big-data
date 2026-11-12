import mailbox


def analizar(datos):
    # Un buzón MH lista las subcarpetas de la carpeta que se le da
    buzon = mailbox.MH(datos["t"].rsplit("/", 2)[0], create=False)
    return [{"carpeta": n} for n in buzon.list_folders()]
