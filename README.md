# Filerobot Migration Script

This script migrates media assets files from a 3rd-party storage provider to Filerobot. It supports any 3rd-party storage provider accessible over HTTP.

## Requirements

1. A Tab-Separated-Values (TSV) file containing source file URLs, tags and metadate to migrate
1. Filerobot CLI (v1.5 or higher)
2. Filerobot API Key and API Secret
3. The desired metadata taxonomy must be created in the Filerobot container before the migration 

## Filerobot CLI setup

Install the Filerobot CLI:

### macOS 
```bash
sudo curl -L "https://github.com/scaleflex/filerobot-cli/releases/latest/download/filerobot-cli-darwin-x86_64" -o /usr/local/bin/filerobot && sudo chmod +x /usr/local/bin/filerobot
```

### Linux 
```bash
sudo curl -L "https://github.com/scaleflex/filerobot-cli/releases/latest/download/filerobot-cli-linux-x86_64" -o /usr/local/bin/filerobot && sudo chmod +x /usr/local/bin/filerobot
```

Once the Filerobot CLI is installed, verify that you have installed v1.5 or higher

```
filerobot version
```

Configure the Filerobot CLI:

```
filerobot config --token=mytoken --key=mysupersecretkey
```

Where

`--token` is your Filerobot token

`--key` is your Filerobot API Secret Key

## Migration

### Source URLs

Before running the migration, prepare an inventory TSV file of all files to be migrated in following format:

|file URL|tags|meta|
|---|---|---|
|http://sample.li/eiffel.jpg|["tag1", "tag2"]|{"meta1\_key": "meta1\_value", "meta2\_key": "meta2\_value"}|
|http://sample.li/folder/subfolder/hotel.jpg|["tag1", "tag2"]|{"meta1\_key": "meta1\_value", "meta2\_key": "meta2\_value"}|

Make sure that the metadata taxnomy ("key" => "value" pairs) is created in the target Filerobot container.

A sample file [sample_tsv.tsv](/sample_tsv.tsv) is provided in the repository.

### Upload files into Filerobot
Once the inventory TSV file has been created, run the command below to start the upload into Filerobot:

```
python upload_files.py --folder=/target_folder --input_file=source_files.tsv --files_per_request=10 --wait_btw_request=0.2
```

Where

`--folder` the target root folder for uploading files, the folder hierarchy will be created under this folder according to the file paths in the TSV file

`--input_file` the TSV inventory TSV file containing files to be migrated, `default=DEFAULT_INPUT_FILE` as defined in `constants.py`

`--files_per_request` number of files to upload per request, `default=5`

`--wait_btw_request` the time in seconds between 2 requests, `default=0.2`, depends on the machine on which you run the script

In order to not overload the origin 3rd-party storage provider, while still migration we recommend to not go below `--wait_btw_request=0.2` and above `--files_per_request=25`. 
This configuration will ensure the successful upload of about 1000 files per minute.

#### Retry logic

If an upload fails, because for example one or multiple files are unavailalbe at the origin (network error, ...), then the script retries automatically once to upload the failed files.

If the 2nd try fails, then the failed upload is logged in `LOG_FAILED_PATH` (see below) and the source file URL, tags and metadata are written in the `failed.tsv`, which can be used to retry the upload of only the failed files.

#### Logging uploads

The target log files are declared in the `constants.py` configuration file. 4 log files are available:

`LOG_DIR` root folder where the following log files will be written to

`LOG_FILE_PATH` logs all responses from the Filerobot uploaders 

`UPLOADED_UUIDS_PATH` logs all Filerobot file UUIDs of successfully uploaded files 

`LOG_FAILED_PATH` logs failed upload responses, one file per failed upload response 

`LOG_RETRY_FAILED_PATH` combines the responses of all failed uploads in one file

It is recommended to delete all log files before starting a new migration.