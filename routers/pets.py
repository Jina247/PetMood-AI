from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.database import get_db
from dependencies import get_current_user
from database.models import User, Pet
from schemas.pets import PetCreate, PetResponse, PetUpdate

router = APIRouter(prefix="/pets", tags=["pets"])

@router.get("/", response_model=list[PetResponse])
def get_pets(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Pet).filter(Pet.owner_id == current_user.id).all()

@router.get("/{pet_id}", response_model=PetResponse)
def get_pet(pet_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    pet = db.query(Pet).filter(Pet.id == pet_id, Pet.owner_id == current_user.id).first()
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")
    return pet

@router.post("/", response_model=PetResponse, status_code=201)
def create_pet(body: PetCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    new_pet = Pet(
        name=body.name,
        age=body.age,
        pet_type=body.pet_type,
        gender=body.gender,
        photoUri = body.photoUri,
        owner_id=current_user.id
    )
    db.add(new_pet)
    db.commit()
    db.refresh(new_pet)
    return new_pet

@router.patch("/{pet_id}", response_model=PetResponse)
def update_pet(pet_id: str, body: PetUpdate,  db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    pet = db.query(Pet).filter(Pet.id == pet_id, Pet.owner_id == current_user.id).first()
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")

    updated_pet = body.model_dump(exclude_unset=True)
    for key, value in updated_pet.items():
        setattr(pet, key, value)

    db.commit()
    db.refresh(pet)
    return pet

@router.delete("/{pet_id}", status_code=204)
def delete_pet(pet_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    pet = db.query(Pet).filter(Pet.id == pet_id, Pet.owner_id == current_user.id).first()
    if not pet:
        return HTTPException(status_code=404, detail="Pet not found")

    db.delete(pet)
    db.commit()
