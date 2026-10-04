import secrets

from flask.testing import FlaskClient

from app import app


class CsrfTestClient(FlaskClient):
    def open(self, *args, **kwargs):
        method = kwargs.get("method")
        if method is None and args and isinstance(args[0], str):
            method = args[0] if len(args) > 1 else "GET"
        method = (method or "GET").upper()
        headers = kwargs.get("headers") or {}
        if method not in {"GET", "HEAD", "OPTIONS", "TRACE"} and "X-CSRFToken" not in headers:
            with self.session_transaction() as user_session:
                token = user_session.get("_csrf_token")
                if not token:
                    token = secrets.token_urlsafe(32)
                    user_session["_csrf_token"] = token
            kwargs["headers"] = {**headers, "X-CSRFToken": token}
        return super().open(*args, **kwargs)


app.test_client_class = CsrfTestClient
