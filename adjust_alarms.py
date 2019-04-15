from wrapper import *
from utils import *
from psycopg2.extensions import AsIs



def adjust_alarms(args, table_name):
    with PSQL_wrapper(args) as psql:
        res = psql.copy_table(table_name, table_name + "_ADJUSTED")
        table_name += "_ADJUSTED"

        operators = psql.get_column_names(table_name)[3:]

        for operator in range(len(operators)):
            dates = []
            command = """
                        UPDATE \"%s\"
                        SET \"%s\" = 0
                        WHERE \"%s\" is NULL
                      """
            res = psql.exec(command, (AsIs(table_name), AsIs(operators[operator]), AsIs(operators[operator])))
