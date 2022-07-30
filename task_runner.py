import logging
import sys
import argparse
import yaml
from components.client import Client
from components.runner import Runner

with open("./config.yaml", 'r', encoding='utf-8') as config_stream:
    try:
        config = yaml.safe_load(config_stream)
        client = Client(config)
    except yaml.YAMLError as exc:
        print(exc)
        sys.exit(1)

log_file = client.resolve_file('logs', 'run.log')
file_handler = logging.FileHandler(filename=log_file)
stdout_handler = logging.StreamHandler(sys.stdout)
handlers = [file_handler, stdout_handler]
target_level = client.get_configured_logging_level()

logging.basicConfig(
    level=target_level,
    format='[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s',
    datefmt='%m/%d/%Y %I:%M:%S %p',
    handlers=handlers
)

argparser = argparse.ArgumentParser()
argparser.add_argument('-rd', '--run-deletion', action='store_true',
                       help='Run parallel deletion of the HDI containers in the given system')
args = argparser.parse_args()

runner = Runner(client.max_concurrency)

if args.run_deletion:
    logging.info(
        'Running parallel deletion of the HDI containers in the given system')
    runner.run(client.deletion_tasks)
