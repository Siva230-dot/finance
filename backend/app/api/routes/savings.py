import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User
from app.schemas import ContributionIn, GoalIn, GoalOut, GoalUpdateIn
from app.services import savings as svc

router = APIRouter(prefix="/savings", tags=["savings"])


@router.get("", response_model=list[GoalOut])
def list_goals(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [svc.enrich(g) for g in svc.list_goals(db, user.id)]


@router.post("", response_model=GoalOut, status_code=201)
def create(body: GoalIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.enrich(svc.create_goal(db, user.id, body.name, body.target_amount, body.current_amount, body.target_date, body.notes))


@router.get("/{goal_id}", response_model=GoalOut)
def get(goal_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.enrich(svc.get_goal(db, user.id, goal_id))


@router.patch("/{goal_id}", response_model=GoalOut)
def update(goal_id: uuid.UUID, body: GoalUpdateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.enrich(svc.update_goal(db, user.id, goal_id, body.model_dump(exclude_unset=True)))


@router.delete("/{goal_id}", status_code=204)
def delete(goal_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    svc.delete_goal(db, user.id, goal_id)


@router.post("/{goal_id}/contributions", response_model=GoalOut, status_code=201)
def contribute(goal_id: uuid.UUID, body: ContributionIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.enrich(svc.add_contribution(db, user.id, goal_id, body.amount, body.contribution_date, body.note))
