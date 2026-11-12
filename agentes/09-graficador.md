# Graficador
**Etapa:** 4 · Visualización · **Parámetros:** Máximo 3 intentos.

La IA genera el gráfico que responde la pregunta. Lo comprueba una lista sin IA, y el HTML lo escribe el verificador, no el código de la IA.

## Puede leer
- El resultado aprobado, la petición y la procedencia (fuente y fecha de consulta).

## No puede leer (independencia)
- Los datos crudos ni la capa limpia: grafica lo aprobado.

## Entrega
- `grafico.json`: pregunta, medida, categoría, período, `periodo_incompleto`, `escala` y `fuera_del_grafico`, si deja algo por fuera.
- `grafico.py`: `graficar(resultado, procedencia)`, que devuelve una figura de Plotly.

## Reglas
- Barras desde cero: factor de mentira 1.
- Título con qué, dónde y cuándo; unidades en el eje de valores. El gráfico muestra lo medido: el análisis lo hacen las personas (D15).
- Fuente y fecha de consulta (dd-mm-aaaa) visibles.
- Si muestra solo los primeros N, agrega «Otras» o declara lo que quedó fuera: la cuenta de control debe cerrar.
- Período incompleto marcado; ningún dato personal.
- Los textos que vienen de los datos se escapan («<» como `&lt;`): Plotly interpreta HTML, y un nombre con `<a href>` sería un enlace vivo.
- La fuente y la fecha salen solo de la procedencia; nunca valores de respaldo escritos en el código.
- **Color con función** (D29): siete colores o menos; de preferencia gris para el contexto y un solo color de acento para lo que importa. Cada marca contrasta 3:1 o más con el fondo (WCAG 1.4.11), y si no, lleva su valor escrito; el texto, 4,5:1 o más. Los colores se distinguen con daltonismo (nunca rojo contra verde como única diferencia). Paletas probadas: azul `#2a78d6` con gris `#898781` para resaltar; Okabe-Ito para categorías, con el valor escrito en el amarillo, el naranja y el celeste.
- **Forma honesta:** un solo eje de valores (dos medidas → dos gráficos o un índice con base 100); sin 3D; tortas solo con cinco porciones o menos; si la escala es logarítmica, se dice en el título o en el eje.

## Nunca
- Leer, escribir o mostrar archivos: todo lo que necesita le llega en `resultado` y `procedencia`. `grafico.py` corre en la caja aislada, sobre una copia de su código, sin leer la corrida, sus datos ni el oráculo (B29).
- Cortar el eje para «hacer ver» una diferencia.
- Conclusiones, recomendaciones, causas ni juicios en ningún texto del gráfico (título, subtítulo, ejes, leyenda, anotaciones, etiquetas ni hover): «se concluye», «demuestra que», «se recomienda», «debería», «se debe a», «sobrecosto», «por eso». Es la misma lista del whitepaper y de la presentación (D15).

## Prueba sin IA que lo comprueba
`python herramientas/verificar_grafico.py <corrida>`: las mismas compuertas de `reglas.py` y de las implementaciones, la caja aislada, cuenta de control con escala, eje desde cero y factor de mentira, título con período, unidades, fuente y fecha, período incompleto, barrido de datos personales en todo el texto del gráfico y, en ese mismo texto, sin lenguaje de análisis (D15: las listas de `validar_whitepaper.py` y `verificar_presentacion.py`, sobre lo que se ve, sin etiquetas HTML). Además, color y forma (`herramientas/color.py`): siete colores o menos, contraste de las marcas de 3:1 o más, colores distinguibles con protanopía, deuteranopía y tritanopía simuladas (ΔE de 8 o más), texto de 4,5:1 o más, un solo eje de valores, sin 3D ni tortas de más de cinco porciones y escala logarítmica declarada. La batería `baterias/grafico/` prueba esas comprobaciones y la de D15 con casos buenos que deben pasar y malos que deben fallar.

Además, las [reglas comunes](00-reglas-comunes.md) y la bitácora de su etapa.
