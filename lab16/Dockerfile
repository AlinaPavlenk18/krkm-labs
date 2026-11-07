FROM python:3.12-slim
ENV PIP_NO_CACHE_DIR=1 PYTHONUNBUFFERED=1 HF_HOME=/hub/.hf PYTHONHASHSEED=42
WORKDIR /hub
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
COPY lab16/requirements.txt lab16/requirements.txt
RUN pip install -r lab16/requirements.txt
RUN python -c "from sentence_transformers import SentenceTransformer, CrossEncoder; \
SentenceTransformer('intfloat/multilingual-e5-small'); CrossEncoder('cross-encoder/mmarco-mMiniLMv2-L12-H384-v1')"
COPY lab11 lab11
COPY lab12 lab12
COPY lab14 lab14
COPY lab15 lab15
COPY lab16 lab16
WORKDIR /hub/lab16
EXPOSE 8000 8501
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
