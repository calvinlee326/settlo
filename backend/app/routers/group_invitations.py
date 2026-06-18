from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models.group import Group, Membership
from app.models.group_invitation import GroupInvitation, GroupInvitationStatus
from app.models.user import User, utcnow
from app.routers.groups import (
    _add_member,
    _group_detail,
    get_group_or_404,
    require_membership,
)
from app.schemas.group import GroupDetail, GroupInviteCreate, GroupInvitationOut

router = APIRouter(prefix="/api/group-invitations", tags=["group-invitations"])


@router.post("", response_model=GroupInvitationOut, status_code=status.HTTP_201_CREATED)
def create_invitation(
    body: GroupInviteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    group = get_group_or_404(db, body.group_id)
    require_membership(db, body.group_id, current_user.id)
    if group.settled_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Group is already settled"
        )
    target = db.query(User).filter(User.phone_number == body.phone_number).first()
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No user with that phone number"
        )
    already_member = (
        db.query(Membership)
        .filter(Membership.group_id == group.id, Membership.user_id == target.id)
        .first()
    )
    if already_member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Already a member"
        )
    existing = (
        db.query(GroupInvitation)
        .filter(
            GroupInvitation.group_id == group.id,
            GroupInvitation.invited_user_id == target.id,
            GroupInvitation.status == GroupInvitationStatus.PENDING,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Already invited"
        )
    inv = GroupInvitation(
        group_id=group.id, invited_user_id=target.id, invited_by=current_user.id
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return GroupInvitationOut(
        id=inv.id,
        group_id=group.id,
        group_name=group.name,
        invited_by_username=current_user.username,
        created_at=inv.created_at,
    )


@router.get("", response_model=list[GroupInvitationOut])
def my_invitations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(GroupInvitation)
        .filter(
            GroupInvitation.invited_user_id == current_user.id,
            GroupInvitation.status == GroupInvitationStatus.PENDING,
        )
        .order_by(GroupInvitation.created_at.desc())
        .all()
    )
    if not rows:
        return []
    groups = {
        g.id: g
        for g in db.query(Group).filter(
            Group.id.in_([r.group_id for r in rows])
        ).all()
    }
    inviters = {
        u.id: u.username
        for u in db.query(User).filter(
            User.id.in_([r.invited_by for r in rows])
        ).all()
    }
    return [
        GroupInvitationOut(
            id=r.id,
            group_id=r.group_id,
            group_name=groups[r.group_id].name if r.group_id in groups else "",
            invited_by_username=inviters.get(r.invited_by),
            created_at=r.created_at,
        )
        for r in rows
        if r.group_id in groups and groups[r.group_id].deleted_at is None
    ]


def _get_pending_or_404(db: Session, invitation_id: str, user_id: str) -> GroupInvitation:
    inv = (
        db.query(GroupInvitation)
        .filter(
            GroupInvitation.id == invitation_id,
            GroupInvitation.invited_user_id == user_id,
            GroupInvitation.status == GroupInvitationStatus.PENDING,
        )
        .first()
    )
    if inv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found"
        )
    return inv


@router.post("/{invitation_id}/accept", response_model=GroupDetail)
def accept_invitation(
    invitation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inv = _get_pending_or_404(db, invitation_id, current_user.id)
    group = get_group_or_404(db, inv.group_id)
    _add_member(db, group, current_user.id)
    inv.status = GroupInvitationStatus.ACCEPTED
    inv.responded_at = utcnow()
    db.commit()
    return _group_detail(db, group)


@router.post("/{invitation_id}/decline", status_code=status.HTTP_204_NO_CONTENT)
def decline_invitation(
    invitation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inv = _get_pending_or_404(db, invitation_id, current_user.id)
    db.delete(inv)
    db.commit()
