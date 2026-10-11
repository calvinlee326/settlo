from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.models.user import User
from app.services import fx

router = APIRouter(prefix="/api/rates", tags=["rates"])


@router.get("")
def get_rates(current_user: User = Depends(get_current_user)):
    return {
        "base": fx.BASE_CURRENCY,
        "rates": {code: float(rate) for code, rate in fx.usd_rates().items()},
    }
