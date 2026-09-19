"""Modelos de entrada, trazabilidad y resultado del motor de sistemas lineales AX=B."""

import math
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

# El diagnóstico usa aritmética exacta (SymPy), cuyo coste crece rápido con n.
# El caso de negocio es 6x6; el tope evita que un request arbitrario bloquee el proceso.
MAX_SYSTEM_SIZE = 20


class LinearSystemInput(BaseModel):
    """Sistema AX=B con A cuadrada nxn y B de longitud n."""

    A: list[list[float]] = Field(min_length=1, max_length=MAX_SYSTEM_SIZE)
    B: list[float] = Field(min_length=1, max_length=MAX_SYSTEM_SIZE)

    @model_validator(mode="after")
    def _check_dimensions(self) -> "LinearSystemInput":
        size = len(self.A)
        bad_rows = [i for i, row in enumerate(self.A) if len(row) != size]
        if bad_rows:
            raise ValueError(
                f"A debe ser cuadrada {size}x{size}; filas con longitud distinta: "
                + ", ".join(str(i + 1) for i in bad_rows)
            )
        if len(self.B) != size:
            raise ValueError(
                f"B debe tener {size} elementos para una A de {size}x{size}; "
                f"recibidos {len(self.B)}."
            )
        non_finite = [
            f"A[{i + 1}][{j + 1}]"
            for i, row in enumerate(self.A)
            for j, value in enumerate(row)
            if not math.isfinite(value)
        ] + [
            f"B[{i + 1}]"
            for i, value in enumerate(self.B)
            if not math.isfinite(value)
        ]
        if non_finite:
            raise ValueError(
                "Los coeficientes deben ser números finitos; valores inválidos en: "
                + ", ".join(non_finite)
            )
        return self

    @property
    def size(self) -> int:
        return len(self.A)


class SystemClassification(str, Enum):
    """Clasificación del sistema según det(A), rango(A) y rango([A|B])."""

    COMPATIBLE_DETERMINADO = "compatible_determinado"
    COMPATIBLE_INDETERMINADO = "compatible_indeterminado"
    INCOMPATIBLE = "incompatible"


class SystemDiagnosis(BaseModel):
    """Análisis previo obligatorio: se calcula antes de intentar resolver."""

    size: int
    determinant: float
    rank_a: int
    rank_augmented: int
    is_singular: bool
    classification: SystemClassification
    message: str


class SingularSystemAlert(SystemDiagnosis):
    """Diagnóstico de un sistema singular.

    Se devuelve en lugar de una solución: cuando det(A) ≈ 0 el motor se detiene y
    nunca acompaña a un vector X.
    """

    is_singular: Literal[True] = True


class SolutionMethod(str, Enum):
    GAUSS = "gauss"
    GAUSS_JORDAN = "gauss_jordan"
    MATRIX_INVERSE = "matrix_inverse"


class RowOperationKind(str, Enum):
    SWAP = "swap"
    SCALE = "scale"
    ELIMINATE = "eliminate"


class RowOperationStep(BaseModel):
    """Una operación elemental de fila y el estado de la matriz de trabajo tras aplicarla.

    Los índices son 0-based; `description` usa la notación matemática 1-based
    (`F3 <- F3 + (-2)*F1`).
    """

    kind: RowOperationKind
    target_row: int
    source_row: int | None = None
    factor: float | None = None
    description: str
    matrix_state: list[list[float]]


class SolutionComponentStep(BaseModel):
    """Despeje de una componente de X.

    En Gauss corresponde a la sustitución hacia atrás; en el método de la inversa,
    al producto de una fila de A^-1 por B.
    """

    variable_index: int
    variable: str
    equation: str
    value: float


class MethodSolution(BaseModel):
    """Vector solución de un método junto con su traza completa de pasos."""

    method: SolutionMethod
    solution: list[float]
    steps: list[RowOperationStep]
    component_steps: list[SolutionComponentStep] = []
    inverse_matrix: list[list[float]] | None = None


class CrossValidationReport(BaseModel):
    """Comparación de los vectores solución devueltos por los tres métodos."""

    passed: bool
    tolerance: float
    max_deviation: float
    methods: list[SolutionMethod]
    solution: list[float]


class SubstitutionCheck(BaseModel):
    """Error de sustitución directa E = ‖AX - B‖."""

    error_norm: float
    tolerance: float
    within_tolerance: bool


class InfeasibleComponent(BaseModel):
    """Componente negativa de X, con el motivo técnico para la capa de orquestación."""

    index: int
    variable: str
    label: str | None = None
    value: float
    reason: str


class InfeasibilityFlag(BaseModel):
    """Marca de negocio: una solución matemáticamente válida puede ser irrealizable."""

    infeasible: bool
    reason_code: str | None = None
    components: list[InfeasibleComponent] = []
    reasons: list[str] = []


class LinearSystemResult(BaseModel):
    """Resultado completo: diagnóstico y, solo si el sistema es no singular, solución."""

    diagnosis: SystemDiagnosis
    solved: bool
    solution: list[float] | None = None
    methods: list[MethodSolution] = []
    cross_validation: CrossValidationReport | None = None
    substitution: SubstitutionCheck | None = None
    feasibility: InfeasibilityFlag | None = None
