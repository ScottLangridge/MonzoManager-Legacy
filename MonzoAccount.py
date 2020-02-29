import json
import random
import string

import requests


def generate_state(size=20, chars=string.ascii_lowercase):
    return ''.join(random.choice(chars) for _ in range(size))


class MonzoAccount:
    # Constructor. Optional parameter to set token without needing to generate it.
    def __init__(self, token='', refresh_token=''):
        with open('secrets.json') as f:
            self._secrets = json.load(f)

        self._token = token
        self._refresh_token = refresh_token
        if not self._token_is_valid():
            self._get_new_access_token()

        accounts = self._get('/accounts')
        self._account_id = accounts['accounts'][0]['id']
        self._user_id = accounts['accounts'][0]['owners'][0]['user_id']

    # Makes a get request to the Monzo API.
    def _get(self, url):
        request_url = 'https://api.monzo.com' + url
        headers = {'Authorization': 'Bearer %s' % self._token}
        response = requests.get(request_url, headers=headers)
        content = json.loads(response.content)

        if response.status_code == 401 and content['code'] == 'unauthorized.bad_access_token.expired':
            self._refresh_access_token()
            return self._get(url)
        if response.status_code != 200:
            raise ConnectionError("%d - %s" % (response.status_code, response.reason))
        return content

    # Makes a post request to the Monzo API.
    def _post(self, url, data):
        request_url = 'https://api.monzo.com' + url
        headers = {'Authorization': 'Bearer %s' % self._token}
        response = requests.post(request_url, data, headers=headers)
        content = json.loads(response.content)

        if response.status_code == 401 and content['code'] == 'unauthorized.bad_access_token.expired':
            self._refresh_access_token()
            return self._post(url, data)
        if response.status_code != 200:
            raise ConnectionError("%d - %s" % (response.status_code, response.reason))
        return content

    # Returns a boolean indicating whether of not the currently stored token is valid.
    def _token_is_valid(self):
        url = '/ping/whoami'
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

        url = '/oauth2/token'
        data = {
            'grant_type': 'authorization_code',
            'client_id': self._secrets['client_id'],
            'client_secret': self._secrets['client_secret'],
            'redirect_uri': 'http://scottlangridge.com/',
            'code': code
        }
        response = self._post(url, data)
        self._token = response['access_token']
        self._refresh_token = response['refresh_token']
        input('\nApprove access in the Monzo app and then press enter.\n')
        print('Access Token Acquired.')
        print('Access Token:\n' + self._token)
        print('Refresh Token:\n' + self._refresh_token)

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
            'refresh_token': self._refresh_token
        }
        response = self._post(url, data)
        self._token = response['access_token']
        self._refresh_token = response['refresh_token']
        if not self._token_is_valid():
            raise AssertionError("Authentication token invalid!")
        else:
            print('Authentication Token Refreshed.\nNew Token: \n%s\nNew Refresh Token: \n%s\n'
                  % (self._token, self._refresh_token))

    # Calls the balance endpoint of the Monzo API.
    def _balance(self):
        url = '/balance?account_id=%s' % self._account_id
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
        url = '/pots'
        response = self._get(url)
        pot_list = response['pots']
        for p in pot_list:
            if p['name'] == pot:
                return p['balance']
        raise KeyError('Invalid pot name.')
