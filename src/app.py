"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import time

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

# Mount the static files directory
current_dir = Path(__file__).parent
teachers_file = Path(os.environ.get("TEACHERS_FILE", current_dir / "teachers.json"))
sessions: dict[str, tuple[str, float, str]] = {}
session_lifetime = 8 * 60 * 60
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")


class LoginDetails(BaseModel):
    username: str
    password: str


def get_teacher_session(request: Request):
    token = request.cookies.get("teacher_session", "")
    session = sessions.get(token)
    if session is None or session[1] <= time.time():
        sessions.pop(token, None)
        raise HTTPException(status_code=401, detail="Teacher login required")
    return session


def require_teacher(request: Request, session=Depends(get_teacher_session)):
    if not hmac.compare_digest(request.headers.get("X-CSRF-Token", ""), session[2]):
        raise HTTPException(status_code=403, detail="Invalid session verification")
    return session[0]


@app.post("/auth/login")
def login(details: LoginDetails, request: Request, response: Response):
    try:
        teachers = json.loads(teachers_file.read_text())
        stored = teachers.get(details.username, {})
        salt = bytes.fromhex(stored.get("salt", "00" * 16))
        candidate = hashlib.pbkdf2_hmac("sha256", details.password.encode(), salt, 600_000).hex()
        valid = hmac.compare_digest(candidate, stored.get("password_hash", ""))
    except (OSError, ValueError, TypeError, AttributeError):
        valid = False
    if not valid:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    now = time.time()
    for token, session in list(sessions.items()):
        if session[1] <= now:
            sessions.pop(token, None)
    sessions.pop(request.cookies.get("teacher_session", ""), None)
    token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    sessions[token] = (details.username, now + session_lifetime, csrf_token)
    response.set_cookie("teacher_session", token, max_age=session_lifetime,
                        httponly=True, samesite="strict",
                        secure=os.environ.get("COOKIE_SECURE", "false").lower() == "true")
    return {"username": details.username, "csrf_token": csrf_token}


@app.get("/auth/session")
def get_session(session=Depends(get_teacher_session)):
    return {"username": session[0], "csrf_token": session[2]}


@app.post("/auth/logout")
def logout(request: Request, response: Response, teacher=Depends(require_teacher)):
    sessions.pop(request.cookies.get("teacher_session", ""), None)
    response.delete_cookie("teacher_session", httponly=True, samesite="strict")
    return {"message": "Logged out"}


# In-memory activity database
activities = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
    }
}


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    return activities


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str, teacher=Depends(require_teacher)):
    """Sign up a student for an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is not already signed up
    if email in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is already signed up"
        )

    # Add student
    activity["participants"].append(email)
    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str, teacher=Depends(require_teacher)):
    """Unregister a student from an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is signed up
    if email not in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is not signed up for this activity"
        )

    # Remove student
    activity["participants"].remove(email)
    return {"message": f"Unregistered {email} from {activity_name}"}
