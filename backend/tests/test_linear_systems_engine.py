"""Escenarios de validación del motor de sistemas lineales sobre el caso TechChip."""

import pytest
from pydantic import ValidationError

from app.models.linear_system import (
    LinearSystemInput,
    SolutionMethod,
    SystemClassification,
)
from app.services.linear_systems_engine import (
    RAW_MATERIAL_CONSTRAINT,
    SOLUTION_TOL,
    SingularSystemError,
    cross_validate_methods,
    solve_gauss,
    solve_gauss_jordan,
    solve_linear_system,
    solve_matrix_inverse,
    validate_system,
)
from tests.fixtures import techchip


def techchip_system(B: list[float] | None = None) -> LinearSystemInput:
    return LinearSystemInput(A=techchip.A, B=techchip.DATASET_B if B is None else B)


def test_prueba_base_los_tres_metodos_devuelven_la_produccion_esperada() -> None:
    """Escenario 1: A y DATASET_B resuelven a X=(15,20,25,10,15,20) sin infactibilidad."""
    result = solve_linear_system(techchip_system(), techchip.VARIABLE_NAMES)

    assert result.solved is True
    assert result.diagnosis.classification is SystemClassification.COMPATIBLE_DETERMINADO
    assert [method.method for method in result.methods] == [
        SolutionMethod.GAUSS,
        SolutionMethod.GAUSS_JORDAN,
        SolutionMethod.MATRIX_INVERSE,
    ]
    for method in result.methods:
        assert method.solution == pytest.approx(techchip.X_ESPERADA, abs=SOLUTION_TOL)
        assert method.steps, f"{method.method} no registró ningún paso intermedio"

    assert result.feasibility.infeasible is False
    assert result.feasibility.reasons == []


def test_prueba_base_error_de_sustitucion_y_validacion_cruzada() -> None:
    """Escenario 2: E = ‖AX - B‖ < 1e-6 y los tres métodos coinciden entre sí."""
    system = techchip_system()
    result = solve_linear_system(system)

    assert result.substitution.error_norm < SOLUTION_TOL
    assert result.substitution.within_tolerance is True

    report = cross_validate_methods(system)
    assert report.passed is True
    assert report.max_deviation <= SOLUTION_TOL
    assert report.solution == pytest.approx(techchip.X_ESPERADA, abs=SOLUTION_TOL)


def test_escenario_escasez_de_resina_marca_la_solucion_como_infactible() -> None:
    """Escenario 3: recortar B3 a 100 produce componentes negativas y levanta el flag."""
    scarce = list(techchip.DATASET_B)
    scarce[techchip.SCARCITY_RESOURCE_INDEX] = techchip.SCARCITY_VALUE

    result = solve_linear_system(
        LinearSystemInput(A=techchip.A, B=scarce), techchip.VARIABLE_NAMES
    )

    assert result.solved is True
    assert any(value < 0 for value in result.solution)
    assert result.feasibility.infeasible is True
    assert result.feasibility.reason_code == RAW_MATERIAL_CONSTRAINT
    assert all(
        RAW_MATERIAL_CONSTRAINT in reason for reason in result.feasibility.reasons
    )

    if techchip.DATASET_B is techchip.B_PRIMARIO:
        assert result.solution == pytest.approx(techchip.X_CON_ESCASEZ, abs=1e-4)
        assert [c.index for c in result.feasibility.components] == [0, 1]
        assert result.feasibility.components[0].label == "AI-Edge 1"


def test_escenario_degenerado_f6_igual_a_2f1_se_detiene_sin_devolver_solucion() -> None:
    """Escenario 4: con F6 = 2*F1 el motor diagnostica y NO intenta resolver."""
    degenerate = [list(row) for row in techchip.A]
    degenerate[5] = [2 * value for value in techchip.A[0]]

    result = solve_linear_system(LinearSystemInput(A=degenerate, B=techchip.DATASET_B))

    assert result.solved is False
    assert result.solution is None
    assert result.methods == []
    assert result.cross_validation is None
    assert result.substitution is None
    assert result.feasibility is None

    assert result.diagnosis.is_singular is True
    assert result.diagnosis.determinant == pytest.approx(0.0, abs=1e-9)
    assert result.diagnosis.rank_a == 5
    assert result.diagnosis.rank_augmented == 6
    assert result.diagnosis.classification is SystemClassification.INCOMPATIBLE


def test_documental_el_b_impreso_en_la_guia_no_produce_la_respuesta_esperada() -> None:
    """Escenario 5: los datos impresos de la guía son inconsistentes con su respuesta.

    Con B_LITERAL_GUIA el sistema es compatible determinado (det(A) = -83), pero su
    solución única tiene x1 negativo y no es X=(15,20,25,10,15,20). El vector que
    reproduce la respuesta del ejercicio es B_PRIMARIO = A*X_ESPERADA.
    """
    system = LinearSystemInput(A=techchip.A, B=techchip.B_LITERAL_GUIA)
    diagnosis = validate_system(system)

    assert diagnosis.determinant == pytest.approx(techchip.DET_A, abs=1e-9)
    assert diagnosis.is_singular is False
    assert diagnosis.classification is SystemClassification.COMPATIBLE_DETERMINADO

    result = solve_linear_system(system, techchip.VARIABLE_NAMES)

    assert result.solution == pytest.approx(techchip.X_REAL_CON_B_LITERAL, abs=1e-6)
    assert result.solution[0] < 0
    assert result.solution != pytest.approx(techchip.X_ESPERADA, abs=1e-3)
    assert result.feasibility.infeasible is True
    assert result.feasibility.components[0].variable == "x1"


def test_la_matriz_inversa_reconstruye_la_identidad() -> None:
    method = solve_matrix_inverse(techchip_system())

    assert method.inverse_matrix is not None
    # pytest.approx no admite listas anidadas: se comparan A*A^-1 e I aplanadas.
    product = [
        sum(techchip.A[i][k] * method.inverse_matrix[k][j] for k in range(6))
        for i in range(6)
        for j in range(6)
    ]
    identity = [1.0 if i == j else 0.0 for i in range(6) for j in range(6)]
    assert product == pytest.approx(identity, abs=1e-9)


@pytest.mark.parametrize(
    ("A", "B"),
    [
        ([[1, 2, 3], [4, 5, 6]], [1, 2, 3]),  # A no es cuadrada
        ([[1, 2], [3, 4]], [1, 2, 3]),  # B no encaja con A
        ([[1, float("nan")], [3, 4]], [1, 2]),  # coeficiente no finito
    ],
)
def test_entradas_con_dimensiones_o_valores_invalidos_se_rechazan(A, B) -> None:
    with pytest.raises(ValidationError):
        LinearSystemInput(A=A, B=B)


@pytest.mark.parametrize("solver", [solve_gauss, solve_gauss_jordan, solve_matrix_inverse])
def test_resolver_directamente_un_sistema_singular_falla(solver) -> None:
    singular = LinearSystemInput(A=[[1, 2], [2, 4]], B=[3, 6])

    with pytest.raises(SingularSystemError):
        solver(singular)
