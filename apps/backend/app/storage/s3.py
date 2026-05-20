from __future__ import annotations

import boto3

from app.core.config import settings


class S3Storage:
    def __init__(self) -> None:
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            region_name=settings.s3_region,
        )
        self.bucket = settings.s3_bucket

    def upload_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        if not self.bucket:
            raise RuntimeError("S3_BUCKET не задан")
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
        return key

    def public_url(self, key: str) -> str:
        if settings.s3_endpoint:
            return f"{settings.s3_endpoint.rstrip('/')}/{self.bucket}/{key}"
        return f"https://{self.bucket}.s3.amazonaws.com/{key}"

