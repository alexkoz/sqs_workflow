import logging
import urllib


class Utils:

    def __init__(self):
        pass

    @staticmethod
    def download_from_http(url) -> str:
        logging.info(f'Document url:{url} will be downloaded')
        opener = urllib.request.build_opener()
        opener.addheaders = [('User-Agent',
                              'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/36.0.1941.0 Safari/537.36')]
        urllib.request.install_opener(opener)
        with urllib.request.urlopen(url) as f:
            document = f.read().decode('utf-8')
        return document
