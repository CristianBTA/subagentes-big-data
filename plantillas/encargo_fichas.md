# Encargo: fichas de oportunidad de datos públicos grandes ({{DOMINIO}})

## Objetivo

Escribir una ficha por conjunto. Cada ficha muestra:
- qué se puede afirmar de cada unidad: «este contrato está así, aquí, y toca a tal sector»;
- qué preguntas de **costo, calidad e impacto** pueden analizar las personas;
- con qué otros conjuntos se cruza;
- cómo se gobiernan los datos personales;
- cómo se procesa según el tamaño medido.

**La IA no concluye:** el análisis lo hacen las personas. Tú propones la ficha y `validar_ficha.py` la comprueba contra la fuente real.

## Candidatos

| id | nombre | filas |
|---|---|---|
{{CANDIDATOS}}

## Fuentes autorizadas (no se negocia)

Solo puedes conectarte a estos conjuntos, que autorizó el dueño: **{{AUTORIZADOS}}**.
- No consultes, cruces ni explores ningún otro conjunto del portal, aunque lo conozcas o aparezca en otra parte.
- Un cruce con un conjunto no autorizado no pasa el validador (V0).
- Si una pregunta necesitaría otro conjunto, anótalo en `riesgos_de_lectura` para que el dueño decida si lo autoriza.

## Insumos

Solo lees estos. Junto a cada ficha está `<id>.dictamen.json`, el tamaño medido sin IA. **No lo modifiques**; copia su `nivel` en `nivel_big_data`.
- Columnas de cada conjunto autorizado: `{{INVENTARIO}}`.
- Consultas de exploración: solo agregadas, como máximo 12 por conjunto. Por ejemplo: `curl -sG "https://{{DOMINIO}}/resource/<id>.json" --data-urlencode '$query=SELECT estado, count(*) AS n GROUP BY estado ORDER BY n DESC LIMIT 20'`. Nunca filas sueltas ni columnas personales.

## Formato: `fichas/<id>.json`

```json
{"id": "<id>", "dominio": "{{DOMINIO}}", "nivel_big_data": 3,
 "grano": {"una_fila_es": "…", "llave": ["…"], "columna_de_conteo": null},
 "que_se_puede_decir": [{"tipo": "estado|lugar|impacto|dinero|tiempo", "plantilla": "El contrato {id_contrato} está {estado} …", "columnas": ["…"]}],
 "preguntas": [{"tipo": "costo|calidad|impacto", "pregunta": "¿…?", "por_que_importa": "…", "columnas": ["…"],
                "consulta_soql": "SELECT … GROUP BY … HAVING count(*) >= 5 LIMIT 20"}],
 "cruces": [{"con": "<id>", "llave_aqui": "…", "llave_alla": "…", "normalizacion": "tal cual", "para_que": "…"}],
 "gobernanza": {"excluir": ["…"], "seudonimizar": [], "k_minimo": 5, "base_legal": "Ley 1712 de 2014 y Ley 1581 de 2012", "nota": "…"},
 "procesamiento": {"estrategia": "…", "pasos": ["…"]},
 "riesgos_de_lectura": ["…"]}
```

## Reglas (las comprueba el validador)

1. **Grano (V10).** Di qué es una fila y cuál es su llave; se mide que la llave sea única. Si el conjunto es muy grande, acota esa medición con `grano.muestra_where`. Si cada fila es un grupo con una columna de conteo, **súmala**: no cuentes filas.
2. **Preguntas.** Entre 2 y 6, cada una con «¿» y «?», sin cifras y sin conclusiones.
   - Las plantillas, las preguntas, su `por_que_importa` y el `para_que` de un cruce no concluyen, no recomiendan, no buscan causas ni juzgan (V6, con la lista D15 del whitepaper): ni «se concluye», «esto muestra que», «se recomienda», «hay que», «conviene», «por eso», «se debe a» ni «sobrecosto», tampoco negados. En los textos de método (nota, riesgos de lectura, pasos) puedes indicar el método («hay que unificar los nombres antes de comparar»), sin conclusiones, causas ni juicios.
   - **Costo:** suma dinero y lo **contrasta** con una referencia (V9 y V16): valor del contrato frente a lo pagado, precio base frente a lo adjudicado.
   - **Calidad:** mira estados, fechas, vacíos o días adicionados.
   - **Impacto:** agrupa por lugar, sector o población.
3. **Consultas (V4 y V14).** Agregadas, con LIMIT 50 o menos, y con `HAVING count(*) >= k_minimo` si hay columnas de personas.
4. **Dinero creíble (V11).** Ningún registro puede pesar más de la mitad del total: pon un tope explícito en el WHERE y dilo.
5. **Lugar (V12).** No uses columnas que sean mayoría de «No disponible» ni una sola sede. En SECOP, `departamento` y `ciudad` son la sede de la entidad, no el lugar de ejecución.
6. **Cruces (V5 y V13).** Con llaves de negocio (`id_contrato`, `id_portafolio`, `proceso_de_compra`, `divipola`); nunca por el NIT de la entidad, porque es muchos a muchos. Si no hay un cruce con propósito, deja la lista vacía.
7. **Datos personales (V3).**
   - Todas las columnas personales, cuasi-identificadoras o de datos sensibles (un diagnóstico, la etnia, la discapacidad) van en `excluir` o en `seudonimizar`, incluidos nombres de proveedores, matrículas inmobiliarias y folios.
   - En datos sensibles (salud, víctimas, menores), solo afirmaciones agregadas y k de 10 o más.
8. **Base legal (V15 y V6).** Cita la Ley 1712 de 2014 y, si hay personas naturales, la Ley 1581 de 2012. Solo normas que estén en `baterias/normas/verificadas.json`.
9. **Procesamiento (V8).** Coherente con el nivel medido.
   - Nivel 3: agregar en la fuente, o `$select` de pocas columnas y `$where` por año → Parquet → DuckDB (o Spark).
   - Nivel 2: DuckDB, Parquet o por partes.
   - Nivel 1: pandas.

## Bucle por ficha

1. Escribe la ficha.
2. Valídala: `{{PYTHON}} {{VALIDADOR}} fichas/<id>.json --inventario {{INVENTARIO}} --autorizados {{AUTORIZADOS_CSV}} --cache .cache_soql.json`.
3. Corrige **la ficha**, nunca el validador. Tienes como máximo 4 intentos.

La verificación final la hace el dueño, sin caché.

**Prohibido:**
- Escribir fuera de esta carpeta, modificar los dictámenes y usar git o gh.
- **Modificar el agente:** herramientas, plantillas, baterías, `flujo.js` o sus documentos, ni siquiera para investigar o para «arreglar» algo que falle. El agente se usa, no se modifica. Antes de tu turno se sella su huella y al final se compara: si cambió algo, la corrida no vale. Si crees que una herramienta tiene un error, anótalo en tu respuesta.
