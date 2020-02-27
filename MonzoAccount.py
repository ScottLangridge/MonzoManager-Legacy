import json
import random
import string

import requests


def generate_state(size=20, chars=string.ascii_lowercase):
    return ''.join(random.choice(chars) for _ in range(size))


class MonzoAccount:
    def __init__(self, token=''):
        with open('secrets.json') as f:
            self.secrets = json.load(f)

        self.token = token
        if not self._token_is_valid():
            self._get_new_access_token()

    def _get(self, url):
        headers = {'Authorization': 'Bearer %s' % self.token}
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise ConnectionError("%d - %s" % (response.status_code, response.reason))
        else:
            content = json.loads(response.content)
            return content

    def _post(self, url, data):
        headers = {'Authorization': 'Bearer %s' % self.token}
        response = requests.post(url, data, headers=headers)
        if response.status_code != 200:
            raise ConnectionError("%d - %s" % (response.status_code, response.reason))
        else:
            content = json.loads(response.content)
            return content

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

    def _get_new_access_token(self):
        state = generate_state()
        url = ('https://auth.monzo.com/?client_id=%s&redirect_uri=%s&response_type=code&state=%s'
               % (self.secrets['client_id'], 'http://scottlangridge.com/', state))

        print('Navigate to the following address in your browser and verify your account:\n' + url)
        code = input('\nCopy the "code" section of the URL that you are redirected to and paste it here:\n')
        print('\nFetching access token.')

        url = 'https://api.monzo.com/oauth2/token'
        data = {
            'grant_type': 'authorization_code',
            'client_id': self.secrets['client_id'],
            'client_secret': self.secrets['client_secret'],
            'redirect_uri': 'http://scottlangridge.com/',
            'code': code
        }
        response = requests.post(url, data)
        content = json.loads(response.content)
        self.token = content['access_token']
        input('\nApprove access in the Monzo app and then press enter.\n')
        print('Access Token:\n' + self.token)

        if self._token_is_valid():
            print("\nAuthentication Completed\n")
        else:
            print("\nAuthentication Error\n")
            raise AssertionError("Authentication token invalid!")
