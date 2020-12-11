import hashlib
import json
import logging
import os
import shutil
import subprocess
import time
import uuid

import boto3

from sqs_workflow.AlertService import AlertService
from sqs_workflow.aws.s3.S3Helper import S3Helper
from sqs_workflow.utils.ProcessingTypesEnum import ProcessingTypesEnum
from sqs_workflow.utils.StringConstants import StringConstants
from sqs_workflow.utils.Utils import Utils
from sqs_workflow.utils.similarity.SimilarityProcessor import SimilarityProcessor


class SqsProcessor:
    alert_service = AlertService()
    s3_helper = S3Helper()

    input_processing_directory = os.environ['INPUT_DIRECTORY']
    output_processing_directory = os.environ['OUTPUT_DIRECTORY']

    def __init__(self, queue_name):

        if "immo" in queue_name:
            logging.info(f'Activate immoviewer session')

            self.session = boto3.session.Session(profile_name=os.environ['IMMO_AWS_PROFILE'],
                                                 region_name=os.environ['IMMO_REGION_NAME'])
        else:
            logging.info(f'Activate docuscetch session')
            self.session = boto3.session.Session(profile_name=os.environ['DOCU_AWS_PROFILE'],
                                                 region_name=os.environ['DOCU_REGION_NAME'])
        self.sqs_client = self.session.client('sqs')
        self.sqs_resource = self.session.resource('sqs')

        get_url_response = self.sqs_client.get_queue_url(QueueName=os.environ['APP_BRANCH'] + queue_name)
        queue_url = get_url_response['QueueUrl']
        self.queue_url = queue_url
        self.return_queue_url = queue_url + "-return-queue"
        logging.info(f'Pulled queues{queue_url}')
        self.queue = self.sqs_resource.Queue(self.queue_url)
        self.return_queue = self.sqs_resource.Queue(self.return_queue_url)

        self.similarity_executable = os.environ[f'{ProcessingTypesEnum.Similarity.value}_EXECUTABLE']
        self.similarity_script = os.environ[f'{ProcessingTypesEnum.Similarity.value}_SCRIPT']
        self.roombox_executable = os.environ[f'{ProcessingTypesEnum.RoomBox.value}_EXECUTABLE']
        self.roombox_script = os.environ[f'{ProcessingTypesEnum.RoomBox.value}_SCRIPT']
        self.rmatrix_executable = os.environ[f'{ProcessingTypesEnum.RMatrix.value}_EXECUTABLE']
        self.rmatrix_script = os.environ[f'{ProcessingTypesEnum.RMatrix.value}_SCRIPT']
        self.doordetecting_executable = os.environ[f'{ProcessingTypesEnum.DoorDetecting.value}_EXECUTABLE']
        self.doordetecting_script = os.environ[f'{ProcessingTypesEnum.DoorDetecting.value}_SCRIPT']
        self.rotate_executable = os.environ[f'{ProcessingTypesEnum.Rotate.value}_EXECUTABLE']
        self.rotate_script = os.environ[f'{ProcessingTypesEnum.Rotate.value}_SCRIPT']
        logging.info(f'SQS processor initialized for profile:{queue_name}')

    def get_attr_value(self, message, attribute_name):
        attr_value = json.loads(message.body)[attribute_name]
        return attr_value

    def send_message_to_queue(self, message_body: str, queue_url: str):
        response_send = self.sqs_client.send_message(QueueUrl=queue_url, MessageBody=message_body)
        logging.info(f'Sent message: {message_body} to queue: {queue_url}')
        return response_send

    def receive_messages_from_queue(self, max_number_of_messages: int, queue_url):
        response_messages = self.queue.receive_messages(QueueUrl=queue_url,
                                                        MaxNumberOfMessages=max_number_of_messages)
        if len(response_messages) != 0:
            logging.info(f'response_message content:{response_messages[0].body}')
        return response_messages

    def pull_messages(self, number_of_messages: int) -> list:
        attempts = 0
        list_of_messages = self.receive_messages_from_queue(number_of_messages, self.queue_url)
        while attempts < 7 and len(list_of_messages) < number_of_messages:
            messages_received = self.receive_messages_from_queue(1, self.queue_url)
            if len(messages_received) > 0:
                list_of_messages += messages_received
                logging.info(f'Len list of messages:{len(list_of_messages)}')
            else:
                attempts += 1
                time.sleep(1)
            logging.info(f'attempts:{attempts} left')
        if attempts == 7:
            logging.info(f'Out of attempts')
        logging.info(f"Pulled {len(list_of_messages)} from a queue:{self.queue_url}")
        return list_of_messages

    def complete_processing_message(self, message, message_body: str):
        logging.info(f'Start completing processing message:{message}')
        self.send_message_to_queue(message_body, self.return_queue_url)
        message.delete()
        logging.info(f'Message:{message} is deleted')

    def create_path_and_save_on_s3(self, message_type: str,
                                   inference_id: str,
                                   processing_result: str,
                                   image_id: str,
                                   image_full_url='document',
                                   is_public=False) -> str:

        s3_path = Utils.create_result_s3_key(StringConstants.COMMON_PREFIX,
                                             message_type,
                                             inference_id,
                                             image_id,
                                             StringConstants.RESULT_FILE_NAME)

        s3_url = self.s3_helper.save_string_object_on_s3(s3_path,
                                                         processing_result,
                                                         image_full_url,
                                                         is_public)
        logging.info(f'Created S3 object key:{s3_path} url:{s3_url} content:{processing_result}')
        return s3_url

    def create_output_file_on_s3(self, message_type: str,
                                 image_hash: str,
                                 image_id: str,
                                 image_absolute_path: str):
        logging.info(f'Start creating output for rotation file:{image_absolute_path}')
        s3_path = Utils.create_result_s3_key(StringConstants.COMMON_PREFIX,
                                             message_type,
                                             image_hash,
                                             "",
                                             image_id)

        self.s3_helper.save_file_object_on_s3(s3_path, image_absolute_path)
        logging.info(f'Created S3 object key:{s3_path} file:{image_absolute_path}')

    def process_message_in_subprocess(self, message_body: str) -> str:
        processing_result = None
        message_object = json.loads(message_body)
        inference_id = str(message_object[StringConstants.INFERENCE_ID_KEY])
        message_type = str(message_object[StringConstants.MESSAGE_TYPE_KEY])
        logging.info(f'Message type of message:{message_type} inference:{inference_id}')
        assert inference_id

        if message_type == ProcessingTypesEnum.Preprocessing.value:
            logging.info(f'Start preprocessing similarity inference:{inference_id}')
            messages_for_sending = SimilarityProcessor.start_pre_processing(message_object)
            for send_message in messages_for_sending:
                self.send_message_to_queue(send_message, self.queue_url)

            message_object['returnData'] = {'preprocessing': 'ok'}
            logging.info(f"Finished processing and updated message:{message_object}.")
            return json.dumps(message_object)

        if message_type == ProcessingTypesEnum.Similarity.value:
            logging.info(f'Start processing similarity inference:{inference_id}')
            document_object = SimilarityProcessor.is_similarity_ready(
                self.s3_helper,
                message_object)
            if document_object is not None:
                processing_result = self.run_process(self.similarity_executable,
                                                     self.similarity_script,
                                                     message_object[StringConstants.EXECUTABLE_PARAMS_KEY])
                s3_url = self.create_path_and_save_on_s3(message_type,
                                                         inference_id,
                                                         processing_result,
                                                         "similarity",
                                                         is_public=True)
                message_object[StringConstants.DOCUMENT_PATH_KEY] = s3_url
                logging.info(f'Finished similarity inference:{inference_id} s3 result:{s3_url}')
                return json.dumps(message_object)
            else:
                logging.info(f'Document is under processing inference:{inference_id}')
                return None

        image_id = os.path.basename(message_object[StringConstants.FILE_URL_KEY])
        image_full_url = message_object[StringConstants.FILE_URL_KEY]
        url_hash = hashlib.md5(image_full_url.encode('utf-8')).hexdigest()

        r_matrix_result = self.check_pry_on_s3(ProcessingTypesEnum.RMatrix.value, url_hash, image_id)

        if message_type == ProcessingTypesEnum.RMatrix.value and not r_matrix_result:
            logging.info(f'No r_matrix for file:{url_hash} image:{image_id} on s3 run r_matrix')
            processing_result = self.run_process(self.rmatrix_executable,
                                                 self.rmatrix_script,
                                                 message_object[StringConstants.EXECUTABLE_PARAMS_KEY])
            self.create_path_and_save_on_s3(ProcessingTypesEnum.RMatrix.value,
                                            url_hash,
                                            processing_result,
                                            image_id,
                                            image_full_url)
            r_matrix_result = processing_result
            logging.info(f'R_matrix:{r_matrix_result}')
        else:
            logging.info(f'R_matrix:{r_matrix_result} is taken from s3. Define as processing result.')
            processing_result = r_matrix_result

        rotated_s3_result = Utils.create_result_s3_key(StringConstants.COMMON_PREFIX,
                                                       ProcessingTypesEnum.Rotate.value,
                                                       url_hash,
                                                       "",
                                                       image_id)
        rotated_result = self.s3_helper.is_object_exist(rotated_s3_result)
        logging.info(f'Rotated image is {rotated_result} on s3')

        if message_type == ProcessingTypesEnum.Rotate.value or not rotated_result:
            logging.info('Start processing rotating')
            assert r_matrix_result
            processing_result = self.run_process(self.rotate_executable,
                                                 self.rotate_script,
                                                 message_object[
                                                     StringConstants.EXECUTABLE_PARAMS_KEY] + f" --r_matrix {r_matrix_result}")
            logging.info(f'Result rotating:{processing_result}')
            self.create_output_file_on_s3(ProcessingTypesEnum.Rotate.value,
                                          url_hash,
                                          image_id,
                                          str(processing_result))
            processing_result = {'output': f'{processing_result}'}
            logging.info(f'Saved rotated image:{processing_result} on s3')
            os.replace(os.path.join(self.output_processing_directory,
                                    url_hash,
                                    image_id),
                       os.path.join(self.input_processing_directory,
                                    url_hash,
                                    image_id))
            logging.info(f'Moved rotated file to input')
            processing_result = []
        else:
            logging.info(f'Download from s3 key:{rotated_s3_result}')
            self.s3_helper.download_file_object_from_s3(
                rotated_s3_result,
                os.path.join(self.input_processing_directory,
                             url_hash,
                             image_id))

        if message_type == ProcessingTypesEnum.RoomBox.value:
            logging.info('Start processing room box')
            processing_result = self.run_process(self.roombox_executable,
                                                 self.roombox_script,
                                                 message_object[StringConstants.EXECUTABLE_PARAMS_KEY])
            logging.info(f'Executed roombox:{processing_result}')
            processing_result = SimilarityProcessor.create_layout_object(ProcessingTypesEnum.RoomBox.value,
                                                                         processing_result)
            logging.info(f'Executed roombox:{processing_result}')
            self.create_path_and_save_on_s3(message_type,
                                            inference_id,
                                            processing_result,
                                            image_id,
                                            image_full_url)
            logging.info(f'Saved roombox:{processing_result} on s3')

        elif message_type == ProcessingTypesEnum.DoorDetecting.value:
            logging.info('Start processing door detecting')
            processing_result = self.run_process(self.doordetecting_executable,
                                                 self.doordetecting_script,
                                                 message_object[StringConstants.EXECUTABLE_PARAMS_KEY])
            self.create_path_and_save_on_s3(message_type,
                                            inference_id,
                                            processing_result,
                                            image_id,
                                            image_full_url)
            logging.info(f'Saved door detecting:{processing_result} on s3')

        message_object['returnData'] = json.loads(processing_result or "[]")
        del message_object[StringConstants.EXECUTABLE_PARAMS_KEY]
        logging.info(f"Finished processing and updated message:{message_object} save result on s3.")
        return json.dumps(message_object)

    def run_process(self, executable: str, script: str, executable_params: str) -> str:
        logging.info(f'Start processing executable:{executable} script:{script} params:{executable_params}')
        subprocess_result = subprocess.run(executable + " " + script + " " + executable_params,
                                           shell=True,
                                           check=True,
                                           stdout=subprocess.PIPE)
        if not subprocess_result.returncode == 0:
            message = f'Process has failed for process:{executable} script:{script} message:{executable_params}.'
            self.alert_service.send_slack_message(message, 0)
        logging.info(f'subprocess code: {subprocess_result.returncode} output: {subprocess_result.stdout}')
        output = subprocess_result.stdout.decode("utf-8").rstrip()
        logging.info(f"Output:{output}")
        return output

    # todo test
    def check_pry_on_s3(self, message_type: str, url_hash: str, image_id: str) -> str:
        pry_s3_key = Utils.create_result_s3_key(StringConstants.COMMON_PREFIX,
                                                message_type,
                                                url_hash,
                                                image_id,
                                                StringConstants.RESULT_FILE_NAME)

        logging.info(f'Checking pry on s3 for key:{pry_s3_key}')
        is_key_exist = self.s3_helper.is_object_exist(pry_s3_key)

        if is_key_exist:
            logging.info(f' Key:{pry_s3_key} exists getting body')
            s3 = boto3.resource('s3')
            result_object = s3.Object(self.s3_helper.s3_bucket, pry_s3_key)
            body = result_object.get()['Body'].read().decode('utf-8')
            logging.info(f' S3 key:{pry_s3_key} content:{body}')
            return body
        else:
            logging.info(f'result.json in {pry_s3_key} does not exist')
            return None  # return None when -> str ?

    def prepare_for_processing(self, message_body: str) -> str:

        logging.info(f"Start preprocessing for message:{message_body}")
        message_object = json.loads(message_body)

        if StringConstants.DOCUMENT_PATH_KEY in message_object:
            message_object[StringConstants.FILE_URL_KEY] = message_object[StringConstants.DOCUMENT_PATH_KEY]
            logging.info(f"Document:{message_body}")

        if StringConstants.IMAGE_PATH_KEY in message_object:
            message_object[StringConstants.FILE_URL_KEY] = message_object[StringConstants.IMAGE_PATH_KEY]
            logging.info(f"Image:{message_body}")

        if StringConstants.PANO_URL_KEY in message_object:
            message_object[StringConstants.FILE_URL_KEY] = message_object[StringConstants.PANO_URL_KEY]
            logging.info(f"Pano:{message_body}")

        if StringConstants.STEPS_DOCUMENT_PATH_KEY in message_object:
            message_object[StringConstants.FILE_URL_KEY] = message_object[StringConstants.STEPS_DOCUMENT_PATH_KEY]
            logging.info(f'Similarity does not have a document yet. Use steps document.')

        url_file_name = message_object[StringConstants.FILE_URL_KEY]
        file_name = os.path.basename(url_file_name)
        url_hash = hashlib.md5(url_file_name.encode('utf-8')).hexdigest()
        logging.info(f"Download url:{url_file_name} file:{file_name} hash:{url_hash}")
        input_path = os.path.join(self.input_processing_directory, url_hash)
        output_path = os.path.join(self.output_processing_directory, url_hash)

        try:
            shutil.rmtree(input_path, ignore_errors=True)
            shutil.rmtree(output_path, ignore_errors=True)
            os.makedirs(input_path)
            os.makedirs(output_path)
            logging.info(f'Created directories input:{input_path}, output:{output_path}')
        except OSError:
            logging.error(f"Creation of the directory input:{input_path} or output:{output_path}  failed")
            raise
        logging.info(f'Input:{input_path}, output:{output_path}, file:{file_name}, hash:{url_hash}')

        assert os.path.exists(input_path) and os.path.exists(output_path)

        Utils.download_from_http(url_file_name, os.path.join(input_path, file_name))

        if StringConstants.INFERENCE_ID_KEY not in message_object:
            message_object[StringConstants.INFERENCE_ID_KEY] = str(uuid.uuid4())
            logging.info(f'Create inference-id:{message_object[StringConstants.INFERENCE_ID_KEY]}')

        message_object[
            StringConstants.EXECUTABLE_PARAMS_KEY] = f' --input_path {os.path.join(input_path, file_name)} --output_path {output_path}'
        logging.info(f"Downloaded and prepared executables:{message_object[StringConstants.EXECUTABLE_PARAMS_KEY]}")
        return json.dumps(message_object)
