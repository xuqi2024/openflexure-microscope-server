# A Dockerfile for the simulator this is useful for making the simulator run in tests.

FROM python:3.11

# Install needed deps for OpenCV and clean up for smaller image.
RUN apt-get update && apt-get install -y libglu1-mesa-dev  && rm -rf /var/lib/apt/lists/

WORKDIR /app

# Copy over the files we need
COPY src/ ./src/
COPY pyproject.toml .
COPY ofm_config_simulation.json .

# As it is containerised turn of the warning about root installation
ENV PIP_ROOT_USER_ACTION=ignore
# Install the server
RUN pip install -e .

#Expose the microscope port
EXPOSE 5000

#Run the server
CMD ["openflexure-microscope-server", "--host", "0.0.0.0", "--fallback", "-c", "./ofm_config_simulation.json"]
