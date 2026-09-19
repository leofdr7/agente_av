"""Resolución determinista de sistemas AX=B por Gauss, Gauss-Jordan y matriz inversa.

El diagnóstico previo (determinante y rangos) usa aritmética exacta con SymPy, de
modo que un sistema singular se detecta sin ruido de coma flotante. La eliminación
se implementa a mano sobre NumPy para poder registrar cada operación de fila.

Módulo 100% determinista: no depende de Anthropic, Clerk ni Supabase.
"""

from collections.abc import Sequence

import numpy as np
import sympy as sp

from app.models.linear_system import (
    CrossValidationReport,
    InfeasibilityFlag,
    InfeasibleComponent,
    LinearSystemInput,
    LinearSystemResult,
    MethodSolution,
    RowOperationKind,
    RowOperationStep,
    SingularSystemAlert,
    SolutionComponentStep,
    SolutionMethod,
    SubstitutionCheck,
    SystemClassification,
    SystemDiagnosis,
)

# det(A) por debajo de esta cota se considera nulo y detiene la resolución.
SINGULARITY_TOL = 1e-9
# Coincidencia entre métodos y error de sustitución directa admitidos.
SOLUTION_TOL = 1e-6
# Un pivote por debajo de esta cota (relativa a la escala de la matriz) es nulo.
PIVOT_TOL = 1e-12
# Margen bajo el cual una componente se considera cero y no negativa.
FEASIBILITY_TOL = 1e-9
# Decimales conservados en las instantáneas de la matriz de trabajo.
SNAPSHOT_DECIMALS = 12

RAW_MATERIAL_CONSTRAINT = "restriccion de materias primas"


class SingularSystemError(Exception):
    """Se intentó resolver un sistema singular; hay que diagnosticarlo, no resolverlo."""


class MethodInconsistencyError(Exception):
    """Los métodos exactos no coincidieron: error interno del motor."""

    def __init__(self, max_deviation: float, solutions: dict[str, list[float]]) -> None:
        self.max_deviation = max_deviation
        self.solutions = solutions
        super().__init__(
            "Los métodos de resolución no coinciden dentro de la tolerancia "
            f"{SOLUTION_TOL:g} (desviación máxima {max_deviation:g}): {solutions}"
        )


def _fmt(value: float) -> str:
    return f"{value:.6g}"


def _exact(rows: Sequence[Sequence[float]]) -> sp.Matrix:
    """Convierte a racionales exactos leyendo la representación decimal del float."""
    return sp.Matrix([[sp.Rational(str(value)) for value in row] for row in rows])


def _snapshot(matrix: np.ndarray) -> list[list[float]]:
    """Copia legible de la matriz de trabajo, sin ruido numérico ni ceros negativos."""
    return (np.round(matrix, SNAPSHOT_DECIMALS) + 0.0).tolist()


def validate_system(system: LinearSystemInput) -> SystemDiagnosis:
    """Analiza el sistema antes de resolverlo: det(A), rango(A) y rango([A|B]).

    No resuelve nada. Si `is_singular` es verdadero, el llamador debe detenerse y
    devolver el diagnóstico sin vector solución.
    """
    size = system.size
    matrix = _exact(system.A)
    augmented = matrix.row_join(sp.Matrix(size, 1, [sp.Rational(str(v)) for v in system.B]))

    determinant = float(matrix.det())
    rank_a = int(matrix.rank())
    rank_augmented = int(augmented.rank())
    is_singular = abs(determinant) < SINGULARITY_TOL

    if not is_singular:
        classification = SystemClassification.COMPATIBLE_DETERMINADO
        message = (
            f"Sistema compatible determinado: det(A) = {_fmt(determinant)} != 0 y "
            f"rango(A) = rango([A|B]) = {size}. Admite solución única."
        )
    elif rank_a != rank_augmented:
        classification = SystemClassification.INCOMPATIBLE
        message = (
            f"Sistema incompatible: det(A) = {_fmt(determinant)} es nulo y "
            f"rango(A) = {rank_a} != rango([A|B]) = {rank_augmented}. "
            "No existe solución; el motor no devuelve ningún vector X."
        )
    elif rank_a < size:
        classification = SystemClassification.COMPATIBLE_INDETERMINADO
        message = (
            f"Sistema compatible indeterminado: det(A) = {_fmt(determinant)} es nulo y "
            f"rango(A) = rango([A|B]) = {rank_a} < {size}. Infinitas soluciones "
            f"({size - rank_a} grado(s) de libertad); el motor no devuelve un X único."
        )
    else:
        # det(A) es no nulo en exacto pero cae bajo la tolerancia: el sistema tiene
        # solución única en teoría y es irresoluble con fiabilidad en coma flotante.
        classification = SystemClassification.COMPATIBLE_DETERMINADO
        message = (
            f"Sistema numéricamente singular: det(A) = {_fmt(determinant)} está por "
            f"debajo de la tolerancia {SINGULARITY_TOL:g}. La matriz está mal "
            "condicionada y el motor no devuelve un vector X."
        )

    return SystemDiagnosis(
        size=size,
        determinant=determinant,
        rank_a=rank_a,
        rank_augmented=rank_augmented,
        is_singular=is_singular,
        classification=classification,
        message=message,
    )


def _pivot(matrix: np.ndarray, col: int, steps: list[RowOperationStep]) -> float:
    """Pivoteo parcial: lleva a la fila `col` el pivote de mayor magnitud."""
    size = matrix.shape[0]
    candidate = col + int(np.argmax(np.abs(matrix[col:, col])))
    if candidate != col:
        matrix[[col, candidate]] = matrix[[candidate, col]]
        steps.append(
            RowOperationStep(
                kind=RowOperationKind.SWAP,
                target_row=col,
                source_row=candidate,
                description=f"F{col + 1} <-> F{candidate + 1}",
                matrix_state=_snapshot(matrix),
            )
        )

    pivot_value = float(matrix[col, col])
    scale = max(1.0, float(np.max(np.abs(matrix[:, :size]))))
    if abs(pivot_value) <= PIVOT_TOL * scale:
        raise SingularSystemError(
            f"Pivote nulo en la columna {col + 1}: la matriz A es singular. "
            "Diagnostica el sistema con validate_system antes de resolverlo."
        )
    return pivot_value


def _eliminate(
    matrix: np.ndarray,
    target: int,
    source: int,
    factor: float,
    steps: list[RowOperationStep],
) -> None:
    """Aplica F_target <- F_target + factor*F_source y registra el estado resultante."""
    factor = float(factor)
    if factor == 0.0:
        return
    matrix[target] += factor * matrix[source]
    steps.append(
        RowOperationStep(
            kind=RowOperationKind.ELIMINATE,
            target_row=target,
            source_row=source,
            factor=factor,
            description=f"F{target + 1} <- F{target + 1} + ({_fmt(factor)})*F{source + 1}",
            matrix_state=_snapshot(matrix),
        )
    )


def _augmented(system: LinearSystemInput) -> np.ndarray:
    return np.column_stack(
        (np.array(system.A, dtype=float), np.array(system.B, dtype=float))
    )


def solve_gauss(system: LinearSystemInput) -> MethodSolution:
    """Eliminación de Gauss: triangular superior y sustitución hacia atrás."""
    size = system.size
    matrix = _augmented(system)
    steps: list[RowOperationStep] = []

    for col in range(size):
        pivot_value = _pivot(matrix, col, steps)
        for row in range(col + 1, size):
            _eliminate(matrix, row, col, -matrix[row, col] / pivot_value, steps)

    solution = np.zeros(size)
    component_steps: list[SolutionComponentStep] = []
    for row in reversed(range(size)):
        known = [
            f"({_fmt(float(matrix[row, col]))})*x{col + 1}"
            for col in range(row + 1, size)
            if matrix[row, col] != 0.0
        ]
        rhs = float(matrix[row, size]) - float(matrix[row, row + 1 : size] @ solution[row + 1 :])
        value = rhs / float(matrix[row, row])
        solution[row] = value

        numerator = _fmt(float(matrix[row, size]))
        if known:
            numerator += " - [" + " + ".join(known) + "]"
        component_steps.append(
            SolutionComponentStep(
                variable_index=row,
                variable=f"x{row + 1}",
                equation=f"x{row + 1} = ({numerator}) / ({_fmt(float(matrix[row, row]))})",
                value=value,
            )
        )

    return MethodSolution(
        method=SolutionMethod.GAUSS,
        solution=solution.tolist(),
        steps=steps,
        component_steps=component_steps,
    )


def _gauss_jordan_reduce(matrix: np.ndarray, size: int) -> list[RowOperationStep]:
    """Reduce in place las primeras `size` columnas de `matrix` a la identidad.

    Sirve tanto para [A|B] (devuelve [I|X]) como para [A|I] (devuelve [I|A^-1]).
    """
    steps: list[RowOperationStep] = []
    for col in range(size):
        pivot_value = _pivot(matrix, col, steps)
        if pivot_value != 1.0:
            factor = 1.0 / pivot_value
            matrix[col] *= factor
            steps.append(
                RowOperationStep(
                    kind=RowOperationKind.SCALE,
                    target_row=col,
                    factor=factor,
                    description=f"F{col + 1} <- ({_fmt(factor)})*F{col + 1}",
                    matrix_state=_snapshot(matrix),
                )
            )
        for row in range(size):
            if row != col:
                _eliminate(matrix, row, col, -matrix[row, col], steps)
    return steps


def solve_gauss_jordan(system: LinearSystemInput) -> MethodSolution:
    """Gauss-Jordan: reduce [A|B] a [I|X] eliminando por encima y por debajo del pivote."""
    size = system.size
    matrix = _augmented(system)
    steps = _gauss_jordan_reduce(matrix, size)

    return MethodSolution(
        method=SolutionMethod.GAUSS_JORDAN,
        solution=matrix[:, size].tolist(),
        steps=steps,
    )


def solve_matrix_inverse(system: LinearSystemInput) -> MethodSolution:
    """Calcula A^-1 reduciendo [A|I] por Gauss-Jordan y evalúa X = A^-1 * B."""
    size = system.size
    matrix = np.column_stack((np.array(system.A, dtype=float), np.eye(size)))
    steps = _gauss_jordan_reduce(matrix, size)

    inverse = matrix[:, size:]
    vector = np.array(system.B, dtype=float)
    solution = inverse @ vector

    component_steps = [
        SolutionComponentStep(
            variable_index=row,
            variable=f"x{row + 1}",
            equation=f"x{row + 1} = "
            + " + ".join(
                f"({_fmt(float(inverse[row, col]))})*B{col + 1}" for col in range(size)
            ),
            value=float(solution[row]),
        )
        for row in range(size)
    ]

    return MethodSolution(
        method=SolutionMethod.MATRIX_INVERSE,
        solution=solution.tolist(),
        steps=steps,
        component_steps=component_steps,
        inverse_matrix=_snapshot(inverse),
    )


def cross_validate_methods(
    system: LinearSystemInput,
    methods: Sequence[MethodSolution] | None = None,
) -> CrossValidationReport:
    """Comprueba que los tres métodos devuelven el mismo X dentro de `SOLUTION_TOL`.

    Lanza `MethodInconsistencyError` si difieren: una discrepancia indica un fallo
    del motor, no un dato de entrada inválido.
    """
    if methods is None:
        methods = [
            solve_gauss(system),
            solve_gauss_jordan(system),
            solve_matrix_inverse(system),
        ]

    vectors = np.array([method.solution for method in methods], dtype=float)
    max_deviation = float(np.max(np.abs(vectors - vectors[0]))) if len(vectors) > 1 else 0.0
    if max_deviation > SOLUTION_TOL:
        raise MethodInconsistencyError(
            max_deviation,
            {method.method.value: method.solution for method in methods},
        )

    return CrossValidationReport(
        passed=True,
        tolerance=SOLUTION_TOL,
        max_deviation=max_deviation,
        methods=[method.method for method in methods],
        solution=methods[0].solution,
    )


def verify_solution(
    system: LinearSystemInput, solution: Sequence[float]
) -> SubstitutionCheck:
    """Error de sustitución directa E = ‖AX - B‖, comparado con `SOLUTION_TOL`."""
    residual = np.array(system.A, dtype=float) @ np.array(solution, dtype=float)
    error_norm = float(np.linalg.norm(residual - np.array(system.B, dtype=float)))
    return SubstitutionCheck(
        error_norm=error_norm,
        tolerance=SOLUTION_TOL,
        within_tolerance=error_norm < SOLUTION_TOL,
    )


def check_feasibility(
    solution: Sequence[float], variable_names: Sequence[str] | None = None
) -> InfeasibilityFlag:
    """Marca como infactible toda solución con componentes negativas.

    El vector es matemáticamente correcto, pero una cantidad negativa no es
    producible. Se devuelve el motivo técnico (qué variable y por qué) para que la
    capa de orquestación lo traduzca a lenguaje de negocio.
    """
    components = [
        InfeasibleComponent(
            index=index,
            variable=f"x{index + 1}",
            label=variable_names[index] if variable_names else None,
            value=float(value),
            reason=(
                f"x{index + 1}"
                + (f" ({variable_names[index]})" if variable_names else "")
                + f" = {_fmt(float(value))} < 0: {RAW_MATERIAL_CONSTRAINT}"
            ),
        )
        for index, value in enumerate(solution)
        if value < -FEASIBILITY_TOL
    ]

    return InfeasibilityFlag(
        infeasible=bool(components),
        reason_code=RAW_MATERIAL_CONSTRAINT if components else None,
        components=components,
        reasons=[component.reason for component in components],
    )


def solve_linear_system(
    system: LinearSystemInput, variable_names: Sequence[str] | None = None
) -> LinearSystemResult:
    """Diagnostica y, solo si el sistema es no singular, lo resuelve por los tres métodos.

    Ante un sistema singular se detiene en el diagnóstico: `solution` queda en None.
    """
    diagnosis = validate_system(system)
    if diagnosis.is_singular:
        return LinearSystemResult(
            diagnosis=SingularSystemAlert(**diagnosis.model_dump(exclude={"is_singular"})),
            solved=False,
        )

    methods = [
        solve_gauss(system),
        solve_gauss_jordan(system),
        solve_matrix_inverse(system),
    ]
    cross_validation = cross_validate_methods(system, methods)
    solution = cross_validation.solution

    return LinearSystemResult(
        diagnosis=diagnosis,
        solved=True,
        solution=solution,
        methods=methods,
        cross_validation=cross_validation,
        substitution=verify_solution(system, solution),
        feasibility=check_feasibility(solution, variable_names),
    )
