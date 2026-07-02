import os
import time
import uuid
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.middleware.cors import CORSMiddleware


EMAIL = "24f3002540@ds.study.iitm.ac.in"

ALLOWED_APP_ORIGIN = "https://app-zt3wel.example.com"

# Add exam page origin using environment variable if needed
EXAM_ORIGIN = os.getenv("EXAM_ORIGIN", "")

ALLOWED_ORIGINS = [ALLOWED_APP_ORIGIN]

if EXAM_ORIGIN:
    ALLOWED_ORIGINS.append(EXAM_ORIGIN)


RATE_LIMIT = 11
WINDOW_SECONDS = 10


# Middleware 1: Request Context
class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID")

        if not request_id:
            request_id = str(uuid.uuid4())

        request.state.request_id = request_id

        response = await call_next(request)

        response.headers["X-Request-ID"] = request_id

        return response


# Middleware 2: Rate Limiter
class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.clients = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        # Do not rate limit OPTIONS request
        if request.method == "OPTIONS":
            return await call_next(request)

        client_id = request.headers.get("X-Client-Id", "anonymous")

        now = time.monotonic()
        bucket = self.clients[client_id]

        # Remove requests older than 10 seconds
        while bucket and now - bucket[0] >= WINDOW_SECONDS:
            bucket.popleft()

        # If already 11 requests in last 10 seconds, block
        if len(bucket) >= RATE_LIMIT:
            request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

            return JSONResponse(
                status_code=429,
                content={
                    "detail": "rate limit exceeded",
                    "request_id": request_id,
                },
                headers={
                    "X-Request-ID": request_id
                }
            )

        bucket.append(now)

        return await call_next(request)


app = FastAPI()


# Add rate limit middleware
app.add_middleware(RateLimitMiddleware)


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["X-Request-ID", "X-Client-Id", "Content-Type"],
    expose_headers=["X-Request-ID"],
)


# Add request context middleware
# Important: this should run first
app.add_middleware(RequestContextMiddleware)


@app.get("/")
def home():
    return {
        "message": "Middleware Stack API is running"
    }


@app.get("/ping")
async def ping(request: Request):
    return {
        "email": EMAIL,
        "request_id": request.state.request_id,
    }