from uuid import UUID
from fastapi import APIRouter, HTTPException
from backend.db import get_people, name_person
from backend.models import PersonProfile, NamePersonRequest

router = APIRouter()


@router.get("/{user_id}", response_model=list[PersonProfile])
def list_profiles(user_id: UUID):
    rows = get_people(str(user_id))
    return [PersonProfile(**row) for row in rows]


@router.patch("/{person_id}/name")
def assign_name(person_id: UUID, body: NamePersonRequest):
    name_person(str(person_id), body.name.strip())
    return {"ok": True, "person_id": str(person_id), "name": body.name.strip()}
