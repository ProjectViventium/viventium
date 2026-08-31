FROM python:3.12-alpine@sha256:78098ea6a3a9c6a7727a5d4674e4a44e57e01fac878ee9cb4d24a86bd93916ff

RUN addgroup -S glasshive && adduser -S -D -H -G glasshive glasshive
WORKDIR /app
COPY proxy.py /app/proxy.py
RUN chmod 0555 /app/proxy.py

USER glasshive
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=2s --start-period=3s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=1).read()"
ENTRYPOINT ["python", "/app/proxy.py"]
