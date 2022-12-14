# hana-task-runner
The Task Runner is a small command-line tool that helps to run time-consuming operations on HDI containers in SAP HANA Database in parallel.The tool is a simple database client using asynchronous threads to invoke SQL queries and procedures in the specified database.

The current main use case and the main characteristics of the addressed problem are as following:

* You develop database artifacts in SAP Web IDE for SAP HANA XS Advanced using HDI containers  (SAP HANA Database Modules). Actively building application, you noticed that the number of HANA service instances, instantiated by the Web IDE for development, has significantly grown.
* You learned that you must manually deallocate resources consumed by development versions of applications based on SAP Web IDE for SAP HANA - Known Issues (https://help.sap.com/docs/SAPWEBIDE/cadd62683c3d4e9d8cc619e16b469768/9c20ea2011d343bdabb4e122504bb63c.html). Based on the same document, you learned that you must keep the number of HDI containers, created in a single space and bound to di-builder, less than 120.
* Attempting to delete development HANA service instances with XS CLI, you noticed that the most of them have beed deleted normally and only a few of them failed with a timeout error. Further attempts to delete those service instances remained unsuccessful with the same error.
* Attempting to directly drop respective HDI containers (https://help.sap.com/docs/SAP_HANA_PLATFORM/3823b0f33420468ba5f1cf7f59bd6bd9/fe51ebe5102c4991813a04b68843515f.html?version=2.0.05)  you observed that the respective procedure call has taken several hours in the database. In my case this process has taken from 2 to 20 hours. Depending on the number of such containers, sequential deletion may take significant time.
* After dropping such an HDI container in the database, you successfully removed the respective HANA service instance and its bindings from the space in XS Advanced.
* Given the circumstances, you decided to find a way to delete problematic HDI containers in parallel without opening multiple SQL Consoles in SAP HANA Studio.



## Table of Contents

- [Important Notes](#important-notes)
- [Deployment](#deployment)
  - [Environment requirements](#environment-requirements)
  - [Packaging](#packaging)
  - [Target System Requirements](#target-system-requirements)
- [Usage](#usage)
  - [Client Configuration](#client-configuration)
  - [General syntax](#general-syntax)
  - [Operation arguments](#operation-arguments)
      - [Argument  `-rd`, `--run-deletion`](#argument---rd---run-deletion)
- [Obtain Support](#obtain-support)



## Important Notes

While using the tool, please consider following important notes:

> The project is not the official software released by SAP. Hence no official support can be assumed from SAP concerning the tool and the implemented functionality.
>
> The tool is dependent on the SAP proprietary package hdbcli that is provided in https://pypi.org/project/hdbcli/ under [SAP Developer License Agreement](https://tools.hana.ondemand.com/developer-license-3_1.txt). The installation of the package is possible via `pip install hdbcli` or manually via the [HANA Client Install](https://help.sap.com/viewer/f1b440ded6144a54ada97ff95dac7adf/latest/en-US/39eca89d94ca464ca52385ad50fc7dea.html).



## Deployment

### Environment requirements

The tool is written and tested with Python 3.9.4. The tool is dependent on following packages:

| Package  | Version | Purpose                                               |
| -------- | ------- | ----------------------------------------------------- |
| argparse | 1.4.0   | Handles command line arguments                        |
| pandas   | 1.3.2   | Operates with DataFrames and produce CSV files output |
| pathlib  | 1.0.1   | Operates with relative file paths                     |
| PyYAML   | 5.4.1   | Parses the configuration files                        |
| hdbcli   | 2.12.22 | Proprietary SAP HANA Python Client                    |
| tabulate | 0.8.9   | Pretty-prints the tabular data                        |

Provided dependencies are listed in the `/requirements.txt` .



### Packaging

The tool can run from the source codes in the respective Python environment with the required packages installed. 

The tool can also be packaged into a single executable file that will contain the Python runtime and required packages for a target platform. The package  `Pyinstaller` can be used for that purpose, e.g.,  running `pyinstaller --onefile task_runner.py`.



### Target System Requirements

The tool was developed and tested with SAP HANA Database 2.0 SPS05 rev. 57 with enabled XS Advanced Platform.

The tool requires a database user with assigned `HDI Container Group Administrator` privileges for all needed Container Groups, e.g., for the default XSA-managed Container Group `_SYS_DI#SYS_XS_HANA_BROKER`.  Please review following steps provided as a reference to fulfill the requirements:

> The complete and comprehensive guidelines to manage SAP HANA HDI Containers are provided in [SAP HANA Deployment Infrastructure (HDI) Reference for SAP HANA Platform](https://help.sap.com/docs/SAP_HANA_PLATFORM/3823b0f33420468ba5f1cf7f59bd6bd9/4e9d59759b294124baa97c5b6d675072.html?version=2.0.05).

#### 1. User SYSTEM creates `HDI Administrator` and `HDI Container Group Administrator` users

```sql
CREATE USER HDI_ADMIN PASSWORD YOUR_PASSWORD NO FORCE_FIRST_PASSWORD_CHANGE;
CREATE USER CONTAINER_GROUP_ADMIN PASSWORD YOUR_PASSWORD NO FORCE_FIRST_PASSWORD_CHANGE;
```

#### 2. User SYSTEM grants HDI administration permissions to `HDI Administrator`

```sql
CREATE LOCAL TEMPORARY TABLE #PRIVILEGES LIKE _SYS_DI.TT_API_PRIVILEGES;
INSERT INTO #PRIVILEGES (PRINCIPAL_NAME, PRIVILEGE_NAME, OBJECT_NAME) SELECT 'HDI_ADMIN', PRIVILEGE_NAME, OBJECT_NAME FROM _SYS_DI.T_DEFAULT_DI_ADMIN_PRIVILEGES;
CALL _SYS_DI.GRANT_CONTAINER_GROUP_API_PRIVILEGES('_SYS_DI', #PRIVILEGES, _SYS_DI.T_NO_PARAMETERS, ?, ?, ?);
DROP TABLE #PRIVILEGES;
```

#### 3. User HDI_ADMIN (`HDI Administrator`) grants administration permissions for container group SYS_XS_HANA_BROKER to user CONTAINER_GROUP_ADMIN (`HDI Container Group Administrator`) 

```sql
CREATE LOCAL TEMPORARY COLUMN TABLE #PRIVILEGES LIKE _SYS_DI.TT_API_PRIVILEGES;
INSERT INTO #PRIVILEGES (PRINCIPAL_NAME, PRIVILEGE_NAME, OBJECT_NAME) SELECT 'CONTAINER_GROUP_ADMIN', PRIVILEGE_NAME, OBJECT_NAME FROM _SYS_DI.T_DEFAULT_CONTAINER_GROUP_ADMIN_PRIVILEGES;
CALL _SYS_DI.GRANT_CONTAINER_GROUP_API_PRIVILEGES('SYS_XS_HANA_BROKER', #PRIVILEGES, _SYS_DI.T_NO_PARAMETERS, ?, ?, ?);
DROP TABLE #PRIVILEGES;
```

#### 4. User CONTAINER_GROUP_ADMIN (`HDI Container Group Administrator`)  can be used to run operations on container group SYS_XS_HANA_BROKER as an administrator



## Usage

General configuration flow:

* Prepare the environment. Optionally package the tool using the `Pyinstaller`

* Review the documentation
* Configure connection details and lists of containers in `config.yaml`
* Run the required commands



### Client Configuration

The configuration of the tool is stored in the `config.yaml`. The file should be located in the same directory as the executable file. The default configuration is provided below:

```yaml
connection:
  indexserver_hostname: hostname  # The indexserver hostname
  indexserver_port: 30015         # The indexserver SQL port
  container_group_admin: USER     # The user with Container Group Administrator
  password: PLAIN_PASSWORD        # The password
  encrypt: False                  # Keep False by default for not SSL-enforced connections
  sslValidateCertificate: False   # Keep False by default

client_config:
  output_dir: ./output
  logging_level: INFO # CRITICAL | ERROR | WARNING | INFO | DEBUG | NOTSET

processing:
  max_concurrency: 3 # The allowed number of parallel operations

operations:
  _SYS_DI#SYS_XS_HANA_BROKER: # The container group name
    delete:                   # The operation to be performed, supported now options: delete
      - NAMED_CONTAINER_1     # The container name
      - NAMED_CONTAINER_2     # The container name
```



### General syntax

Please find the general command line syntax below.

```
task_runner [-rd, --run-deletion]
```



### Operation arguments

##### Argument  `-rd`, `--run-deletion`

Having the argument given, the tool will attempt to drop all Containers specified in `delete` for every Container Group specified in `operations` in parallel.

```yaml
processing:
  max_concurrency: 3 # The allowed number of parallel operations

operations:
  _SYS_DI#SYS_XS_HANA_BROKER: # The container group name
    delete:                   # The operation to be performed, supported now options: delete
      - NAMED_CONTAINER_1     # The container name
      - NAMED_CONTAINER_2     # The container name
```

The produced output will contain the log entries and pretty-printed results of the `DROP_CONTAINER` HDI procedure.



## Obtain Support

In case of the bugs, malfunctions or feature requests, please raise an [Issue](https://github.com/nklinked/otter/issues/new/choose) in the repository.
