import logging
import urllib
import os
import requests
import shutil


class Utils:

    def __init__(self):
        pass

    @staticmethod
    def create_result_s3_key(path_to_s3: str, inference_type: str, inference_id: str, image_id: str,
                             filename: str) -> str:
        s3_path = os.path.join(path_to_s3, inference_type, inference_id, image_id, filename)
        logging.info(f'Created s3 path:{s3_path}')
        return s3_path

    @staticmethod
    def download_from_http(url: str, absolute_file_path=None) -> str:
        if not url.endswith('.json'):
            return Utils.download_from_http_and_save(url, absolute_file_path)
        logging.info(f'Document url:{url} will be downloaded')
        opener = urllib.request.build_opener()
        opener.addheaders = [('User-Agent',
                              'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/36.0.1941.0 Safari/537.36')]
        urllib.request.install_opener(opener)
        with urllib.request.urlopen(url) as f:
            document = f.read().decode('utf-8')
            if absolute_file_path:
                with open(absolute_file_path, 'w') as document_file:
                    document_file.write(document)
                    document_file.close()
        return document

    @staticmethod
    def download_from_http_and_save(url, absolute_file_path):
        logging.info(f'Document url:{url} will be downloaded')

        r = requests.get(url, stream=True)
        if r.status_code == 200:
            r.raw.decode_content = True
            with open(absolute_file_path, 'wb') as f:
                shutil.copyfileobj(r.raw, f)
            logging.info(f'Image sucessfully Downloaded:{absolute_file_path}')
        else:
            logging.info('Image Couldn\'t be retreived')
            raise
