import time

from monzo_account.MonzoAccount import MonzoAccount
import webhook_listener
import json


class TransactionListener:
    webhook_file = 'transaction_listener/data_dir/webhook.json'

    def __init__(self):
        self.account = MonzoAccount()

        self.url = None
        self.port = None
        self.host = None
        self.load_webhook_definition()

        self.init_webhooks()

        listener = webhook_listener.Listener(host=self.host, port=self.port, handlers={'POST': self.receive_post})
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
        body_raw = request.body.read(int(request.headers['Content-Length'])) if int(
            request.headers.get('Content-Length', 0)) > 0 else '{}'
        body = json.loads(body_raw.decode('utf-8'))

        if body['type'] != 'transaction.created':
            raise ValueError(f'Unexpected request received: {body}.')

        transaction_id = body['data']['id']
        # TODO: Handle transaction
