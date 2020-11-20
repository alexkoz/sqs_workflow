import logging
import os
from sqs_workflow.utils.StringConstants import StringConstants

import boto3


class S3Helper:
    s3_bucket = os.environ['S3_BUCKET']
    s3_client = boto3.client(
        's3',
        aws_access_key_id=os.environ['ACCESS'],
        aws_secret_access_key=os.environ['SECRET'],
        region_name=os.environ['REGION_NAME']
    )

    def __init__(self):
        assert self.s3_bucket
        assert self.s3_client
        pass

    def is_object_exist(self, s3_key: str) -> bool:
        logging.info(f'Start checking object: {s3_key}')
        response = self.s3_client.list_objects_v2(Bucket=self.s3_bucket, Prefix=s3_key, Delimiter='/')
        if 'Contents' in response:
            for obj in response['Contents']:
                if obj['Key'] == s3_key + 'result.json':
                    return True
        return False

    def save_object_on_s3(self, s3_key: str, object_body: str, full_url_tag="document"):
        logging.info(f'Start saving object: {s3_key}')

        session = boto3.Session(
            aws_access_key_id=os.environ['ACCESS'],
            aws_secret_access_key=os.environ['SECRET']
        )
        s3 = session.resource('s3')
        obj = s3.Object(self.s3_bucket, s3_key)
        obj.put(Body=object_body,
                Tagging=f'{StringConstants.PANO_URL_KEY}={full_url_tag}')
        logging.info(f'Uploaded new file: {s3_key} to s3')

    def read_s3_object(self, s3_key) -> str:
        obj = self.s3_client.Object(self.s3_bucket, s3_key)
        object_from_s3 = obj.get()['Body'].read().decode('utf-8')
        # todo save object locally
        return object_from_s3

    def list_s3_objects(self, prefix: str):
        paginator = self.s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=self.s3_bucket, Prefix=prefix)
        list_of_objects = []
        logging.info('list of objects: ', list_of_objects)
        for page in pages:
            if 'Contents' in page:
                for obj in page['Contents']:
                    list_of_objects.append(obj['Key'])
                    logging.info(f'Added object {obj["Key"]} to list of objects')
        return list_of_objects

    def count_files_s3(self, s3_key: str) -> list:
        logging.info(f'Start count objects in: {s3_key}')
        response = self.s3_client.list_objects_v2(Bucket=self.s3_bucket, Prefix=s3_key)
        if 'Contents' in response:
            array_of_result_json = []
            for obj in response['Contents']:
                key = obj['Key']
                if key.endswith('result.json'):
                    array_of_result_json.append(key)
            return array_of_result_json

    def is_processing_complete(self, prefix: str, num_of_expected_results: int) -> bool:
        list_of_objects = self.list_s3_objects(prefix)
        logging.info(f'Len of s3_objects_list w/ prefix: {prefix} =', len(list_of_objects))
        return len(list_of_objects) == num_of_expected_results
