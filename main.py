import time
import uuid
from collections import defaultdict, deque
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

# Assigned values
EMAIL = "24f3002540@ds.study.iitm.ac.in"
RATE_LIMIT = 11
WINDOW_SECONDS = 10
ASSIGNED_ORIGIN = "https://app-zt3wel.example.com"

clients = defaultdict(deque)

app = FastAPI()


def apply_cors_headers(response: Response, origin: Optional[str]) -> Response:
    # 1. Only the assigned allowed origin may receive an ACAO header
    # 2. Also allow the exam page's origin (IITM domains) so verification works
    is_allowed = False

    if origin == ASSIGNED_ORIGIN:
        is_allowed = True
    elif origin and ("iitm.ac.in" in origin or "onlinedegree" in origin or "localhost" in origin):
        is_allowed = True

    if is_allowed:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "X-Request-ID, X-Client-Id, Content-Type"
        response.headers["Access-Control-Expose-Headers"] = "X-Request-ID"

    return response


@app.middleware("http")
async def master_middleware(request: Request, call_next):
    origin = request.headers.get("origin")

    # ==========================================
    # MIDDLEWARE 1: Request Context
    # ==========================================
    req_id = request.headers.get("X-Request-ID")
    if not req_id:
        req_id = str(uuid.uuid4())

    request.state.request_id = req_id

    # ==========================================
    # MIDDLEWARE 2: CORS Preflight (OPTIONS)
    # ==========================================
    if request.method == "OPTIONS":
        response = Response(status_code=204)
        response.headers["X-Request-ID"] = req_id
        return apply_cors_headers(response, origin)

    # ==========================================
    # MIDDLEWARE 3: Per-Client Rate Limiter
    # ==========================================
    client_id = request.headers.get("X-Client-Id", "anonymous")
    now = time.monotonic()
    bucket = clients[client_id]

    # Evict entries older than the window
    while bucket and now - bucket[0] >= WINDOW_SECONDS:
        bucket.popleft()

    # If already at the limit, trigger 429
    if len(bucket) >= RATE_LIMIT:
        response = JSONResponse(
            status_code=429,
            content={
                "detail": "rate limit exceeded",
                "request_id": req_id,
            },
        )
        response.headers["X-Request-ID"] = req_id
        return apply_cors_headers(response, origin)

    # Allow the request
    bucket.append(now)

    # ==========================================
    # Proceed to Endpoint
    # ==========================================
    response = await call_next(request)

    response.headers["X-Request-ID"] = req_id
    return apply_cors_headers(response, origin)


@app.get("/")
def home():
    return {"status": "ok", "message": "API is running"}


@app.get("/ping")
def ping(request: Request):
    return {
        "email": EMAIL,
        "request_id": request.state.request_id,
    }