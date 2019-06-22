# -*- coding: utf-8 -*-

import psycopg2
from psycopg2.extensions import AsIs
from configparser import ConfigParser
from collections import namedtuple

# SQL query result data structure
Query_result = namedtuple('Query_result', 'success result')


class PSQL_wrapper:
    """A class that abstracts PSQL queries"""
    def __init__(self, args):
        """Class constructor"""
        self.db_opened = False
        self.connection = None
        self.cursor = None
        self.args = args

    def __enter__(self):
        """What to do at the beginning of a "with resources" block"""
        self.connection = psycopg2.connect(**self.args)
        self.cursor = self.connection.cursor()
        self.db_opened = True
        return self

    def __exit__(self, type, value, traceback):
        """What to do at the end of a "with resources" block"""
        if self.db_opened:
            self.cursor.close()
            self.connection.close()

    def exec(self, expr, params={}):
        """Executes a PSQL command and returns a Query_result"""
        try:
            self.cursor.execute(expr, params)
            self.connection.commit()
            if self.cursor.description is not None:
                return Query_result(True, self.cursor.fetchall())
            else:
                return Query_result(True, [])

        except (psycopg2.Error) as error:
            if self.connection is not None:
                self.connection.rollback()
            return Query_result(False, error)


def read_config(filename, section, args):
    """Reads config from a specified file"""
    Config = ConfigParser()
    Config.read(filename)

    result = {}

    for arg in args:
        result[arg] = Config.get(section, arg)

    return result


def write_new_defaults(filename, args):
    """Overwrites "Default" section of a config file"""
    Config = ConfigParser()
    Config.read('config.ini')

    for key in args.keys():
        Config.set('Defaults', key, args[key])

    with open(filename, 'w') as configfile:
        Config.write(configfile)


def get_public_tables(psql):
    """Fetches names of all public tables in a current database"""
    tables = []
    command = "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
    res = psql.exec(command)

    if res.success is False:
        return []
    else:
        for elem in res.result:
            tables.append(elem[0])

    return tables


def get_operators(psql, table_name):
    """Fetches names of all operators from a software table"""
    operators = []
    command = "SELECT DISTINCT \"Operator_name\" FROM \"%s\""
    res = psql.exec(command, (AsIs(table_name),))

    if res.success is False:
        return []
    else:
        for i in range(len(res.result)):
            operators.append(res.result[i][0])

    return operators


def get_softwares(psql, table_name):
    """Fetches names of all software versions from a software table"""
    softwares = []
    command = "SELECT DISTINCT \"SW_version\" FROM \"%s\""
    res = psql.exec(command, (AsIs(table_name),))

    if res.success is False:
        return []
    else:
        for i in range(len(res.result)):
            softwares.append(res.result[i][0])
    return sorted(softwares)


def software_dates(psql, table_name, operator_id):
    """Fetches dates of all registered software data"""
    dates = []
    command = (
        """
        SELECT DISTINCT \"Date\", \"SW_version\", \"Value\"
        FROM \"%s\"
        WHERE \"Operator_name\" = '%s'
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


def copy_csv(psql, file, table_name):
    """Copies CSV from file to a specified table"""
    command = "SELECT exists(SELECT * FROM information_schema.tables WHERE table_name='\"%s\"')"
    res = psql.exec(command, (AsIs(table_name),))

    if res.result[0][0] is True:
        print("[INFO] Table already exists, skipping")
        return

    columns = file.readline().strip().split(';')
    command = "CREATE TABLE IF NOT EXISTS \"%s\" ("
    file.seek(0)

    for c in columns:
        if c.startswith('Operator:') or c == "Value":
            command += ("\"%s\"" % c) + ' real, '
        elif c == 'Date':
            command += "\"Date\" date, "
        else:
            command += ("\"%s\"" % c) + ' varchar, '

    command = command[0:-2] + ')'

    print('[INFO] Creating table ', table_name, '...', sep='')
    res = psql.exec(command, (AsIs(table_name),))

    try:
        print('[INFO] Copying data...')
        psql.cursor.copy_expert("COPY \"%s\" FROM STDIN WITH DELIMITER ';' CSV HEADER QUOTE '\"'" % table_name, file)
        psql.connection.commit()
        print('[INFO] Data copied successfully!')
    except (psycopg2.Error) as error:
        if psql.connection is not None:
            psql.connection.rollback()


def copy_table(psql, table_in, table_out='_COPY'):
    """Makes a copy of an existing table"""
    command = "SELECT * INTO \"%s\" from \"%s\""
    table_out = AsIs(table_out)

    return psql.exec(command, (table_out, AsIs(table_in)))


def get_column_names(psql, table_name):
    """Fetches names of all columns in a specified table"""
    command = "SELECT * FROM \"%s\" LIMIT 0"
    psql.cursor.execute(command, (AsIs(table_name),))
    return [desc[0] for desc in psql.cursor.description]
