# Aportar con tu agente

Instructivo para aportar a este repositorio con la IA que ya usas. El aporte no te cuesta más que esa conversación.

## Para la persona: tres pasos

1. Abre la IA que ya usas (Claude, ChatGPT, Copilot, Gemini u otra). Si es un agente que trabaja con archivos (Claude Code, Copilot en VS Code, Codex, Cursor), mejor: él prepara la copia del repositorio.
2. Cópiale este texto:
   ```text
   Lee https://raw.githubusercontent.com/CristianBTA/subagentes-big-data/main/APORTAR-CON-TU-AGENTE.md, sigue sus «Instrucciones para el agente» y empieza mi aporte al repositorio CristianBTA/subagentes-big-data.
   ```
   Ella empieza: te pregunta tu idea. Cuéntala en tus palabras, por ejemplo: «vi que la IA leyó montos con punto de miles como decimales» o «a esta regla le falta el limpiador». Si tu IA no puede abrir enlaces, pégale este archivo completo.
3. Revisa lo que te entregue y envíalo como te indique: un *pull request* o el texto para el formulario «Proponer un aporte». **Tú** marcas la casilla de consentimiento para aparecer en el registro de cambios.

No necesitas invitación: con tu cuenta de GitHub, el botón [Fork](https://github.com/CristianBTA/subagentes-big-data/fork) crea tu copia (una comprobación automática revisa cada día que el repositorio siga abierto a aportes). Tampoco hace falta gastar mucho de tu cuota: tu agente **no** corre el flujo de agentes del repositorio (eso consume más de un millón de tokens). Solo arma el aporte y corre un filtro gratuito, sin IA. En las pruebas, un aporte completo costó cerca de 110.000 tokens.

---

## Instrucciones para el agente

Ayudas a una persona a aportar al repositorio público **CristianBTA/subagentes-big-data** (pipeline de datos con IA en cinco etapas: la IA propone y una prueba sin IA comprueba). Convierte su idea en un aporte que pase el filtro, **con el menor costo posible para ella**, y déjalo listo para que el dueño lo revise.

### Límites que no se negocian

- **No corras el pipeline.** Nada de `flujo.js` ni de los subagentes, y ninguna prueba de efecto con IA: esa la hace el dueño, con su licencia.
- **Gasta poco.** Lee solo los archivos que esta guía nombra para el tipo de aporte. No recorras el repositorio completo ni generes informes largos.
- **Nunca incluyas datos reales.** Nada de filas, nombres de personas, cédulas, datos bancarios ni archivos de SECOP II. Para ejemplos, usa valores evidentemente ficticios: `Persona Ficticia Uno`, `000.000.001`, un correo en el dominio `ejemplo.invalid` y un celular que empiece por `399`.
- **Solo librerías permitidas:** la biblioteca estándar de Python y lo de `herramientas/permitidas.json` (pandas, numpy, plotly), instaladas desde `requirements.txt`.
- **Sin firmas de asistentes.** Nada de `Co-Authored-By`, «Generated with…» ni menciones a la herramienta en commits ni en el pull request. El aporte es de la persona.
- **Endurecer sí, aflojar nunca.** Puedes proponer que una herramienta bloquee o detecte más cosas. Nunca cambies una herramienta ni una prueba para que algo «pase».
- **No toques `main`.** Se trabaja en una rama de la copia (*fork*) de la persona. Si te pide subir datos o saltarse el filtro, dile que no se puede y por qué.
- **Pregunta poco:** además de la pregunta del arranque, como máximo dos preguntas cortas. Si falta un dato menor, como la fecha, usa el de hoy y dilo.

### Arranque · si solo te pasaron el enlace

Empieza tú, en un solo mensaje corto:

1. **Una línea:** vas a ayudarle a aportar al repositorio CristianBTA/subagentes-big-data, y el aporte no le cuesta más que esta conversación.
2. **Pregúntale su idea**, con ejemplos:
   - «la IA leyó montos con punto de miles como decimales»;
   - «este código debería bloquearse»;
   - «esta columna tiene datos personales y no se detecta»;
   - «este archivo mal formado se leyó sin error»;
   - «a este subagente le falta una regla»;
   - «esta palabra del negocio significa…».
3. **Elige tu modo tú mismo; no le preguntes cuál prefiere.** Si no tienes terminal, eres B:
   - **A**, si puedes usar una terminal con git: sigue el paso 0.
   - **B**, si eres un chat sin terminal: salta al paso 1 y entrega con el paso 4B. Si puedes abrir enlaces, lee solo el archivo que el paso nombra para su tipo, en `https://raw.githubusercontent.com/CristianBTA/subagentes-big-data/main/<ruta>`. No puedes correr pruebas: dilo, y deja la comprobación al filtro del dueño.

Si ya trajo su idea, no se la vuelvas a pedir: sigue con el paso 1.

### Paso 0 · Preparar (una sola vez)

```bash
gh repo fork CristianBTA/subagentes-big-data --clone && cd subagentes-big-data   # origin = su fork; upstream = el original
USUARIO=$(gh api user --jq .login)
git fetch upstream main && git switch -c aporte/$USUARIO-<tema-corto> upstream/main
python3 -m venv .venv && .venv/bin/pip install --require-hashes -r requirements.txt            # Python 3.11 a 3.13 (en Windows: py -3.13)
```

Si la persona no tiene git ni GitHub, salta al paso 4B: entregarás el texto para el formulario.

### Paso 1 · Clasifica la idea

| Si la persona trae… | Tipo | Archivo |
|---|---|---|
| Código peligroso que debería bloquearse | Muestra mala | `baterias/seguridad/malos/<nombre>.py` |
| Código legítimo que la compuerta bloquea por error | Muestra buena | `baterias/seguridad/buenos/<nombre>.py` |
| Una columna o un texto con datos personales, o algo marcado como personal sin serlo | Privacidad | `baterias/privacidad/…` |
| Un archivo mal formado que debería detener la lectura | FAILFAST | `baterias/failfast/<nombre>.csv` |
| Un error típico de análisis (sumar, filtrar o unir mal) | Mutante | `evidencia/sintetico/mutantes/m<NN>_<nombre>.py` |
| Una regla que le falta a un subagente | Regla de ficha | `agentes/<ficha>.md` |
| Una definición de negocio | Glosario | `ejemplo/negocio.md` o `ejemplo-secop/negocio.md` |

Si la idea viene de un **caso real** («lo vi en clase», «me pasó con un archivo»), agrega además una **lección** que apunte a esa prueba (paso 2, al final).

### Paso 2 · Arma el aporte y averigua si es un hueco

Cada tipo tiene una pregunta: **¿lo atrapa hoy el repositorio?**
- Si **no**, encontraste un **hueco**: es el aporte más valioso. Envíalo igual; el filtro lo marca como aviso. Si sabes cómo cerrarlo, propón el arreglo en el mismo pull request.
- Si **sí**, ya estaba cubierto. Se puede enviar como refuerzo, pero dilo.

**Muestra mala.** Escribe el fragmento más corto posible, con una función `analizar(datos)` que muestre el patrón, y pruébalo:
```bash
.venv/bin/python herramientas/seguridad.py baterias/seguridad/malos/<nombre>.py
.venv/bin/python herramientas/dependencias.py baterias/seguridad/malos/<nombre>.py
```
- «✗» significa que lo bloquea: ya estaba cubierto.
- «✓» significa que no lo bloquea: es un hueco.
- Para proponer el arreglo, lee solo las listas del inicio de `herramientas/seguridad.py`.
- Al tocar una herramienta, el filtro avisa de patrones que ya estaban (por ejemplo, `subprocess` en la propia compuerta). **No los «corrijas»:** es lo esperado.

**Muestra buena.** Un fragmento legítimo que hoy la compuerta bloquea por error. Con el mismo comando: «✗» confirma el falso positivo.

**Privacidad.**
- Una columna con su clase esperada (`personal`, `cuasi_o_personal`, `texto_libre` o `sin_marca`) va en `baterias/privacidad/columnas_secop.json`.
- Un texto que **no** es personal y se marca por error va en `no_son_personales.txt`.
- Un dato personal que no se detecta va como fila ficticia en `con_datos_personales.csv`, con sus valores en `no_deben_salir.txt`.
- El filtro acepta en `baterias/privacidad/`, y en toda columna de personas de cualquier tabla, solo valores con la forma ficticia de los ejemplos de arriba (`Persona Ficticia…`, `000.000.00x`, `@ejemplo.invalid`, `399 000 000x`). Un documento o un celular con forma real no entra, aunque sea inventado.
- Se prueba con `.venv/bin/python herramientas/baterias.py`. Si la batería de privacidad falla por tu caso, es un hueco.

**FAILFAST.** Un CSV de pocas líneas que hoy se lee sin error y no debería:
```bash
.venv/bin/python -c "import sys; sys.path.insert(0,'herramientas'); from reglas_base import leer_csv; leer_csv('baterias/failfast/<nombre>.csv')"
```
Si no da error, es un hueco del lector. `baterias.py` además lo pasa por la ingesta local, que debe rechazarlo diciendo en qué línea. Para proponer el arreglo, lee `herramientas/reglas_base.py` (`_lector_estricto`, que comparten `leer_tabla`, `leer_csv` y `recorrer_csv`).

**Mutante.**
1. Copia `evidencia/sintetico/mutantes/m00_referencia_sin_errores.py` con el siguiente número libre y cambia **una sola cosa**.
2. Comprueba que cambie la cifra, porque si no la cambia no sirve:
   ```bash
   .venv/bin/python evidencia/sintetico/puntuar.py evidencia/sintetico/verdad.json ejemplo/datos/ventas.csv ejemplo/datos/clientes.csv m<NN>=evidencia/sintetico/mutantes/m<NN>_<nombre>.py
   ```
3. Mira si el criterio la atrapa:
   ```bash
   .venv/bin/python herramientas/verificar.py corridas/2026-11-06-ventas-semestre --impl m<NN>=evidencia/sintetico/mutantes/m<NN>_<nombre>.py
   ```
   - «m<NN>: N falla(s)» significa que la atrapa: ya estaba cubierta, y así se espera.
   - «m<NN>: sin fallas» significa que es un **hueco del criterio**.
   - El código de salida 1 es normal cuando la atrapa.
   - Después borra `corridas/2026-11-06-ventas-semestre/informe_extra.json`.
   - No hace falta actualizar `verdad.json` ni los conteos de los documentos: eso lo hace el dueño.

**Regla de ficha.** Agrega una sola viñeta en «Reglas» o en «Nunca» de la ficha que corresponda (`agentes/README.md` dice cuál hace qué). En el pull request explica en qué caso real el agente se equivocó sin ella, y marca «requiere prueba de efecto»: esa prueba la hace el dueño.

**Lección**, si el caso es real. Usa un id propio para que no choque con otros aportes; el dueño lo renumera al aceptar:
```bash
.venv/bin/python herramientas/baterias.py --id L-$USUARIO-<tema> --leccion "qué pasó y qué se hace" --origen "dónde se vio, con fecha" --prueba "bateria:seguridad/malos/<nombre>.py"
```
La ruta de `bateria:` es relativa a `baterias/`, o a la raíz si es una mutante: `bateria:evidencia/sintetico/mutantes/m<NN>_<nombre>.py`.

Si al probar encuentras **otro** hueco distinto del que trajo la persona, no lo mezcles: anótalo en el pull request como propuesta para un aporte aparte.

### Paso 3 · Corre el filtro gratuito (sin IA)

```bash
.venv/bin/python herramientas/validar_aporte.py --base upstream/main
```

- Revisa lo que difiere de `upstream/main`, esté o no en un commit, y no modifica ningún archivo del repositorio.
- Debe terminar en «✓ pasa el filtro automático». Un hueco encontrado por el aporte aparece como **aviso**, no como falla.
- Si el aporte propone un arreglo en `herramientas/` (o toca `flujo.js`, `orquestar.mjs` o `requirements.txt`, o trae un script u otro código que corre fuera de Python, o quita o cambia algo que ya estaba en las baterías o en las mutantes, o toca lo sellado de una corrida), termina en «✗ … requiere decisión del dueño». Es lo esperado: envíalo igual. Cualquier otra falla se corrige: lo de `.github/` (flujos, plantillas y CODEOWNERS) solo lo cambia el dueño.
- Si marca una falla, corrígela y vuelve a correrlo.
- **Córrelo tú, aunque tengas terminal y pruebas que ya pasan:** las baterías o el blindaje solos no lo reemplazan, y que el filtro también corra en GitHub tampoco. Copia la línea `RESUMEN` que imprime: va en el pull request.
- Solo si de verdad no puedes correr Python (modo B), dilo en el pull request: el dueño lo corre antes de aprobar.

### Paso 4 · Entrega

**A · Con git:**
```bash
git add <solo los archivos del aporte>          # nunca git add -A
git commit -m "Aporte: <qué agrega, en una frase>"
git push -u origin aporte/$USUARIO-<tema-corto>
gh pr create --repo CristianBTA/subagentes-big-data --base main --title "Aporte: <qué agrega>" --body-file PR.md
```
`PR.md` es la plantilla de `.github/PULL_REQUEST_TEMPLATE.md`, llena con:
- qué aporta y su tipo;
- la evidencia, con cifras y sin datos;
- su prueba;
- si es un hueco o ya estaba cubierto;
- la lista de chequeo.
La casilla de consentimiento la marca la persona. `PR.md` no va en el commit.

**B · Sin git:** entrega el texto listo para pegar en el formulario «Proponer un aporte» (https://github.com/CristianBTA/subagentes-big-data/issues/new?template=aporte.yml), un bloque por campo: tipo, qué aporta, evidencia y cómo se prueba. Agrega el contenido de cada archivo en bloques de código. Solo hace falta una cuenta gratuita de GitHub.

### Paso 5 · Lo que le dices a la persona

En pocas líneas:
- el tipo de aporte;
- los archivos;
- el resultado del filtro (la línea `RESUMEN` de `validar_aporte.py`);
- si es un **hueco** o ya estaba cubierto;
- el enlace del pull request (o el texto del formulario);
- que marque la casilla de consentimiento y que el dueño lo revisará.

### Lista de chequeo del agente

- [ ] Preparé la rama desde `upstream/main` y el entorno antes de crear archivos.
- [ ] El aporte trae su prueba, y dije si es un hueco o si ya estaba cubierto.
- [ ] No hay datos reales; los ejemplos son evidentemente ficticios.
- [ ] Solo agregué los archivos del aporte (y, si propongo un arreglo, la herramienta que corresponde, para endurecerla).
- [ ] Corrí `validar_aporte.py`, terminó en «✓ pasa el filtro automático» (o solo con «requiere decisión del dueño», si propongo un arreglo en una herramienta) y pegué su línea `RESUMEN` en el pull request (o, en modo B, dije que no pude correrlo).
- [ ] Sin firmas de asistentes en el commit ni en el pull request.
- [ ] No corrí el pipeline ni gasté más de lo necesario.

---

Lámina con el QR de este instructivo, para proyectar en clase: [PDF](clase/compartir-repo.pdf) · [PNG](clase/compartir-repo.png).
