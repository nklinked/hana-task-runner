from datetime import datetime
import os
import re
from pathlib import Path
import logging
from functools import partial
from hdbcli import dbapi
from tabulate import tabulate
import pandas as pd

class Client:

    def __init__(self, config):
        self.config = config

        output_dir = self.config.get('client_config').get('output_dir')

        current_run_timestamp = datetime.now()
        current_run_timestamp = current_run_timestamp.strftime('%d-%m-%Y-%H-%M-%S')
        current_run_dir = f'{output_dir}/{current_run_timestamp}'

        self.output_dir = re.sub(r'\/+', '/', output_dir)
        self.current_run_dir = re.sub(r'\/+', '/', current_run_dir)

        if not os.path.exists(Path(output_dir)):
            os.makedirs(Path(output_dir))
            if not os.path.exists(Path(current_run_dir)):
                os.makedirs(Path(current_run_dir))

        self.max_concurrency = self.config.get('processing').get('max_concurrency')
        self._deletion_tasks = []

    def resolve_file(self, path, file):
        path = f'{self.current_run_dir}/{path}'
        path = re.sub(r'\/+', '/', path)
        if not os.path.exists(Path(path)):
            os.makedirs(Path(path))
        file_path = f'{path}/{file}'
        file_path = re.sub(r'\/+', '/', file_path)
        return Path(file_path)

    def get_configured_logging_level(self):
        logging_level = self.config.get('client_config').get('logging_level')
        allowed_levels = ['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG', 'NOTSET']
        return logging_level if logging_level in allowed_levels else 'NOTSET'

    def get_database_connection(self):
        try:
            configuration = self.config['connection']
            connection = dbapi.connect(
                address = configuration['indexserver_hostname'],
                port = configuration['indexserver_port'],
                user = configuration['container_group_admin'],
                password = configuration['password'],
                encrypt = configuration['encrypt'],
                sslValidateCertificate = configuration['sslValidateCertificate'],
                communicationTimeout = 0)
        except Exception as e: # pylint: disable=invalid-name
            address = configuration['indexserver_hostname']
            port = configuration['indexserver_port']
            user = configuration['container_group_admin']
            logging.error(
                (f'Failed to establish connection to indexserver on {address}:{port} '
                 f'with user {user}'),
                exc_info=e)
            return None
        else:
            return connection

    def drop_container(self, container_group_name, container_name):
        try:
            connection = self.get_database_connection()
            cursor = connection.cursor()
        except Exception as e: # pylint: disable=invalid-name
            logging.error(
                ('Failed to establish connection to database when deleting '
                 f'container {container_name} from group {container_group_name}'),
                exc_info=e)
        else:
            try:
                logging.info((f'Started dropping container {container_name} '
                              f'from group {container_group_name}'))
                cursor.execute(("create local temporary column table #drop_container_parameters "
                                "like _sys_di.tt_parameters;"))
                cursor.execute(("insert into #drop_container_parameters ( key, value ) "
                                "values ( 'ignore_errors', 'true' );"))
                cursor.execute(("insert into #drop_container_parameters ( key, value ) "
                                "values ( 'ignore_work', 'true' );"))
                cursor.execute(("insert into #drop_container_parameters ( key, value ) "
                                "values ( 'ignore_deployed', 'true' );"))
                cursor.execute((f"call {container_group_name}.drop_container('{container_name}', "
                                "#drop_container_parameters, ?, ?, ?);"))

                keys = [ x[0] for x in cursor.description]
                rows = cursor.fetchall()
                result_set = pd.DataFrame(rows, columns=keys)
                pretty_printed_results = tabulate(result_set, headers='keys', tablefmt='psql')
                logging.info(
                    (
                        'Results of executing SQL: '
                        f'call {container_group_name}.drop_container(\'{container_name}\', '
                        f'#drop_container_parameters, ?, ?, ?))\n'
                        f'{pretty_printed_results}'
                        )
                    )

                cursor.execute('drop table #drop_container_parameters;')
                logging.info((f'Dropped container {container_name} '
                              f'from group {container_group_name}'))
            except Exception as e: # pylint: disable=invalid-name
                logging.error((
                    (f'Failed to drop container {container_name} '
                     f'from group {container_group_name}')
                    ),exc_info=e)
        finally:
            cursor.close()
            connection.close()

    @property
    def deletion_tasks(self):
        return self._deletion_tasks

    @deletion_tasks.getter
    def deletion_tasks(self):
        tasks = []
        if not self._deletion_tasks:
            operations = self.config['operations']
            for container_group in operations:
                if operations[container_group].get('delete'):
                    for container_name in operations[container_group]['delete']:
                        tasks.append(partial(self.drop_container, container_group, container_name))
                        self._deletion_tasks = tasks
        return self._deletion_tasks

    @deletion_tasks.setter
    def deletion_tasks(self, deletion_tasks):
        self._deletion_tasks = deletion_tasks
