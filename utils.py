import psycopg2
from psycopg2.extensions import AsIs
from configparser import ConfigParser


def read_config(filename, args):
    Config = ConfigParser()
    Config.read('config.ini')

    res = {}

    for arg in args:
        res[arg] = Config.get('PSQL', arg)

    return res


def get_operators(psql, table_name):
    operators = []
    command = "SELECT DISTINCT \"Operator_name\" FROM \"%s\""
    res = psql.exec(command, (AsIs(table_name),))

    if res.success is False:
        return []
    else:
        for i in range(len(res.result)):
            operators.append(res.result[i][0])

    return operators


def software_dates(psql, table_name, operator_id):
    dates = []
    command = (
        """
        SELECT DISTINCT \"Date\", \"SW_version\", \"Value\"
        FROM \"%s\"
        WHERE \"Operator_name\" = \"%s\"
        ORDER BY \"Date\"
        """
    )

    res = psql.exec(command, (AsIs(table_name), AsIs(operator_id)))

    if res.success is False:
        return []
    else:
        dates.append([res.result[0][0], [[res.result[0][1], res.result[0][2]]]])
        di = 0
        for i in range(1, len(res.result)):
            if res.result[i][0] == dates[di][0]:
                dates[di][1].append([res.result[i][1],res.result[i][2]])
            else:
                di += 1
                dates.append([res.result[i][0], [[res.result[i][1], res.result[i][2]]]])

    return dates

