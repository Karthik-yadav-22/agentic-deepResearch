import os
import tempfile
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError

AWS_REGION = os.getenv("AWS_REGION")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")


def is_s3_enabled() -> bool:
    return bool(AWS_REGION and S3_BUCKET_NAME)


def _get_s3_client():
    return boto3.client("s3", region_name=AWS_REGION)


def is_s3_path(path: str) -> bool:
    return path.startswith("s3://")


def parse_s3_path(s3_path: str) -> tuple[str, str]:
    parsed = urlparse(s3_path)
    return parsed.netloc, parsed.path.lstrip("/")


def generate_presigned_post(key: str, content_type: str) -> dict:
    client = _get_s3_client()
    return client.generate_presigned_post(
        Bucket=S3_BUCKET_NAME,
        Key=key,
        Fields={},
        Conditions=[
            ["content-length-range", 0, 100 * 1024 * 1024]
        ],
        ExpiresIn=3600,
    )


def generate_presigned_url(s3_path: str, expires_in: int = 3600) -> str:
    bucket, key = parse_s3_path(s3_path)
    client = _get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in,
    )


def download_s3_to_temp(s3_path: str) -> str:
    bucket, key = parse_s3_path(s3_path)
    suffix = os.path.splitext(key)[1] or ".pdf"
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_file.close()

    client = _get_s3_client()
    with open(temp_file.name, "wb") as f:
        client.download_fileobj(bucket, key, f)

    return temp_file.name


def delete_s3_object(s3_path: str) -> None:
    bucket, key = parse_s3_path(s3_path)
    client = _get_s3_client()
    try:
        client.delete_object(Bucket=bucket, Key=key)
    except ClientError:
        pass