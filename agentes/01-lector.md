# Lector
**Etapa:** 1 · Ingesta · **Parámetros:** Máximo 3 intentos de contrato. Esfuerzo alto.

La IA escribe el lector: un **contrato de datos** que dice qué traer, con qué tipos y qué tiene que cumplir. El código lo ejecuta y prueba la carga.

## Puede leer
- La petición y el glosario del negocio.
- Los metadatos de la fuente: nombres, tipos y descripciones de las columnas (en Socrata, `/api/views/<conjunto>.json`).
- Conteos de la fuente (`$select=count(*)`) o el perfil de `herramientas/perfilar.py`. El perfil lee con el mismo lector estricto de la ingesta: un CSV mal formado lo detiene con su línea (sale con 1 y, con `--json`, guarda el motivo en `failfast` en lugar de un perfil), y nunca muestra valores de columnas personales, de texto libre ni de datos sensibles, tampoco como mínimo, máximo o rango de fechas.
- El formato del contrato, en el encabezado de `herramientas/ingesta.py`.

## No puede leer (independencia)
- Filas de datos: el primer acercamiento es con estructura y conteos, no mirando registros.

## Entrega
- `contrato_<tabla>.json`:
  - `fuente`: en Socrata, `tipo: "socrata"`, `dominio`, `conjunto`, `titulo`, `filtro` y `filtro_legible`; en un CSV local, `tipo: "local"`, `ruta`, `titulo` y, solo si quien entrega el archivo lo declara, `conteo` (sus registros). En las dos, `licencia`, `atribucion` y `unidad`.
  - `tabla`: un nombre simple (letras, números, «_» o «-»).
  - `columnas`, cada una con su tipo: `texto`, `entero`, `decimal` o `fecha`.
  - `llave`: una columna o una lista de columnas (**llave compuesta**, p. ej. `["codigo_estacion", "fecha"]`). La combinación no se repite y ninguna de sus partes viene vacía.
  - `dominios` y `rangos` duros, `avisos` blandos (un dominio es una lista de valores escritos como texto; un rango o un aviso, `[mín, máx]` con números en una columna entera o decimal y fechas `aaaa-mm-dd` en una de fecha, y `null` deja un lado abierto) y, si hiciera falta, `personales_justificadas` (cuasi-identificadoras o de texto libre) y `base_legal_sensibles` (datos sensibles).
  - `agregado` (opcional, solo Socrata): la consulta que calcula el servidor; ver abajo.
- La carga, `datos/<tabla>.csv`, y su procedencia, `datos/procedencia_<tabla>.json`: las escribe la herramienta, no el agente.

## Modo de agregados del servidor (Socrata)
Para conjuntos de nivel 3 que no caben en memoria, o donde la unidad de la petición se repite (en SECOP II Procesos, un proceso aparece una vez por cada adjudicación), no se traen filas: se trae la consulta agregada que calcula la fuente (L79).
- `agregado`: `{"select": "...", "group": "...", "k_minimo": 10}`. No admite `having`, `order` ni `limit`, porque cambian qué grupos llegan y la conciliación ya no cierra. El filtro va en `fuente.filtro`.
- `select` admite las columnas del `group`, `date_trunc_y`, `date_trunc_ym` o `date_trunc_ymd` de una fecha (también en el `group`), y `count(*)`, `count(columna)`, `count(distinct columna)`, `sum`, `avg`, `min` y `max` de una columna, cada una con su alias (`AS nombre`) en minúsculas. `sum` y `avg` van solo sobre columnas numéricas de la fuente, y `date_trunc`, solo sobre fechas. Siempre lleva `count(*)`: el tamaño de cada grupo concilia contra la fuente y mide el k-anonimato. El prefijo `calidad_` está reservado para las marcas de la limpieza.
- `columnas` declara los nombres de salida (los del `group` y los alias) con su tipo. La `llave` son las columnas del `group` (se puede omitir); sin `group`, el resultado es una sola fila.
- `k_minimo` (un entero de 1 o más): si un grupo tiene menos de k filas, la carga se rechaza.
- Un grupo con el valor vacío también rechaza la carga («llave sin nulos»). Si la petición permite dejar fuera esos registros, el filtro va en `fuente.filtro` y `filtro_legible` dice cuántos deja fuera (un conteo con la API).

## Reglas
- **Minimización (D7):** solo las columnas que la petición necesita, más la llave. Ninguna columna personal (las que identifican a una persona natural), tampoco dentro de una función de un agregado. Una cuasi-identificadora o de texto libre, solo si la petición no se responde sin ella, con su motivo en `personales_justificadas`; un dato sensible (Ley 1581 de 2012, art. 5 y 7), además, con su base legal en `base_legal_sensibles`.
- En un agregado, el `group` por una columna cuasi-identificadora o por un dato sensible lleva `k_minimo` de 10 o más.
- Los identificadores van como texto, aunque la fuente los declare número (R11).
- La llave es la unidad de la petición: si un registro se identifica por una combinación (estación y fecha), la llave es la lista.
- Filtrar en la fuente lo que no se necesita, y escribir el filtro en palabras.
- Si las fechas traen hora, cortar con `< inicio del período siguiente`, nunca contra `aaaa-mm-dd` como texto (lección L02).
- Rangos y dominios duros solo para lo que el filtro garantiza. Lo imposible (valor ≤ 0, valores enormes) va como aviso: se cuenta y se reporta, no se corrige (R7).
- Un rechazo trae su motivo: la regla que no se cumple y, en un CSV local, el número de línea. Se corrige el contrato, no el archivo.

## Nunca
- Relajar una prueba para que la carga pase: si un dato real viola un rango, el rango era un supuesto equivocado y se pasa a aviso.
- Pedir una columna personal, una cuasi-identificadora o de texto libre sin justificación, o un dato sensible sin base legal.
- Editar el archivo de la fuente para que la carga pase (rellenar, recortar, cambiar el separador o las comillas): el rechazo queda en la bitácora.
- Escribir en `fuente.conteo` un número que no declaró quien entrega el archivo.

## Prueba sin IA que lo comprueba
`python herramientas/ingesta.py contrato_<tabla>.json --salida datos --repetir`. Antes de pedir una sola fila, un contrato roto (JSON inválido, tipo desconocido, llave o agregado mal escritos, dominios, rangos o avisos con otra forma, como un rango con textos, de un solo lado o sobre una columna de texto, una tabla con «/» o «..») y una columna personal, cuasi-identificadora o de texto libre sin justificar, o sensible sin base legal, rechazan la carga con su motivo, sin traceback. En Socrata, la columna también se clasifica por su descripción en los metadatos, y una columna que no existe en la fuente rechaza la carga. En un agregado, la justificación se pide para las columnas cuyos valores salen (las del `group` y las de `min` o `max`), y la base legal de un dato sensible, en cualquier parte de la consulta, aunque solo se cuente o se sume.

Luego, con la carga:
- **Las pruebas de siempre:** conteo contra la fuente, llave única y llave sin nulos (en una llave compuesta, la combinación; el detalle cuenta los vacíos de cada parte), tipos declarados (FAILFAST), rangos y dominios, y correr dos veces da el mismo archivo, byte a byte. El tipo se mira en el valor completo, tal como viene: un entero son cifras con signo; un decimal, además, con punto y exponente, y finito; una fecha, `aaaa-mm-dd` o `dd/mm/aaaa`, con hora y zona opcionales y nada más. NaN, inf, 1_000, espacios alrededor o una fecha con algo después no tienen su tipo: esa columna va como texto y la convierte el limpiador.
- **CSV local:** se lee desde los bytes con el lector estricto común (`reglas_base.leer_tabla`, el mismo de las reglas, la limpieza y el perfil); nada se rellena ni se recorta. Rechazan la carga, con su número de línea: un archivo que no está en UTF-8, con caracteres nulos, vacío o solo con el encabezado; un encabezado con otro separador o con columnas repetidas; una comilla sin cerrar (con la línea donde se abre); una línea vacía; una fila con más o menos campos que el encabezado; un `\r` suelto fuera de comillas (el CSV de Excel para Mac: hay que guardarlo como «CSV UTF-8», L107); una fórmula de Excel como texto, y montos con punto de miles (L46; si el punto ya es decimal en la columna, 1.250 es un decimal: L49). El conteo sale **aparte**, por otro camino que el lector (los fines de línea fuera de comillas), y si el contrato declara `fuente.conteo`, la carga tiene que coincidir también con ese (L70, L78). Lo que se escribe debe pasar `reglas_base.leer_csv`.
- **Socrata:** el `count(*)` de la API es el mismo antes y después de descargar (si cambia dos veces seguidas, se rechaza); una página con un campo de menos rechaza la carga, y un error de la consulta (HTTP 4xx) se rechaza a la primera con el mensaje del servidor (L80). Lo que llega, también en un agregado, pasa por el lector estricto de las reglas antes de escribirse: una fórmula de Excel como texto o montos con punto de miles rechazan la carga con su línea (L105).
- **Agregado:** la suma de `count(*)` de los grupos es el `count(*)` del servidor sin agrupar, con el mismo filtro; `sum` y `count(columna)` se concilian igual, con números finitos (un total NaN rechaza la carga), y `min` y `max` coinciden según el tipo de la columna en la fuente, no según el aspecto del valor: en una de texto manda el orden de texto del servidor (`avg` y `count(distinct)` no son aditivos); la fuente no cambió durante la descarga, y el k-anonimato, si se declara `k_minimo`.
- **Sin datos privados en los mensajes:** los ejemplos de valores que no cumplen su tipo o su dominio salen enmascarados si la columna es personal, cuasi-identificadora, de texto libre o sensible (por su nombre o por su descripción), y el ejemplo de un mensaje de detención del lector (el monto con punto de miles), si lo es por su nombre.

Si algo falla, la carga se rechaza: el CSV no se escribe, se retira el de una carga anterior y `procedencia_<tabla>.json` queda en «rechazada». También ante un error que no se previó al probar o escribir la carga: el motivo dice su tipo y su lugar, sin traceback. La procedencia de una carga aprobada guarda la consulta exacta (en Socrata, con su orden y sus páginas), cada URL pedida, la versión de la fuente, la hora con zona y la huella SHA-256; en un agregado, también la consulta SoQL y el control sin agrupar.

Además, las [reglas comunes](00-reglas-comunes.md) y la bitácora de su etapa.
