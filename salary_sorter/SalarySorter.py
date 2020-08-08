import logging

from monzo_account.MonzoAccount import MonzoAccount


class SalarySorter:
    def __init__(self):
        self.account = MonzoAccount()
        self._log = logging.getLogger("SalarySorter")

    def sort(self, transaction_id):
        self._log.info(f"Sorting Salary - {transaction_id}")
        transaction = self.account.retrieve_transaction(transaction_id)
        to_transfer = transaction['amount']
        if not to_transfer > 0:
            raise ValueError('Cannot sort salary on a transaction with an amount <= 0.')

        bills_top_up = 100000 - self.account.pot_balance('Bills')
        accessible_funds_top_up = 200000 - self.account.pot_balance('Accessible Funds')

        if to_transfer > bills_top_up:
            self.account.deposit_to_pot('Bills', bills_top_up)
            to_transfer -= bills_top_up
        else:
            self.account.deposit_to_pot('Bills', to_transfer)
            self.account.notify("Salary Sorted")
            return

        if to_transfer > accessible_funds_top_up:
            self.account.deposit_to_pot('Accessible Funds', accessible_funds_top_up)
            to_transfer -= accessible_funds_top_up
        else:
            self.account.deposit_to_pot('Accessible Funds', to_transfer)
            self.account.notify("Salary Sorted")
            return

        self.account.deposit_to_pot('Long Term Savings', to_transfer)
        self.account.notify("Salary Sorted")
