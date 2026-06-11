from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import UserOut


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=255)


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str | None
    phone_number: str
    joined_at: datetime


class GroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    max_members: int
    created_by: str
    created_at: datetime
    member_count: int = 0


class GroupDetail(GroupOut):
    members: list[MemberOut] = []


class InviteOut(BaseModel):
    invite_token: str
    invite_link: str


class InvitePreview(BaseModel):
    group_id: str
    name: str
    description: str | None
    member_count: int
    max_members: int
    created_by_username: str | None
    is_member: bool
