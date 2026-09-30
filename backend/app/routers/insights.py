from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import AiInsight, User
from ..schemas import AiInsightOut, AiInsightStatus
from ..services import ai_insights

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/latest", response_model=AiInsightStatus)
def latest(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = (
        db.query(AiInsight)
        .filter(AiInsight.user_id == user.id)
        .order_by(AiInsight.date.desc())
        .first()
    )
    return AiInsightStatus(enabled=ai_insights.is_enabled(), insight=row)


@router.get("", response_model=list[AiInsightOut])
def history(
    limit: int = Query(default=30, ge=1, le=365),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(AiInsight)
        .filter(AiInsight.user_id == user.id)
        .order_by(AiInsight.date.desc())
        .limit(limit)
        .all()
    )


@router.post("/generate", response_model=AiInsightOut)
async def generate(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return await ai_insights.generate(db, user.id, source="manual")
    except ai_insights.AiNotConfiguredError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ai_insights.AiGenerationError as e:
        raise HTTPException(status_code=502, detail=str(e))
