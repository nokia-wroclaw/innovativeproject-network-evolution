from wrapper import *
from utils import *
from psycopg2.extensions import AsIs

args = read_config('config.ini', ['host', 'port', 'dbname', 'user', 'password'])
prox = 50

with PSQL_wrapper(args) as psql:
    table_name = "PM_KPI_1_CRITICAL_2018-03-01_2019-02-28"
    #table_name = "PM_KPI_2_MAJOR_2018-03-01_2019-02-28"
    #table_name = "PM_KPI_3_MINOR_2018-03-01_2019-02-28"
    #table_name = "PM_KPI_4_WARNING_2018-03-01_2019-02-28"

    res = psql.copy_table(table_name, table_name + "_ADJUSTED")
    table_name += "_ADJUSTED"

    operators = psql.get_column_names(table_name)[3:]
    print(operators)
    for operator in range(len(operators)):
        dates = []
        command = """UPDATE \"%s\"
                     SET \"%s\" = 0
                     WHERE \"%s\" is NULL"""
        res = psql.exec(command, (AsIs(table_name), AsIs(operators[operator]), AsIs(operators[operator])))





