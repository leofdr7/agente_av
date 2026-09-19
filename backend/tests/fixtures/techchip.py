"""Datos del caso TechChip Systems S.A.: consumo de recursos por línea de producto.

Cada fila de A es un recurso y cada columna una línea de producto (x1..x6), de modo
que A*X = B expresa el consumo total de cada recurso.

Inconsistencia conocida en la guía impresa
------------------------------------------
La guía lista como disponibilidades el vector `B_LITERAL_GUIA` y afirma que la
respuesta es X = (15, 20, 25, 10, 15, 20). Ambas cosas no pueden ser ciertas a la
vez: con `B_LITERAL_GUIA` el sistema sí es compatible determinado (det(A) = -83),
pero su solución única es

    X = (-105/83, 345/83, 2430/83, 1170/83, 1130/83, 2010/83)
      ≈ (-1.265, 4.157, 29.277, 14.096, 13.614, 24.217)

cuyo x1 es negativo y por tanto no producible. El vector que sí reproduce la
respuesta esperada es `B_PRIMARIO`, que es exactamente A*(15, 20, 25, 10, 15, 20).
Por eso `B_PRIMARIO` es el dataset por defecto y `B_LITERAL_GUIA` se conserva
documentado en el test correspondiente.
"""

RESOURCE_NAMES = [
    "litografia EUV",
    "pruebas ATE",
    "resina de encapsulado",
    "sustrato de silicio",
    "energia de cortado laser",
    "inspeccion optica",
]

VARIABLE_NAMES = [
    "AI-Edge 1",
    "AI-Server Pro",
    "AI-Autonomous Car",
    "AI-IoT LowPower",
    "AI-Robotics Heavy",
    "AI-Medical Vision",
]

A = [
    [2, 1, 3, 1, 2, 1],
    [1, 3, 2, 2, 1, 2],
    [3, 2, 4, 1, 3, 2],
    [1, 1, 1, 4, 2, 1],
    [2, 1, 2, 1, 5, 3],
    [1, 2, 1, 2, 1, 4],
]

# Coherente con el ejercicio: B_PRIMARIO == A * X_ESPERADA.
B_PRIMARIO = [185, 200, 280, 150, 245, 195]

# Disponibilidades tal y como aparecen impresas en la guía (ver nota superior).
B_LITERAL_GUIA = [155, 160, 225, 140, 215, 175]

# Vector activo en los tests. Cambiar a B_LITERAL_GUIA con esta única línea.
DATASET_B = B_PRIMARIO

X_ESPERADA = [15, 20, 25, 10, 15, 20]

X_REAL_CON_B_LITERAL = [
    -1.26506024,
    4.15662651,
    29.27710843,
    14.09638554,
    13.61445783,
    24.21686747,
]

DET_A = -83

# Escenario de escasez: se recorta B3 (resina de encapsulado) de 280 a 100.
SCARCITY_RESOURCE_INDEX = 2
SCARCITY_VALUE = 100

X_CON_ESCASEZ = [
    -440.42168675,
    -103.61445783,
    304.75903614,
    44.69879518,
    56.20481928,
    98.07228916,
]
