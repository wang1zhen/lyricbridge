from fastapi import APIRouter

router = APIRouter()


@router.get("/", summary="Health probe")
async def health_probe() -> dict[str, str]:
    return {"status": "ok"}


# Accept the no-trailing-slash variant to avoid 307 redirects
@router.get("", include_in_schema=False)
async def health_probe_no_slash() -> dict[str, str]:
    return {"status": "ok"}
