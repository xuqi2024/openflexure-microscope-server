from __future__ import annotations

from typing import Optional
from copy import copy

from labthings_fastapi.server import cli, ThingServer
import uvicorn
from .serve_static_files import add_static_files
from .legacy_api import add_v2_endpoints
from ..logging import configure_logging, retrieve_log, retrieve_log_from_file


def customise_server(server: ThingServer, log_folder: str):
    """Customise the server with additional endpoints, etc."""
    configure_logging(log_folder)
    add_v2_endpoints(server)
    add_static_files(server.app)

    # Add an endpoint to get the logs - (directly calling the FastAPI decorator)
    server.app.get("/log/")(retrieve_log)
    server.app.get("/logfile/")(retrieve_log_from_file)


def serve_from_cli(argv: Optional[list[str]] = None):
    """Start the server from the command line"""
    args = cli.parse_args(argv)

    log_config = copy(uvicorn.config.LOGGING_CONFIG)
    log_config["loggers"]["uvicorn"]["propagate"] = True
    log_config["loggers"]["uvicorn.access"]["propagate"] = True

    try:
        config = cli.config_from_args(args)
        log_folder = config.get("log_folder", "./openflexure/logs")
        server = cli.server_from_config(config)
        customise_server(server, log_folder)
        uvicorn.run(
            server.app,
            host=args.host,
            port=args.port,
            log_config=log_config,
        )

    except BaseException as e:
        if args.fallback:
            print(f"Error: {e}")
            fallback_server = "labthings_fastapi.server.fallback:app"
            print(f"Starting fallback server {fallback_server}.")
            app = cli.object_reference_to_object(fallback_server)
            app.labthings_config = config
            app.labthings_server = server
            app.labthings_error = e
            uvicorn.run(
                app,
                host=args.host,
                port=args.port,
                log_config=log_config,
            )
        else:
            raise e
