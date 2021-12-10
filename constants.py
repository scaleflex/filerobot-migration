# Version of the migration tool
VERSION = "0.6"
LOG_DIR="/var/log"
LOG_FILE_PATH="%s/filerobot-migrate.log" % LOG_DIR
UPLOADED_UUIDS_PATH="%s/filerobot-migrate-uploaded-uuids.log" % LOG_DIR
LOG_FAILED_PATH="%s/filerobot-migrate-failed" % LOG_DIR
LOG_RETRY_FAILED_PATH="%s/filerobot-migrate-retry-failed.log" % LOG_DIR

DEFAULT_INPUT_FILE="input.tsv"
