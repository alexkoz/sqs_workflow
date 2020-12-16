import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from unittest import TestCase

from sqs_workflow.aws.sqs.SqsProcessor import SqsProcessor
from sqs_workflow.tests.S3HelperMock import S3HelperMock
from sqs_workflow.tests.test_sqsProcessor import TestSqsProcessor
from sqs_workflow.utils.ProcessingTypesEnum import ProcessingTypesEnum
from sqs_workflow.utils.StringConstants import StringConstants
from sqs_workflow.utils.Utils import Utils
from sqs_workflow.utils.similarity.SimilarityProcessor import SimilarityProcessor

logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)


class TestSimilarityProcessor(TestCase):
    similarity_processor = SimilarityProcessor()

    common_path = os.path.join(str(Path.home()),
                               'projects',
                               'python',
                               'misc',
                               'sqs_workflow',
                               'sqs_workflow')

    def setUp(self):
        os.environ['INPUT_DIRECTORY'] = os.path.join(self.common_path, 'tmp', 'input')
        os.environ['OUTPUT_DIRECTORY'] = os.path.join(self.common_path, 'tmp', 'output')
        os.environ['S3_BUCKET'] = "test_bucket"
        os.environ['IMMO_ACCESS'] = "clipnow"
        os.environ['IMMO_SECRET'] = "clipnow"
        os.environ['IMMO_REGION_NAME'] = 'eu-west-1'
        os.environ['IMMO_AWS_PROFILE'] = 'clipnow'
        os.environ['DOCU_AWS_PROFILE'] = 'sqs'
        os.environ['DOCU_ACCESS'] = 'sqs'
        os.environ['DOCU_SECRET'] = 'sqs'
        os.environ['S3_REGION'] = 'sqs'
        aids = os.path.join(self.common_path, 'aids')
        os.environ[f'{ProcessingTypesEnum.Similarity.value}_EXECUTABLE'] = sys.executable
        os.environ[f'{ProcessingTypesEnum.Similarity.value}_SCRIPT'] = os.path.join(aids, 'dummy_similarity.py')
        os.environ[f'{ProcessingTypesEnum.RoomBox.value}_EXECUTABLE'] = sys.executable
        os.environ[f'{ProcessingTypesEnum.RoomBox.value}_SCRIPT'] = os.path.join(aids, 'dummy_roombox.py')
        os.environ[f'{ProcessingTypesEnum.RMatrix.value}_EXECUTABLE'] = sys.executable
        os.environ[f'{ProcessingTypesEnum.RMatrix.value}_SCRIPT'] = os.path.join(aids, 'dummy_rmatrix.py')
        os.environ[f'{ProcessingTypesEnum.DoorDetecting.value}_EXECUTABLE'] = sys.executable
        os.environ[f'{ProcessingTypesEnum.DoorDetecting.value}_SCRIPT'] = os.path.join(aids, 'dummy_dd.py')
        os.environ[f'{ProcessingTypesEnum.Rotate.value}_EXECUTABLE'] = sys.executable
        os.environ[f'{ProcessingTypesEnum.Rotate.value}_SCRIPT'] = os.path.join(aids, 'dummy_rmatrix.py')
        Utils.download_from_http = TestSqsProcessor.download_from_http

    def test_create_layout_object(self):
        room_box_result = '{"z0": "0", "z1": "0", "uv": [[0.8942103326473919, 0.3353772676236854], [0.5747235927670448, 0.6223832045044406], [0.575059459160671, 0.37344853854460625], [0.8946108521103336, 0.6597705138137632], [0.4391388923396096, 0.3687213328274126], [0.08800329189223322, 0.6700959772611611], [0.08779664823660581, 0.3244858638081926], [0.4389803229974563, 0.6268292928215364]]}'
        layout_object = self.similarity_processor.create_layout_object(ProcessingTypesEnum.RoomBox.value,
                                                                       room_box_result)
        layout_object = json.loads(layout_object)
        list_of_corners = layout_object['layout']
        self.assertTrue(list_of_corners[0]['x'] == 141.9157197530611)

        self.assertTrue(list_of_corners[0]['y'] == -29.632091827736627)
        self.assertTrue(list_of_corners[0]['type'] == 'corner')

    def test_create_empty_layout_object(self):
        room_box_result = '{"z0": "0", "z1": "0", "uv": []}'
        layout_object = self.similarity_processor.create_layout_object(ProcessingTypesEnum.RoomBox.value,
                                                                       room_box_result)
        layout_object = json.loads(layout_object)
        list_of_corners = layout_object['layout']
        self.assertTrue(list_of_corners == [])

    def test_assemble_results_into_document(self):
        s3_helper_mock = S3HelperMock([])
        message_object = {
            StringConstants.FLOOR_ID_KEY: 1,
            "fpUrl": "https://docusketch-production-resources.s3.amazonaws.com/items/76fu441i6j/5f0f90925e8a061aff256c76/Tour/map-images/1-floor-5i2cvu550f.jpg",
            StringConstants.PANOS_KEY: [
                {"createdDate": "16.07.2020 02:26:13",
                 "fileUrl": "http://domen.com/img1.JPG"},
                {"createdDate": "18.07.2020 02:43:15",
                 "fileUrl": "http://domen.com/img2.JPG"},
                {"createdDate": "18.07.2020 02:43:15",
                 "fileUrl": "http://domen.com/empty.JPG"}
            ]
        }
        list_result = [
            os.path.join('api', 'inference', ProcessingTypesEnum.RoomBox.value, '1111', 'img1.JPG', 'result.json'),
            os.path.join('api', 'inference', ProcessingTypesEnum.RoomBox.value, '1111', 'img2.JPG', 'result.json'),
            os.path.join('api', 'inference', ProcessingTypesEnum.RoomBox.value, '1111', 'empty.JPG', 'result.json'),
            os.path.join('api', 'inference', ProcessingTypesEnum.DoorDetecting.value, '1111', 'img1.JPG',
                         'result.json'),
            os.path.join('api', 'inference', ProcessingTypesEnum.DoorDetecting.value, '1111', 'img2.JPG',
                         'result.json'),
            os.path.join('api', 'inference', ProcessingTypesEnum.DoorDetecting.value, '1111', 'empty.JPG',
                         'result.json')]

        new_message_object = SimilarityProcessor.assemble_results_into_document(s3_helper_mock, message_object,
                                                                                list_result)
        self.assertEqual(new_message_object['panos'][0]['fileUrl'], "http://domen.com/img1.JPG")
        self.assertEqual(new_message_object['panos'][1]['layout'][0]['type'], 'corner')
        self.assertEqual(new_message_object['panos'][1]['layout'][8]['id'], 'door_108')

    def test_start_pre_processing(self):

        SqsProcessor.define_sqs_queue_properties = TestSqsProcessor.define_sqs_queue_properties
        sqs_processor = SqsProcessor('-immoviewer-ai')

        preprocessing_message = {
            StringConstants.MESSAGE_TYPE_KEY: ProcessingTypesEnum.Preprocessing.value,
            StringConstants.ORDER_ID_KEY: "5da5d5164cedfd0050363a2e",
            StringConstants.INFERENCE_ID_KEY: 1111,
            StringConstants.FLOOR_ID_KEY: 1,
            StringConstants.TOUR_ID_KEY: "1342386",
            StringConstants.DOCUMENT_PATH_KEY: f"{self.common_path}/test_assets/two_panos.json",
            StringConstants.STEPS_KEY: [ProcessingTypesEnum.RoomBox.value, ProcessingTypesEnum.DoorDetecting.value]
        }
        json_message_object = sqs_processor.prepare_for_processing(json.dumps(preprocessing_message))
        similarity_message = json.loads(json_message_object)
        file_path = similarity_message[StringConstants.EXECUTABLE_PARAMS_KEY].replace('--input_path', '') \
            .split()[0].strip()

        with open(file_path) as f:
            json_message_object = json.load(f)

        list_json_messages = self.similarity_processor.start_pre_processing(similarity_message)
        self.assertTrue(
            len(list_json_messages) == (len(preprocessing_message[StringConstants.STEPS_KEY]) * len(
                json_message_object[StringConstants.PANOS_KEY]) + 1))
        for json_message in list_json_messages:
            message_object = json.loads(json_message)
            if message_object[StringConstants.MESSAGE_TYPE_KEY] == ProcessingTypesEnum.Similarity.value:
                self.assertTrue(len(message_object[StringConstants.STEPS_KEY]) == 2)
                self.assertTrue(StringConstants.DOCUMENT_PATH_KEY not in message_object)
            else:
                self.assertTrue(
                    message_object[StringConstants.MESSAGE_TYPE_KEY] == ProcessingTypesEnum.DoorDetecting.value
                    or message_object[StringConstants.MESSAGE_TYPE_KEY] == ProcessingTypesEnum.RoomBox.value)

    def test_is_similarity_ready(self):

        Utils.download_from_http = TestSqsProcessor.download_from_http
        similarity_message_w_document_path = {
            StringConstants.MESSAGE_TYPE_KEY: ProcessingTypesEnum.Similarity.value,
            StringConstants.DOCUMENT_PATH_KEY: f"{self.common_path}/test_assets/fccc6d02b113260b57db5569e8f9c897/order_1012550_floor_1.json.json",
            StringConstants.TOUR_ID_KEY: "5fa1df49014bf357cf250d52",
            StringConstants.PANO_ID_KEY: "5fa1df55014bf357cf250d64"
        }

        res = self.similarity_processor.is_similarity_ready(S3HelperMock([]), similarity_message_w_document_path)
        self.assertTrue(len(res[StringConstants.PANOS_KEY]) == 23)

        hash_document_path = hashlib.md5(
            similarity_message_w_document_path.get(StringConstants.DOCUMENT_PATH_KEY).encode('utf-8')).hexdigest()
        filename = 'filename.json'
        absolute_input_path = os.path.join(os.environ['INPUT_DIRECTORY'], hash_document_path, filename)

        similarity_message_w_steps_document_path = {

            StringConstants.MESSAGE_TYPE_KEY: ProcessingTypesEnum.Similarity.value,
            StringConstants.DOCUMENT_PATH_KEY: f"{self.common_path}/test_assets/with_layout/order_1017707_floor_1.json",
            StringConstants.TOUR_ID_KEY: "5fa1df49014bf357cf250d52",
            StringConstants.INFERENCE_ID_KEY: 100,
            StringConstants.PANO_ID_KEY: "5fa1df55014bf357cf250d64",
            StringConstants.STEPS_KEY: [ProcessingTypesEnum.RoomBox.value, ProcessingTypesEnum.DoorDetecting.value],
            StringConstants.PANOS_KEY: "pano1",
            StringConstants.EXECUTABLE_PARAMS_KEY: f"--input_path {absolute_input_path} --output_path {os.environ['OUTPUT_DIRECTORY']}"
        }

        res2 = self.similarity_processor.is_similarity_ready(S3HelperMock([]), similarity_message_w_steps_document_path)
        self.assertTrue(res2[StringConstants.PANOS_KEY][0]['layout'])
