import psycopg2
from psycopg2.extensions import AsIs
from collections import namedtuple
from utils import read_config


Query_result = namedtuple('Query_result', 'success result')


class PSQL_wrapper:
    def __init__(self, args):
        self.db_opened = False
        self.connection = None
        self.cursor = None
        self.args = args

    def __enter__(self):
        self.connection = psycopg2.connect(**self.args)
        self.cursor = self.connection.cursor()
        self.db_opened = True
        return self

    def __exit__(self, type, value, traceback):
        if self.db_opened:
            self.cursor.close()
            self.connection.close()

    def exec(self, expr, params={}):
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

    def copy_csv(self, file, table_name, overwrite=False):
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

        print('Creating ', table_name, '...', sep='')
        res = self.exec(command, (AsIs(table_name),))
        if res.success is False:
            print(res.result)

        if overwrite:
            print('Truncating...')
            res = self.exec("TRUNCATE TABLE \"%s\"", (AsIs(table_name),))
            if res.success is False:
                print(res.result)

        try:
            print('Commiting data...')
            self.cursor.copy_expert("COPY \"%s\" FROM STDIN WITH DELIMITER ';' CSV HEADER QUOTE '\"'" % table_name, file)
            self.connection.commit()
            print('Data copied successfully!')
            print()
        except (psycopg2.Error) as error:
            if self.connection is not None:
                self.connection.rollback()
            print(error)

    def copy_table(self, table_in, table_out=''):
        command = "SELECT * INTO \"%s\" from \"%s\""
        if table_out == '':
            table_out = AsIs(table_in + '_COPY')
        else:
            table_out = AsIs(table_out)

        return self.exec(command, (table_out, AsIs(table_in)))

    def get_column_names(self, table_name):
        command = "SELECT * FROM \"%s\" LIMIT 0"
        self.cursor.execute(command, (AsIs(table_name),))
        return [desc[0] for desc in self.cursor.description]



if __name__ == '__main__':
    args = read_config('config.ini', ['host', 'port', 'dbname', 'user', 'password'])

    with PSQL_wrapper(args) as psql:
        table_name = "CM_MACRO_SW_version_2018-03-01_2019-03-07"
        print(psql.get_column_names(table_name))
        """
        # res = psql.copy_table(table_name, table_name + "_ADJUSTED")
        # res = psql.copy_table('changes_in_operators_data', 'nowa_tabela')
        # res = psql.exec("select * from changes_dates where \"Operator_ID\" = %(id)s", {'id': 'Operator: 1006'})
        if res.success is False:
            print('Error:', res.result, sep='\n')
        else:
            print('Result:', res.result, sep='\n')
        """
