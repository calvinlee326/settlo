from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=255)


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str | None
    joined_at: datetime


class GroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    max_members: int
    created_by: str
    created_at: datetime
    settled_at: datetime | None = None
    total: float = 0
    member_count: int = 0


class GroupDetail(GroupOut):
    members: list[MemberOut] = []


class AddMemberRequest(BaseModel):
    user_id: str


class InviteOut(BaseModel):
    invite_token: str


class InvitePreview(BaseModel):
    group_id: str
    name: str
    description: str | None
    member_count: int
    max_members: int
    created_by_username: str | None
    is_member: bool


class GroupInviteCreate(BaseModel):
    group_id: str
    phone_number: str = Field(min_length=3, max_length=20)


class GroupInvitationOut(BaseModel):
    id: str
    group_id: str
    group_name: str
    invited_by_username: str | None
    created_at: datetime
