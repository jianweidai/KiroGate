# -*- coding: utf-8 -*-

# KiroGate
# Based on kiro-openai-gateway by Jwadow (https://github.com/Jwadow/kiro-openai-gateway)
# Original Copyright (C) 2025 Jwadow
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""
KiroGate FastAPI routes.

Contains all API endpoints:
- / and /health: Health check
- /v1/models: Model list
- /v1/chat/completions: OpenAI compatible chat completions
- /v1/messages: Anthropic compatible messages API
"""

import json
import secrets
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Security, Header
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from fastapi.security import APIKeyHeader
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from loguru import logger

from kiro_gateway.config import (
    PROXY_API_KEY,
    AVAILABLE_MODELS,
    APP_VERSION,
    RATE_LIMIT_PER_MINUTE,
)
from kiro_gateway.models import (
    OpenAIModel,
    ModelList,
    ChatCompletionRequest,
    AnthropicMessagesRequest,
)
from kiro_gateway.auth import KiroAuthManager
from kiro_gateway.auth_cache import auth_cache
from kiro_gateway.cache import ModelInfoCache
from kiro_gateway.request_handler import RequestHandler
from kiro_gateway.utils import get_kiro_headers
from kiro_gateway.config import settings
from kiro_gateway.pages import (
    render_home_page,
    render_docs_page,
    render_playground_page,
    render_deploy_page,
    render_status_page,
    render_dashboard_page,
    render_swagger_page,
)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# 预创建速率限制装饰器（避免重复创建）
_rate_limit_decorator_cache = None


def rate_limit_decorator():
    """
    Conditional rate limit decorator (cached).

    Applies rate limit when RATE_LIMIT_PER_MINUTE > 0,
    disabled when RATE_LIMIT_PER_MINUTE = 0.
    """
    global _rate_limit_decorator_cache
    if _rate_limit_decorator_cache is None:
        if RATE_LIMIT_PER_MINUTE > 0:
            _rate_limit_decorator_cache = limiter.limit(f"{RATE_LIMIT_PER_MINUTE}/minute")
        else:
            _rate_limit_decorator_cache = lambda func: func
    return _rate_limit_decorator_cache


try:
    from kiro_gateway.debug_logger import debug_logger
except ImportError:
    debug_logger = None


# --- Security scheme ---
api_key_header = APIKeyHeader(name="Authorization", auto_error=False)


def _mask_token(token: str) -> str:
    """
    Mask token for logging (show only first and last 4 chars).

    Args:
        token: Token to mask

    Returns:
        Masked token string
    """
    if len(token) <= 8:
        return "***"
    return f"{token[:4]}...{token[-4:]}"


async def _parse_auth_header(auth_header: str) -> tuple[str, KiroAuthManager]:
    """
    Parse Authorization header and return proxy key and AuthManager.

    Supports two formats:
    1. Traditional: "Bearer {PROXY_API_KEY}" - uses global AuthManager
    2. Multi-tenant: "Bearer {PROXY_API_KEY}:{REFRESH_TOKEN}" - creates per-user AuthManager

    Args:
        auth_header: Authorization header value

    Returns:
        Tuple of (proxy_key, auth_manager)

    Raises:
        HTTPException: 401 if key is invalid or missing
    """
    if not auth_header or not auth_header.startswith("Bearer "):
        logger.warning("Missing or invalid Authorization header format")
        raise HTTPException(status_code=401, detail="Invalid or missing API Key")

    token = auth_header[7:]  # Remove "Bearer "

    # Check if token contains ':' (multi-tenant format)
    if ':' in token:
        parts = token.split(':', 1)  # Split only once
        proxy_key = parts[0]
        refresh_token = parts[1]

        # Verify proxy key
        if not secrets.compare_digest(proxy_key, PROXY_API_KEY):
            logger.warning(f"Invalid proxy key in multi-tenant format: {_mask_token(proxy_key)}")
            raise HTTPException(status_code=401, detail="Invalid or missing API Key")

        # Get or create AuthManager for this refresh token
        logger.debug(f"Multi-tenant mode: using custom refresh token {_mask_token(refresh_token)}")
        auth_manager = await auth_cache.get_or_create(
            refresh_token=refresh_token,
            region=settings.region,
            profile_arn=settings.profile_arn
        )
        return proxy_key, auth_manager
    else:
        # Traditional mode: verify entire token as PROXY_API_KEY
        if not secrets.compare_digest(token, PROXY_API_KEY):
            logger.warning("Invalid API key in traditional format")
            raise HTTPException(status_code=401, detail="Invalid or missing API Key")

        # Return None to indicate using global AuthManager
        logger.debug("Traditional mode: using global AuthManager")
        return token, None


async def verify_api_key(
    request: Request,
    auth_header: str = Security(api_key_header)
) -> KiroAuthManager:
    """
    Verify API key in Authorization header and return appropriate AuthManager.

    Supports two formats:
    1. Traditional: "Bearer {PROXY_API_KEY}" - uses global AuthManager
    2. Multi-tenant: "Bearer {PROXY_API_KEY}:{REFRESH_TOKEN}" - creates per-user AuthManager

    Args:
        request: FastAPI Request for accessing app.state
        auth_header: Authorization header value

    Returns:
        KiroAuthManager instance (global or per-user)

    Raises:
        HTTPException: 401 if key is invalid or missing
    """
    proxy_key, auth_manager = await _parse_auth_header(auth_header)

    # If auth_manager is None, use global AuthManager
    if auth_manager is None:
        auth_manager = request.app.state.auth_manager

    return auth_manager


async def verify_anthropic_api_key(
    request: Request,
    x_api_key: str = Header(None, alias="x-api-key"),
    auth_header: str = Security(api_key_header)
) -> KiroAuthManager:
    """
    Verify Anthropic or OpenAI format API key and return appropriate AuthManager.

    Anthropic uses x-api-key header, but we also support
    standard Authorization: Bearer format for compatibility.

    Supports two formats:
    1. Traditional: "{PROXY_API_KEY}" - uses global AuthManager
    2. Multi-tenant: "{PROXY_API_KEY}:{REFRESH_TOKEN}" - creates per-user AuthManager

    Args:
        request: FastAPI Request for accessing app.state
        x_api_key: x-api-key header value (Anthropic format)
        auth_header: Authorization header value (OpenAI format)

    Returns:
        KiroAuthManager instance (global or per-user)

    Raises:
        HTTPException: 401 if key is invalid or missing
    """
    # Try x-api-key first (Anthropic format)
    if x_api_key:
        # Check if x-api-key contains ':' (multi-tenant format)
        if ':' in x_api_key:
            parts = x_api_key.split(':', 1)
            proxy_key = parts[0]
            refresh_token = parts[1]

            # Verify proxy key
            if not secrets.compare_digest(proxy_key, PROXY_API_KEY):
                logger.warning(f"Invalid proxy key in x-api-key: {_mask_token(proxy_key)}")
                raise HTTPException(status_code=401, detail="Invalid or missing API Key")

            # Get or create AuthManager for this refresh token
            logger.debug(f"Multi-tenant mode (x-api-key): using custom refresh token {_mask_token(refresh_token)}")
            auth_manager = await auth_cache.get_or_create(
                refresh_token=refresh_token,
                region=settings.region,
                profile_arn=settings.profile_arn
            )
            return auth_manager
        else:
            # Traditional mode: verify entire x-api-key as PROXY_API_KEY
            if secrets.compare_digest(x_api_key, PROXY_API_KEY):
                logger.debug("Traditional mode (x-api-key): using global AuthManager")
                return request.app.state.auth_manager

    # Try Authorization header (OpenAI format)
    if auth_header:
        return await verify_api_key(request, auth_header)

    logger.warning("Access attempt with invalid API key (Anthropic endpoint).")
    raise HTTPException(status_code=401, detail="Invalid or missing API Key")


# --- Router ---
router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def root():
    """
    Home page with dashboard.

    Returns:
        HTML home page
    """
    return HTMLResponse(content=render_home_page())


@router.get("/api", response_class=JSONResponse)
async def api_root():
    """
    API health check endpoint (JSON).

    Returns:
        Application status and version info
    """
    return {
        "status": "ok",
        "message": "Kiro API Gateway is running",
        "version": APP_VERSION
    }


@router.get("/docs", response_class=HTMLResponse)
async def docs_page():
    """
    API documentation page.

    Returns:
        HTML documentation page
    """
    return HTMLResponse(content=render_docs_page())


@router.get("/playground", response_class=HTMLResponse)
async def playground_page():
    """
    API playground page.

    Returns:
        HTML playground page
    """
    return HTMLResponse(content=render_playground_page())


@router.get("/deploy", response_class=HTMLResponse)
async def deploy_page():
    """
    Deployment guide page.

    Returns:
        HTML deployment guide page
    """
    return HTMLResponse(content=render_deploy_page())


@router.get("/status", response_class=HTMLResponse)
async def status_page(request: Request):
    """
    Status page with system health info.

    Returns:
        HTML status page
    """
    from kiro_gateway.metrics import metrics

    auth_manager: KiroAuthManager = request.app.state.auth_manager
    model_cache: ModelInfoCache = request.app.state.model_cache

    # Check if token is valid
    token_valid = False
    try:
        if auth_manager._access_token and not auth_manager.is_token_expiring_soon():
            token_valid = True
    except Exception:
        token_valid = False

    status_data = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": APP_VERSION,
        "token_valid": token_valid,
        "cache_size": model_cache.size,
        "cache_last_update": model_cache.last_update_time
    }

    return HTMLResponse(content=render_status_page(status_data))


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page():
    """
    Dashboard page with metrics and charts.

    Returns:
        HTML dashboard page
    """
    return HTMLResponse(content=render_dashboard_page())


@router.get("/swagger", response_class=HTMLResponse)
async def swagger_page():
    """
    Swagger UI page for API documentation.

    Returns:
        HTML Swagger UI page
    """
    return HTMLResponse(content=render_swagger_page())


@router.get("/health")
async def health(request: Request):
    """
    Detailed health check.

    Returns:
        Status, timestamp, version and runtime info
    """
    from kiro_gateway.metrics import metrics

    auth_manager: KiroAuthManager = request.app.state.auth_manager
    model_cache: ModelInfoCache = request.app.state.model_cache

    # Check if token is valid
    token_valid = False
    try:
        if auth_manager._access_token and not auth_manager.is_token_expiring_soon():
            token_valid = True
    except Exception:
        token_valid = False

    # Update metrics
    metrics.set_cache_size(model_cache.size)
    metrics.set_token_valid(token_valid)

    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": APP_VERSION,
        "token_valid": token_valid,
        "cache_size": model_cache.size,
        "cache_last_update": model_cache.last_update_time
    }


@router.get("/metrics")
async def get_metrics():
    """
    Get application metrics in JSON format.

    Returns:
        Metrics data dictionary
    """
    from kiro_gateway.metrics import metrics
    return metrics.get_metrics()


@router.get("/api/metrics")
async def get_api_metrics():
    """
    Get application metrics in Deno-compatible format for dashboard.

    Returns:
        Deno-compatible metrics data dictionary
    """
    from kiro_gateway.metrics import metrics
    return metrics.get_deno_compatible_metrics()


@router.get("/metrics/prometheus")
async def get_prometheus_metrics():
    """
    Get application metrics in Prometheus format.

    Returns:
        Prometheus text format metrics
    """
    from kiro_gateway.metrics import metrics
    return Response(
        content=metrics.export_prometheus(),
        media_type="text/plain; charset=utf-8"
    )


@router.get("/v1/models", response_model=ModelList)
@rate_limit_decorator()
async def get_models(
    request: Request,
    auth_manager: KiroAuthManager = Depends(verify_api_key)
):
    """
    Return available models list.

    Uses static model list with optional dynamic updates from API.
    Results are cached to reduce API load.

    Args:
        request: FastAPI Request for accessing app.state
        auth_manager: KiroAuthManager instance (from verify_api_key)

    Returns:
        ModelList containing available models
    """
    logger.info("Request to /v1/models")

    model_cache: ModelInfoCache = request.app.state.model_cache

    # Trigger background refresh if cache is empty or stale
    if model_cache.is_empty() or model_cache.is_stale():
        # Don't block - just trigger refresh in background
        try:
            import asyncio
            asyncio.create_task(model_cache.refresh())
        except Exception as e:
            logger.warning(f"Failed to trigger model cache refresh: {e}")

    # Return static model list immediately
    openai_models = [
        OpenAIModel(
            id=model_id,
            owned_by="anthropic",
            description="Claude model via Kiro API"
        )
        for model_id in AVAILABLE_MODELS
    ]

    return ModelList(data=openai_models)


@router.post("/v1/chat/completions")
@rate_limit_decorator()
async def chat_completions(
    request: Request,
    request_data: ChatCompletionRequest,
    auth_manager: KiroAuthManager = Depends(verify_api_key)
):
    """
    Chat completions endpoint - OpenAI API compatible.

    Accepts OpenAI format requests and converts to Kiro API.
    Supports streaming and non-streaming modes.

    Args:
        request: FastAPI Request for accessing app.state
        request_data: OpenAI ChatCompletionRequest format
        auth_manager: KiroAuthManager instance (from verify_api_key)

    Returns:
        StreamingResponse for streaming mode
        JSONResponse for non-streaming mode

    Raises:
        HTTPException: On validation or API errors
    """
    logger.info(f"Request to /v1/chat/completions (model={request_data.model}, stream={request_data.stream})")

    # Store auth_manager and model in request state for RequestHandler and metrics
    request.state.auth_manager = auth_manager
    request.state.model = request_data.model

    return await RequestHandler.process_request(
        request,
        request_data,
        "/v1/chat/completions",
        convert_to_openai=False,
        response_format="openai"
    )


# ==================================================================================================
# Anthropic Messages API Endpoint (/v1/messages)
# ==================================================================================================

@router.post("/v1/messages")
@rate_limit_decorator()
async def anthropic_messages(
    request: Request,
    request_data: AnthropicMessagesRequest,
    auth_manager: KiroAuthManager = Depends(verify_anthropic_api_key)
):
    """
    Anthropic Messages API endpoint - Anthropic SDK compatible.

    Accepts Anthropic format requests and converts to Kiro API.
    Supports streaming and non-streaming modes.

    Args:
        request: FastAPI Request for accessing app.state
        request_data: Anthropic MessagesRequest format
        auth_manager: KiroAuthManager instance (from verify_anthropic_api_key)

    Returns:
        StreamingResponse for streaming mode
        JSONResponse for non-streaming mode

    Raises:
        HTTPException: On validation or API errors
    """
    logger.info(f"Request to /v1/messages (model={request_data.model}, stream={request_data.stream})")

    # Store auth_manager and model in request state for RequestHandler and metrics
    request.state.auth_manager = auth_manager
    request.state.model = request_data.model

    return await RequestHandler.process_request(
        request,
        request_data,
        "/v1/messages",
        convert_to_openai=True,
        response_format="anthropic"
    )


# --- Rate limit error handler ---
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Handle rate limit errors."""
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "message": "Rate limit exceeded. Please try again later.",
                "type": "rate_limit_exceeded",
                "code": 429
            }
        }
    )