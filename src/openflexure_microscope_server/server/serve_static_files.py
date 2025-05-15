import os

from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI


def add_static_file(app: FastAPI, fname: str, folder: str):
    p = os.path.join(folder, fname)
    app.get(f"/{fname}", response_class=FileResponse, include_in_schema=False)(
        lambda: FileResponse(p)
    )


def add_static_files(app: FastAPI):
    static_path = os.path.abspath(os.path.join(__file__, "..", "static"))
    if not os.path.isdir(static_path):
        raise RuntimeError("Can't find static files")

    @app.get("/", response_class=RedirectResponse)
    async def redirect_fastapi():
        return "/index.html"

    # Mounting the webapp at / file by file to allow other endpoints to be created
    for fname in os.listdir(static_path):
        fpath = os.path.join(static_path, fname)
        if os.path.isfile(fpath):
            add_static_file(app, fname, static_path)
        elif os.path.isdir(fpath):
            app.mount(
                f"/{fname}/",
                StaticFiles(directory=fpath),
                name=f"static_{fname}",
            )
