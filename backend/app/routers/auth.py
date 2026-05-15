from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..crud import get_user_by_username
from ..database import get_db
from ..deps import get_current_user
from ..models import IolCredential, User
from ..schemas import LoginRequest, MeResponse, TokenResponse
from ..security import create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = get_user_by_username(db, body.username)
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")
    token, expires_in = create_access_token(sub=user.username, extra={"uid": user.id})
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MeResponse:
    iol = db.query(IolCredential).filter(IolCredential.user_id == user.id).first()
    return MeResponse(
        id=user.id,
        username=user.username,
        is_admin=user.is_admin,
        iol_connected=iol is not None,
    )
