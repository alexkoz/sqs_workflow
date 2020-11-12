from unittest import TestCase
from sqs_workflow.aws.sqs.SqsProcessor import SqsProcessor
from sqs_workflow.aws.s3.S3Helper import S3Helper
import time
import os
import subprocess
import sys
from pathlib import Path
import logging
from sqs_workflow.utils.StringConstants import StringConstants
import boto3

logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)


class TestSqsProcessor(TestCase):
    processor = SqsProcessor()
    s3_helper = S3Helper()

    def pull_messages(self, processor: SqsProcessor, number_of_messages: int) -> list:
        attemps = 0
        list_of_messages = processor.receive_messages(number_of_messages)
        while attemps < 7 and len(list_of_messages) < number_of_messages:
            messages_received = processor.receive_messages(1)
            if len(messages_received) > 0:
                list_of_messages += messages_received
                print('len list of messages = ', len(list_of_messages))
            else:
                attemps += 1
                time.sleep(1)
            print('attemps =', attemps)
        if attemps == 3:
            logging.info('out of attemps')
        return list_of_messages

    def test_read_write_messages(self):
        processor = SqsProcessor()

        self.purge_queue(self.processor.queue_str)
        req_receive = processor.receive_messages(5)
        self.assertTrue(len(req_receive) == 0)

        for i in range(10):
            processor.send_message(
                '{ \"inferenceId\":\"similarity-test\",  \"messageType\":\"similarity\", \"orderId\":' + str(i) + '}',
                self.processor.queue_str)

        req_receive = self.pull_messages(processor, 3)
        self.assertTrue(len(req_receive) == 3)

        for message in req_receive:
            processor.complete_processing_message(message)
        logging.info(f'len req_receive after delete = ', len(req_receive))

        req_receive = self.pull_messages(processor, 10)
        logging.info(f'len req_receive = ', len(req_receive))

        self.assertTrue(len(req_receive) == 7)
        logging.info('get attr values: ===================')

        for message in req_receive:
            req_get_attr = processor.get_attr_value(message, 'messageType')
            self.assertEqual(req_get_attr, 'similarity')

    def clear_directory(self, path_to_folder_in_bucket: str):
        sync_command = f"aws s3 --profile {os.environ['AWS_PROFILE']} rm s3://{os.environ['S3_BUCKET']}/{path_to_folder_in_bucket} --recursive"
        logging.info(f'sync command: {sync_command}')
        stream = os.popen(sync_command)
        output = stream.read()
        logging.info(f'output: {output}')

    def purge_queue(self, queue_url):
        sqs_client = boto3.client('sqs')
        req_purge = sqs_client.purge_queue(QueueUrl=queue_url)
        logging.info(f'Queue is purged')
        return req_purge

    def pull_all_messages(self, queue_url):
        pulled_message = self.processor.pull_messages(1)
        logging.info('Pulled message')
        return str(pulled_message)
        # message_type = self.processor.get_attr_value(message, 'messageType')

    def test_e2e(self):
        self.clear_directory(StringConstants.COMMON_PREFIX)
        self.clear_directory('api/inference/')
        self.purge_queue(self.processor.queue_str)
        self.purge_queue(self.processor.return_queue_str)

        # checks that queue is empty
        req_receive = self.processor.receive_messages(5)
        self.assertTrue(len(req_receive) == 0)

        for i in range(4):
            similarity_message = '{\"messageType\": \"SIMILARITY\",\
                                   \"inferenceId\": \"'f'345{i}\", \
                                   \"panoUrl\": \"'f'https://img.docusketch.com/items/s967284636/5fa1d{i}f49014bf357cf250d53/Tour/ai-images/s7zu187383.JPG\",\
                                   \"tourId\": \"5fa1df49014bf357cf250d52\",\
                                   \"panoId\": \"5fa1df55014bf357cf250d64\"' + '}'
            self.processor.send_message(similarity_message)
            logging.info('sent similarity message')

        for i in range(0):
            rmatrix_message = '{\"messageType\": \"R_MATRIX\",\
                                               \"inferenceId\": \"'f'123{i}\", \
                                               \"panoUrl\": \"'f'https://img.docusketch.com/items/s96{i}7284636/5fa1df49014bf357cf250d53/Tour/ai-images/s7zu187383.JPG\",\
                                               \"tourId\": \"5fa1df49014bf357cf250d52\",\
                                               \"panoId\": \"5fa1df55014bf357cf250d64\"' + '}'
            self.processor.send_message(rmatrix_message)
            logging.info('sent r_matrix message')

        main_script_path = os.path.join(str(Path.home()), 'projects', 'sqs_workflow', 'sqs_workflow') + '/main.py'
        for i in range(4):
            subprocess.run([sys.executable,  # path to python
                            main_script_path],  # path to main.py
                           universal_newlines=True)

        object_list = self.s3_helper.list_s3_objects(StringConstants.COMMON_PREFIX)
        print('Object list =', object_list)
        print('Len of obj list =', len(object_list))

        self.assertTrue(self.s3_helper.is_processing_complete(StringConstants.COMMON_PREFIX + '/SIMILARITY/', 10))
        self.assertTrue(self.s3_helper.is_processing_complete(StringConstants.COMMON_PREFIX + '/R_MATRIX/', 10))

        # Checks Queue for return messages
        # todo pull all messages from return queue
        # todo check number of return messages
        list_of_returned_messages = []
        for i in range(4):
            list_of_returned_messages.append(self.pull_all_messages(self.processor.return_queue_str))
        self.assertEqual(len(list_of_returned_messages), 4)


