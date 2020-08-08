import json
import random
import string
import requests
import logging


# Generates a random string for dedupe_ids and states etc.
def generate_random_string(size=20, chars=string.ascii_lowercase):
    return ''.join(random.choice(chars) for _ in range(size))


# Wrapper class for accessing a Monzo account through the Monzo API.
class MonzoAccount:
    # Constructor. Optional parameter to set token without needing to generate it.
    def __init__(self):
        # Set up logger
        self._log = logging.getLogger('MonzoAccount')
        self._log.info('New MonzoAccount Initialised')

        # Load secrets and tokens.
        self._secrets_file = 'monzo_account/data_dir/secrets.json'
        self._tokens_file = 'monzo_account/data_dir/tokens.json'
        with open(self._secrets_file) as f:
            self._secrets = json.load(f)
        with open(self._tokens_file) as f:
            self._tokens = json.load(f)

        # Fetch new tokens if needed.
        # Note: Refresh of token will be attempted if expired as part of _token_is_valid().
        if not self._token_is_valid():
            self._log.info("Invalid token detected. Fetching new token.")
            self._get_new_access_token()

        # Fetch account details.
        accounts = self._api_call('get', '/accounts')
        account_list = accounts['accounts']
        if len(account_list) != 1:
            raise AssertionError('MonzoAccount can currently only handle users with one account.')
        self._account_id = account_list[0]['id']
        self._user_id = account_list[0]['owners'][0]['user_id']

    # Performs the actual request that is sent to the Monzo API.
    def _api_call(self, verb, url, params=None, data=None):
        http_verbs = {
            'get': requests.get,
            'post': requests.post,
            'put': requests.put,
            'delete': requests.delete
        }
        request_url = 'https://api.monzo.com' + url

        # Calls to /oauth2/token (e.g. when refreshing a token) do not work if you send an bearer token.
        if url == "/oauth2/token":
            headers = {}
        else:
            token = self._tokens['access_token']
            headers = {'Authorization': f'Bearer {token}'}

        self._log.debug(f'API Call. URL: {request_url} Params: {params} Data:{data}')
        response = http_verbs[verb](request_url, headers=headers, params=params, data=data)
        content = json.loads(response.content)

        if response.status_code == 401 and content['code'] == 'unauthorized.bad_access_token.expired':
            self._refresh_access_token()
            return self._api_call('get', url)
        if response.status_code != 200:
            raise ConnectionError(f'{response.status_code} - {response.reason}')
        return content

    # Returns a boolean indicating whether of not the currently stored token is valid.
    def _token_is_valid(self):
        url = '/ping/whoami'
        try:
            response = self._api_call('get', url)
        except ConnectionError as ex:
            if ex.args[0] == '401 - Unauthorized':
                return False
            else:
                raise ConnectionError(ex.args[0])
        return response['authenticated']

    # Guides the user through the process of setting up a new token.
    def _get_new_access_token(self):
        url = (f'https://auth.monzo.com/?'
               f'client_id={self._secrets["client_id"]}'
               f'&redirect_uri=http://scottlangridge.com/'
               f'&response_type=code&state={generate_random_string()}')

        print('Navigate to the following address in your browser and verify your account:\n' + url)
        code = input('\nCopy the "code" section of the URL that you are redirected to and paste it here:\n')
        print('\nFetching access token.')

        url = '/oauth2/token'
        data = {
            'grant_type': 'authorization_code',
            'client_id': self._secrets['client_id'],
            'client_secret': self._secrets['client_secret'],
            'redirect_uri': 'http://scottlangridge.com/',
            'code': code
        }
        response = self._api_call('post', url, data=data)
        self._tokens['access_token'] = response['access_token']
        self._tokens['refresh_token'] = response['refresh_token']
        input('\nApprove access in the Monzo app and then press enter.\n')

        print('Access Token Acquired.')
        with open(self._tokens_file, 'w') as f:
            f.write(json.dumps(self._tokens, sort_keys=True, indent=2, separators=(',', ': ')))

        if self._token_is_valid():
            print("\nAuthentication Completed.\n")
        else:
            print("\nAuthentication Error.\n")
            raise AssertionError("Authentication token invalid!")

    # Refresh an expired authentication token
    def _refresh_access_token(self):
        url = '/oauth2/token'
        data = {
            'grant_type': 'refresh_token',
            'client_id': self._secrets['client_id'],
            'client_secret': self._secrets['client_secret'],
            'refresh_token': self._tokens['refresh_token']
        }
        response = self._api_call('post', url, data=data)
        self._tokens['access_token'] = response['access_token']
        self._tokens['refresh_token'] = response['refresh_token']
        if not self._token_is_valid():
            raise AssertionError("Authentication token invalid!")
        else:
            with open(self._tokens_file, 'w') as f:
                f.write(json.dumps(self._tokens, sort_keys=True, indent=2, separators=(',', ': ')))

    # Calls the balance endpoint of the Monzo API.
    def _balance(self):
        url = '/balance'
        params = {'account_id': self._account_id}
        return self._api_call('get', url, params)

    # Lists pots
    def _list_pots(self):
        url = '/pots'
        params = {'current_account_id': self._account_id}
        response = self._api_call('get', url, params)
        return response['pots']

    # Gets pot_id of a pot given it's name.
    def _get_pot_id_by_name(self, name):
        pot_list = self._list_pots()
        for p in pot_list:
            if p['name'].lower() == name.lower():
                return p['id']
        raise ValueError(f'No pot with the name "{name}" was found.')

    # Returns the balance in pence in the current account.
    def available_balance(self):
        balance = self._balance()
        return balance['balance']

    # Returns the balance in pence across all pots.
    def total_balance(self):
        balance = self._balance()
        return balance['total_balance']

    # Returns the balance in pence of a given pot.
    def pot_balance(self, pot):
        pot_id = self._get_pot_id_by_name(pot)
        url = '/pots'
        response = self._api_call('get', url)
        pot_list = response['pots']
        for p in pot_list:
            if p['id'] == pot_id:
                return p['balance']
        raise ValueError('Pot could not be found.')

    # Deposits a given amount (in pence) into a given pot from the available balance.
    def deposit_to_pot(self, pot, amount):
        if amount <= 0:
            raise ValueError('Deposits must have an amount greater than zero.')

        pot_id = self._get_pot_id_by_name(pot)
        dedupe_id = generate_random_string()
        url = f'/pots/{pot_id}/deposit'
        data = {
            'source_account_id': self._account_id,
            'amount': amount,
            'dedupe_id': dedupe_id
        }
        self._api_call('put', url, data=data)

    # Withdraw a given amount (in pence) from a pot to the available balance.
    def withdraw_from_pot(self, pot, amount):
        if amount <= 0:
            raise ValueError('Withdraws must have an amount greater than zero.')

        pot_id = self._get_pot_id_by_name(pot)
        dedupe_id = generate_random_string()
        url = f'/pots/{pot_id}/withdraw'
        data = {
            'destination_account_id': self._account_id,
            'amount': amount,
            'dedupe_id': dedupe_id
        }
        self._api_call('put', url, data=data)

    # Calls withdraw_from_pot or deposit_to_pot as appropriate based on the amount.
    # Withdraws if amount is -ve, deposits if amount is +ve.
    def pot_transfer(self, pot, amount):
        if amount > 0:
            self.withdraw_from_pot(pot, amount)
        elif amount < 0:
            self.deposit_to_pot(pot, abs(amount))
        else:
            return

    # Creates a new feed item in the user's app.
    def notify(self, title, body=None, bg_colour=None, title_colour=None, body_colour=None, image=None, link_url=None):
        self._log.info(f'Sending Notification. Title: {title}, Body: {body}')

        if title is None:
            raise ValueError('Notification title cannot be None.')
        if title == '':
            raise ValueError('Notification title cannot be the empty string.')

        url = '/feed'
        if image is None:
            image = 'https://cdn.pixabay.com/photo/2017/10/24/00/39/bot-icon-2883144_960_720.png'
        data = {
            'account_id': self._account_id,
            'type': 'basic',
            'params[title]': title,
            'params[body]': body,
            'params[image_url]': image,
            'params[background_color]': bg_colour,
            'params[body_color]': body_colour,
            'params[title_color]': title_colour,
            'url': link_url
        }

        # Remove empty values from data.
        empties = []
        for i in data:
            if data[i] is None:
                empties.append(i)
        [data.pop(i) for i in empties]

        self._api_call('post', url, data=data)

    # Gets the webhook id from the url.
    def _get_webhook_id(self, webhook_url):
        self._log.info(f'Getting webhook id for {webhook_url}')

        if webhook_url is None or webhook_url == '':
            raise ValueError('Url cannot be None or the empty string.')

        webhooks = self.list_webhooks()
        for webhook in webhooks:
            if webhook['url'] == webhook_url:
                return webhook['id']
        raise ValueError(f'No webhook with the url: {webhook_url} exists.')

    # Returns a list of the webhooks registered on the account
    def list_webhooks(self):
        self._log.info('Fetching active webhooks.')

        url = '/webhooks'
        params = {
            'account_id': self._account_id
        }
        webhooks = self._api_call('get', url, params=params)['webhooks']
        return webhooks

    # Checks if a webhook exists based off of either the url.
    def webhook_exists(self, webhook_url):
        self._log.info(f'Checking for existence of webhook: {webhook_url} by URL.')

        if webhook_url is None or webhook_url == '':
            raise ValueError('URL cannot be None or the empty string.')

        webhooks = self.list_webhooks()
        for webhook in webhooks:
            if webhook['url'] == webhook_url:
                return True
        return False

    # Registers a new webhook
    def register_webhook(self, webhook_url):
        self._log.info(f'Registering webhook: {webhook_url}.')

        if webhook_url is None or webhook_url == '':
            raise ValueError('Webhook URL cannot be None or the empty string.')

        if self.webhook_exists(webhook_url):
            raise ValueError(f'Webhook already exits for URL: {webhook_url}.')

        url = '/webhooks'
        data = {
            'account_id': self._account_id,
            'url': webhook_url
        }
        self._api_call('post', url, data=data)

    # Deletes a webhook
    def delete_webhook(self, webhook_url):
        self._log.info(f'Deleting webhook: {webhook_url}.')

        if not self.webhook_exists(webhook_url):
            raise ValueError(f'Webhook: {webhook_url} does not exist.')

        webhook_id = self._get_webhook_id(webhook_url)
        if webhook_id is None or webhook_id == '':
            raise ValueError('Webhook id cannot be None or the empty string.')

        url = f'/webhooks/{webhook_id}'
        self._api_call('delete', url)

    # Deletes all webhooks
    def clear_webhooks(self):
        self._log.info('Clearing webhooks.')

        webhooks = self.list_webhooks()
        [self.delete_webhook(x['url']) for x in webhooks]

    # Lists all transactions available for an account.
    # (Note: Only the most recent 90 days are available five mins after authentication.
    def list_transactions(self):
        self._log.info('Listing transactions.')

        url = '/transactions'
        params = {'account_id': self._account_id}

        return self._api_call('get', url, params)

    # Fetches information about a transaction
    def retrieve_transaction(self, transaction_id, expand_merchant=False):
        self._log.info(f'Retrieving Transaction: {transaction_id}.')

        if transaction_id is None or transaction_id == '':
            raise ValueError('Transaction ID cannot be None or the empty string.')

        url = f'/transactions/{transaction_id}'

        if expand_merchant:
            params = {'expand[]': 'merchant'}
        else:
            params = []

        raw_json = self._api_call('get', url, params)
        return raw_json['transaction']
