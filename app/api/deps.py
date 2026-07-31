from fastapi import Depends, Header, HTTPException, status

async def get_api_key(x_api_key: str | None = Header(None)) -> str:
    if x_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key header"
        )
    return x_api_key
