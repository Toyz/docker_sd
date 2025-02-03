# Use an official lightweight Python image.
FROM python:3.9-slim

# Set the working directory in the container.
WORKDIR /app

# Install the Docker SDK for Python.
RUN pip install --no-cache-dir docker

# Copy the scraper script into the container.
# (Ensure that generate_targets.py is in the same folder as this Dockerfile.)
COPY generate_targets.py .

# Set the default command to run the script.
CMD ["python", "generate_targets.py"]
