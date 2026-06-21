FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
# To enable real Cellpose: add `RUN pip install cellpose pillow numpy`,
# COPY your samples/ folder, and set CV_MODE=real.
ENV CV_MODE=stub
EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
