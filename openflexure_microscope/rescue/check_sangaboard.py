from openflexure_microscope.config import user_configuration

from .error_sources import ErrorSource


def main():
    error_sources = []

    try:
        from sangaboard import Sangaboard
    except ImportError as e:
        error_sources.append(ErrorSource(str(e)))
    else:
        configuration = user_configuration.load()
        stage_type = configuration["stage"].get("type")
        stage_port = configuration["stage"].get("port")

        # If any Sangaboard-based stage is configured for use
        if stage_type in ("SangaBoard", "SangaStage", "SangaDeltaStage"):
            # Try connecting on the specified port
            try:
                stage = Sangaboard(stage_port)
            except FileNotFoundError as _:
                if stage_port:
                    error_sources.append(
                        ErrorSource(
                            f"No {stage_type} device was found on the configured port {stage_port}."
                        )
                    )
                else:
                    error_sources.append(
                        ErrorSource(
                            f"No {stage_type} device was found during port scanning."
                        )
                    )
            else:
                stage.close()
        else:
            error_sources.append(
                ErrorSource(
                    f"Invalid stage type {stage_type} specified in configuration file."
                )
            )

    return error_sources
