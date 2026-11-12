# Agente masivo de datos públicos: cómo usarlo

El agente recorre un catálogo completo de datos abiertos (datos.gov.co tiene 8.470 conjuntos). Con mediciones sin IA, encuentra los conjuntos que son **big data de verdad** y que permiten decir «esta unidad está así, aquí, y tiene tal impacto» (un contrato, un caso de salud, una estación de medición, un trámite). A los mejores les pide a la IA una **ficha de oportunidad**: preguntas de costo, calidad e impacto para que **las personas** hagan el análisis. Después valida cada ficha sin IA contra la fuente real.

La IA propone y una prueba sin IA comprueba. **Que una ficha pase el validador no la hace publicable:** el validador mide la forma y el juicio de valor lo hacen un juez ciego y las personas.

## Antes de empezar

```bash
git clone https://github.com/CristianBTA/subagentes-big-data && cd subagentes-big-data
python3.13 -m venv .venv && .venv/bin/pip install --require-hashes -r requirements.txt
```

En macOS, usa el Python 3.13 de Homebrew o, si es el del instalador de python.org, corre antes una vez «Install Certificates.command» (en la carpeta de Python 3.13, dentro de Aplicaciones): ese Python no trae los certificados raíz, y la ingesta, el agente masivo y la vigilancia de dependencias se detienen con «certificado no verificado» en vez de consultar datos.gov.co.

**La primera vez cuenta las filas de todo el catálogo**, y eso tarda horas: unos 8.470 conjuntos, de 1 a 4 segundos cada uno. Queda en `fuentes/catalogo/.cache.json`; las veces siguientes usa esa caché, y `--actualizar` retoma el conteo. Nada de eso entra a Git.

## Fuentes autorizadas: el agente no se conecta a nada que no declares

El agente **no trae ningún conjunto por defecto,** ni SECOP ni otro, y **no elige solo a qué datos conectarse.** Trabaja únicamente con los conjuntos que declara el dueño, cada uno con su id de Socrata (la forma `abcd-1234`):

```bash
--conjuntos <id>,<id>          # o un archivo:  --fuentes fuentes.json
```

`fuentes.json` tiene esta forma: `{"dominio": "www.datos.gov.co", "conjuntos": ["<id>"], "nota": "por qué se autoriza"}`.

- **Sin fuentes declaradas no se conecta a ningún conjunto:** explica cómo declararlas y termina.
- **`--descubrir`** recorre el catálogo del portal, con tu permiso explícito, **solo para sugerir** candidatos y el comando para autorizarlos. No trabaja con ninguno hasta que lo autorices.
- **Se le sugiere de qué se va a tratar con `--tema`:** `--descubrir --tema "salud"` (o «movilidad transporte», «educación», «energía», «víctimas»…) propone los conjuntos grandes de ese tema, buscando en el nombre, la categoría, el publicador y las columnas. Si ninguno del tema llega a `--min-filas`, lo dice y muestra los más grandes; decides tú.
- **Sin tema,** propone conjuntos que digan al menos dos de estado, lugar e impacto, con un tope de 2 por publicador (`--por-publicador`), para que una sola fuente no llene la lista. Medido el 7 de noviembre de 2026 en el catálogo de datos.gov.co (8.470 conjuntos): la regla anterior, que exigía los tres, solo dejaba pasar 5 conjuntos de 1.000.000 de filas o más, y los 5 eran de SECOP. Ahora la lista trae contratación, catastro, salud, tránsito, educación y ambiente, y nombra los temas del portal para sugerir uno.
- Las sugerencias quedan en `sugerencias.json`, en la carpeta de trabajo.
- La lista queda en `fuentes_autorizadas.json`, en la carpeta de trabajo, y el whitepaper la muestra.
- El encargo le prohíbe a la IA consultar o cruzar otros conjuntos, y el validador lo comprueba sin IA (V0): una ficha o un cruce con un conjunto no autorizado no pasa.

## Tres formas de invocarlo

### 1. Desde la terminal: el agente lanza la IA que escribe las fichas (Claude, agy o Codex)

```bash
.venv/bin/python herramientas/agente_masivo.py www.datos.gov.co --trabajo fuentes/fichas/mi-corrida --conjuntos <los que autorizas> --motor claude   # o agy, o codex
```

Las tres herramientas se invocan sin interacción, como en `orquestar.mjs`. **Servidores MCP:** Claude corre sin ninguno (`--strict-mcp-config`); agy y Codex, en cambio, cargan los MCP de tu configuración (`~/.gemini/config/mcp_config.json` y `~/.codex/config.toml`), que pueden conectarse a tu navegador. `orquestar.mjs` sí los apaga; aquí todavía no. Si no quieres eso, usa `--motor claude` o `--motor ninguno`. Se puede cambiar el binario con `CLAUDE_BIN`, `AGY_BIN` o `CODEX_BIN`. Claude usa el perfil de `CLAUDE_CONFIG_DIR`, si está definido.

**Conviene correrlo con más de una IA** (por ejemplo, Claude y agy, cada una en su carpeta de trabajo) y comparar: una IA encuentra lo que la otra no ve. El tamaño ya medido se reutiliza entre corridas.

### 2. Desde dentro de tu IA de terminal (Claude Code, Codex, Gemini CLI u otra)

Pégale este texto:

```text
En la carpeta del repositorio subagentes-big-data corre: .venv/bin/python herramientas/agente_masivo.py www.datos.gov.co --trabajo fuentes/fichas/mi-corrida --conjuntos <los conjuntos que autorizo> --motor ninguno. Después escribe las fichas siguiendo el ENCARGO.md que genera en esa carpeta, cada una con su bucle de validación, sin tocar los archivos *.dictamen.json. Al final corre el mismo comando con --solo-validar y muéstrame RESULTADO.md.
```

### 3. Paso a paso, sin ninguna IA conectada

1. Corre el comando con `--motor ninguno`. Deja listos los candidatos, su tamaño medido y el `ENCARGO.md`.
2. Escribe o consigue las fichas en `fuentes/fichas/mi-corrida/fichas/<id>.json`.
3. Valida con `--solo-validar`.

**Los chats sin terminal** (ChatGPT o Gemini en el navegador) no sirven para este agente: necesita leer el catálogo local y consultar el portal. Para aportar al repositorio desde un chat está [«Conectar la IA»](README.md#conectar-la-ia).

## Llamarlo con una palabra, en tu propia herramienta

Si tu IA de terminal permite comandos propios, crea uno con el texto de la forma 2 y un nombre como `agente-masivo`. Ese comando va en **tu** configuración personal, **nunca dentro de este repositorio**. Por ejemplo, en Claude Code es un archivo en `~/.claude/commands/`.

## Opciones

| Opción | Qué hace |
|---|---|
| `<dominio>` | El portal Socrata, por ejemplo `www.datos.gov.co` |
| `--trabajo <carpeta>` | Dónde quedan `ENCARGO.md`, `fichas/` y `RESULTADO.md` |
| `--conjuntos <id,…>` o `--fuentes <archivo>` | **Las únicas fuentes a las que se conecta** (obligatorio para trabajar) |
| `--descubrir` | Con tu permiso: recorre el catálogo y sugiere candidatos, sin trabajar con ninguno |
| `--tema "<de qué se va a tratar>"` | Con `--descubrir`: sugiere los conjuntos de ese tema (por ejemplo `"salud"`) |
| `--top 8` | Cuántos candidatos sugiere `--descubrir` |
| `--por-publicador 2` | Con `--descubrir`: cuántos candidatos del mismo publicador, como máximo (`0`, sin tope) |
| `--min-filas 1000000` | Tamaño mínimo para ser candidato |
| `--motor claude`, `agy`, `codex` o `ninguno` | Esa IA escribe las fichas, o se imprime el texto para pegarlo en otra |
| `--actualizar` | Retoma el conteo del catálogo completo |
| `--solo-validar` | Solo valida las fichas que ya están en la carpeta |

## Qué hace, paso a paso

1. **Catálogo sin IA** (`explorador_catalogo.py`): inventario, filas reales y riesgo de datos personales.
2. **Relevancia sin IA** (`relevancia_catalogo.py`): si cada conjunto permite decir estado, lugar e impacto, y con qué llaves de cruce.
3. **Candidatos:** los que autorizaste. Con `--descubrir`, solo sugerencias: los del tema que sugeriste o, sin tema, los mejores con al menos `--min-filas`, de varios publicadores.
4. **Tamaño medido sin IA** (`dictamen_bigdata.py`): nivel 1, «no es big data»; nivel 2, «frontera»; nivel 3, «big data». La IA no escribe este dato. Si un conjunto no se puede medir, el agente lo avisa y lo deja fuera.
5. **Encargo para la IA,** desde `plantillas/encargo_fichas.md`.
6. **La IA escribe las fichas.**
7. **Validación sin IA,** contra la fuente real y sin caché (`validar_ficha.py`, de V1 a V16): columnas, consultas reales, cruces medidos, grano, sumas creíbles, lugar, k-anonimato, normas verificadas y que no haya conclusiones (con la lista D15 del whitepaper del pipeline). El resultado queda en `RESULTADO.md`.
8. **Whitepaper para el estudiante, sin IA** (`whitepaper_fichas.py`): el resumen en **tres hojas tamaño carta** (`WHITEPAPER.pdf` y `.html`). La primera hoja es el panorama con la tabla de conjuntos; la segunda y la tercera, las fichas y una guía para el análisis. No concluye ni agrega cifras: el análisis lo hace el estudiante, y el resumen de la IA entra solo si pasa la misma lista D15. Se imprime con Chrome y se cuentan las páginas; la letra no baja de 8,5 pt, y si no caben todas las fichas, el documento nombra las que quedaron fuera.

## Uso local: el agente se usa, no se modifica

El agente es para correrlo en tu máquina. La IA que escribe las fichas, o la que haga una investigación con él, **solo escribe en la carpeta de trabajo; nunca cambia el agente.** Para que no dependa de que la IA obedezca:
- Antes de darle el turno, el agente sella la huella SHA-256 de lo que lo forma: `herramientas/`, `plantillas/`, `baterias/`, `flujo.js`, `orquestar.mjs` y estos documentos. Al terminar la compara. Si algo cambió, **la corrida no vale**: `RESULTADO.md` lo dice con los archivos.
- La validación final corre con las herramientas de la versión de Git (`git archive HEAD`), no con las de la carpeta.
- El catálogo, las fichas y los resultados viven en `fuentes/`, que está fuera de Git: nada de una corrida se publica. Si `--trabajo` apunta a una carpeta que Git versionaría, el agente se detiene antes de escribir nada.
- Para cambiar el agente, el camino es un aporte, no una corrida: [`APORTAR-CON-TU-AGENTE.md`](APORTAR-CON-TU-AGENTE.md).
- Autoprueba sin red: `.venv/bin/python herramientas/agente_masivo.py --autoprueba`.

## Reglas que el agente no negocia

- Ninguna fila de datos se guarda en el repositorio: todo vive en `fuentes/`, que está fuera de Git.
- Las columnas personales se excluyen. Que un dato sea público no autoriza a usar cédulas, cuentas ni nombres (Ley 1712 de 2014 y Ley 1581 de 2012).
- **La IA no concluye:** el análisis lo hacen las personas.
