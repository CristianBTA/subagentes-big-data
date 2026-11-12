# Generador (A y B)
**Etapa:** 2 · Procesamiento · **Parámetros:** Herramienta: A = pandas; B = solo biblioteca estándar.

Dos generadores **independientes** escriben el análisis con herramientas distintas: A con pandas y B con Python puro. Un error propio de una herramienta no se repite en la otra.

## Puede leer
- `spec.json`, el glosario, `perfil.json`, los planes de limpieza con su informe y la capa limpia.

## No puede leer (independencia)
- `reglas.py`, `caso_conocido/`, `sellos.json`, los informes y la implementación del otro generador. La verificación tiene que ser independiente de su código.

## Entrega
- `impl_a.py` o `impl_b.py`, con `analizar(datos) -> list[dict]` (una fila por grupo con las columnas de la salida) y `conciliar(datos)` (filas leídas, usadas, excluidas por motivo y marcadas). Cada conteo es un entero (`len(...)`, `int(...)`): un decimal, un texto, un booleano o un infinito hacen fallar la conciliación.

## Reglas
- Seguir la spec al pie de la letra; si algo parece contradictorio, seguirla igual y anotarlo.
- Usar las marcas `calidad_*` como dice `spec.capa_limpia`: excluir o solo avisar.
- Todo conteo cierra: leídas = usadas + excluidas (R3, R5).
- Funcionar con cualquier dato que tenga las mismas columnas, porque también se corre sobre el caso conocido. Nada de rutas fijas ni de valores escritos a mano.
- Repetible: misma entrada, mismo resultado.

## Nunca
- Leer el criterio ni copiar al otro generador.
- Escribir archivos o usar algo fuera de la lista de librerías.

## Prueba sin IA que lo comprueba
`python herramientas/verificar.py <corrida>`: compuertas antes de ejecutar, caja de arena, reglas, caso conocido, A = B, conciliación, repetibilidad y tiempos.

Además, las [reglas comunes](00-reglas-comunes.md) y la bitácora de su etapa.
