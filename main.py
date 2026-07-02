import time
import uuid
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response


EMAIL = "24f3002540@ds.study.iitm.ac.in"

ALLOWED_ORIGINS = {
    "https://app-zt3wel.example.com",

    "https://middleware-stack-0ihn.onrender.com",
}

RATE_LIMIT = 11
WINDOW_SECONDS = 10

clients = defaultdict(deque)

app = FastAPI()


def add_cors_headers(response: Response, origin: str | None):
    if origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "X-Request-ID, X-Client-Id, Content-Type"
        response.headers["Access-Control-Expose-Headers"] = "X-Request-ID"
        response.headers["Vary"] = "Origin"
    return response


@app.middleware("http")
async def combined_middleware(request: Request, call_next):
    origin = request.headers.get("origin")

    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id

    # CORS preflight
    if request.method == "OPTIONS":
        response = Response(status_code=204)
        response.headers["X-Request-ID"] = request_id
        return add_cors_headers(response, origin)

    # Rate limit
    client_id = request.headers.get("X-Client-Id", "anonymous")
    now = time.monotonic()
    bucket = clients[client_id]

    while bucket and now - bucket[0] >= WINDOW_SECONDS:
        bucket.popleft()

    if len(bucket) >= RATE_LIMIT:
        response = JSONResponse(
            status_code=429,
            content={
                "detail": "rate limit exceeded",
                "request_id": request_id,
            },
        )
        response.headers["X-Request-ID"] = request_id
        return add_cors_headers(response, origin)

    bucket.append(now)

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return add_cors_headers(response, origin)


@app.get("/")
def home():
    return {"message": "Middleware Stack API is running"}


@app.get("/ping")
def ping(request: Request):
    return {
        "email": EMAIL,
        "request_id": request.state.request_id,
    }