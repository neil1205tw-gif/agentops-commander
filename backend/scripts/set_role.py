"""Set a user's role: python -m scripts.set_role <email|uuid> <viewer|operator|admin>

Connects with DATABASE_URL (environment or .env). The connection string is never printed.
"""

import argparse
import sys
import uuid
from collections.abc import Sequence

from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import PROFILE_ROLES, Profile


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m scripts.set_role", description=__doc__)
    parser.add_argument("user", help="user email or profile UUID")
    parser.add_argument("role", choices=PROFILE_ROLES)
    return parser.parse_args(argv)


def _find_profile(session: Session, user: str) -> Profile | None:
    try:
        return session.get(Profile, uuid.UUID(user))
    except ValueError:
        statement = select(Profile).where(func.lower(Profile.email) == user.lower())
        return session.scalar(statement)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        settings = Settings()  # type: ignore[call-arg]
    except ValidationError:
        print("error: DATABASE_URL is not configured", file=sys.stderr)
        return 2
    engine = create_engine(
        settings.DATABASE_URL.get_secret_value(), connect_args={"connect_timeout": 5}
    )
    try:
        with Session(engine) as session:
            profile = _find_profile(session, args.user)
            if profile is None:
                print(f"error: user not found: {args.user}", file=sys.stderr)
                return 1
            previous = profile.role
            profile.role = args.role
            session.commit()
            print(f"updated {profile.email or profile.id}: {previous} -> {args.role}")
    except SQLAlchemyError as exc:
        print(f"error: database operation failed ({type(exc).__name__})", file=sys.stderr)
        return 2
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
