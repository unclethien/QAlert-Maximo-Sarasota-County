# The scheduled watsonx.ai missing-information check (scripts/ai_missing_info.py --new --apply).
# Built on the cluster by the BuildConfig in openshift.yaml, from the repository root.
FROM registry.access.redhat.com/ubi9/python-312

RUN pip install --no-cache-dir "requests>=2.32" "python-dotenv>=1.0"

COPY loader/ loader/
COPY scripts/ai_missing_info.py scripts/flag_missing_info.py scripts/pilot_catalog.py scripts/
COPY scripts/autoscript/srqmissinfo.py scripts/autoscript/
COPY data/reference/ data/reference/
COPY data/answer-key.csv data/

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "scripts/ai_missing_info.py"]
CMD ["--new", "--apply", "--limit", "25"]
