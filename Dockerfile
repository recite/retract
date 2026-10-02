FROM python:3.14-slim
COPY pyproject.toml README.md LICENSE /opt/retract/
COPY retract /opt/retract/retract
RUN python -m pip install --no-cache-dir /opt/retract
ENTRYPOINT ["retract-check"]
