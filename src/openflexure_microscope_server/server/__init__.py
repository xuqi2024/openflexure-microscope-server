from __future__ import annotations

from typing import Optional

from labthings_fastapi.server import cli, ThingServer
import uvicorn
from .serve_static_files import add_static_files
from .legacy_api import add_v2_endpoints
from ..logging import configure_logging, retrieve_log


def customise_server(server: ThingServer):
    """Customise the server with additional endpoints, etc."""
    configure_logging()
    add_v2_endpoints(server)
    try:
        add_static_files(server.app)
    except RuntimeError:
        print("Failed to add static files - you will have to do without them!")

    # Add an endpoint to get the log
    server.app.get("/log/")(retrieve_log)


def serve_from_cli(argv: Optional[list[str]] = None):
    """Start the server from the command line"""
    args = cli.parse_args(argv)
    try:
        config, server = None, None
        config = cli.config_from_args(args)
        server = cli.server_from_config(config)
        customise_server(server)
        uvicorn.run(server.app, host=args.host, port=args.port)
    except BaseException as e:
        if args.fallback:
            print(f"Error: {e}")
            fallback_server = "labthings_fastapi.server.fallback:app"
            print(f"Starting fallback server {fallback_server}.")
            app = cli.object_reference_to_object(fallback_server)
            app.labthings_config = config
            app.labthings_server = server
            app.labthings_error = e
            uvicorn.run(app, host=args.host, port=args.port)
        else:
            raise e
