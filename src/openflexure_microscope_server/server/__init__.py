from __future__ import annotations

from typing import Optional
import logging
import time
from datetime import datetime
import re

from labthings_fastapi.server import cli, ThingServer
import uvicorn
from .serve_static_files import add_static_files
from .legacy_api import add_v2_endpoints
from ..logging import configure_logging, retrieve_log, retrieve_log_from_file


def customise_server(server: ThingServer):
    """Customise the server with additional endpoints, etc."""
    configure_logging()
    add_v2_endpoints(server)
    try:
        add_static_files(server.app)
    except RuntimeError:
        print("Failed to add static files - you will have to do without them!")

    # Add an endpoint to get the logs - (directly calling the FastAPI decorator)
    server.app.get("/log/")(retrieve_log)
    server.app.get("/logfile/")(retrieve_log_from_file)


def serve_from_cli(argv: Optional[list[str]] = None):
    """Start the server from the command line"""
    start_time = time.time()
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
            start_fallback_server(args, server, config, e, start_time)
        else:
            raise e


def start_fallback_server(
    args: dict, server: ThingServer, config: dict, err: BaseException, start_time: float
):
    """LabThings has failed to start, start fallback server instead"""
    fallback_server = "labthings_fastapi.server.fallback:app"
    logging.info(f"Starting fallback server {fallback_server}.")
    log_history = None
    try:
        root_logger = logging.getLogger()
        logfile_path = root_logger.root.handlers[0].baseFilename
        with open(logfile_path, "r", encoding="utf-8") as log_file:
            log_history = log_file.read()
    except BaseException as e:
        logging.error(f"Error: {e}")
        logging.info("Cannot send logging history to fallback server")
    app = cli.object_reference_to_object(fallback_server)
    app.labthings_config = config
    app.labthings_server = server
    app.labthings_error = err
    app.log_history = filter_log_history_by_start_time(log_history, start_time)
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_config={
            "version": 1,
            "disable_existing_loggers": False,
        },
    )


def filter_log_history_by_start_time(log_history: str, start_time: float) -> str:
    """Filter logs since start of running"""
    log_list = log_history.split("\n")

    if log_list:
        for i, line in enumerate(reversed(log_list)):
            if m := re.match(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line):
                dtime = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")

                if time.mktime(dtime.timetuple()) < start_time:
                    return "\n".join(log_list[-i:])
        return "\n".join(log_list)
    return ""
