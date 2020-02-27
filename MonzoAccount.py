import json
import random
import string

import requests


def generate_state(size=20, chars=string.ascii_lowercase):
    return ''.join(random.choice(chars) for _ in range(size))


class MonzoAccount:
    # Constructor. Optional parameter to set token without needing to generate it.
    def __init__(self, token=''):
        with open('secrets.json') as f:
            self._secrets = json.load(f)

        self._token = token
        if not self._token_is_valid():
            self._get_new_access_token()

        accounts = self._get('https://api.monzo.com/accounts')
        self._account_id = accounts['accounts'][0]['id']
        self._user_id = accounts['accounts'][0]['owners'][0]['user_id']

    # Makes a get request to the Monzo API.
    def _get(self, url):
        headers = {'Authorization': 'Bearer %s' % self._token}
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise ConnectionError("%d - %s" % (response.status_code, response.reason))
        else:
            content = json.loads(response.content)
            return content

    # Makes a post request to the Monzo API.
    def _post(self, url, data):
        headers = {'Authorization': 'Bearer %s' % self._token}
        response = requests.post(url, data, headers=headers)
        if response.status_code != 200:
            raise ConnectionError("%d - %s" % (response.status_code, response.reason))
        else:
            content = json.loads(response.content)
            return content

    # Returns a boolean indicating whether of not the currently stored token is valid.
    def _token_is_valid(self):
        url = 'https://api.monzo.com/ping/whoami'
        try:
            response = self._get(url)
        except ConnectionError as ex:
            if ex.args[0] == '401 - Unauthorized':
                return False
            else:
                raise ConnectionError(ex.args[0])
        return response['authenticated']

    # Guides the user through the process of setting up a new token.
    def _get_new_access_token(self):
        state = generate_state()
        url = ('https://auth.monzo.com/?client_id=%s&redirect_uri=%s&response_type=code&state=%s'
               % (self._secrets['client_id'], 'http://scottlangridge.com/', state))

        print('Navigate to the following address in your browser and verify your account:\n' + url)
        code = input('\nCopy the "code" section of the URL that you are redirected to and paste it here:\n')
        print('\nFetching access token.')

        url = 'https://api.monzo.com/oauth2/token'
        data = {
            'grant_type': 'authorization_code',
            'client_id': self._secrets['client_id'],
            'client_secret': self._secrets['client_secret'],
            'redirect_uri': 'http://scottlangridge.com/',
            'code': code
        }
        response = requests.post(url, data)
        content = json.loads(response.content)
        self._token = content['access_token']
        input('\nApprove access in the Monzo app and then press enter.\n')
        print('Access Token:\n' + self._token)

        if self._token_is_valid():
            print("\nAuthentication Completed\n")
        else:
            print("\nAuthentication Error\n")
            raise AssertionError("Authentication token invalid!")

    # Calls the balance endpoint of the Monzo API.
    def _balance(self):
        url = 'https://api.monzo.com/balance?account_id=%s' % self._account_id
        return self._get(url)

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
        url = 'https://api.monzo.com/pots'
        response = self._get(url)
        pot_list = response['pots']
        for p in pot_list:
            if p['name'] == pot:
                return p['balance']
        raise KeyError('Invalid pot name.')
