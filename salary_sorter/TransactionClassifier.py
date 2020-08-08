import json

from salary_sorter.TransactionClass import _TransactionClass


class _TransactionClassifier:
    transaction_classes_file = 'salary_sorter/data_dir/transaction_classes.json'

    def __init__(self):
        self._classes = None
        self._load_classes()

    def _load_classes(self, file=transaction_classes_file):
        self._classes = []
        with open(file, 'r') as f:
            classes_json = json.loads(f.read())
        for class_definition in classes_json.items():
            self._classes.append(_TransactionClass(class_definition))
        pass

    def classify_transaction(self, transaction):
        matching_classes = []
        for transaction_class in self._classes:
            if transaction_class.is_member(transaction):
                matching_classes.append(transaction_class.name)
        return matching_classes
