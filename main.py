import boto3
from botocore.exceptions import ClientError
import logging
import os

def upload_file_to_s3(file_name, bucket_name, object_name=None):
    """Upload a file to an S3 bucket.

    :param file_name: File to upload (local path).
    :param bucket_name: Name of the S3 bucket.
    :param object_name: S3 object name. If not specified, file_name is used.
    :return: True if file was uploaded, else False.
    """
    if object_name is None:
        object_name = os.path.basename(file_name)

    s3_client = boto3.client('s3')
    try:
        s3_client.upload_file(file_name, bucket_name, object_name)
        logging.info(f"File '{file_name}' uploaded to '{bucket_name}/{object_name}'")
        return True
    except ClientError as e:
        logging.error(e)
        return False

# Example usage:
if __name__ == "__main__":
    # Replace with your actual file path, bucket name, and desired S3 object name
    local_file_path = "./videos/unprocessed-videos/game_30s.mp4"
    my_s3_bucket = "anb-rising-stars-videos-gr14"
    s3_object_key = "unprocessed-videos/game_30s.mp4" 

    # Create a dummy file for testing
    with open(local_file_path, "w") as f:
        f.write("This is a test file.")

    if upload_file_to_s3(local_file_path, my_s3_bucket, s3_object_key):
        print("File uploaded successfully!")
    else:
        print("File upload failed.")

    # Clean up the dummy file
    # os.remove(local_file_path)
