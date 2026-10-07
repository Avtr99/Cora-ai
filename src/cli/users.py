"""User account recovery CLI.

Run inside the container:
``docker compose exec app python -m src.cli.users reset-password <username>``
— ``exec`` allocates a TTY by default, so ``getpass`` does not echo.
``run_migrations()`` runs first so the tool works on a fresh volume. The
password is never printed or logged.
"""
import argparse
import getpass
import sys

from pydantic import TypeAdapter, ValidationError

from ..api.auth.credentials import Password, Username, hash_password
from ..api.auth.session_auth import delete_sessions
from ..db.database import run_migrations
from ..db.users import (
    get_user_by_username,
    list_users,
    set_password,
)

_PASSWORD = TypeAdapter(Password)
_USERNAME = TypeAdapter(Username)


def _cmd_list() -> int:
    for row in list_users():
        print(f"{row['username']}\t{row['role']}")
    return 0


def _cmd_reset_password(username: str) -> int:
    try:
        username = _USERNAME.validate_python(username)
    except ValidationError:
        print(f"Unknown user: {username}", file=sys.stderr)
        return 1
    user = get_user_by_username(username)
    if user is None:
        print(f"Unknown user: {username}", file=sys.stderr)
        return 1

    first = getpass.getpass("New password: ")
    second = getpass.getpass("Repeat new password: ")
    if first != second:
        print("Passwords do not match.", file=sys.stderr)
        return 2
    try:
        _PASSWORD.validate_python(first)
    except ValidationError as exc:
        print(exc.errors()[0]["msg"].removeprefix("Value error, "), file=sys.stderr)
        return 2

    set_password(user["id"], hash_password(first))
    delete_sessions(user["id"])
    print(f"Password reset for {username}; all sessions signed out.")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.cli.users",
        description="User account recovery for a Cora instance.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="List user accounts.")
    reset_parser = subparsers.add_parser(
        "reset-password", help="Reset a user's password and end their sessions."
    )
    reset_parser.add_argument("username")

    args = parser.parse_args(argv)
    run_migrations()

    if args.command == "list":
        return _cmd_list()
    if args.command == "reset-password":
        return _cmd_reset_password(args.username)
    return 2  # unreachable: subparsers is required


if __name__ == "__main__":
    sys.exit(main())
