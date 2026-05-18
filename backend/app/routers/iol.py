from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import IolCredential, OauthToken, User
from ..schemas import IolConnectRequest, IolStatusResponse
from ..services import iol_auth

router = APIRouter(prefix="/iol", tags=["iol"])


@router.post("/connect", response_model=IolStatusResponse)
async def connect(
    body: IolConnectRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        await iol_auth.connect_user(db, user.id, body.iol_username, body.iol_password)
    except iol_auth.IolAuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return _status_for(db, user.id)


@router.get("/status", response_model=IolStatusResponse)
def status_endpoint(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _status_for(db, user.id)


@router.post("/disconnect", response_model=IolStatusResponse)
async def disconnect(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    await iol_auth.disconnect_user(db, user.id)
    return _status_for(db, user.id)


@router.post("/refresh", response_model=IolStatusResponse)
async def refresh(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        await iol_auth.get_valid_access_token(db, user.id, force_refresh=True)
    except iol_auth.IolNotConnectedError:
        raise HTTPException(status_code=409, detail="IOL not connected")
    except iol_auth.IolAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return _status_for(db, user.id)


def _status_for(db: Session, user_id: int) -> IolStatusResponse:
    cred = db.query(IolCredential).filter(IolCredential.user_id == user_id).first()
    tok = db.query(OauthToken).filter(OauthToken.user_id == user_id).first()
    return IolStatusResponse(
        connected=cred is not None,
        iol_username=cred.iol_username if cred else None,
        connected_at=cred.connected_at if cred else None,
        access_expires_at=tok.access_expires_at if tok else None,
        refresh_expires_at=tok.refresh_expires_at if tok else None,
        last_keepalive_at=tok.last_keepalive_at if tok else None,
        last_error=cred.last_error if cred else None,
    )
