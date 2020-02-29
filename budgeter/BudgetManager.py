import json

from monzo_account.MonzoAccount import MonzoAccount


# Controls the process of running budgets.
class BudgetManager:
    budget_file = 'budgeter/data_dir/budget.json'

    def __init__(self):
        self.monzo = MonzoAccount()

        # Components of a budget:
        # Buffer - The amount of "buffer" (in pence) left in the account to allow spending beyond the budget within a
        # period.
        #
        # Budget - The amount of money (in pence) planned to be spent each period.
        #
        # Current Net - The amount of money (in pence) that the user is currently over or under budget.
        # (100 means £1 within budget).
        #
        # For Example: If you have a buffer of £100 and a budget of £50 per period, you will start each period with £150
        # on your card. Say you spend £40 that period, you will add £5 to your current net.
        #
        self.buffer = None
        self.budget = None
        self.current_net = None
        self.schedule_expression = None
        self._load_budget_file()

    # Read in data from the JSON file.
    def _load_budget_file(self):
        with open(self.budget_file) as f:
            json_data = json.loads(f.read())
        self.buffer = json_data['buffer']
        self.budget = json_data['budget']
        self.current_net = json_data['current_net']
        self.schedule_expression = json_data['schedule_expression']

    # Updates any values which may have changed in the JSON file.
    def _save_budget_file(self):
        with open(self.budget_file) as f:
            json_data = json.loads(f.read())

        json_data['current_net'] = self.current_net

        with open(self.budget_file, 'w') as f:
            f.write(json.dumps(json_data, sort_keys=True, indent=2, separators=(',', ': ')))

    # Tops up account from savings pot and updates current_net as appropriate.
    # Should only ever be called by the schedule expression in the budget JSON file.
    def update(self):
        # Fetch data
        self._load_budget_file()
        balance = self.monzo.available_balance()

        # Calculate derived data
        current_net_change = balance - self.buffer
        to_transfer = (self.buffer + self.budget) - balance

        # Action Updates
        self.current_net += current_net_change
        self.monzo.withdraw_from_pot('savings', to_transfer)

        # Save data
        self._save_budget_file()

        # Notify user
        self.monzo.notify('Budget Manager', 'New net: £%.2f' % (self.current_net / 100))
