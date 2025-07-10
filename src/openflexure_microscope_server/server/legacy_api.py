"""Provide endpoints that mimic the v2 API for OpenFlexure Connect discoverability."""

import labthings_fastapi as lt
from fastapi import Response
from socket import gethostname


def add_v2_endpoints(thing_server: lt.ThingServer):
    """Add the v2 API endpoints for OpenFlexure Connect discoverability."""
    app = thing_server.app

    # TODO: update openflexure connect to make this unnecessary!!
    # The endpoints below fool OpenFlexure Connect into thinking we are a
    # v2 microscope, so we show up correctly.
    # This is necessary until Connect is rebuilt.
    @app.get("/routes")
    def routes_stub() -> dict[str, dict]:
        """Return a stub list of routes.

        This is used by OF Connect to identify the microscope.
        """
        fake_routes = [
            "/api/v2/",
            "/api/v2/streams/snapshot",
            "/api/v2/instrument/settings/name",
        ]
        return {url: {"url": url, "methods": ["GET"]} for url in fake_routes}

    class JPEGResponse(Response):
        media_type = "image/jpeg"

    @app.get("/api/v2/streams/snapshot")
    @app.head("/api/v2/streams/snapshot")
    async def thumbnail() -> JPEGResponse:
        """Return a low-resolution snapshot, for compatibility with OF connect."""
        blob = await thing_server.things["/camera/"].lores_mjpeg_stream.grab_frame()
        return JPEGResponse(blob)

    @app.get("/api/v2/instrument/settings/name")
    def get_hostname() -> str:
        """Get the hostname of the device, for compatibility with OF connect."""
        return gethostname()
