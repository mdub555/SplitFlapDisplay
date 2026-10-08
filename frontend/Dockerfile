# syntax=docker/dockerfile:1

# Build an image with the Python 3.14 image
FROM python:3.14-slim

# Set the working directory to `/code`
WORKDIR /code

# Keep settings.json (calibrations, playlists, the schedule) on the volume
# compose.yaml mounts at /code/data, so a rebuild or update doesn't lose it.
ENV SPLITFLAP_CONFIG_PATH=/code/data/settings.json
# The port the app listens on inside the container (compose.yaml maps it).
ENV SPLITFLAP_PORT=5000
# Log output straight away rather than in buffered chunks.
ENV PYTHONUNBUFFERED=1

# Install `gcc` and other dependencies
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     gcc \
#     libc-dev \
#     linux-headers-generic \
#     && rm -rf /var/lib/apt/lists/*

# Copy `requirements.txt`
COPY requirements.txt .

# Install the Python dependencies
RUN pip install -r requirements.txt

# Copy the current directory `.` in the project to the workdir `.` in the image
COPY . .

RUN mkdir -p /code/data

EXPOSE 5000

# Run the app itself: it starts the playlist, schedule and serial threads and
# serves with threads (needed for the live updates). Not `flask run --debug`,
# whose debugger shouldn't be left running on a device that's always on.
CMD ["python", "app.py"]
