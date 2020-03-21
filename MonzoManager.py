import schedule
import logging
import json
import time

from budgeter.BudgetManager import BudgetManager


def main():
    # Set up logging
    logging.basicConfig(filename='MonzoManager.log',
                        filemode='a+',
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        level=logging.DEBUG)
    logging.info('--------------------- MONZO MANAGER STARTED ---------------------')

    # Initialise and schedule each component.
    budget_manager = initialise_budget()

    # Print components.
    print('INITIALISATION COMPLETED\n\nACTIVE COMPONENTS:')
    if budget_manager:
        print('Budget Manager - %s' % budget_manager.schedule_expression)

    # Running schedule on infinite loop.
    print('\nRUNNING...')
    while True:
        schedule.run_pending()
        time.sleep(1)


# Initialise and schedule the budget component.
def initialise_budget():
    # Load budget data
    with open(BudgetManager.budget_file) as f:
        budget_data = json.loads(f.read())

    # If active: create manager and add it to schedule.
    if budget_data['active']:
        budget_manager = BudgetManager()
        exec(budget_data['schedule_expression'] + '.do(budget_manager.update)')
        return budget_manager
    else:
        return None


main()
