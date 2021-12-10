# Include standard modules
import shutil
import glob
import json
import os
import subprocess
import sys
import time
import distutils.spawn
import urllib
import logging
import random

from threading import Timer, Thread
from urllib.parse import urlparse
from constants import VERSION, LOG_DIR, LOG_FILE_PATH, UPLOADED_UUIDS_PATH, LOG_FAILED_PATH, LOG_RETRY_FAILED_PATH
from string import digits, ascii_uppercase


### LOGGER

logger = logging.getLogger('logger')
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler(LOG_RETRY_FAILED_PATH)
formatter    = logging.Formatter('%(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

uploaded_uuid_logger = logging.getLogger('uploaded_uuid')
uploaded_uuid_logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler(UPLOADED_UUIDS_PATH)
formatter    = logging.Formatter('%(message)s')
file_handler.setFormatter(formatter)
uploaded_uuid_logger.addHandler(file_handler)

### FUNCTIONS

def parse_failed_file_to_cmd(failed_file):
    f = open(failed_file, "r")
    file_lines = f.readlines()
    if len(file_lines) == 0:
        return None
    first_line = file_lines[0]
    if first_line[:7] != "COMMAND":
        return None

    command_str = first_line[8:]
    try:
        cmd = eval(command_str)
        return cmd
    except Exception as e:
        print("Error: %s" % str(e))
        return None

def rand_string(length, char_set=digits + ascii_uppercase):
    return ''.join( random.choice(char_set) for _ in range(length) )

def process_output_processing(process_stdout, line, cmd, to_retry_queue, is_retry = False):
    global uploaded_uuid_logger

    data_output = process_stdout.read().decode("utf-8")
    try:
        logger.info("line: %s" % line)
        logger.info(data_output)
        logger.info("")
    except Exception as e:
        raise Exception("Failed to log after process done: %s" % str(e))

    if data_output[:7] == "SUCCESS":
        data = json.loads(data_output[9:])
        files_uuids = [file["uuid"] for file in data["files"]]
        uploaded_uuid_logger.info("\n".join(files_uuids))

        shutil.move(line, "%s/retry-success/" % LOG_DIR)
    else:
        if not is_retry:
            to_retry_queue.append((line, cmd))
        else:
            failed_file_path = LOG_FAILED_PATH + "-retried-" + rand_string(10) + ".log"
            try:
                f = open(failed_file_path, "w")
                f.write(f"COMMAND:{cmd}\n")
                f.write("\n\n")
                f.write("OUTPUT:\n")
                f.write(data_output)
                f.close()
            except Exception as e:
                raise Exception("Failed to log the failed upload to file %s:\n %s" % (failed_file_path, str(e)))

def process_retry_cmd(cmd, failed_file, log_threads, to_retry_one_more_queue):
    print(f"Running command: {cmd}")
    print(f"Uploading ... 🚀")
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    timer = Timer(50, process.kill)
    try:
        timer.start()
    finally:
        timer.cancel()

    thread = Thread(target = process_output_processing, args = (process.stdout, failed_file, cmd, to_retry_one_more_queue))
    thread.start()
    log_threads.append(thread)

### LIST FAILED QUERIES

failed_list = glob.glob('%s*' % LOG_FAILED_PATH)

retry_threads = []
log_threads = []
to_retry_one_more_queue = []
for failed_file in failed_list:
    cmd = parse_failed_file_to_cmd(failed_file)

    if cmd is None:
        print("Skip %s" % failed_file)
        continue

    thread = Thread(target = process_retry_cmd, args = (cmd, failed_file, log_threads, to_retry_one_more_queue))
    thread.start()
    retry_threads.append(thread)

    time.sleep(0.5)

print("=========")
print("Currently having %s log threads" % len(log_threads))
print("and %s retry threads still running" % len(retry_threads))
print("=========")

print("🟨 Waiting all logs threads done...")
for thread in log_threads:
    thread.join()

print("🟨 Waiting all retry threads done...")
for thread in retry_threads:
    thread.join()

if len(to_retry_one_more_queue) > 0:
    print("=========")
    print("🟧 There are %s requests failed, now we retry one by one, with time wait between requests == 0.8" % len(to_retry_one_more_queue))
    print("=========")

    retry_logs_threads = []
    retry_failed = []
    for line, cmd in to_retry_one_more_queue:
        print(f"Running command: {cmd}")
        print(f"Uploading ... 🚀")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        timer = Timer(50, process.kill)
        try:
            timer.start()
        finally:
            timer.cancel()

        thread = Thread(target = process_output_processing, args = (process.stdout, line, cmd, retry_failed, True))
        thread.start()
        retry_logs_threads.append(thread)
        time.sleep(0.8)
    print("🟧 Waiting all retry logs threads done...")
    for thread in retry_logs_threads:
        thread.join()

print("🟩 OK all good!")




