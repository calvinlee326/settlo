from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models.friendship import Friendship, FriendshipStatus
from app.models.user import User, utcnow
from app.schemas.friend import FriendRequestCreate, FriendRequestOut
from app.services import friends as friends_svc

router = APIRouter(prefix="/api/friends", tags=["friends"])


@router.post(
    "/requests", response_model=FriendRequestOut, status_code=status.HTTP_201_CREATED
)
def send_friend_request(
    body: FriendRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = (
        db.query(User).filter(User.phone_number == body.phone_number).first()
    )
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No user with that phone number"
        )
    if target.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot add yourself",
        )
    if friends_svc.get_friendship(db, current_user.id, target.id) is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A friend request already exists",
        )

    friendship = Friendship(requester_id=current_user.id, addressee_id=target.id)
    db.add(friendship)
    db.commit()
    db.refresh(friendship)
    return FriendRequestOut(
        id=friendship.id,
        requester_id=friendship.requester_id,
        requester_username=current_user.username,
        created_at=friendship.created_at,
    )


@router.get("/requests", response_model=list[FriendRequestOut])
def incoming_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Friendship)
        .filter(
            Friendship.addressee_id == current_user.id,
            Friendship.status == FriendshipStatus.PENDING,
        )
        .order_by(Friendship.created_at.desc())
        .all()
    )
    requesters = (
        {
            u.id: u.username
            for u in db.query(User)
            .filter(User.id.in_([f.requester_id for f in rows]))
            .all()
        }
        if rows
        else {}
    )
    return [
        FriendRequestOut(
            id=f.id,
            requester_id=f.requester_id,
            requester_username=requesters.get(f.requester_id),
            created_at=f.created_at,
        )
        for f in rows
    ]


def _get_incoming_or_404(db: Session, friendship_id: str, user_id: str) -> Friendship:
    friendship = (
        db.query(Friendship)
        .filter(
            Friendship.id == friendship_id,
            Friendship.addressee_id == user_id,
            Friendship.status == FriendshipStatus.PENDING,
        )
        .first()
    )
    if friendship is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Friend request not found"
        )
    return friendship


@router.post("/requests/{friendship_id}/accept", status_code=status.HTTP_204_NO_CONTENT)
def accept_request(
    friendship_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    friendship = _get_incoming_or_404(db, friendship_id, current_user.id)
    friendship.status = FriendshipStatus.ACCEPTED
    friendship.responded_at = utcnow()
    db.commit()


@router.post("/requests/{friendship_id}/decline", status_code=status.HTTP_204_NO_CONTENT)
def decline_request(
    friendship_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    friendship = _get_incoming_or_404(db, friendship_id, current_user.id)
    db.delete(friendship)
    db.commit()
