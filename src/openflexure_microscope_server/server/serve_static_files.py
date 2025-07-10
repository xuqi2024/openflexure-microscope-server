import os
from typing import Optional

from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI

THIS_DIR = os.path.dirname(os.path.abspath(__file__))


def add_static_file(app: FastAPI, fname: str, folder: str) -> None:
    """Add a single file to the root of the FastAPI app.

    The file  with name ``fname`` will be mounted at ``/fname`` - the
    ``folder`` does not affect where it is mounted in the app.

    app: The FastAPI app to add to, in this case the OpenFlexure server
    fname: the name of the file to add
    folder: the containing folder of the file
    """
    p = os.path.join(folder, fname)
    app.get(f"/{fname}", response_class=FileResponse, include_in_schema=False)(
        lambda: FileResponse(p)
    )


def add_static_files(app: FastAPI, scans_folder: Optional[str]) -> None:
    """Add the static files responsible for the webapp app to the FastAPI app.

    app: The FastAPI app to add to, in this case the OpenFlexure server
    """
    static_path = os.path.normpath(os.path.join(THIS_DIR, "..", "static"))

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

    # If scans folder is None, there is not smart scan thing. So nothing to mount.
    if scans_folder is not None:
        # Mount the scan directory to .../scans/, to allow dzi viewing
        if not os.path.isdir(scans_folder):
            os.makedirs(scans_folder)
        app.mount(
            "/scans/",
            StaticFiles(directory=scans_folder),
            name="scans",
        )
