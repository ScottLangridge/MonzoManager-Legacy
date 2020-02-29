import json

from MonzoAccount import MonzoAccount


class BudgetManager:
    def __init__(self):
        # The JSON file containing the budget data.
        self.budget_file = 'weekley_budgeter/data_dir/budget.json'
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

    def load_budget_file(self):
        with open(self.budget_file) as f:
            json_data = json.loads(f.read())
        self.buffer = json_data['buffer']
        self.budget = json_data['weekly_budget']
        self.current_net = json_data['current_net']

    def save_budget_file(self):
        json_data = {
            'buffer': self.buffer,
            'weekly_budget': self.budget,
            'current_net': self.current_net,
        }
        with open(self.budget_file, 'w') as f:
            f.write(json.dumps(json_data, sort_keys=True, indent=2, separators=(',', ': ')))

    # Run at the end of a period to update the budget.
    def update(self):
        # Fetch data
        self.load_budget_file()
        balance = self.monzo.available_balance()

        # Calculate derived data
        current_net_change = balance - self.buffer
        to_transfer = (self.buffer + self.budget) - balance

        # Action Updates
        self.current_net += current_net_change
        self.monzo.withdraw_from_pot('savings', to_transfer)

        # Save data
        self.save_budget_file()
