# Azure Functions Python runtime
FROM mcr.microsoft.com/azure-functions/python:4-python3.10

# Set working directory
WORKDIR /home/site/wwwroot

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy function code
COPY . .

# Environment variables (override at runtime)
ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true \
    FUNCTIONS_WORKER_RUNTIME=python

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:80/api/health || exit 1

# Expose port
EXPOSE 80
