from fastapi import APIRouter

from app.api.deps import CurrentEmployee
from app.models.employee import Employee

router = APIRouter()


@router.get("/me", response_model=Employee)
def read_current_employee(employee: CurrentEmployee) -> Employee:
    return employee
