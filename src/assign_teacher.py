import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import secrets


def main():
    parser = argparse.ArgumentParser(description="Assign or reset a teacher's password locally.")
    parser.add_argument("username")
    args = parser.parse_args()
    if not args.username.strip():
        parser.error("Username must not be blank")
    password = getpass.getpass("Assigned password (at least 12 characters): ")
    if len(password) < 12:
        parser.error("Password must contain at least 12 characters")
    if password != getpass.getpass("Confirm password: "):
        parser.error("Passwords do not match")
    path = Path(os.environ.get("TEACHERS_FILE", Path(__file__).parent / "teachers.json"))
    teachers = json.loads(path.read_text()) if path.exists() else {}
    salt = secrets.token_bytes(16)
    teachers[args.username] = {
        "salt": salt.hex(),
        "password_hash": hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000).hex(),
    }
    with path.open("w", opener=lambda filename, flags: os.open(filename, flags, 0o600)) as output:
        json.dump(teachers, output, indent=2)
    path.chmod(0o600)
    print(f"Assigned credentials for {args.username}. Restart the server after password resets.")


if __name__ == "__main__":
    main()