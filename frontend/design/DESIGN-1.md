# AgentA: hoja de cálculo verificable

Fase exclusivamente visual. Plan redactado y revisado antes de implementar.

## Primera pasada: decisiones

Paleta base: hoja `#FFFFFF`, superficie `#EEF3F8`, tinta azul `#182D49`,
acción `#234DB5`, lectura secundaria `#506279`, verificación `#146B60`.
El azul reemplaza al cobre porque conecta selección, navegación y cálculo.
El verde identifica comprobación; las alertas usan rojo `#A32840` sobre
`#FBECEE`, junto a texto explícito, sin depender del color.

Instrument Sans sirve títulos y cuerpo: aperturas claras, buena lectura en
pantallas pequeñas y cifras tabulares que permiten comparar presupuestos.
Fragment Mono se reserva para ecuaciones y matrices, donde la alineación sí
es información. No se heredan IBM Plex ni Geist, presentes en el historial.
Títulos completos a 28–40 px, secciones a 19–20 px, cuerpo a 14–16 px.

Proyectos: registro de expedientes, filas amplias y presupuestos alineados a
la derecha; en móvil el importe cae bajo el nombre. Nueva estimación:
datos del proyecto a la izquierda y enunciado a la derecha, apilados en móvil.
Resultado: enunciado como referencia lateral, resumen de lectura amplia,
desarrollo matemático debajo. Historial: fechas en una columna y narración
en otra, conectadas por una guía cronológica; una columna en móvil.
La alineación del texto es siempre izquierda y las cifras matriciales derecha.

Los paneles conservan su expansión nativa: Diagnóstico como comprobaciones,
Gauss como secuencia de eliminación, Gauss-Jordan como reducción de la
matriz ampliada e Inversa con su bloque de matriz y componentes. Corchetes,
barra de ampliación y numeración de operaciones expresan matemática real.

La marca entre corchetes es el gesto distintivo. La jerarquía surge del
trabajo del empleado: elegir expediente, describir recursos, leer decisión,
comprobar operaciones. Controles de al menos 44 px y navegación inferior
en móvil acompañan ese recorrido.

## Segunda pasada: revisión de los seis patrones

1. Se evitan cajas redondeadas repetidas: filas para proyectos, guía temporal
   para historial, zonas de trabajo para el formulario y paneles desplegables
   para cálculo. El radio de 4 px identifica controles; una esquina de 12 px
   identifica el enunciado de referencia. No se aplica un radio universal.
2. Se evita crema, terracota y serif de contraste: paleta fría y tipografía
   sans elegidas para lectura operacional.
3. Se evita casi negro con acento ácido: el oscuro existente se redefine en
   azul profundo `#162B46`, hoja `#203B59`, tinta `#F1F6FC`, texto secundario
   `#BACCDD`, acción `#A9C5FF` y verificación `#86D9C8`.
4. Se evitan tarjetas SaaS, sombras uniformes y gradientes decorativos.
   Se descartó también la retícula decorativa de fondo para dejar que las
   matrices reales aporten la estructura matemática.
5. Se eliminan los puntos medios del encabezado y selector, los eyebrows
   decorativos y el monoespaciado de fechas, presupuestos y etiquetas.
   Fechas y estado conservan su contenido, debajo del título. La tinta es
   un azul intencional, no un sustituto casi negro. No hay flechas añadidas
   a botones ni etiquetas con guion largo decorativo.
6. No se resaltan palabras aisladas del título ni se usan etiquetas en
   mayúsculas. La numeración pertenece solo a secuencias reales de cálculo.

Además se evitó convertir la eliminación de tarjetas en un diseño de
periódico: hay espacios amplios, superficies funcionales y controles claros.

## Límites

Se conservan rutas, autenticación, Server Actions, llamadas y contratos API,
helpers de datos, validación, matrices, operaciones y texto del agente.
`markdown-summary.tsx` permanece intacto. El token heredado `--copper` es
un alias del nuevo azul para mantener coherencia con ese renderizador.
Las utilidades de movimiento se desactivan con `prefers-reduced-motion`.

La evidencia y sus condiciones de reproducción se documentan en
`verification/README.md`.
