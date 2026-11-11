import copy
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from src import app as application


class TeacherAuthTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        credentials = Path(self.directory.name) / "teachers.json"
        salt = bytes.fromhex("01" * 16)
        credentials.write_text(json.dumps({"teacher": {
            "salt": salt.hex(),
            "password_hash": hashlib.pbkdf2_hmac(
                "sha256", b"test-password", salt, 600_000).hex()
        }}))
        self.file_patch = patch.object(application, "teachers_file", credentials)
        self.file_patch.start()
        self.original = copy.deepcopy(application.activities)
        application.sessions.clear()
        self.client = TestClient(application.app)

    def tearDown(self):
        self.client.close()
        application.activities.clear()
        application.activities.update(self.original)
        application.sessions.clear()
        self.file_patch.stop()
        self.directory.cleanup()

    def authenticate(self):
        response = self.client.post("/auth/login", json={
            "username": "teacher", "password": "test-password"})
        self.assertEqual(response.status_code, 200)
        return {"X-CSRF-Token": response.json()["csrf_token"]}

    def test_public_listing_and_anonymous_mutations(self):
        response = self.client.get("/activities")
        self.assertEqual(response.status_code, 200)
        self.assertIn("participants", response.json()["Chess Club"])
        for method, action in [("POST", "signup"), ("DELETE", "unregister")]:
            response = self.client.request(method, f"/activities/Chess Club/{action}",
                                           params={"email": "michael@mergington.edu"})
            self.assertEqual(response.status_code, 401)
        self.assertEqual(application.activities, self.original)

    def test_invalid_credentials(self):
        for username in ["teacher", "unknown"]:
            response = self.client.post("/auth/login", json={
                "username": username, "password": "wrong"})
            self.assertEqual(response.status_code, 401)
            self.assertNotIn("teacher_session", response.cookies)

    def test_teacher_signup_duplicate_and_unregister(self):
        headers = self.authenticate()
        params = {"email": "new@mergington.edu"}
        url = "/activities/Chess Club/"
        self.assertEqual(self.client.post(url + "signup", params=params, headers=headers).status_code, 200)
        self.assertEqual(self.client.post(url + "signup", params=params, headers=headers).status_code, 400)
        self.assertEqual(self.client.delete(url + "unregister", params=params, headers=headers).status_code, 200)
        self.assertEqual(self.client.delete(url + "unregister", params=params, headers=headers).status_code, 400)

    def test_session_and_csrf_protection(self):
        self.authenticate()
        session = self.client.get("/auth/session")
        self.assertEqual(session.json()["username"], "teacher")
        for method, action in [("POST", "signup"), ("DELETE", "unregister")]:
            for headers in [{}, {"X-CSRF-Token": "wrong"}]:
                response = self.client.request(method, f"/activities/Chess Club/{action}",
                    params={"email": "michael@mergington.edu"}, headers=headers)
                self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.post("/auth/logout").status_code, 403)
        self.assertEqual(application.activities, self.original)

    def test_logout_revokes_session(self):
        headers = self.authenticate()
        token = self.client.cookies.get("teacher_session")
        self.assertEqual(self.client.post("/auth/logout", headers=headers).status_code, 200)
        self.client.cookies.set("teacher_session", token)
        self.assertEqual(self.client.get("/auth/session").status_code, 401)
        self.assertEqual(self.client.post("/activities/Chess Club/signup",
            params={"email": "new@mergington.edu"}, headers=headers).status_code, 401)

    def test_expired_session(self):
        headers = self.authenticate()
        token = self.client.cookies.get("teacher_session")
        application.sessions[token] = ("teacher", time.time() - 1, headers["X-CSRF-Token"])
        self.assertEqual(self.client.get("/auth/session").status_code, 401)
        self.assertNotIn(token, application.sessions)

    def test_missing_credentials_fail_closed(self):
        application.teachers_file.unlink()
        response = self.client.post("/auth/login", json={
            "username": "teacher", "password": "test-password"})
        self.assertEqual(response.status_code, 401)

    def test_cookie_and_credential_file_are_private(self):
        response = self.client.post("/auth/login", json={
            "username": "teacher", "password": "test-password"})
        self.assertIn("HttpOnly", response.headers["set-cookie"])
        self.assertIn("SameSite=strict", response.headers["set-cookie"])
        self.assertEqual(self.client.get("/static/teachers.json").status_code, 404)


if __name__ == "__main__":
    unittest.main()