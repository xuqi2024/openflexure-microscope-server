from __future__ import annotations

from typing import Optional, Callable
from functools import wraps
from copy import copy

import labthings_fastapi as lt
import uvicorn
import logging
from uvicorn.main import Server
from .serve_static_files import add_static_files
from .legacy_api import add_v2_endpoints
from ..logging import configure_logging, retrieve_log, retrieve_log_from_file


def set_shutdown_function(shutdown_function: Callable[[], None]):
    """
    Ensure a function is called before the shutdown

    This monkey patches the Uvicorn Server's handle_exit. This is needed because
    the uvicorn `lifecycle` events and FastAPI `shutdown` events only fire once
    background tasks have completed.

    Without this the system exits cleanly only if no client is receiving a
    StreamingResponse. This patch is used to stop the async generators that
    send streaming responses.

    :param shutdown_function: A callable with no arguments or outputs. This
    should stop any async generators that may be sending to streaming responses.
    """

    original_handler = Server.handle_exit

    @wraps(Server.handle_exit)
    def handle_exit(*args, **kwargs):
        shutdown_function()
        original_handler(*args, **kwargs)

    Server.handle_exit = handle_exit


def customise_server(
    server: lt.ThingServer, log_folder: str, scans_folder: Optional[str]
):
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
    args = lt.cli.parse_args(argv)

    log_config = copy(uvicorn.config.LOGGING_CONFIG)
    log_config["loggers"]["uvicorn"]["propagate"] = True
    log_config["loggers"]["uvicorn.access"]["propagate"] = True

    # Create server and config vars before trying to configure so they are defined
    # if fallback is needed before they are set.
    config = None
    server = None
    try:
        config = lt.cli.config_from_args(args)
        log_folder = config.get("log_folder", "./openflexure/logs")
        scans_folder = _get_scans_dir(config)
        server = lt.cli.server_from_config(config)
        customise_server(server, log_folder, scans_folder)

        def shutdown_call():
            try:
                # Kill any mjpeg streams so that StreamingResponses close.
                server.things["/camera/"].kill_mjpeg_streams()
            except BaseException as e:
                # Catch anything and log as it is essential that this
                # function cannot raise an unhandled exception or Uvicorn
                # will never get a shutdown signal.
                logging.error(e, exc_info=True)

        # Monkey patch uvicorn's exit handling to stop the MJPEG Streams
        # before waiting for background tasks to complete.
        set_shutdown_function(shutdown_call)

        uvicorn.run(
            server.app,
            host=args.host,
            port=args.port,
            log_config=log_config,
            timeout_graceful_shutdown=2,
        )

    except BaseException as e:
        if args.fallback:
            print(f"Error: {e}")
            fallback_server = "labthings_fastapi.server.fallback:app"
            print(f"Starting fallback server {fallback_server}.")
            app = lt.cli.object_reference_to_object(fallback_server)
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
