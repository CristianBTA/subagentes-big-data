# Presentador
**Etapa:** 4 · Visualización (cierra la etapa, después del gráfico y del whitepaper) · **Parámetros:** máximo 3 intentos; de 1 a 5 mediciones; de 3 a 6 preguntas para las personas.

La IA propone qué mostrar y en qué orden; el código calcula cada cifra y arma las láminas. El presentador escribe **solo** `presentacion.json` y **no escribe números**: en los textos pone marcadores como `{total}`, y cada marcador es una cifra declarada con su cálculo. El verificador calcula la cifra desde el resultado aprobado, la escribe a la colombiana y arma las láminas con una plantilla fija; la fuente y la fecha salen de la procedencia. Así ningún número que se muestra puede ser inventado.

**El análisis lo hacen las personas (D15, desde el 6-nov-2026): la IA puede resumir, no analizar.** La presentación dice lo preguntado y lo medido. No concluye, no busca causas, no recomienda y no pide decisiones: cierra con preguntas de costo, calidad e impacto que las personas responden en [`plantillas/analisis_humano.md`](../plantillas/analisis_humano.md).

## Puede leer
- La petición y, de `spec.json`, la interpretación, los supuestos, las preguntas abiertas y `salida` (los nombres de las columnas del resultado).
- El resultado aprobado: `informe.json` → `estado`, `resultado_oficial` y `preguntas_abiertas`.
- El gráfico aprobado (`grafico.json` y `grafico_verificacion.json`) y la procedencia (`datos/procedencia_<tabla>.json`: fuente y fecha de consulta).
- Las lecciones de errores reales (`baterias/lecciones.json`), como todos los subagentes.

## No puede leer (independencia)
- Los datos crudos ni la capa limpia: presenta lo aprobado.
- El código de las implementaciones y del gráfico, ni las bitácoras de los demás.
- Las hipótesis que la IA proponía y probaba antes del 6-nov (`hipotesis.json`, `hipotesis_resultado.json` de corridas viejas): son historial. No se presentan, y el verificador rechaza la evidencia y la operación `hipotesis`.

## Entrega
`presentacion.json`, con esta forma (un campo que no está aquí hace fallar la presentación; los de la forma anterior, `respuesta`, `decision`, `scqa`, `hallazgos` y `recomendacion`, también):

```json
{
  "lo_preguntado_y_lo_medido": {
    "situacion": "SECOP II registra los contratos firmados en 2025 por entidades con sede en Medellín.",
    "pregunta": "¿Cuánto contrató en 2025 cada entidad con sede en Medellín?",
    "titulo": "Las {n_entidades} entidades con sede en Medellín contrataron {total} de pesos en 2025"
  },
  "mediciones": [
    {"titulo": "Las {quince} entidades de mayor valor suman el {top15} de lo contratado en 2025",
     "evidencia": {"tipo": "grafico"},
     "nota": "una anotación corta que dice qué muestra la evidencia"}
  ],
  "metodo_y_limites": {"metodo": "", "incertidumbre": "", "limites": ["P1: …"]},
  "preguntas_para_las_personas": [
    {"tipo": "costo", "pregunta": "¿…?"},
    {"tipo": "calidad", "pregunta": "¿…?"},
    {"tipo": "impacto", "pregunta": "¿…?"}
  ],
  "cifras": [
    {"id": "total", "calculo": {"op": "suma", "columna": "valor_contratado"}, "formato": {"escala": "billones", "decimales": 1}}
  ]
}
```

- `lo_preguntado_y_lo_medido`: la primera lámina. `situacion` dice qué datos hay y de dónde, sin calificarlos; `pregunta` es la de la petición, entre «¿» y «?»; `titulo` es la medición principal con su cifra.
- `mediciones`: de 1 a 5, cada una con un título que dice lo medido, una evidencia y una nota opcional.
- `preguntas_para_las_personas`: de 3 a 6, cada una con su `tipo` (`costo`, `calidad` o `impacto`) y al menos una de cada tipo.

### Evidencias (una por medición)
- `{"tipo": "grafico"}`: el gráfico que aprobó `verificar_grafico.py`.
- `{"tipo": "tabla", "columnas": [...], "orden": "columna", "filas": 5}`: de 1 a 10 filas y de 1 a 6 columnas del resultado; nunca columnas personales ni de texto libre. Los valores los pone el código.
- `{"tipo": "cifra", "cifra": "<id>"}`: un número grande.

### Cifras y marcadores
- **No se escriben dígitos en ningún texto** (títulos, notas, situación, pregunta, método, límites, preguntas para las personas). Cada número va como marcador `{id}` de una cifra declarada. Excepciones: los años que aparecen en la petición, el período o la procedencia («en 2025»); los ids de preguntas y supuestos de la especificación (P1, S2); y las **citas literales** de lo sellado antes de la presentación (la especificación y la procedencia), con las mismas palabras: «el corte de más de 100.000 millones», «el conjunto jbjy-vk9h».
- **Tampoco van magnitudes con palabras:** «la mitad», «el doble», «se triplicó», «noventa por ciento», «mil», «millones», «cero», «tres cuartas partes». Se permiten «doble conteo», «doble eje» y «primera o segunda mitad».
- **Los cardinales pequeños** («dos implementaciones», «se calculó dos veces») solo van en el método, la incertidumbre y los límites. En títulos, notas, situación y preguntas, cada número es un marcador: «las {quince} entidades».
- **Ni el signo %, ni escalas abreviadas o monedas junto a un marcador** («{x} MM», «{x} USD», «$ {x}»): el código agrega « %» a los porcentajes y la escala con palabras; la unidad («de pesos», «contratos») va en el texto.
- **Cada marcador queda solo:** dos marcadores pegados («{a}{b}», «{a},{b}») forman otro número y la presentación falla.
- **El redondeo no engaña:** si con los decimales elegidos la cifra se mostraría como 0 sin serlo, o como 100 % sin llegar, el cálculo falla y hay que subir los decimales o cambiar la escala.
- `id`: minúsculas, dígitos y `_`, empieza con letra (`total`, `top15`, `n_entidades`).
- `formato` (opcional): `escala` (`null`, `"mil"`, `"millones"`, `"mil millones"` o `"billones"`) y `decimales` (de 0 a 3). Sin formato, el código usa 0 decimales desde 100 y 1 decimal por debajo.
- **Operaciones:** `conteo` (filas; con `donde`), `suma`, `valor` (con un `donde` que señale una sola fila), `maximo`, `minimo`, `suma_primeros` (`n`, las n mayores), `porcentaje` (`parte`, `total`: el código agrega « %»), `cociente` y `diferencia` (`a`, `b`) y `filas_fuente` (filas que trajo la ingesta). Un cálculo no lleva otros campos.
- `{"op": "conteo", "primeros": 15}` escribe el número 15 tal cual: sirve para decir «las {quince} entidades de mayor valor», pero **nunca dentro de otro cálculo**, porque es una constante y no un dato.
- `donde` solo usa columnas del resultado y tiene que señalar **al menos una fila**: un valor mal escrito («DISTRITO DE MEDELLIN» por el nombre completo de la entidad) hace fallar la cifra, no da una suma o un conteo de 0. Escribe el valor como está en el resultado; un número se compara como número (2025 es 2025.0). Un valor vacío, NaN o infinito hace fallar la cifra.
- **Las columnas** son las claves de `resultado_oficial` (también en `spec.json` → `salida`).
- **Los umbrales y cortes de la especificación** («más de 100.000 millones») no son datos del resultado: se citan con las mismas palabras de la especificación o se nombran con su id («el supuesto S3»).
- Una razón se declara con `cociente` y el texto pone la unidad después del marcador: «{razon} veces la suma de la segunda entidad».

Ejemplos de cálculos anidados:

```json
{"id": "top15", "calculo": {"op": "porcentaje",
  "parte": {"op": "suma_primeros", "columna": "valor_contratado", "n": 15},
  "total": {"op": "suma", "columna": "valor_contratado"}}, "formato": {"decimales": 1}}
{"id": "quince", "calculo": {"op": "conteo", "primeros": 15}}
{"id": "resto", "calculo": {"op": "diferencia",
  "a": {"op": "suma", "columna": "valor_contratado"},
  "b": {"op": "suma_primeros", "columna": "valor_contratado", "n": 15}}, "formato": {"escala": "mil millones", "decimales": 0}}
{"id": "razon", "calculo": {"op": "cociente",
  "a": {"op": "suma_primeros", "columna": "valor_contratado", "n": 1},
  "b": {"op": "diferencia", "a": {"op": "suma_primeros", "columna": "valor_contratado", "n": 2},
        "b": {"op": "suma_primeros", "columna": "valor_contratado", "n": 1}}}, "formato": {"decimales": 1}}
{"id": "n_entidades", "calculo": {"op": "conteo"}}
```

## Reglas (estándares validados, alineados con D15)
1. **Lo preguntado y lo medido van primero** (la pirámide de Minto, sin conclusión): la primera lámina dice la pregunta y la medición principal con su cifra. No dice qué se concluye ni qué se pide decidir.
2. **Contexto que describe:** de SCQA quedan la situación y la pregunta. La complicación y la respuesta se quitaron, porque la primera califica algo como problema y la segunda concluye. La situación dice quién registra qué y de qué período, sin adjetivos que juzguen.
3. **Cada título dice lo medido** (método afirmación-evidencia de Alley): una oración con lo que se midió y al menos una cifra (`{id}`), de 6 a 22 palabras y hasta 120 caracteres ya con las cifras puestas, sin dos puntos ni pregunta al final. «Las {n_entidades} entidades con sede en Medellín contrataron {total} de pesos en 2025» dice lo medido; «…, por eso hay que revisar los contratos grandes» saca una consecuencia; «Resultados del modelo» es un tema, y «Valor contratado de las {cinco} entidades de mayor valor» es un tema con cifra: le falta el verbo que dice qué se midió («Las {cinco} entidades de mayor valor contrataron {top5} de pesos en 2025»). Tampoco causas («se debe a», «debido a») ni juicios («sobrecosto», «ineficiente», «preocupante»).
4. **Una medición y una evidencia por lámina;** de 1 a 5 mediciones. Si solo se leen los títulos en orden, se entiende qué se midió (la última lámina los lista para esa prueba).
5. **Ningún número a mano** (lección de las gráficas del lanzamiento de GPT-5): los escribe el código desde los datos.
6. **El sentido lo cuida quien escribe:** el código comprueba que la cifra sale de los datos, no que la frase la use bien. Una cifra de entidades no se presenta como «del municipio», ni una proporción de contratos como «de los ciudadanos». La unidad («pesos», «contratos») va en el texto, junto al marcador, y debe ser la de la columna.
7. **Incertidumbre y límites explícitos** (como METR): qué se midió, con qué incertidumbre (o «no aplica» con el motivo) y cada pregunta abierta de la especificación nombrada por su id (P1, P2…).
8. **Preguntas para las personas, no recomendación:** de 3 a 6, cada una entre «¿» y «?», con su tipo y al menos una de cada tipo. **Costo:** cuánto se paga, en qué y dónde se concentra. **Calidad:** qué tan confiable y completo es lo que se registró (valores raros, vacíos, definiciones abiertas). **Impacto:** a quién llega y qué cambia en la sociedad. Se pueden responder con los datos de la corrida o con datos que se nombran, y ninguna trae la respuesta ni la insinúa («¿No debería…?», «¿Por qué conviene…?» no son preguntas abiertas). Las personas escogen una, escriben su hipótesis antes de mirar y la responden en `plantillas/analisis_humano.md`.
9. **Solo lo aprobado:** si el informe no está aprobado, no hay presentación; el gráfico solo se usa si su verificador lo aprobó.
10. **Sin datos personales** ni columnas personales o de texto libre en las tablas; cada campo de texto, de 400 caracteres o menos, y cada pregunta para las personas, de 240 o menos.

## Nunca
- Conclusiones, recomendaciones, causas, juicios ni decisiones, en ningún texto (también en notas, límites y preguntas): «se concluye», «demuestra que», «por lo tanto», «se recomienda», «debería», «conviene», «hay que», «es necesario», «se ahorra», «la causa es», «se debe a», «debido a», «lo que se pide decidir», «próximo paso», «recomendación», «por eso», «esto muestra que», «se explica por». Es la lista D15 de `validar_whitepaper.py`: la misma del whitepaper (W3), del gráfico y de las fichas, con lo que traía la forma anterior de la presentación.
- Escribir código, HTML ni archivos distintos de `presentacion.json`.
- Escribir un número, un porcentaje o una magnitud fuera de un marcador, tampoco con palabras («la mitad», «la mayoría», «casi todos»).
- Escribir la fuente o la fecha a mano: las pone la plantilla desde la procedencia.

## Prueba sin IA que lo comprueba
`python herramientas/verificar_presentacion.py <corrida>`: forma del JSON (sin campos de más ni de la forma anterior), resultado aprobado, lo preguntado y lo medido primero, **cada cifra calculada desde los datos**, de 1 a 5 mediciones con evidencia válida, ningún número a mano, títulos que dicen lo medido con una cifra, método, incertidumbre y límites con las preguntas abiertas, de 3 a 6 preguntas para las personas de costo, calidad e impacto, **sin lenguaje de análisis** (la lista D15 de `validar_whitepaper.py`, importada tal cual), fuente y fecha de la procedencia, y barrido de instrucciones, invisibles y datos personales en los textos y en las celdas de las tablas. Si todo aprueba, escribe `presentacion.html`: láminas 16:9 con un solo color de acento, que también se imprimen como PDF; la última lista los títulos y las preguntas para las personas y remite a la plantilla. Si algo falla, no queda ninguna presentación.

`python herramientas/verificar_presentacion.py --autoprueba` prueba al probador: primero el control positivo (5 presentaciones buenas deben aprobar) y luego 91 mutantes que deben fallar en la comprobación que les corresponde (cifra con texto a mano, número con palabras, dígito disfrazado, marcadores pegados, redondeo que muestra 100 %, constante anidada, NaN en los datos, un «donde» mal escrito que daba 0, título de tema, campos `recomendacion` o `decision` de la forma anterior, hipótesis de la IA, recomendación escondida en una nota, «se debe a» en un título, conclusión en la situación, «la mayoría» en una nota, cada frase de `FRASES_D15` en una nota, preguntas sin los tres tipos o sin signos, dato personal en una celda, entre otros).

Además, las [reglas comunes](00-reglas-comunes.md) y la bitácora de su etapa.
