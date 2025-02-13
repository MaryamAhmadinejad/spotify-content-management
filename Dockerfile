FROM bitnami/spark:latest

# Set the working directory
WORKDIR /app

# Copy the requirements file (if you have one)
# COPY requirements.txt .

# Install any needed packages
# RUN pip install --no-cache-dir -r requirements.txt

# Copy your application code
COPY src /app/src

# You might not need an ENTRYPOINT if you're using spark-submit in the docker-compose command
