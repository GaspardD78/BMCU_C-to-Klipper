# Use a stable Ubuntu image as the base
FROM ubuntu:22.04

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies required for the build process
RUN apt-get update && apt-get install -y \
    git \
    python3 \
    python3-pip \
    make \
    wget \
    unzip \
    gcc \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file first to leverage Docker layer caching
COPY matrix_flow/requirements.txt ./matrix_flow/requirements.txt

# wchisp is a binary, not a pip package. Remove it from requirements for the build.
RUN sed -i '/wchisp/d' ./matrix_flow/requirements.txt

# Install Python dependencies
RUN pip3 install --no-cache-dir -r ./matrix_flow/requirements.txt

# Copy the rest of the application code
COPY . .

# Set the default command to show that the container is running
CMD ["python3", "-m", "matrix_flow.run_workflow", "--help"]
