"""Reparto de harina, horno y amasado entre tres panes.

Caso independiente de TechChip: el enunciado no incluye la matriz en JSON y el
orden de filas y columnas queda fijado en la prosa. B = A * X_ESPERADA, con
det(A) = -10. La resolución de referencia es X = (4, 3, 2).
"""

from tests.fixtures import techchip

VARIABLE_NAMES = [
    "pan de caja",
    "baguette",
    "bolillo",
]

RESOURCE_NAMES = [
    "harina",
    "tiempo de horno",
    "tiempo de amasado",
]

A = [
    [2, 1, 3],
    [1, 2, 2],
    [3, 1, 1],
]

B = [17, 14, 17]

X_ESPERADA = [4, 3, 2]

PROBLEM_TEXT = """\
Una panadería quiere agotar exactamente la harina, el tiempo de horno y el tiempo \
de amasado de los que dispone hoy: 17 kg de harina, 14 minutos de horno y 17 \
minutos de amasado.

El consumo por lote, con las variables en el orden pan de caja, baguette y bolillo, \
es el siguiente.
Harina, en kilogramos: 2 por lote de pan de caja, 1 por lote de baguette y 3 por \
lote de bolillo.
Tiempo de horno, en minutos: 1 por lote de pan de caja, 2 por lote de baguette y 2 \
por lote de bolillo.
Tiempo de amasado, en minutos: 3 por lote de pan de caja, 1 por lote de baguette y \
1 por lote de bolillo.

¿Cuántos lotes de cada pan se pueden producir? Antes de interpretar, consulta la \
base de conocimiento por si hay notas internas sobre este proceso de panadería. Si \
no hay notas relevantes, quédate únicamente con este enunciado.\
"""

# Vocabulario que no puede colarse desde el caso de semiconductores ni desde el vault.
TERMINOS_PROHIBIDOS = list(
    dict.fromkeys(
        [
            "TechChip",
            "litografia EUV",
            "litografía EUV",
            "EUV",
            "resina de encapsulado",
            "resina",
            "encapsulado",
            "silicio",
            *techchip.RESOURCE_NAMES,
            *techchip.VARIABLE_NAMES,
        ]
    )
)
