import operator

ops = {
    "=": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge}


def _flatten_transaction_json(transaction_json, prefix=""):
    flat_json = dict()
    for kvp in transaction_json.items():
        key = kvp[0]
        value = kvp[1]

        if type(value) != dict:
            flat_json[prefix + key] = value
        else:
            flat_json.update(_flatten_transaction_json(value, key + '.'))

    return flat_json


def _try_parse_int(value):
    try:
        return int(value)
    except ValueError:
        return value


def _get_rules(class_definition):
    rules = {}
    rules_definition = class_definition["rules"]
    for rule in rules_definition.items():
        key = rule[0]
        condition_definition = rule[1]

        cond_op = condition_definition["operator"]
        cond_val = condition_definition["value"]
        rules[key] = (lambda a, op=cond_op, val=cond_val: ops[op](a, val))

    return rules


def _get_actions(class_definition):
    return class_definition["actions"]


class _TransactionClass:
    def __init__(self, class_definition):
        self.name = class_definition[0]
        self.rules = _get_rules(class_definition[1])
        self.actions = _get_actions(class_definition[1])

    def is_member(self, transaction):
        transaction = _flatten_transaction_json(transaction)
        for key, value in transaction.items():
            if key in self.rules.keys():
                if not self.rules[key](value):
                    return False
        return True
