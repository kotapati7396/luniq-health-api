from fastapi import Header, HTTPException, status

from app.config import settings


async def verify_api_key(x_api_key: str = Header(default=settings.API_KEY)) -> None:
    """If settings.API_KEY is empty, auth is disabled (local dev only).
    In production, set API_KEY and require clients to send X-API-Key.

    NOTE: the default value above is set to your real API_KEY so the Swagger
    docs page (/docs) shows it pre-filled - convenient for your own testing.
    Real client apps should still send the X-API-Key header explicitly on
    every request; don't rely on the default for anything but your own
    manual testing in /docs.
    """
    if not settings.API_KEY:
        return
    if x_api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Send it in the X-API-Key header.",
        )
