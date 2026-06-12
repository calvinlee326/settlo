from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.security import get_current_user
from app.database import get_db
from app.models.expense import Expense, ExpenseSplit, Settlement
from app.models.group import Group, Membership
from app.models.user import User
from app.schemas.group import (
    GroupCreate,
    GroupDetail,
    GroupOut,
    InviteOut,
    InvitePreview,
    MemberOut,
)

router = APIRouter(prefix="/api/groups", tags=["groups"])


def get_group_or_404(db: Session, group_id: str) -> Group:
    group = db.query(Group).filter(Group.id == group_id).first()
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )
    return group


def require_membership(db: Session, group_id: str, user_id: str) -> Membership:
    membership = (
        db.query(Membership)
        .filter(Membership.group_id == group_id, Membership.user_id == user_id)
        .first()
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this group",
        )
    return membership


def _member_out(membership: Membership) -> MemberOut:
    return MemberOut(
        id=membership.user.id,
        username=membership.user.username,
        phone_number=membership.user.phone_number,
        joined_at=membership.joined_at,
    )


@router.post("/", response_model=GroupDetail, status_code=status.HTTP_201_CREATED)
def create_group(
    body: GroupCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    group = Group(
        name=body.name.strip(),
        description=body.description,
        created_by=current_user.id,
    )
    db.add(group)
    db.flush()
    db.add(Membership(user_id=current_user.id, group_id=group.id))
    db.commit()
    db.refresh(group)
    return _group_detail(db, group)


def _group_detail(db: Session, group: Group) -> GroupDetail:
    memberships = (
        db.query(Membership)
        .options(joinedload(Membership.user))
        .filter(Membership.group_id == group.id)
        .order_by(Membership.joined_at)
        .all()
    )
    return GroupDetail(
        id=group.id,
        name=group.name,
        description=group.description,
        max_members=group.max_members,
        created_by=group.created_by,
        created_at=group.created_at,
        member_count=len(memberships),
        members=[_member_out(m) for m in memberships],
    )


@router.get("/", response_model=list[GroupOut])
def list_my_groups(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    groups = (
        db.query(Group)
        .join(Membership, Membership.group_id == Group.id)
        .filter(Membership.user_id == current_user.id)
        .order_by(Group.created_at.desc())
        .all()
    )
    counts = {
        g.id: db.query(Membership).filter(Membership.group_id == g.id).count()
        for g in groups
    }
    return [
        GroupOut(
            id=g.id,
            name=g.name,
            description=g.description,
            max_members=g.max_members,
            created_by=g.created_by,
            created_at=g.created_at,
            member_count=counts[g.id],
        )
        for g in groups
    ]


@router.get("/join/{invite_token}", response_model=InvitePreview)
def preview_invite(
    invite_token: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    group = db.query(Group).filter(Group.invite_token == invite_token).first()
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid invite link"
        )
    member_count = (
        db.query(Membership).filter(Membership.group_id == group.id).count()
    )
    creator = db.query(User).filter(User.id == group.created_by).first()
    is_member = (
        db.query(Membership)
        .filter(
            Membership.group_id == group.id, Membership.user_id == current_user.id
        )
        .first()
        is not None
    )
    return InvitePreview(
        group_id=group.id,
        name=group.name,
        description=group.description,
        member_count=member_count,
        max_members=group.max_members,
        created_by_username=creator.username if creator else None,
        is_member=is_member,
    )


@router.post("/join/{invite_token}", response_model=GroupDetail)
def join_group(
    invite_token: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    group = db.query(Group).filter(Group.invite_token == invite_token).first()
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid invite link"
        )
    existing = (
        db.query(Membership)
        .filter(
            Membership.group_id == group.id, Membership.user_id == current_user.id
        )
        .first()
    )
    if existing:
        return _group_detail(db, group)
    member_count = (
        db.query(Membership).filter(Membership.group_id == group.id).count()
    )
    if member_count >= group.max_members:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Group is full"
        )
    db.add(Membership(user_id=current_user.id, group_id=group.id))
    db.commit()
    return _group_detail(db, group)


@router.get("/{group_id}", response_model=GroupDetail)
def get_group(
    group_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    group = get_group_or_404(db, group_id)
    require_membership(db, group_id, current_user.id)
    return _group_detail(db, group)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(
    group_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    group = get_group_or_404(db, group_id)
    if group.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the group creator can delete the group",
        )
    expense_ids = [
        e.id for e in db.query(Expense.id).filter(Expense.group_id == group_id).all()
    ]
    if expense_ids:
        db.query(ExpenseSplit).filter(
            ExpenseSplit.expense_id.in_(expense_ids)
        ).delete(synchronize_session=False)
    db.query(Expense).filter(Expense.group_id == group_id).delete(
        synchronize_session=False
    )
    db.query(Settlement).filter(Settlement.group_id == group_id).delete(
        synchronize_session=False
    )
    db.query(Membership).filter(Membership.group_id == group_id).delete(
        synchronize_session=False
    )
    db.delete(group)
    db.commit()


@router.get("/{group_id}/invite", response_model=InviteOut)
def get_invite(
    group_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    group = get_group_or_404(db, group_id)
    require_membership(db, group_id, current_user.id)
    return InviteOut(invite_token=group.invite_token)


@router.delete(
    "/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_member(
    group_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    group = get_group_or_404(db, group_id)
    require_membership(db, group_id, current_user.id)

    # A member may remove themselves; only the creator may remove others
    if user_id != current_user.id and group.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the group creator can remove other members",
        )
    if user_id == group.created_by:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The group creator cannot be removed",
        )
    membership = (
        db.query(Membership)
        .filter(Membership.group_id == group_id, Membership.user_id == user_id)
        .first()
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Member not found"
        )
    db.delete(membership)
    db.commit()
