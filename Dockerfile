FROM ghcr.io/astral-sh/uv:0.9.26 AS uv

FROM public.ecr.aws/lambda/python:3.12

COPY --from=uv /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ${LAMBDA_TASK_ROOT}/
RUN cd ${LAMBDA_TASK_ROOT} \
    && uv export --frozen --no-dev --no-emit-project --no-hashes --extra google --format requirements.txt -o requirements.txt \
    && pip install --no-cache-dir -r requirements.txt \
    && rm -f requirements.txt pyproject.toml uv.lock

COPY src/argumenta ${LAMBDA_TASK_ROOT}/argumenta

CMD ["argumenta.entrypoints.rest_application.handler"]
