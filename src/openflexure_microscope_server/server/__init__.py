from __future__ import annotations

from typing import Optional
from copy import copy

from labthings_fastapi.server import cli, ThingServer
import uvicorn
from .serve_static_files import add_static_files
from .legacy_api import add_v2_endpoints
from ..logging import configure_logging, retrieve_log, retrieve_log_from_file


def customise_server(server: ThingServer, log_folder: str, scans_folder: Optional[str]):
    """Customise the server with additional endpoints, etc."""
    configure_logging(log_folder)
    add_v2_endpoints(server)
    add_static_files(server.app, scans_folder)

    # Add an endpoint to get the logs - (directly calling the FastAPI decorator)
    server.app.get("/log/")(retrieve_log)
    server.app.get("/logfile/")(retrieve_log_from_file)


def _get_scans_dir(config: dict) -> Optional[str]:
    """
    Read the config and return the scans directory.

    Return is None if there is no /smart_scan/ thing loaded.
    """

    if "/smart_scan/" in config["things"]:
        try:
            return config["things"]["/smart_scan/"]["kwargs"]["scans_folder"]
        except KeyError as e:
            msg = "Configuration error smart scan should have scans_folder kwarg set"
            raise RuntimeError(msg) from e
    return None


def serve_from_cli(argv: Optional[list[str]] = None):
    """Start the server from the command line"""
    args = cli.parse_args(argv)

    log_config = copy(uvicorn.config.LOGGING_CONFIG)
    log_config["loggers"]["uvicorn"]["propagate"] = True
    log_config["loggers"]["uvicorn.access"]["propagate"] = True

    # Create server and config vars before trying to configure so they are defined
    # if fallback is needed before they are set.
    config = None
    server = None
    try:
        config = cli.config_from_args(args)
        log_folder = config.get("log_folder", "./openflexure/logs")
        scans_folder = _get_scans_dir(config)
        server = cli.server_from_config(config)
        customise_server(server, log_folder, scans_folder)
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
