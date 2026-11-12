# Limpiador
**Etapa:** 2 · Procesamiento · **Parámetros:** Esfuerzo alto.

La IA propone la limpieza; `herramientas/limpieza.py` la ejecuta igual cada vez y la prueba. Del dato crudo sale la **capa limpia**, con las mismas filas y una marca por cada problema.

## Puede leer
- `spec.json` (tratamiento de los datos), `perfil.json`, las lecciones y el formato del plan, en el encabezado de `herramientas/limpieza.py`.
- `perfil.json` lo escribe `perfilar.py` con el lector estricto común: si trae `failfast` en lugar del perfil, el CSV crudo no se pudo leer (el motivo dice la línea) y no hay plan que lo arregle; se anota en la bitácora y la etapa no se aprueba.

## No puede leer (independencia)
- Las implementaciones, el caso conocido y las reglas.

## Entrega
- `plan_limpieza_<tabla>.json`:
  - `tabla` (de su nombre sale el informe, `limpieza_<tabla>.json`), `entrada` (el CSV crudo ingerido) y `salida` (`limpio/<tabla>.csv`), relativas a la carpeta del plan.
  - `llave`: una columna o una lista de columnas (**llave compuesta**): la prueba de orden compara la combinación.
  - `operaciones`, en orden: `texto` (recorte, invisibles, Unicode NFC, espacios internos y, si se pide, mayúsculas), `reemplazar`, `nulos_disfrazados`, `mapear`, `fecha`, `numero`, `rango`, `atipicos`, `repetidos` (con su `desempate`) y `comparar`.
  - `umbrales`: `completitud_minima`, `validez_minima`, `unicidad`, `marcadas_maximo` y `vacios_maximo`. Dentro de `umbrales`, una clave que empieza con «_» es una nota y no se evalúa.
  - `umbrales_caso` (opcional): ver las reglas.
- La actualización de `spec.json`: `datos_crudos`, `datos` (la capa limpia) y `capa_limpia` (qué significa cada marca y si excluye la fila o solo avisa).

## Reglas
- **Limpiar es marcar (R14):** nada se borra. Cada problema queda en `calidad_<marca>` y `calidad_ok` dice si la fila está limpia.
- Los mapas de variantes van completos, como lista cerrada; lo que quede fuera se marca, no se adivina.
- Los nulos disfrazados («No Definido», «N/A», «-») se vuelven vacío y se marcan.
- Se quitan los caracteres invisibles y se normaliza a Unicode NFC.
- Atípicos y valores imposibles se marcan con un método explícito (rango intercuartílico sobre log10); no se corrigen (R7).
- Una llave repetida con valores distintos no se resuelve por el orden del archivo ni descartando filas: la operación `repetidos` declara `desempate` (columna y `conservar`: `ultimo` o `primero`; por ejemplo, la `fecha_actualizacion` más reciente) y las demás filas quedan marcadas, no se borran. Si la limpieza avisa que faltó el desempate o que hubo empates, el plan se corrige.
- Los montos se leen con su decimal declarado: con `numero` y decimal «.», montos con punto de miles mezclados con números sin separador (78.000 junto a 1628100) detienen la limpieza, porque se leerían divididos por mil (L46; si el punto ya es decimal en la columna, como 12.5, 1.250 es un decimal: L49); con decimal «,», 1.250,50 se convierte y cada punto tiene que agrupar tres cifras: 12.5 o 1,234.5 se marcan `numero_invalido`, no se leen como 125 o 1.2345 (L108). El decimal es «.» o «,» (otro detiene la limpieza), y con los dos solo valen cifras ASCII: 1_000, «٣» o Infinity se marcan aunque `float()` los acepte.
- **Los umbrales se justifican sobre el dato real (L75).** Un umbral relativo pensado para el caso conocido deja perder miles de filas en el dato real sin que nada falle. Lo que no debería faltar va en `vacios_maximo`, en conteos absolutos: cuenta las celdas vacías después de limpiar, también las de un nulo disfrazado que se vació. El detalle de completitud y validez dice la **holgura**, cuántas filas (o valores) más puede perder el dato antes de que el umbral bloquee: una holgura de miles es un umbral que no protege nada.
- **El caso conocido pasa por el mismo plan y con los mismos umbrales:** `verificar.py` lo limpia con `umbrales`, los del dato real. Si el caso incumple un umbral a propósito (trae vacíos o repetidos), primero un conteo absoluto que cumplan los dos (`vacios_maximo`, `marcadas_maximo`); aflojar el umbral del dato real es el último recurso y se anota por qué.
- **`umbrales_caso`** son los umbrales del caso conocido. La limpieza los revisa siempre: cada uno tiene que estar también en `umbrales` y ser igual o más laxo (el caso no exige más que el dato real); si no, se detiene. Solo se aplican cuando quien llama lo pide (`limpiar(..., caso=True)`, con la entrada del caso), nunca desde la línea de comandos ni sobre la entrada del plan. Hoy `verificar.py` no lo pide: no sirven para que el caso conocido pase.
- **Un umbral mal escrito detiene la limpieza (L76):** un nombre desconocido (`completitud_minimo`), una columna que no existe o una marca que ninguna operación pone. En `marcadas_maximo` va el nombre exacto de la marca: la que declara la operación o la que pone por defecto (`nulo_disfrazado_<columna>`, `fuera_de_mapa_<columna>`, `fecha_invalida_<columna>`, `numero_invalido_<columna>`, `repetido` y `formula_neutralizada`).

## Nunca
- Tocar el dato crudo.
- Borrar filas.
- Ajustar un umbral sin anotar por qué: si el dato real lo incumple, el umbral era un supuesto y se escribe en la bitácora.

## Prueba sin IA que lo comprueba
`python herramientas/limpieza.py plan_limpieza_<tabla>.json` (las rutas del plan son relativas a su carpeta).
- **Lectura FAILFAST, con el número de línea:** la limpieza lee el crudo con el mismo lector estricto de la ingesta, las reglas y el perfil (`reglas_base.leer_tabla`). Un archivo que no está en UTF-8, vacío o sin encabezado, con otro separador o columnas repetidas, una comilla sin cerrar, una línea vacía, una fila con más o menos campos que el encabezado o un `\r` suelto fuera de comillas (el CSV de Excel para Mac) la detienen; también las columnas crudas con el prefijo `calidad_`. Nunca se lee a medias. Una fórmula de Excel como texto no la detiene: se neutraliza (se le antepone «'») y se marca `formula_neutralizada`.
- **Las pruebas del plan:** mismas filas antes y después, dato crudo intacto (huella), llave y orden conservados (en una llave compuesta, la combinación), completitud y validez antes y después con el mismo tipo (2025-02-30 no es una fecha válida) y los umbrales, con su holgura (completitud y validez se comparan con los conteos enteros, no con la proporción redondeada: L110). Un umbral que no se puede evaluar (también uno de otro tipo: completitud y validez entre 0 y 1, los máximos enteros ≥ 0, unicidad una lista) detiene la limpieza con «FAILFAST» y su motivo.
- **Ejemplos sin datos privados:** cada operación informa cuántas filas cambió y cuántas marcó, con ejemplos; los de una columna personal, de texto libre o con un dato sensible salen enmascarados, y un valor con forma de instrucción para una IA se omite. El ejemplo de un mensaje de detención (el monto con punto de miles) sale enmascarado si la columna es personal, cuasi-identificadora, de texto libre o sensible.
- El caso conocido pasa por el mismo plan dentro de `verificar.py`, con `umbrales`.
- **Rechazo que detiene:** la capa limpia se escribe solo si la limpieza se aprueba. Si queda rechazada o se detiene, la capa limpia de una limpieza anterior se retira y `limpieza_<tabla>.json` queda en «rechazada», con su motivo; `verificar.py` deja la corrida en «revisar» con una limpieza sin aprobar o con una capa limpia que no tiene la huella de su informe. Tu «ok» no la reemplaza (L109). La salida es un `.csv` que no es la entrada, y la tabla, un nombre simple.

Además, las [reglas comunes](00-reglas-comunes.md) y la bitácora de su etapa.
