import os
import boto3

BUCKET = "amzn-deep-research"
ALLOWED_ORIGIN = "https://agentic-deep-research-omega.vercel.app"
AWS_REGION = "us-east-1"

s3 = boto3.client("s3", region_name=AWS_REGION)

cors_config = {
  "CORSRules": [
    {
      "AllowedOrigins": [ALLOWED_ORIGIN],
      "AllowedMethods": ["GET", "POST", "PUT", "HEAD"],
      "AllowedHeaders": ["*"],
      "ExposeHeaders": ["ETag"],
      "MaxAgeSeconds": 3000
    }
  ]
}

s3.put_bucket_cors(Bucket=BUCKET, CORSConfiguration=cors_config)
print("CORS applied to", BUCKET)