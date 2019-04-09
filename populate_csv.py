import os
from wrapper import *
from utils import read_config


if __name__ == '__main__':
    args = read_config('config.ini', ['host', 'port', 'dbname', 'user', 'password'])

    with PSQL_wrapper(args) as psql:
        path = './csv/'
        for filename in os.listdir(path):
            psql.copy_csv(open(path + filename, 'r'), filename.split('.')[0], True)
