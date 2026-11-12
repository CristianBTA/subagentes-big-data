# Directrices de análisis de datos con IA

> Los parámetros de cada subagente (rol, qué puede leer y qué no, qué entrega, reglas, lo que nunca hace y la prueba que lo comprueba) están en [`agentes/`](agentes/README.md).

Estas son las directrices que un analista de datos senior le exige a un análisis hecho con IA antes de firmar una cifra. Cada una dice **qué exige**, **por qué**, **dónde está aplicada** en este repositorio y **cómo se comprueba**. Sirven para validar este trabajo y para revisar cualquier otro.

El principio que las ordena todas: **la IA propone y una prueba sin IA comprueba.** La IA acorta el tiempo de cada etapa, pero no reemplaza ninguna. Por eso cada etapa tiene su prueba, y la prueba no la escribe quien escribe el código.

---

## Validar este repositorio en 15 minutos

Se necesita macOS o Linux con Python 3.13. La caja de arena usa `sandbox-exec`, que trae macOS; en Linux el código corre igual, pero sin esa capa. En macOS, usa el Python 3.13 de Homebrew o, si es el del instalador de python.org, corre antes una vez «Install Certificates.command» (en la carpeta de Python 3.13, dentro de Aplicaciones): ese Python no trae los certificados raíz, y la ingesta (el paso 6), el agente masivo y la vigilancia de dependencias se detienen con «certificado no verificado» en vez de consultar datos.gov.co.

```bash
python3.13 -m venv .venv && .venv/bin/pip install --require-hashes -r requirements.txt
T=$(mktemp -d)   # verificar una corrida reescribe sus informes: los pasos 2, 3, 5 y 6 trabajan en una copia y el clon no cambia

# 1. Las baterías (hoy 10): seguridad (código malo bloqueado y bueno aceptado), privacidad, FAILFAST, inyección,
#    cruces, fechas, repetidos, factor de expansión, gráfico y lecciones
.venv/bin/python herramientas/baterias.py

# 2. La corrida sellada del ejemplo sintético se vuelve a verificar desde cero (sin IA), en la copia
cp -R corridas/2026-11-06-ventas-semestre "$T"/
.venv/bin/python herramientas/verificar.py "$T"/2026-11-06-ventas-semestre

# 3. Probar al probador: cada mutante comete un error típico y el criterio debe atraparlo
ls evidencia/sintetico/mutantes/*.py | sed 's#.*/\(.*\)\.py#\1=&#' | \
  xargs .venv/bin/python herramientas/verificar.py "$T"/2026-11-06-ventas-semestre --impl

# 4. El oráculo del ejemplo sintético se rehace igual (semilla fija; los dos caminos deben coincidir)
.venv/bin/python evidencia/sintetico/generar_datos.py /tmp/datos-prueba /tmp/verdad-prueba.json
cmp /tmp/datos-prueba/ventas.csv ejemplo/datos/ventas.csv && echo "datos idénticos"

# 5. Gobernanza de una corrida (la copia del paso 2): datos personales, salidas limpias, k-anonimato
.venv/bin/python herramientas/gobernanza.py "$T"/2026-11-06-ventas-semestre

# 5b. Blindaje: se ataca cada capa a propósito (caja de arena, compuerta, perfil, salidas, integridad, dependencias, fichas)
.venv/bin/python herramientas/blindaje.py
# y cada control con su prueba: se quita en una copia y la prueba que lo cubre debe ceder (36 mutantes)
.venv/bin/python herramientas/mutar_controles.py

# 5c. SGSI: la tríada C·I·D, los riesgos y la Declaración de Aplicabilidad, comprobados sin IA (y el probador, probado)
.venv/bin/python herramientas/sgsi.py --autoprueba
.venv/bin/python herramientas/sgsi.py --efectividad

# 5d. Probar al probador de la presentación: 5 presentaciones buenas aprueban y 91 mutantes (número a mano, marcadores pegados, NaN, un «donde» mal escrito, título de tema, recomendación escondida, campos de la forma anterior…) fallan
.venv/bin/python herramientas/verificar_presentacion.py --autoprueba

# 5e. Probar al probador del whitepaper (89 casos: conclusiones, también con énfasis o letras disfrazadas, cifras sin respaldo, con espacios o con palabras, texto oculto, procedencias de otra carpeta…) y su versión en tres hojas carta (36 casos, sin Chrome, con el PDF que el informe final enlaza solo si tiene tres hojas carta)
.venv/bin/python herramientas/validar_whitepaper.py --autoprueba
.venv/bin/python herramientas/whitepaper_corrida.py --autoprueba

# 6. (Opcional, con red) SECOP II: los datos no vienen en el repositorio; se descargan con su contrato y se prueban al cargar
.venv/bin/python herramientas/ingesta.py ejemplo-secop/contrato_recorte_2024-2026.json --salida ejemplo-secop/datos --repetir
cp -R corridas/2026-11-06-secop-medellin-2025 "$T"/
.venv/bin/python herramientas/verificar.py "$T"/2026-11-06-secop-medellin-2025

# 7. El clon quedó igual: no debe salir nada
git status --short
```

SECOP II se actualiza a diario. Si el recorte de hoy no es idéntico al del 6-nov-2026, el paso 6 puede dar otras cifras: es lo esperado, y la procedencia de la carga dice qué cambió (filas, huella). Esas cifras quedan en la copia: el informe publicado de la corrida no cambia.

Si corriste los pasos sobre `corridas/` directamente (como decía una versión anterior de esta guía), `git status` muestra `informe.json`, `informe.md` y `gobernanza.json` modificados, con el tiempo medido y la ruta de tu carpeta; `git restore corridas/` los deja como estaban. Nunca entran en un aporte.

Lo que debe salir: todas las baterías en ✓ (hoy son 10), el blindaje con todas sus pruebas en «RESISTE» (hoy son 39, con el control B00; en Linux no hay sandbox-exec: B01, B11, B12, B24 y B29 salen «NO APLICA» y el banco lo dice, porque ahí el código de la IA tendría red y escritura; por eso el filtro de aportes corre en macOS) y sus 36 mutantes de los controles muertos, la corrida en «aprobado», la referencia `m00` sin fallas y las mutantes `m01` a `m13` con al menos una falla cada una, los datos idénticos, la gobernanza aprobada, el SGSI sin fallas, con sus 21 mutantes atrapados, las autopruebas de la presentación y del whitepaper sin fallas ni errores, y `git status` sin ningún archivo. Si algo no sale así, el repositorio no cumple lo que dice.

---

## A · Antes de escribir código

**D1 · La pregunta se convierte en una especificación verificable.**
Qué cifra sale, qué incluye y qué excluye, en qué unidades y período, con qué columnas y en qué forma.
*Por qué:* una petición de una frase admite varias cifras correctas, y la IA escoge una sin avisar.
*Dónde:* `spec.json` de cada corrida (`interpretacion`, `definiciones`, `salida`).
*Cómo se comprueba:* cada definición dice su fuente (`glosario`, `datos` o `supuesto`).

**D2 · El glosario del negocio manda; lo que no resuelve se pregunta.**
Toda decisión que cambie la cifra y no salga del glosario ni de los datos se escribe como pregunta, con su valor por defecto y su impacto en pesos.
*Por qué:* lo que la IA no sabe, lo inventa. Los datos no dicen si el Concejo es una entidad aparte del Distrito.
*Dónde:* `ejemplo/negocio.md` y `ejemplo-secop/negocio.md`; `preguntas` y `supuestos` en la spec.
*Cómo se comprueba:* la corrida de SECOP abrió dos preguntas (el NIT que agrupa al Concejo y la Personería, y la universidad privada), cada una con su cifra.

**D3 · Conocer los datos antes de pedir código: perfil completo, determinista y sin filas.**
*Por qué:* explorar quita que la IA invente la **estructura** (columnas, tipos, formatos), pero no el **significado** (D2). Los problemas son raros y no salen en `head()`: 6 códigos vacíos en 1.520 filas, o 5 contratos del 31 de diciembre con hora.
*Dónde:* `herramientas/perfilar.py`: formatos mezclados, fechas ambiguas con su lectura demostrada, filas repetidas, claves repetidas, variantes de escritura, códigos que no cruzan, un código con varios nombres y fechas con hora. Lee con el lector estricto común de la ingesta y la limpieza: un CSV mal formado lo detiene con su línea, nunca se perfila a medias (L93). Nunca muestra valores de columnas personales, de texto libre ni de datos sensibles (Ley 1581, art. 5 y 7): tampoco como mínimo o máximo, en el rango de fechas ni entre los ejemplos que no cruzan (L94).
*Cómo se comprueba:* `herramientas/baterias.py` (baterías de privacidad y FAILFAST) y el blindaje (B32, B33).

**D4 · Anticipar el número antes de ejecutar.**
Un rango de magnitud, escrito antes de tener la cifra.
*Por qué:* un error de unidades o de unión salta a la vista si ya había una expectativa.
*Dónde:* `anticipo` en la spec; el informe dice si el resultado quedó dentro.

## B · Ingesta

**D5 · Contrato de datos: columnas mínimas, tipos declarados, llave, dominios y rangos.**
Los identificadores van como texto. Lo que no cumple el tipo rechaza la carga (FAILFAST), mirado en el texto completo, tal como viene: NaN, inf, 1_000, « 5 » o una fecha con algo después no tienen su tipo, aunque `float()` o un recorte los acepten (L104). La llave es una columna o una lista de columnas (llave compuesta, como estación y fecha): la combinación no se repite y ninguna de sus partes viene vacía.
Un CSV local se lee desde los bytes con el lector estricto común de las reglas, la limpieza y el perfil, y nada se rellena ni se recorta: un archivo que no está en UTF-8, con caracteres nulos o solo con el encabezado, otro separador, columnas repetidas, una comilla sin cerrar, una línea vacía, una fila con más o menos campos, un `\r` suelto fuera de comillas (el CSV de Excel para Mac), una fórmula de Excel como texto o montos con punto de miles rechazan la carga con su número de línea (L70, L78, L107). Los dos lectores de las reglas (`leer_csv` y `recorrer_csv`) parten las líneas igual, solo en `\n`, y detienen lo mismo (L107). Lo que llega de Socrata o de un agregado pasa por el mismo lector antes de escribirse, porque las reglas leen el crudo con él (L105).
Para conjuntos de nivel 3 que no caben en memoria, el contrato pide la consulta agregada que calcula el servidor (`agregado`): con `count(*)`, sin `having`, `order` ni `limit`, y con `k_minimo` si se declara: ningún grupo con menos de k filas (L79).
*Dónde:* `contrato_<tabla>.json` (lo escribe la IA con su ficha, [`agentes/01-lector.md`](agentes/01-lector.md)) y `herramientas/ingesta.py` (lo ejecuta).
*Cómo se comprueba:* `herramientas/ingesta.py --autoprueba`, con casos ficticios y sin red, y la batería FAILFAST. Un contrato roto (también con dominios, rangos o avisos de otra forma: un rango con textos, de un solo lado o sobre una columna de texto), una columna que no existe en la fuente o una columna personal sin justificar rechazan la carga antes de descargar filas, y un error que no se previó al probarla también la rechaza: nunca queda la carga anterior en «aprobada» (L103). Los ejemplos de valores que no cumplen su tipo o su dominio salen enmascarados si la columna es personal, cuasi-identificadora, de texto libre o sensible.

**D6 · Las cinco pruebas de cada carga, más repetibilidad y procedencia.**
Conteo contra la fuente, llave única, llave sin nulos, rangos y dominios. El conteo no lo da el mismo lector que se prueba: en Socrata es el `count(*)` de la API, igual antes y después de descargar; en un CSV local se cuenta aparte, por otro camino (los fines de línea fuera de comillas), y también contra el `fuente.conteo` del contrato, si quien entrega el archivo lo declara. En un agregado, la suma de `count(*)` de los grupos es el `count(*)` del servidor sin agrupar con el mismo filtro, `sum` y `count` se concilian igual, con números finitos, y `min` y `max` coinciden según el tipo de la columna en la fuente (en una de texto, con el orden de texto del servidor; L106). Leer dos veces debe dar el mismo archivo, byte a byte. Queda una procedencia con fecha y zona horaria, la consulta exacta (en Socrata, con su orden y sus páginas; en un agregado, la consulta SoQL y el control sin agrupar), la versión de la fuente, filas, huella SHA-256 completa, licencia y atribución.
Cada tabla tiene su procedencia, y la etapa se aprueba solo si todas lo están. Una carga rechazada no deja su CSV donde lo leen las etapas siguientes, y `verificar.py` comprueba que la huella del crudo sea la de su procedencia.
*Dónde:* `procedencia_<tabla>.json`, que se publica (no trae filas).

**D7 · Minimización: que un dato sea público no lo vuelve de uso libre.**
Solo se descargan las columnas que la pregunta necesita. Sin una justificación escrita en el contrato de datos no entra ninguna columna:
- personal: nombres de personas, documentos, datos bancarios o domicilios;
- cuasi-identificadora: tipo de documento, género, edad, nacionalidad o ubicación;
- de texto libre: el objeto, la descripción del proceso, las observaciones o los comentarios;
- sensible (Ley 1581, art. 5 y 7): origen étnico, salud o discapacidad, vida sexual, biométricos, convicciones o menores de edad. Además de la justificación, el contrato registra la base legal (`base_legal_sensibles`).

La columna se clasifica por su nombre y, en Socrata, también por su descripción en los metadatos.
*Por qué:* SECOP II publica la cédula de los contratistas, sus cuentas bancarias y los nombres de supervisores y ordenadores del gasto para la transparencia de la contratación. Eso no autoriza cualquier otro uso: todo tratamiento sigue sujeto a los principios de la Ley 1581 de 2012 (finalidad, circulación restringida, seguridad). Además, el texto libre trae nombres o cédulas escritos a mano en cerca de 1 de cada 1.000 filas. Lo que no se descarga no se filtra.
*Cómo se comprueba:* `baterias/privacidad/columnas_secop.json` fija la clase esperada de 78 columnas de SECOP II y de nombres genéricos (29 personales, 13 cuasi-identificadoras, 2 de texto libre, 19 sin marca, 8 datos sensibles y 7 que se clasifican por su descripción); si el clasificador cambia, la batería falla. La ingesta rechaza el contrato que pide una de esas columnas sin justificación (o sin base legal, si es sensible), y la gobernanza marca «revisar» si el resultado publica una clave que identifica a personas. Los CSV de este repositorio solo traen valores ficticios: lo que el clasificador marca como personal en ellos es inventado (empresas `Distribuidora 001 S.A.S.`, facturas `FV-001022`, `Persona Ficticia Uno`).

## C · Procesamiento

**D8 · El criterio se escribe antes y aparte del código, y se sella.**
Las reglas y el caso conocido los escribe un agente que no escribe el código; otro agente los revisa y los sella con huellas SHA-256. Cambiar el criterio después invalida la aprobación.
*Dónde:* `reglas.py`, `caso_conocido/`, `sellos.json`; la constancia de un sello rehecho está en `historial/NOTA-SELLOS.md`.

**D9 · Las reglas son más simples que el análisis y no comparten su lógica.**
La conservación compara el total del resultado con un total sacado directo de la fuente, sin unir tablas. Las reglas usan solo la biblioteca estándar, así una trampa de pandas no se cuela en el criterio.
*Cómo se comprueba:* la regla de conservación atrapó un error real de pandas, `dayfirst=True` (lección L01), sin que nadie leyera el código.

**D10 · Caso con respuesta conocida que contenga cada borde.**
Fechas límite (00:00 del 1 de enero, 23:59 del 31 de diciembre), repetidos, vacíos, variantes de escritura y códigos que no cruzan.
*Cómo se comprueba:* en SECOP, el error de zona horaria no cambia nada en los datos de hoy, pero el caso conocido lo atrapa. Protege contra datos que todavía no han llegado.

**D11 · Dos implementaciones independientes, con herramientas distintas, que deben dar lo mismo.**
pandas y Python puro. Un error propio de una herramienta no se repite en la otra.
Que concuerden no basta: cada valor de la salida tiene que ser un número finito. Un infinito, un «NaN» o un «1e400» en texto, un entero que no cabe en un float o una suma que desborda detienen la corrida, aunque A y B den lo mismo (inf menos inf no supera la tolerancia) y la conservación no mire esa columna (B31, L92).

**D12 · Todo conteo cierra; limpiar es marcar.**
Cada implementación concilia: filas leídas = usadas + excluidas por motivo. Nada se borra en silencio. La conciliación no se autodeclara: el verificador cuenta las filas reales de la entrada (y las compara con las de la procedencia), en los datos reales y en el caso conocido, y A y B deben conciliar igual motivo por motivo (B25, L82). Cada conteo es un número entero (un `int`, o un decimal sin parte decimal como 1520.0): 1520,9, «1520» en texto, un booleano o un infinito son un motivo, no se truncan ni tumban el verificador (B25, L112).
*Dónde:* `conciliar(datos)` en `impl_a.py` e `impl_b.py`; tabla de conciliación en el informe.
*Por qué:* quitar «duplicados» por (entidad, valor, fecha) borró 25.824 contratos legítimos en una de las mutantes (lección L08).

**D13 · Repetible.** Misma entrada, mismo resultado. El verificador corre cada implementación dos veces.

**D14 · Probar al probador.**
Un criterio vale lo que atrapa. Se mide con mutantes, que son la referencia con un solo error típico, y la referencia sin errores no debe dar falsas alarmas.
*Cómo se comprueba:* `evidencia/*/resultados_mutacion.txt`: 12 de 12 en el ejemplo sintético y 11 de 11 en SECOP, sin falsas alarmas. En el sintético, además, `m13_lee_oraculo` prueba al verificador: una implementación que busca el `esperado.json` del caso conocido junto a sus datos no lo ve y queda atrapada.

## C2 · Limpieza de datos (dentro del procesamiento)

La IA propone el plan de limpieza (`plan_limpieza_<tabla>.json`) y `herramientas/limpieza.py` lo ejecuta igual cada vez. Ficha del subagente: [`agentes/03-limpiador.md`](agentes/03-limpiador.md).

**DL1 · Tres capas: cruda, limpia y respuesta.** El dato crudo no se toca y conserva su procedencia y su huella. La capa limpia (`limpio/<tabla>.csv`) se reconstruye desde el plan. La respuesta se calcula sobre la capa limpia.
*Cómo se comprueba:* la limpieza verifica que la huella del crudo no cambió.

**DL2 · Limpiar es marcar (R14).** La capa limpia tiene las mismas filas, en el mismo orden y con la misma llave (una columna o, si es compuesta, la combinación). Cada problema queda en una columna `calidad_<marca>`, y `calidad_ok` dice si la fila está limpia. La spec decide qué marcas excluyen la fila del análisis y cuáles solo avisan, y la conciliación las cuenta.

**DL3 · Reglas declaradas, no código suelto.** Cada operación (texto, invisibles y Unicode NFC, reemplazar, nulos disfrazados, mapear, fecha, número, rango, atípicos, repetidos, comparar entre columnas) informa cuántas filas cambió, cuántas marcó y sus ejemplos: los de una columna personal, de texto libre o con un dato sensible salen enmascarados, y un valor con forma de instrucción se omite. Los mapas de variantes son listas cerradas y versionadas: lo que no está en el mapa se marca, no se adivina. La operación número mira la forma completa del valor con su decimal declarado («.» o «,», solo cifras ASCII): con «,», 12.5 o 1,234.5 se marcan en vez de leerse como 125 o 1.2345 (L108). El crudo se lee con el lector estricto común de la ingesta, las reglas y el perfil: un CSV mal formado detiene la limpieza con su número de línea, y una fórmula de Excel como texto no la detiene, se neutraliza y se marca (DB5).

**DL4 · Lo disfrazado y lo invisible también se limpia.** «No Definido», «N/A» o «-» son nulos disfrazados. Los caracteres de control (en SECOP apareció un U+0096 dentro de un nombre) se quitan, y el texto se normaliza a NFC antes de comparar.

**DL5 · Atípicos e imposibles se marcan con un método explícito.** El método es el rango intercuartílico sobre log10, para montos que abarcan varios órdenes de magnitud. Nada se corrige en silencio (R7). Los límites quedan en el informe, en pesos.

**DL6 · Calidad medida antes y después, con umbrales que bloquean.** Completitud, validez y unicidad por columna, filas marcadas por marca y celdas vacías en conteos absolutos (`vacios_maximo`). Los umbrales se justifican sobre el dato real: uno relativo pensado para el caso conocido dejaba perder 1.987 contratos en las 49.662 filas de SECOP sin que nada fallara, y el detalle de completitud y validez dice la holgura, cuántas filas más puede perder el dato antes de bloquear (L75). Completitud y validez se comparan con los conteos enteros y el umbral tal como se escribió, nunca con la proporción redondeada: redondeada a 6 decimales, 2.969.999 de 3.000.000 pasaba 0,99 (L110). Un umbral mal escrito (un nombre desconocido, una columna o una marca que no existen, o un valor de otro tipo: completitud y validez entre 0 y 1, los máximos enteros ≥ 0, unicidad una lista) detiene la limpieza (L76, L109). Los umbrales del caso conocido (`umbrales_caso`) nunca exigen más que los del dato real y solo se aplican si quien llama lo pide: `verificar.py` limpia el caso conocido con los del dato real. Un umbral que el dato real incumple no se relaja en silencio: o el umbral era un supuesto equivocado (se anota) o el dato no sirve para la pregunta. Y una limpieza rechazada detiene, sin IA: La capa limpia se escribe solo si la limpieza se aprueba; una rechazada o detenida (FAILFAST, un plan que no se puede ejecutar o un error que no se previó) retira la capa limpia de la anterior y deja `limpieza_<tabla>.json` en «rechazada», con su motivo y sin traceback. `verificar.py` deja la corrida en «revisar» si la limpieza de una tabla de la spec no está aprobada o si la capa limpia no tiene la huella de su informe, y el informe final no da el ✅ del procesamiento: el «ok» del limpiador no es la compuerta (B39, L109).

**DL7 · Una limpieza mal planteada también se atrapa.** Las reglas y el caso conocido calculan desde el dato **crudo**, y el caso conocido pasa por el **mismo** plan antes de la implementación. Una regla de limpieza mal escrita (por ejemplo, «IVA mayor que el subtotal», que marcó 1.150 filas en una prueba) aparece en el conteo de marcas y en la conservación.

## D · Análisis

**D15 · El análisis lo hacen las personas; la IA solo documenta lo desarrollado.**
Desde el 6-nov-2026 la IA no propone ni prueba hipótesis ni da el análisis. El documentador escribe un whitepaper con la pregunta, los datos y su procedencia, la limpieza, la cifra verificada y cómo se verificó, el gráfico, la gobernanza, los límites y preguntas de costo, calidad e impacto, sin conclusiones. Las personas escriben su hipótesis antes de mirar, la prueban con una consulta (pueden usar `herramientas/verificar_hipotesis.py`, que la sella) y concluyen en la plantilla. Trabajan en una carpeta propia que arma `verificar_hipotesis.py --preparar`, con solo el `spec.json` de la corrida y la plantilla: una copia entera de la corrida les heredaba las hipótesis de la IA de antes del 6-nov y su sello, que veían antes de escribir la suya y que no las dejaba sellar. En `analisis/`, git no sube `datos/`, `limpio/` ni ningún CSV (L120).
*Dónde:* `agentes/13-documentador.md`, `whitepaper.md` de cada corrida, `herramientas/validar_whitepaper.py` (y `herramientas/whitepaper_corrida.py`, que lo maqueta en tres hojas carta sin cambiar una palabra y sin enlaces en el PDF, L84; el informe final mide ese PDF y lo enlaza solo si tiene tres hojas carta sin enlaces: con más, no lo enlaza y el análisis no queda aprobado, L113) y `plantillas/analisis_humano.md`; las fichas del proponente y del probador, en `historial/agentes-retirados/`.
*Cómo se comprueba:* `validar_whitepaper.py`: secciones obligatorias, cada cifra en los artefactos verificados (con tolerancia de redondeo, con dígitos y en formato colombiano: agrupada con espacios, pegada a letras, con palabras o en el destino de un enlace que no es un archivo no pasa, L119), sin conclusiones, recomendaciones ni causas, al menos tres preguntas y sin instrucciones ni datos personales; `--autoprueba` con whitepapers buenos y malos. Las frases de análisis se buscan con **una sola lista** (`ANALISIS`, en `validar_whitepaper.py`), la que importan también la presentación, el gráfico, las fichas del agente masivo y el resumen de su whitepaper; las frases de prueba (`FRASES_D15`) las prueban las autopruebas del whitepaper, de la presentación y de las fichas. Todos la buscan con `buscar_d15`: en el texto tal cual y en como lo lee una persona, así el énfasis de Markdown («Esto \*demuestra\* que», «se \*\*recomienda\*\*»), las letras de ancho completo y las de otro alfabeto que se leen como latinas (la «o» cirílica) no esconden una frase; una palabra que mezcla letras latinas con esas letras no pasa W5 ni la presentación, y el maquetado del whitepaper busca la lista en lo que imprime (L117). Cada frase que una ficha o el encargo de las fichas le nombran a la IA como prohibida está en la lista, y la autoprueba del whitepaper lo comprueba leyendo las fichas: «preocupante», que prohibía la ficha 12, no estaba (L118). En los textos de método de una ficha (nota, riesgos de lectura, pasos) no cuentan las de acción («hay que unificar los nombres antes de comparar» describe el método). Es una lista: una frase de análisis con otras palabras pasa (por ejemplo, «porque», «de modo que», «los contratos muestran que» o «debe» con un verbo sin «se», como «la Alcaldía debe publicar», no se buscan, porque también describen el método o una regla; tampoco «grave» ni «inflado», que también nombran un dato o el método), y lo que no conoce lo revisa una persona.
*Por qué:* el valor del trabajo con datos (reducir un costo, mejorar una calidad, el impacto de un contrato en la sociedad) lo concluyen las personas, no la IA. Y la hipótesis va antes de mirar: mover el umbral después de ver el resultado convierte cualquier dato en confirmación.

**D16 · Si hay modelo:** partición temporal, línea base de la misma partición, solo variables que se conocen en el momento de decidir (sin fuga), métrica según el costo del error y umbral explícito. Lo exige el módulo 3 del curso; los ejemplos de este repositorio no entrenan modelos.

## E · Visualización

**D17 · El gráfico responde la pregunta y no exagera.**
- Barras desde cero (factor de mentira 1).
- Título con qué, dónde y cuándo; unidades en el eje.
- Fuente y fecha de consulta visibles; período incompleto marcado.
- Cuenta de control: lo que suma el gráfico más lo que se dejó fuera es igual al total de la tabla.
- El gráfico muestra lo medido (D15): ningún texto de la figura concluye, recomienda, busca causas ni juzga. Se buscan con las mismas listas del whitepaper y de la presentación, sobre el texto que se ve (sin etiquetas HTML); una categoría de los datos que trae una de esas palabras es un dato, no lo que escribe la IA.
*Dónde:* `herramientas/verificar_grafico.py`, con la batería `baterias/grafico/`. El HTML lo escribe el verificador, no el código de la IA, que corre en la caja aislada sin leer ningún archivo (B29).

**D29 · El color tiene una función y se mide.**
- Siete colores o menos; lo ideal es gris para el contexto y un color de acento para lo que importa (Datawrapper).
- Contraste de 3:1 o más de cada marca contra el fondo (WCAG 1.4.11) y de 4,5:1 para el texto (WCAG 1.4.3). Un color por debajo de 3:1 solo pasa si la marca lleva su valor escrito.
- Colores distinguibles con daltonismo: diferencia perceptual (ΔE en OKLab ×100) de 8 o más entre cada par, con protanopía, deuteranopía y tritanopía simuladas; nunca rojo contra verde como única diferencia.
- Un solo eje de valores (con dos ejes, quien diseña escoge dónde se cruzan las líneas); sin 3D; tortas de cinco porciones o menos; si la escala es logarítmica, se dice.
*Dónde:* `herramientas/verificar_grafico.py` y `herramientas/color.py`, con la batería `baterias/grafico/` (casos buenos que deben pasar y malos que deben fallar).
*Por qué:* el ojo compara mejor posiciones y longitudes que colores (Cleveland y McGill, 1984); un color que no se distingue o no contrasta borra el dato para una parte del público.

**D30 · La presentación dice lo preguntado y lo medido, y cada cifra sale de los datos.**
- Primero la pregunta y la medición principal con su cifra (la pirámide de Minto, sin conclusión). De SCQA quedan la situación y la pregunta, que describen; la complicación y la respuesta se quitaron porque piden interpretar. Como en D15, la IA resume y no analiza: ni conclusiones, ni causas, ni juicios, ni decisiones que se pidan, ni recomendación.
- Cada título dice lo medido con su cifra, de dos líneas como máximo, y debajo va una sola evidencia (método afirmación-evidencia de Alley). «Las {n} entidades con sede en Medellín contrataron {total} en 2025» dice lo medido; «…, por eso hay que…» saca una consecuencia. Si solo se leen los títulos, se entiende qué se midió.
- La IA no escribe números: pone marcadores (`{total}`) y declara el cálculo de cada uno; el código calcula la cifra desde el resultado aprobado y la escribe. Un dígito, una magnitud con palabras o un «%» fuera de un marcador hacen fallar la presentación. En el lanzamiento de GPT-5 (agosto de 2025), una barra de 52,8 % se dibujó más alta que una de 69,1 %: lo que no calcula el código, no se presenta.
- Método, incertidumbre y límites explícitos, con cada pregunta abierta nombrada (como METR). En lugar de una recomendación, de 3 a 6 preguntas para las personas, de costo, calidad e impacto (como el whitepaper), que ellas responden en `plantillas/analisis_humano.md`.
- La IA escribe solo `presentacion.json`; las láminas, las tablas, la fuente y la fecha las pone el verificador, y solo si todo aprueba.
- Un «donde» que no señala ninguna fila hace fallar la cifra: un nombre mal escrito daba una suma y un conteo de 0 que aprobaban, y un número se comparaba por su texto (2025 no era 2025.0) (L111).
- Una cifra que no es un número finito no se publica. Se comprueba en tres capas, cada una con su ataque: cada dato que entra al cálculo (un «NaN» en texto que `max()` se tragaría), el resultado del cálculo (dos valores finitos cuya diferencia desborda) y la lectura de `informe.json`, que rechaza `NaN` e `Infinity` (B31, L92).
- Las frases de análisis se buscan en todos los textos con la lista D15 de `validar_whitepaper.py` (importada, no copiada), la misma del whitepaper, del gráfico y de las fichas, que ya trae la de la forma anterior («lo que se pide decidir», «próximo paso», «por eso»). Las magnitudes con palabras que el whitepaper no deja pasar («la mayoría», «casi todos») tampoco pasan. Un campo de la forma anterior (`recomendacion`, `decision`, `scqa`, `hallazgos`) hace fallar la presentación.
- Lo que el código no puede ver: que la frase use bien una cifra correcta (por ejemplo, llamar «Medellín» a las entidades con sede en Medellín) y las frases de análisis que la lista no conoce. Eso lo revisa una persona o un juez ciego con la última lámina, que lista los títulos y las preguntas para las personas.
*Dónde:* `agentes/12-presentador.md` y `herramientas/verificar_presentacion.py` (`--autoprueba`: primero 5 presentaciones buenas aprueban y luego 91 mutantes fallan donde deben).

## F · Gobernanza

**D18 · Nunca filas a la IA; el texto libre es un dato personal en potencia.**
La IA trabaja con nombres, tipos y conteos. Antes de publicar, un barrido determinista busca cédulas con contexto, correos, celulares y nombres con tratamiento en los datos y en todo lo que se publica: informe, resultado, gráfico, whitepaper (también en hojas carta) y presentación (B27, L87). Barre la forma canónica del texto: en NFKC, que vuelve la arroba y las cifras de ancho completo a su forma común, sin los caracteres de formato (el espacio de ancho cero, la unión invisible, el guion suave) y, en una página, también sin etiquetas, así un correo partido por un `<span>` no se esconde (L116). No ve un nombre sin tratamiento, una cédula sin contexto, un celular de 10 cifras pegado ni un correo escrito con palabras: esos límites quedan para la revisión de una persona. Si se publican personas, se exige k-anonimato (k ≥ 5). Los mensajes de error que llegan al informe tapan lo que va entre comillas, las cifras largas y toda palabra que aparezca en una celda de la entrada (B26, L83).
*Dónde:* `herramientas/gobernanza.py`. La IA (custodio) clasifica todas las columnas de la fuente y el código compara su clasificación con la propia.
*Por qué:* además de proteger a las personas, la IA no puede seguir una instrucción escondida en un texto que nunca lee.

**D19 · Licencia y atribución de la fuente.** SECOP II se publica con CC BY-SA 4.0; la atribución va en la procedencia, en la cita y en este repositorio.

**D20 · Citar con fecha (R9).** Fuente, conjunto, filtro, fecha de consulta y filas, en cada cifra que sale.

## G · Seguridad del código que escribe la IA

**D21 · Lista cerrada de librerías y versiones fijas.**
El código de la IA solo importa la biblioteca estándar y lo de `herramientas/permitidas.json`; se instala solo desde `requirements.txt`. Nunca se instala desde el código.
*Por qué:* un nombre inventado (`pandas-secop-tools`) lo puede registrar un atacante. Comprobar que el paquete exista no basta (*slopsquatting*).

**D22 · Contrato estrecho y análisis estático antes de ejecutar.**
El código de la IA es una función pura. Antes de correrlo se revisan con reglas propias y con Bandit: ejecución de texto, comandos, deserialización, red, escritura, reflexión, recorrer o navegar carpetas (listar, subir o ir al archivo vecino: así buscaría el oráculo; B28, L90) y secretos. Si algo bloquea, no se ejecuta. Rige igual para `reglas.py`, que también escribe la IA: una regla que la compuerta bloquea no se carga y la corrida queda en «revisar» (B30, L92).
*Dónde:* `herramientas/seguridad.py` y `herramientas/dependencias.py`.
*Dos perfiles:* `pura` es el contrato de este párrafo. `usuario` es para código que sí necesita red y archivos: permite TLS, escritura y procesos con lista de argumentos, y bloquea la debilidad en sí (11 CWE, `herramientas/seguridad_cwe.py`). Un comentario `# nosec` no apaga nada.
*Cómo se mide:* con un lote que escribe otro modelo sin ver la compuerta (`herramientas/medir_compuerta.py`). Revelar un lote lo descarta como medida; la meta se juzga con la cota inferior.

**D23 · Caja de arena.** Sin red y sin escritura fuera de una carpeta temporal (`herramientas/caja.py`).

**D24 · Los datos son entrada no confiable.** Todo lo que viene de los datos se escapa al armar el HTML: un nombre con `<script>` se muestra, no se ejecuta.

**D25 · Revisión ciega de seguridad, con prueba por hallazgo.**
Un agente que no conoce a los autores revisa todo el código generado. Cada hallazgo trae un fragmento que lo reproduce, y un hallazgo sin prueba no cuenta. Lo confirmado entra a la batería.

## H · Aprendizaje y evidencia

**D26 · Baterías: lo que falló una vez se vuelve prueba para siempre.**
- Seguridad: código malo que debe bloquearse y código bueno que debe pasar. Así se prueba al probador: el falso positivo de `re.compile` es un caso.
- Privacidad: datos personales que no pueden salir y textos que no son personales.
- Lecciones: cada error real, con la prueba que lo atrapa. Esa prueba tiene que existir y la batería lo comprueba: un id del blindaje, un mutante de los controles, un caso de una batería, una herramienta con su autoprueba o un archivo versionado; el texto libre solo no cuenta (L96).
- Solo crecen, y el filtro de aportes lo hace cumplir: borrar un archivo de `baterias/` o una mutante del banco sintético, quitar o cambiar una línea, un caso o lo esperado de uno que ya estaba, o tocar lo sellado de una corrida (sus sellos, lo que nombran, `reglas.py`, `spec.json`, `hipotesis.json` y `caso_conocido/`) queda como «requiere decisión del dueño». Un JSON se compara por su estructura: agregar un caso pasa. La corrida de referencia y las mutantes con que se mide el criterio salen de la base, más las mutantes nuevas del aporte (B37, L101).
*Dónde:* `baterias/`, `herramientas/baterias.py`.

**D27 · Bitácora del copiloto.** Por etapa: qué se pidió, qué devolvió, cómo se probó, qué se corrigió y qué quedó sin verificar (`bitacora/`). Va en el informe final.

**D28 · Evidencia honesta y control según el riesgo.**
Se reporta también cuando la IA sola acertó, y se mide lo que cuesta el control.
*Dónde:* `evidencia/README.md`: los generadores de un solo disparo acertaron en los seis casos (en SECOP, uno excluyó una universidad privada y lo declaró); el procesamiento verificado costó entre 3,4 y 4,5 veces los tokens de un generador solo.
*Cómo se aplica:* para explorar basta con el perfil y una revisión rápida. Cuando la cifra va a sostener una decisión con plata, una norma o un informe público, se usa el pipeline completo.

---

## I · Blindaje del pipeline: atacar cada capa a propósito

El mismo patrón del generador y el validador, aplicado al pipeline entero: un atacante (cada prueba de `herramientas/blindaje.py`) y un defensor (cada capa). El detalle y la línea base están en [`evidencia/blindaje/README.md`](evidencia/blindaje/README.md).

**DB1 · Toda batería de ataques lleva un control positivo.** Un ataque que «resiste» porque nada funciona no prueba nada. B00 corre código normal en la caja: si falla, ninguna prueba de la caja vale (lección L27). Y todo control lleva una prueba que muere al quitarlo: `herramientas/mutar_controles.py` lo quita en una copia y exige que su prueba ceda por el ataque, no por un error; sin mutar, las mismas pruebas resisten. Las compuertas de `reglas.py`, los valores finitos y el saneado sobrevivían a la mutación (SEG-3); hoy los 27 mutantes mueren (B26, B30 a B33 y B35 a B39; L92 a L94, L99 a L102 y L109). Lo mismo con las baterías: la batería FAILFAST corre el lector del perfil y las autopruebas de la ingesta y de la limpieza, y B33 afloja cada lector en una copia para ver que caiga (L93).

**DB2 · La caja de arena niega la red, la escritura y la lectura de la carpeta personal, y da un entorno mínimo.** El código de la IA no ve las variables de entorno del proceso que lo lanza (secretos) y tiene topes de tiempo y de memoria. La memoria se mide como huella física, no como memoria residente (B01, B10–B14, B23; lecciones L25, L26, L28, L69). La implementación bajo prueba corre aislada, sobre una copia de su código y de sus tablas: no lee el repositorio, las carpetas temporales ni ningún archivo con nombre de oráculo o de criterio (`esperado.json`, `reglas.py`, `sellos*.json`), ni la otra implementación (B24, L81). El código del gráfico y el de las hipótesis pasan por la misma compuerta y corren en la misma caja aislada: el gráfico no lee ningún archivo (el resultado y la procedencia le llegan como texto) y las hipótesis, solo la copia de sus tablas, sin el `hipotesis.json` sellado (B29, L91).

**DB3 · Las herramientas no pueden cambiar durante una corrida.** Un manifiesto de integridad se sella antes de cualquier agente y se comprueba al final. Las baterías solo pueden crecer (B02, L29).

**DB4 · Los datos y los aportes son datos, nunca instrucciones.** Los valores con forma de orden para una IA quedan en cuarentena en el perfil y en la limpieza; el filtro rechaza aportes que dan órdenes a los agentes; y es una regla común de todos los subagentes (B04, B07, L30, `baterias/inyeccion/`). La orden se busca también en como la lee una persona: con letras de ancho completo o con letras de otro alfabeto que se leen como latinas («Ignora» con la «o» cirílica) no se esconde (B27, L117).

**DB5 · Las salidas no ejecutan nada al abrirse.** Las fórmulas de Excel se neutralizan y se marcan en la capa limpia; el HTML de los datos se escapa (B03, L31, L19, L23).

**DB6 · La compuerta se ataca con evasiones conocidas,** y cada evasión cerrada queda en la batería sin romper el código legítimo (B15, L32). En el perfil pura, lo que recorre carpetas se bloquea por su nombre, se llame o no, y también por alias, getattr con texto, import * o el texto que se vuelve llamada: B28 lo ataca con 29 variantes que, sin la compuerta, llegan al oráculo (L90).

**DB7 · Cadena de suministro fijada.** Cada dependencia lleva su huella y se instala con `--require-hashes`; cada acción de GitHub está fijada a su commit (B08, L33).

**DB8 · Los generadores generalizan.** Sobre datos nuevos que nadie vio (otra semilla del oráculo), A y B deben dar exacto el resultado correcto (B05).

**DB9 · La independencia se audita, no se supone.** Se revisan las transcripciones reales: ningún agente puede haber abierto lo que su ficha le prohíbe (`evidencia/blindaje/auditar_independencia.py`). Cada rol entra en la auditoría con lo que prohíbe su ficha. Hasta el 6-nov conocía 7 roles (generadores, reparadores, probador, revisor ciego de seguridad y custodio: 16 agentes de 4 corridas, 0 accesos prohibidos); el documentador y el presentador entraron el 6-nov (L88), y el lector, el especificador, el limpiador, el revisor de la especificación y el graficador el 7-nov (L121), con lo que el custodio tampoco puede leer filas (de una tabla, con un comando o pedidas a Socrata). Su `--autoprueba` exige que cada «Eres el …» de `flujo.js` y cada ficha con «No puede leer» tengan su rol: un rol nuevo sin auditar la hace fallar. Sobre las transcripciones de las 3 corridas orquestadas del 6-nov que quedan en el equipo del dueño (32 agentes), la tabla de antes marcaba 1 uso prohibido (del presentador) y la de hoy 13: en dos corridas, el limpiador abrió `reglas.py` o el caso conocido y pasó su plan por el caso conocido por fuera de `verificar.py` (10), y el graficador listó y comparó la capa limpia (2). Límites: mira las rutas y los comandos que escribió el agente, no lo que leyó un programa que corrió, y un comando que encadena una herramienta del pipeline con una lectura prohibida no se marca.

**DB10 · Quien toca una herramienta corre el banco de blindaje.** El filtro de aportes lo corre si el aporte cambia `herramientas/`: debilitar una defensa hace fallar el aporte. El banco y las baterías de la base cargan las herramientas del aporte en su mismo proceso, y ese código puede escribir en su salida: un `limpieza.py` debilitado con un RESUMEN falso al salir escondía la falla de B03. Por eso el `baterias.py` del aporte no se corre, cada herramienta debe dejar una sola línea RESUMEN, la salida del banco tiene que cuadrar (una línea por cada prueba de la base y el RESUMEN igual a lo marcado) y lo que cede en las líneas o en el RESUMEN es falla (B38, L102). Límite: un código que reescribe toda la salida de forma coherente no se detecta, así que que resista no prueba nada y el aporte queda en «requiere decisión del dueño»; cerrarlo pide correr cada herramienta del aporte en un proceso aparte, sin importarla en el que da el veredicto.

**DB11 · La ficha dice lo que hace el motor que la comprueba.** Lo que admiten la ingesta y la limpieza (tipos y claves del contrato y del agregado, claves de la fuente, claves del plan, operaciones y umbrales) sale de su código, y la ficha del lector o del limpiador y su instrucción en `flujo.js` tienen que nombrarlo, y la instrucción, mandar a su ficha. Tras PIP-4 y PIP-5, el motor admitía llaves compuestas, agregados con `k_minimo`, `vacios_maximo` y `umbrales_caso`, y las fichas no los nombraban: faltaban 42 (B34, L95).

**DB12 · El filtro compara las rutas como las ve el disco del dueño.** En macOS (el equipo del dueño y el runner del filtro) «.Githooks/pre-commit» es el gancho que corre en cada commit y «Flujo.js» es `flujo.js`. Las rutas que solo cambia el dueño, lo que juzga a los aportes y lo que no puede entrar se comparan con la clave de la ruta: sin mayúsculas, con los acentos en una sola forma y sin los invisibles que ignora HFS+. Una ruta del aporte que en ese disco cae sobre otra escrita distinto bloquea en el chequeo de main y es falla en el juez, que no lee su contenido: el disco solo guarda uno de los dos archivos (B35, L99). Lo que solo iguala Windows (nombres cortos 8.3, el punto final) no se compara.

**DB13 · Lo que corre fuera de Python lo decide el dueño.** Las compuertas revisan Python y los cuadernos; nada más. `orquestar.mjs`, que lanza agy y Codex sin pedir permisos en el equipo del dueño, es de lo que decide el dueño, igual que `flujo.js`, y un aporte que agrega o cambia un script (`.sh`, `.js`, `.mjs`, `.ts`, `.ps1`, `.bat`, un Makefile…), un archivo con permiso de ejecución o con «#!», o una página con `<script>`, `on…=` o `javascript:` en un atributo queda como «requiere decisión del dueño». El gráfico de una corrida trae el paquete de Plotly y lo revisa su verificador (B36, L100).

**DB14 · El filtro lee cada archivo por su contenido, no por su extensión.** El barrido de datos personales y el de órdenes a los agentes corren sobre todo lo que el aporte agrega, sea cual sea su extensión: todo texto tiene que ser UTF-8 (uno en UTF-16, en latin-1 o con un NUL es falla: leído con `errors="ignore"` deja un NUL entre cada letra y ninguna expresión lo encuentra); de un JSON se leen también sus cadenas decodificadas (un «\u0040» no esconde un correo); de una página, un SVG o un XML, el texto con las entidades resueltas y, aparte, sin etiquetas; de un PDF, el texto de sus páginas con el mapa a Unicode de cada fuente, sus metadatos y sus enlaces (un enlace `file://` es falla, L84); y de un PNG o un JPEG, sus metadatos. Lo que el filtro no sabe leer (un PDF cifrado, con adjuntos, código o fuentes sin mapa; un GIF, un WebP o un ICO; bytes de más después del final) y una ruta nueva del equipo de alguien (`/Users/<usuario>/…`, R07) quedan como «requiere decisión del dueño». De `datos/` y `limpio/` solo entra la procedencia de cada tabla, y 20 ids de SECOP fuera de un caso conocido ya son un extracto (B40, L114). En toda tabla delimitada, `.csv` o `.tsv`, una celda que empieza con `=`, `+`, `-`, `@`, un tabulador o un retorno y no es un número es falla: una hoja de cálculo la ejecuta al abrir el archivo (`=HYPERLINK`, una carga DDE); en `baterias/failfast/` son casos a propósito (L115). Límites: lo que una imagen o un PDF traen dibujado sin texto no se lee, y un nombre sin tratamiento («Firmó Juana Pérez») o una cédula sin contexto no tienen una forma que el barrido reconozca: los ve el dueño al revisar.

## J · SGSI: la tríada C·I·D aplicada al pipeline

La seguridad del repositorio, ordenada como un sistema de gestión (ISO/IEC 27001:2022) y comprobada sin IA, igual que el análisis. El método, el alcance y los proveedores están en [`sgsi/README.md`](sgsi/README.md); lo que hay hoy, en [`sgsi/INFORME-SGSI.md`](sgsi/INFORME-SGSI.md).

**DS1 · Cada activo dice cuánto vale en confidencialidad, en integridad y en disponibilidad, y por qué.** Su clasificación sale de la C, y lo restringido nunca entra al repositorio público (A.5.9, A.5.12).
*Cómo se comprueba:* `sgsi.py` cruza el inventario con `git ls-files` y `.gitignore`: los datos de SECOP con personas deben quedar ignorados y sin versionar.

**DS2 · Cada riesgo pierde una sola propiedad, y su impacto no se escribe: sale del valor del activo.** Así nadie baja un riesgo bajando el impacto a mano. Nivel = probabilidad × impacto; criterio de aceptación: 10 o menos (6.1.2).

**DS3 · La regla de la tríada.** La confidencialidad no tiene reversa: solo un control preventivo baja su riesgo. La integridad se corrige si se detecta: hace falta un control detectivo. La disponibilidad se restablece: hace falta un control correctivo. Si un residual baja sin el control que corresponde, la herramienta lo rechaza.

**DS4 · La Declaración de Aplicabilidad tiene los 93 controles del Anexo A, y cada «sí» apunta a un control que existe en el repositorio** (6.1.3 d). Un control cuya evidencia desaparece invalida su fila.

**DS5 · Un control vale lo que su prueba.** `--efectividad` corre el banco de blindaje, las baterías, la corrida sintética y los mutantes, y solo cuenta los controles que pasan (9.1). La vigilancia diaria (`vigilancia-diaria`) lo repite sobre `main` y consulta OSV por vulnerabilidades conocidas en las dependencias fijadas (A.8.8).

**DS6 · Probar al probador también aquí.** `sgsi.py --autoprueba` daña el SGSI 21 veces a propósito (un riesgo de C rebajado con un control detectivo, una fila de la SoA que dice «sí» sin control, evidencia que ya no existe…) y debe atraparlas todas, con los datos de hoy como control positivo.

**DS7 · Lo que queda por encima del criterio se ve y lo decide el dueño del riesgo, por escrito** (6.1.3 f). R16 (una referencia legal inventada por la IA) estuvo por encima del criterio hasta que se trató: hoy toda ley o decreto de una ficha debe estar comprobado contra su texto oficial en `baterias/normas/verificadas.json` (V6, CT40).

**DS8 · Cada corrida sale con su etiqueta C·I·D:** si sus salidas se pueden publicar (barrido y k-anonimato), si su criterio sigue sellado (huellas recalculadas) y si se puede reconstruir (contrato de datos o semilla). Las vulnerabilidades se reportan en privado y se responden según la propiedad que se perdió ([`SECURITY.md`](SECURITY.md)).

## Correspondencia con el curso «Big Data con IA» (NODO · EAFIT)

| Módulo | Reglas del agente del curso | Directrices |
|---|---|---|
| 1 · Pedir, probar, citar | R1 solo nombres reales · R2 nunca filas · R3 todo conteo cierra · R4 prueba independiente · R5 no borrar en silencio · R6 fechas · R7 valores imposibles se cuentan · R8 primero igual, después rápido · R9 citar con fecha | D1–D4, D9, D12, D13, D18, D20 |
| 2 · Ingesta y procesamiento | R10 leer completo · R11 esquema declarado · R12 correr dos veces da lo mismo · R13 particionar sin perder nulos · R14 limpiar es marcar · R15 las cinco pruebas · R16 sin traer todo a memoria | D5–D7, D12, D13, DL1–DL7 |
| 3 · Analítica | lo hacen las personas: hipótesis escrita antes de mirar, línea base, partición temporal, fuga, umbral, desmentir con una consulta; la IA solo documenta (whitepaper) y deja bitácora | D15, D16, D27 |
| 4 · Visualización y gobernanza | etiqueta exacta, eje desde cero, factor de mentira, período incompleto, cuenta de control, color con contraste y apto para daltonismo, presentación con lo preguntado y lo medido primero, preguntas para las personas y cifras que escribe el código, unicidad (k), qué no se pega al asistente, cita | D17–D20, D24, D29, D30 |

R13 y R16 son de PySpark: aquí no aplican, porque los datos caben en memoria (91.072 filas).

## Lo que este repositorio no garantiza

- «Aprobado» quiere decir que pasa las comprobaciones escritas, no que sea correcto en todo sentido.
- Si el especificador y el revisor entienden mal lo mismo, el error pasa. Por eso el informe muestra la interpretación, los supuestos y las preguntas: es lo único que una persona tiene que leer.
- El barrido de datos personales usa expresiones regulares: puede dejar pasar formas que no conoce. La minimización (D7) es la primera defensa.
- La caja de arena depende de `sandbox-exec` de macOS.
- La compuerta de seguridad es análisis estático: sigue el dato dentro de una función, no entre funciones, y solo conoce las 11 debilidades de su catálogo. Su cifra vale para ese catálogo y para fragmentos cortos; no es un certificado de que el código sea seguro.
