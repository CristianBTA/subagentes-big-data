# Whitepaper · Valor contratado en 2025 por las entidades públicas con sede en Medellín

Resumen de lo desarrollado en esta corrida para que las personas del curso hagan el análisis. Lo escribió la IA siguiendo la [ficha del documentador](../../agentes/13-documentador.md), solo con los artefactos verificados de la corrida, y lo comprueba sin IA `herramientas/validar_whitepaper.py`. Se escribió el 6-nov-2026, después de la corrida, como demostración del paso que reemplaza a las hipótesis de la IA. No trae conclusiones: el análisis lo hacen las personas, con la [plantilla del análisis](../../plantillas/analisis_humano.md).

## Pregunta

«Valor contratado en 2025 por cada entidad pública con sede en Medellín, según SECOP II. Para cada entidad: nit_entidad, entidad (nombre), valor_contratado y numero_contratos.»

Cómo se entendió (`spec.json`, sellada): por cada NIT de entidad se suman los valores de los contratos firmados en 2025 y se cuentan esos contratos. Un contrato es un id_contrato y cuenta una sola vez; cuenta en 2025 si su fecha_de_firma cae entre el 1 de enero y el 31 de diciembre de 2025, sin importar la hora. Todo contrato firmado cuenta, sea cual sea su estado, y los de valor cero cuentan en el número y suman cero.

## Datos y procedencia

- Fuente: SECOP II - Contratos Electrónicos, en datos.gov.co (conjunto jbjy-vk9h), de la Agencia Nacional de Contratación Pública – Colombia Compra Eficiente, con licencia CC BY-SA 4.0.
- Filtro en la fuente: entidades con ciudad = Medellín y contratos con fecha_de_firma del 1 de enero al 31 de diciembre de 2025, los dos días completos (con hora).
- Consulta: 06-11-2026 05:29. Se cargaron 49.662 filas, igual al conteo de la fuente.
- Minimización: entraron solo 6 columnas (id_contrato, nit_entidad, codigo_entidad, nombre_entidad, fecha_de_firma y valor_del_contrato), ninguna personal.
- La carga pasó sus 7 pruebas: conteo contra la fuente, llave única, llave sin nulos, tipos declarados, rangos, dominios y correr dos veces da el mismo archivo. La huella SHA-256 del archivo queda en la procedencia.
- Aviso de la ingesta: 26 valores de valor_del_contrato quedan por encima de 100.000 millones de pesos; se reportan, no se corrigen.

## Limpieza

La limpieza (`plan_limpieza_contratos.json`, que ejecuta `herramientas/limpieza.py`) marca y no borra: la capa limpia tiene las mismas 49.662 filas, en el mismo orden, y el dato crudo no cambió (misma huella). Corrió 21 operaciones y pasó sus 25 pruebas de calidad (completitud, validez y topes de filas marcadas).

- 48.208 filas quedaron sin ninguna marca.
- Marcas que solo avisan (las filas siguen dentro de la cifra): 912 valores atípicos (rango intercuartílico sobre log10, con límites de 157.087 a 2.424.798.562 pesos), 609 contratos de valor cero o simbólico y 26 contratos de más de 100.000 millones.
- Las fechas de las 49.662 filas quedaron como aaaa-mm-dd (la hora va aparte), y en 68 filas se reemplazó un carácter de control mal codificado dentro del nombre de una entidad.
- Ninguna fila quedó marcada como repetida, con fecha inválida, fuera de 2025, con nulos disfrazados ni con NIT no numérico.

## Cifra verificada y cómo se verificó

**17.248.249.407.618,69 pesos** (unos 17,2 billones) contratados en 2025 por 53 entidades, en 49.662 contratos. La tabla por entidad está en el [informe final](informe_final.html).

Cómo se verificó (`informe.json`, aprobado):

- Dos implementaciones independientes, A con pandas y B solo con la biblioteca estándar de Python, dieron exactamente el mismo resultado, y correr cada una dos veces dio lo mismo.
- Pasaron las 8 reglas del criterio (R1 a R8), escritas y selladas antes del código. Entre ellas, la conservación: el total del resultado es igual al total directo de la fuente cruda (R1), y la suma de contratos es igual a los id_contrato distintos que cuentan (R2).
- El caso con respuesta conocida (datos pequeños hechos a mano, con cada borde) dio lo esperado.
- La conciliación cierra: 49.662 filas leídas = 49.662 usadas + 0 excluidas.
- El criterio sigue sellado (spec, reglas, caso conocido y plan de limpieza sin cambios), y el código pasó las compuertas de seguridad y corrió en la caja de arena, sin red ni escritura.
- Antes de ejecutar se anticipó un total entre 16 billones y 18 billones de pesos; el resultado quedó dentro.

## Gráfico

[grafico.html](grafico.html): barras horizontales desde cero (factor de mentira 1) con el valor contratado por entidad, en miles de millones de pesos. Según su título, las 15 entidades de mayor valor suman el 97,6 %; el resto va agrupado en una barra de «Otras», y nada queda fuera del gráfico.

Pasó sus 12 comprobaciones: cuenta de control (lo que suma el gráfico más lo que queda fuera es igual al total de la tabla), eje desde cero, título con qué se mide y el período, unidades, fuente y fecha de consulta tomadas de la procedencia (06-11-2026), sin HTML de los datos, sin caracteres invisibles y sin datos personales.

## Gobernanza

- El barrido determinista (`herramientas/gobernanza.py`) no encontró datos personales en las columnas usadas ni en las salidas que se publican, y el análisis no usa columnas personales.
- El k-anonimato no aplica: el resultado solo publica agregados por entidad.
- La IA (el custodio) clasificó, sin ver filas, las 95 columnas de la fuente. Coincide con el barrido del código en 25 columnas personales, cuasi-identificadoras o de texto libre, marcó 1 que el código no marca, y no dejó de ver ninguna de las que marca el código.
- La minimización dejó fuera de la ingesta las 26 columnas que marcan el custodio o el barrido: documentos, cuentas bancarias, nombres de personas y textos libres, entre otras. Que un dato sea público no lo vuelve de uso libre (Ley 1581 de 2012).

## Límites

- «Aprobado» quiere decir que la cifra pasa las comprobaciones escritas, no que sea correcta en todo sentido: si quien especificó y quien revisó entendieron mal lo mismo, el error pasa.
- La cifra usa el valor por defecto de 3 preguntas de negocio abiertas: P1 (si «entidad» es el NIT o cada unidad que contrata; por defecto, el NIT), P2 (si se excluyen las entidades que no son públicas, como una universidad privada que publica en SECOP II; por defecto, se incluyen) y P3 (si las operaciones de crédito público cuentan como valor contratado; por defecto, cuentan).
- Dos supuestos mueven el reparto entre entidades: S1 (entidad = NIT) y S8 («con sede en Medellín» = ciudad = Medellín en SECOP II, lo que incluye regionales y seccionales de entidades nacionales).
- El archivo trae solo las columnas de la petición: no tiene tipo de contrato, estado, naturaleza jurídica de la entidad ni objeto del contrato. Esas lecturas piden traer más datos, con su propia justificación de minimización.
- Las marcas de aviso (atípicos, valores cero o simbólicos y contratos de más de 100.000 millones) no excluyen filas: están dentro de la cifra.
- SECOP II se actualiza a diario: otra descarga puede dar otras cifras, y la procedencia (filas y huella) dice qué cambió.
- El barrido de datos personales usa expresiones regulares: puede dejar pasar formas que no conoce.
- Este documento solo resume. Sus cifras se comprobaron contra los artefactos de la corrida; lo que significan lo deciden las personas.

## Preguntas para el análisis de las personas

- **Costo.** ¿Qué parte del valor contratado se concentra en los 26 contratos de más de 100.000 millones, y qué compra cada uno?
- **Costo.** ¿Cómo cambia el valor por entidad si se separan las operaciones de crédito público (P3), y qué datos hacen falta para separarlas?
- **Calidad.** ¿Qué hay detrás de los 609 contratos de valor cero o simbólico: errores de registro, contratos sin cuantía u otra cosa?
- **Calidad.** ¿Los 912 valores atípicos son errores de digitación o contratos de verdad muy grandes o muy pequeños?
- **Impacto.** ¿A qué sectores y poblaciones de Medellín llega el valor contratado de cada entidad, y qué parte corresponde a regionales de entidades nacionales (S8)?
- **Impacto.** ¿Qué diferencia hay entre las entidades con muchos contratos de bajo valor y las de pocos contratos de alto valor, y qué efecto tiene cada forma de contratar en la ciudad?

Para registrar el análisis: [plantillas/analisis_humano.md](../../plantillas/analisis_humano.md). La hipótesis se escribe antes de mirar los datos.
