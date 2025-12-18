from __future__ import annotations
import os
from dotenv import load_dotenv
from urllib.parse import urlparse
import boto3
from botocore.config import Config

__all__ = ["load_s3_config","build_rasterio_s3_opts","to_vsis3_paths"]

def load_s3_config():
    """
    Load and validate S3 / CloudFerro configuration from environment variables.
    Returns a dict with validated values.
    """
    load_dotenv()  # default path

    config = {
        "AWS_ACCESS_KEY_ID": os.getenv("AWS_ACCESS_KEY_ID"),
        "AWS_SECRET_ACCESS_KEY": os.getenv("AWS_SECRET_ACCESS_KEY"),
        "AWS_SESSION_TOKEN": os.getenv("AWS_SESSION_TOKEN"),  # optional
        "S3_BUCKET": os.getenv("S3_BUCKET"),
        "ENDPOINT_URL": os.getenv("ENDPOINT_URL"),
    }

    required = [
        config["AWS_ACCESS_KEY_ID"],
        config["AWS_SECRET_ACCESS_KEY"],
        config["S3_BUCKET"],
        config["ENDPOINT_URL"],
    ]

    if not all(required):
        raise RuntimeError(
            "Missing required environment variables. "
            "Check AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, "
            "S3_BUCKET, ENDPOINT_URL."
        )

    return config


def build_rasterio_s3_opts(cfg: dict) -> dict:
    return boto3.client(
        "s3",
        endpoint_url=cfg["ENDPOINT_URL"],          # your S3-compatible endpoint
        aws_access_key_id=cfg["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=cfg["AWS_SECRET_ACCESS_KEY"],
        aws_session_token=cfg.get("AWS_SESSION_TOKEN"),
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def to_vsis3_paths(s3, bucket, key, expires=3600):
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires,
    )
