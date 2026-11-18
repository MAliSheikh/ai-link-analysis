"""FastAPI app. Run: uvicorn app.main:app --host 0.0.0.0 --port 4000"""
import logging

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import settings
from app.schemas import ErrorResponse, LinkAnalysisRequest, LinkAnalysisResponse
from app.services.analysis_service import AnalysisService
from app.utils.validators import AppError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("link-analysis")

app = FastAPI(
    title="AI-Powered Website Link Analysis API",
    version="1.0.0",
    description="Send a website URL and get competitor, search query, SEO, services "
                "and target audience analysis made by an LLM (Large Language Model).",
)

_service = AnalysisService()


def get_analysis_service() -> AnalysisService:
    return _service


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status,
                        content={"success": False, "error": {"code": code, "message": message}})


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    logger.warning("%s: %s", exc.code, exc.message)
    return _error(exc.status_code, exc.code, exc.message)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return _error(422, "invalid_request", 'Request body must be JSON like {"url": "https://example.com"}')


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception):
    logger.exception("Unexpected error")
    return _error(500, "internal_error", "Something went wrong on the server. Please try again.")


@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok", "llm_provider": settings.LLM_PROVIDER, "llm_model": settings.LLM_MODEL}


@app.post(
    "/link-analysis",
    response_model=LinkAnalysisResponse,
    tags=["Analysis"],
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse},
               500: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
async def link_analysis(body: LinkAnalysisRequest, service: AnalysisService = Depends(get_analysis_service)):
    return await service.analyze(body.url)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=4000)
