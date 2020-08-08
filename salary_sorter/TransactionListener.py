import logging
import time

from monzo_account.MonzoAccount import MonzoAccount
import webhook_listener
import json

from salary_sorter.SalarySorter import SalarySorter
from salary_sorter.TransactionClassifier import _TransactionClassifier


class TransactionListener:
    webhook_file = 'salary_sorter/data_dir/webhook.json'

    def __init__(self):
        self._log = logging.getLogger("TransactionListener")

        self.account = MonzoAccount()
        self.classifier = _TransactionClassifier()
        self.sorter = SalarySorter()

        self.url = None
        self.port = None
        self.host = None
        self.load_webhook_definition()

        self._log.info("Initialising Webhooks")
        self.init_webhooks()

        self._log.info("Initialising Listener")
        listener = webhook_listener.Listener(host=self.host, port=self.port, handlers={'POST': self.receive_post})

        self._log.info("Starting Listener")
        listener.start()

    def load_webhook_definition(self, file=webhook_file):
        with open(file, 'r') as f:
            raw_json = json.loads(f.read())
        self.url = raw_json['url']
        self.port = int(raw_json['listener_port'])
        self.host = raw_json['listener_host']

    def init_webhooks(self):
        if not self.account.webhook_exists(self.url):
            self.account.register_webhook(self.url)
        assert self.account.webhook_exists(self.url)

    def receive_post(self, request, *args, **kwargs):
        self._log.info("POST Received")
        body_raw = request.body.read(int(request.headers['Content-Length'])) if int(
            request.headers.get('Content-Length', 0)) > 0 else '{}'
        body = json.loads(body_raw.decode('utf-8'))

        if body['type'] != 'transaction.created':
            raise ValueError(f'Unexpected request received: {body}.')
        self.handle_post(body)

    def handle_post(self, body):
        transaction_id = body['data']['id']
        transaction = self.account.retrieve_transaction(transaction_id)
        transaction_classes = self.classifier.classify_transaction(transaction)
        if 'salary' in transaction_classes:
            self._log.info('Salary Transaction Detected')
            self.sorter.sort(transaction_id)
