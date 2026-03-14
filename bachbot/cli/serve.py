from __future__ import annotations

import uvicorn


def serve_api(*, host: str, port: int, reload: bool = False) -> None:
    uvicorn.run("bachbot.api:app", host=host, port=port, reload=reload, factory=False)
