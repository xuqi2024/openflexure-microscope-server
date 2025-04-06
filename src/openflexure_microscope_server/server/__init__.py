from __future__ import annotations

from typing import Optional
import logging

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
        uvicorn.run(
            server.app,
            host=args.host,
            port=args.port,
            log_config={
                "version": 1,
                "disable_existing_loggers": False,
            },
        )
    except BaseException as e:
        if args.fallback:
            logging.error(f"Error: {e}")
            fallback_server = "labthings_fastapi.server.fallback:app"
            logging.info(f"Starting fallback server {fallback_server}.")
            log_history = None
            try:
                root_logger = logging.getLogger()
                logfile_path = root_logger.root.handlers[0].baseFilename
                with open(logfile_path) as log_file:
                    log_history = log_file.read()
            except BaseException as e:
                logging.error(f"Error: {e}")
                logging.info("Cannot send logging history to fallback server")
            app = cli.object_reference_to_object(fallback_server)
            app.labthings_config = config
            app.labthings_server = server
            app.labthings_error = e
            app.log_history = log_history
            uvicorn.run(
                app,
                host=args.host,
                port=args.port,
                log_config={
                    "version": 1,
                    "disable_existing_loggers": False,
                },
            )
        else:
            raise e
