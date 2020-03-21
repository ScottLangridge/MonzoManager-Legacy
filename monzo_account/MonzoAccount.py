import json
import random
import string
import requests


# Generates a random string for dedupe_ids and states etc.
def generate_random_string(size=20, chars=string.ascii_lowercase):
    return ''.join(random.choice(chars) for _ in range(size))


# Wrapper class for accessing a Monzo account through the Monzo API.
class MonzoAccount:
    # Constructor. Optional parameter to set token without needing to generate it.
    def __init__(self):
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
            self._get_new_access_token()

        # Fetch account details.
        accounts = self._api_call('get', '/accounts')
        account_list = accounts['accounts']
        if len(account_list) != 1:
            raise AssertionError('MonzoAccount can currently only handle users with one account.')
        self._account_id = account_list[0]['id']
        self._user_id = account_list[0]['owners'][0]['user_id']

    # Performs the actual request that is sent to the Monzo API.
    def _api_call(self, verb, url, data=None):
        http_verbs = {
            'get': requests.get,
            'post': requests.post,
            'put': requests.put,
        }
        request_url = 'https://api.monzo.com' + url

        # Calls to /oauth2/token (e.g. when refreshing a token) do not work if you send an bearer token.
        if url == "/oauth2/token":
            headers = {}
        else:
            token = self._tokens['access_token']
            headers = {'Authorization': f'Bearer {token}'}

        response = http_verbs[verb](request_url, data=data, headers=headers)
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
        response = self._api_call('post', url, data)
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
        response = self._api_call('post', url, data)
        self._tokens['access_token'] = response['access_token']
        self._tokens['refresh_token'] = response['refresh_token']
        if not self._token_is_valid():
            raise AssertionError("Authentication token invalid!")
        else:
            with open(self._tokens_file, 'w') as f:
                f.write(json.dumps(self._tokens, sort_keys=True, indent=2, separators=(',', ': ')))

    # Calls the balance endpoint of the Monzo API.
    def _balance(self):
        url = f'/balance?account_id={self._account_id}'
        return self._api_call('get', url)

    # Gets pot_id of a pot given it's name.
    def _get_pot_id_by_name(self, name):
        url = '/pots'
        response = self._api_call('get', url)
        pot_list = response['pots']
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
        if type(pot) != string:
            raise TypeError('Pot argument must be a string.')

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
        self._api_call('put', url, data)

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
        self._api_call('put', url, data)

    # Calls withdraw_from_pot or deposit_to_pot as appropriate based on the amount.
    # Withdraws if amount is -ve, deposits if amount is +ve.
    def pot_transfer(self, pot, amount):
        if amount > 0:
            self.withdraw_from_pot(amount, pot)
        elif amount < 0:
            self.deposit_to_pot(abs(amount), pot)
        else:
            return

    # Creates a new feed item in the user's app.
    def notify(self, title, body=None, bg_colour=None, title_colour=None, body_colour=None, image=None, link_url=None):
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

        self._api_call('post', url, data)
