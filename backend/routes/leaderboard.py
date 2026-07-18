"""
Leaderboard Route — Returns real-time promoter rankings.

Only counts submissions with status='valid' (no duplicates, no OCR failures).
Promoters are ranked by their valid submission count in descending order.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db, Promoter, Submission, ValidUsername
from models import LeaderboardResponse, LeaderboardEntry
from utils import mask_ic_number

router = APIRouter()


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(db: Session = Depends(get_db)):
    """
    Get the real-time leaderboard.

    Ranking logic:
      - Only valid_usernames entries count toward a promoter's score.
      - Promoters with 0 valid submissions are excluded from the ranking.
      - Ties are broken alphabetically by promoter name.
    """
    results = (
        db.query(
            Promoter.name,
            Promoter.ic_number,
            Promoter.avatar,
            func.count(ValidUsername.id).label("valid_count"),
        )
        .join(ValidUsername, ValidUsername.promoter_id == Promoter.id)
        .group_by(Promoter.id, Promoter.name, Promoter.ic_number, Promoter.avatar)
        .order_by(func.count(ValidUsername.id).desc(), Promoter.name.asc())
        .all()
    )

    # Build ranked entries
    entries = []
    for rank, (name, ic_number, avatar, valid_count) in enumerate(results, start=1):
        entries.append(
            LeaderboardEntry(
                rank=rank,
                promoter_name=name,
                ic_number_masked=mask_ic_number(ic_number),
                valid_count=valid_count,
                avatar=avatar,
            )
        )

    # ── Aggregate statistics ──
    total_promoters = db.query(func.count(Promoter.id)).scalar() or 0
    total_valid = db.query(func.count(ValidUsername.id)).scalar() or 0
    total_submissions = db.query(func.count(Submission.id)).scalar() or 0

    # Calculate today's valid signups
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_valid = (
        db.query(func.count(Submission.id))
        .filter(
            Submission.status == "valid",
            Submission.created_at >= today_start
        )
        .scalar()
        or 0
    )

    return LeaderboardResponse(
        entries=entries,
        total_promoters=total_promoters,
        total_valid=total_valid,
        total_submissions=total_submissions,
        today_valid=today_valid,
        last_updated=datetime.now(timezone.utc).isoformat(),
    )
