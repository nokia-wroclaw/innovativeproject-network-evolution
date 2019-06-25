# Use Python runtime
FROM python:slim

# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install the required packages
RUN pip3 install --no-cache-dir -r requirements.txt

# Make Bokeh's default port available to the world
EXPOSE 5006

# Run the app
CMD ["bokeh", "serve", "--allow-websocket-origin", "0.0.0.0:5006", "--show", "gui.py"]
