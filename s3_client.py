import hashlib
import functools


def catch_exceptions_decorator(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"An error occurred in {func.__name__}: {e}")
            # 你可以在这里进行其他的异常处理或记录日志
            return None  # 如果需要，也可以返回其他值或重新引发异常

    return wrapper


def calculate_md5(file_path):
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


import boto3
import os
from botocore.config import Config


class S3Client:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(S3Client, cls).__new__(cls)
        return cls._instance

    def __init__(self, access_key, secret_key, bucket_name, end_point=None, region='us-east-1'):

        self.access_key = access_key
        self.secret_key = secret_key
        self.end_point = end_point
        self.region = region
        self.bucket_name = bucket_name
        self.s3 = self.init_s3(access_key=access_key, secret_key=secret_key, end_point=end_point, region=region)

    def init_s3(self, access_key=None, secret_key=None, end_point=None, region='us-east-1'):
        return boto3.client(
            's3',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            use_ssl=True,
            region_name=region,
            endpoint_url=end_point,
            config=Config(
                s3={"addressing_style": "path"},  # 对于许多 S3 兼容服务使用 path
                retries={'max_attempts': 10, 'mode': 'standard'}
            )
        )

    def get_file(self, filename):
        s3 = self.s3
        bucket_name = self.bucket_name

        return s3.get_object(
            Bucket=bucket_name,
            Key=filename,
        )

    @catch_exceptions_decorator
    def put_file(self, filename, upfile):
        s3 = self.s3
        bucket_name = self.bucket_name

        try:
            with open(upfile, 'rb') as f:
                return s3.put_object(
                    Bucket=bucket_name,
                    Body=f,
                    Key=filename,
                )
        except Exception as e:
            print(f"Failed to upload {filename}: {str(e)}")
            return None

    def have_bucket(self):
        s3 = self.s3
        bucket_name = self.bucket_name

        buckets = s3.list_buckets()['Buckets']
        for bucket in buckets:
            if bucket_name == bucket['Name']:
                return True
        return False

    def download_file(self, filename, local_filename):
        """Download a file from S3 and save it locally."""
        s3 = self.s3
        bucket_name = self.bucket_name

        response = self.get_file(filename)
        with open(local_filename, 'wb') as f:
            f.write(response['Body'].read())
        print(f"File '{filename}' has been downloaded and saved as '{local_filename}'.")

    def list_files(self):
        """List all files in the specified S3 bucket."""
        s3 = self.s3
        bucket_name = self.bucket_name

        file_items = {}
        response = s3.list_objects_v2(Bucket=bucket_name)
        if 'Contents' in response:
            for obj in response['Contents']:
                file_key = obj['Key']
                file_size = obj['Size']
                file_url = s3.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': bucket_name, 'Key': file_key},
                    ExpiresIn=3600  # 预签名 URL 的有效期，单位为秒
                )
                file_items[file_key] = {'size': file_size, 'url': file_url}
        else:
            print("The bucket is empty or does not exist.")

        return file_items



    @catch_exceptions_decorator
    def upload_folder(self, folder_path):
        """Upload all files in a folder to the specified S3 bucket, preserving the folder structure."""
        bucket_name = self.bucket_name

        target_folder_name = os.path.basename(folder_path)
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                s3_key = os.path.join(target_folder_name, os.path.relpath(file_path, folder_path)).replace("\\",
                                                                                                           "/")  # 转换为正斜杠
                print(f"Uploading {s3_key} - {file_path}")
                self.put_file(s3_key, file_path)

    @catch_exceptions_decorator
    def delete_file(self, filename):
        """
        Delete a file from the specified S3 bucket.

        :param s3: S3 client object
        :param bucket_name: Name of the S3 bucket
        :param filename: Name of the file (key) to delete
        :return: Response from the delete operation
        """
        s3 = self.s3
        bucket_name = self.bucket_name

        try:
            response = s3.delete_object(
                Bucket=bucket_name,
                Key=filename,
            )
            print(f"File '{filename}' has been deleted from bucket '{bucket_name}'.")
            return response
        except Exception as e:
            print(f"Failed to delete {filename}: {str(e)}")
            return None

    @catch_exceptions_decorator
    def delete_folder(self, folder_name):
        """
        Delete all files within a specified folder (directory) in the S3 bucket.

        :param s3: S3 client object
        :param bucket_name: Name of the S3 bucket
        :param folder_name: Name of the folder (directory) to delete
        :return: Response from the delete operation
        """
        s3 = self.s3
        bucket_name = self.bucket_name

        try:
            # Ensure folder name ends with '/'
            if not folder_name.endswith('/'):
                folder_name += '/'

            # List all objects with the folder prefix
            objects_to_delete = s3.list_objects_v2(Bucket=bucket_name, Prefix=folder_name)

            # Check if there are any objects to delete
            if 'Contents' in objects_to_delete:
                delete_keys = [{'Key': obj['Key']} for obj in objects_to_delete['Contents']]

                # Delete the objects
                response = s3.delete_objects(
                    Bucket=bucket_name,
                    Delete={'Objects': delete_keys}
                )

                print(f"Folder '{folder_name}' and its contents have been deleted from bucket '{bucket_name}'.")
                return response
            else:
                print(f"Folder '{folder_name}' does not exist or is already empty.")
                return None

        except Exception as e:
            print(f"Failed to delete folder {folder_name}: {str(e)}")
            return None

    def create_folder(self, folder_name):
        """
        Create a folder (prefix) in the specified S3 bucket.

        :param folder_name: Name of the folder (prefix) to create
        :return: Response from the put_object operation
        """
        s3 = self.s3
        bucket_name = self.bucket_name

        # Ensure folder name ends with '/'
        if not folder_name.endswith('/'):
            folder_name += '/'

        try:
            response = s3.put_object(
                Bucket=bucket_name,
                Key=folder_name,
                Body=b''  # Empty body to create a "folder"
            )
            print(f"Folder '{folder_name}' has been created in bucket '{bucket_name}'.")
            return response
        except Exception as e:
            print(f"Failed to create folder {folder_name}: {str(e)}")
            return None
