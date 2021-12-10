# Include standard modules
import argparse
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
from constants import VERSION, LOG_FILE_PATH, UPLOADED_UUIDS_PATH, LOG_FAILED_PATH, DEFAULT_INPUT_FILE
from string import digits, ascii_uppercase


### LOGGER

logger = logging.getLogger('logger')
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler(LOG_FILE_PATH)
formatter    = logging.Formatter('%(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

uploaded_uuid_logger = logging.getLogger('uploaded_uuid')
uploaded_uuid_logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler(UPLOADED_UUIDS_PATH)
formatter    = logging.Formatter('%(message)s')
file_handler.setFormatter(formatter)
uploaded_uuid_logger.addHandler(file_handler)

def extract_name(url, extension=False):
    """
    Extract file name from the URL
    Can include or exclude the extension of the file
    return: filename
    """
    filename = os.path.basename(urlparse(url).path)

    if not extension:
        filename = os.path.splitext(filename)[0]

    return filename


def sanitize_url(url):
    # add protocol if missing)
    if not url.startswith("http"):
        return f"http://{url}"
    return url


def extract_frb_folder(url):
    """
    Extract the folder from frb address
    :param url: a valid URL from frb resource
    :return: None | string
    """
    # format: /{account_name}/{asset_type}/upload/{path/to/file}

    try:
        # Get only path of the URL and remove the last part
        path_without_filename = os.path.dirname(urlparse(url).path)

        path_segments = [s for s in path_without_filename.split("/") if s != ""]
        actual_folder_path = "/" + "/".join(path_segments[3:])

        return actual_folder_path
    except:
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
    else:
        if not is_retry:
            to_retry_queue.append((line, cmd))
        else:
            failed_file_path = LOG_FAILED_PATH + "-" + rand_string(10) + ".log"
            try:
                f = open(failed_file_path, "w")
                f.write(f"COMMAND:{cmd}\n")
                f.write("\n\n")
                f.write("OUTPUT:\n")
                f.write(data_output)
                f.close()
            except Exception as e:
                raise Exception("Failed to log the failed upload to file %s:\n %s" % (failed_file_path, str(e)))

def upload_files(raw_data, line, log_threads, to_retry_queue):
    filerobot = distutils.spawn.find_executable("filerobot")
    cmd = [filerobot, 'upload', '-m', 'URL', "-w", raw_data]

    if filerobot:
        print(f"Running command: {cmd}")
        print(f"Uploading ... 🚀")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        timer = Timer(50, process.kill)
        try:
            timer.start()
        finally:
            timer.cancel()

        #data_output = process.stdout.read().decode("utf-8")
        thread = Thread(target = process_output_processing, args = (process.stdout, line, cmd, to_retry_queue))
        thread.start()
        log_threads.append(thread)


def save_last_uploaded_line(last_line):
    """
    Saves the number of the last uploaded
    line from the input file
    :param last_line: the current line of the file
    :return:
    """
    file = open(".seek", "w")
    file.write(last_line)
    file.close()


def get_last_uploaded_line() -> int:
    """
    Extracts the number of the last uploaded line
    from input file. if the file does not exist
    it will create it with default value 0
    :return: the line number
    """
    file_path = ".seek"
    line = "0"
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            line = f.read()
            f.close()
    else:
        with open(file_path, "w") as f:
            f.write("0")
            f.close()

    return int(line)


def save_failed_url(line):
    """
    Saves lines that are failed
    after retry uploading
    :param line: url with tags and meta
    :return:
    """
    failed_urls_file = "failed.tsv"
    with open(failed_urls_file, "a+") as f:
        f.write(line)
        f.write(new_line_indent)
        f.close()


def sanitize_rawdata(raw):
    # raw = f"{raw}".replace("'", "\"")
    raw = json.dumps(raw)
    # raw = f"'{raw}'"

    return raw


def sanitize_metadata(meta):
    for k in meta:
        k = k.replace("'", "\"")
        meta[k] = f"{meta[k]}"

    return meta


def execute_upload(raw_data, line, log_threads, to_retry_queue):
    try:
        upload_files(raw_data, line, log_threads, to_retry_queue)
    except:
        try:
            upload_files(raw_data, line, log_threads, to_retry_queue)
        except Exception as e:
            # save the failed line in failed.tsv file
            save_failed_url(lines[i])
            print(f"Exception: ", e.__str__())


def uploading_status(log_file):
    # read the response from the log
    content = ""
    with open(log_file, "r+") as log:
        content += log.read()
        log.close()

    lines = content.split("\n")
    uploaded_files = 0
    files_count = 0
    individual_uploads = 0

    for i in range(len(lines)):
        if "uploaded_files" in lines[i]:
            # split the line to extract number of uploaded files
            uploaded_files += int(lines[i].split("\"uploaded_files\": ")[1].split(",")[0])
        if "files_count" in lines[i]:
            # split the line to extract number of total files
            files_count += int(lines[i].split("\"files_count\": ")[1].split(",")[0])
        # Get the files that are uploaded once at time
        if "SUCCESS: Uploaded successfully" in lines[i]:
            individual_uploads += 1

    files_count += individual_uploads
    uploaded_files += individual_uploads
    failed_uploads = files_count - uploaded_files

    print("Total files: ", files_count)
    print(f"Uploaded: ✅ {uploaded_files} files")
    print(f"Failed uploads: ❌ {failed_uploads} uploads")


if __name__ == '__main__':
    # Define the program description
    help = f"Python script for uploading files from a TSV file via Filerobot CLI. Version: {VERSION}"

    # Initiate the parser with a description
    parser = argparse.ArgumentParser(description=help)
   
    parser.add_argument("--folder", "-f", help="Target root folder for uploading files, the folder hierarchy will be created under this folder according to the file paths in the TSV file (default: /)")
    parser.add_argument("--input_file", "-i", help="the TSV inventory TSV file containing files to be migrated, by default: %s" % DEFAULT_INPUT_FILE)
    parser.add_argument("--files_per_request", "-r", type=int, default=5,
                        help="Number of files to upload per request, default=5")
    parser.add_argument("--wait_btw_request", "-w", type=float, default=0.2,
                        help="Time in seconds between 2 requests, default=0.2")
   
    # Read arguments from the command line
    args = parser.parse_args()

    wait_btw_request = args.wait_btw_request
    files_per_request = args.files_per_request

    base_folder = "/"
    if args.folder:
        base_folder = args.folder
        if not base_folder.startswith("/"):
            folder = f"/{base_folder}"
        print(f"Target folder: {base_folder}")

    input_file = DEFAULT_INPUT_FILE
    if args.input_file:
        input_file = args.input_file

        # Making the script dir
        dir = os.path.dirname(os.path.realpath(__file__))
        # Constructing the path
        full_path = os.path.join(dir, input_file)

        if not os.path.exists(full_path):
            print(f"File {full_path} doesn't exist. Terminating ...")
            sys.exit(1)

        print(f"Input file changed to: {args.input_file}")

    content = ""
    new_line_indent = "\n"
    tab_indent = "\t"

    with open(input_file, 'r+') as f:
        content += f.read()
        f.close()

    lines = content.split(new_line_indent)
    last_line = ''
    start_upload_line = int(get_last_uploaded_line())

    # check if the start line is the last line from the input file and reassign it to 0
    if start_upload_line == len(lines) - 2 or start_upload_line > len(lines):
        start_upload_line = 0

    raw_data = ""
    line_counter = 0
    raw_data_list = []
    last_multiply_line = 0
    log_threads = []
    upload_threads = []
    to_retry_queue = []
    for i in range(start_upload_line, len(lines)):
        if lines[i] == "":
            continue
        line_counter += 1
        secure_url = sanitize_url(lines[i].split(tab_indent)[0])
        tags = json.loads(lines[i].split(tab_indent)[1])
        metadata = json.loads(lines[i].split(tab_indent)[2])

        if metadata is None:
            metadata = {}
        
        # Combine the base folder
        frb_folder = extract_frb_folder(secure_url)

        folder = base_folder
        if frb_folder:
            folder = f"{base_folder}{frb_folder}"
            # Avoid double slashes
            folder = folder.replace("//", "/")

        # extracting file name from the url
        filename = extract_name(secure_url)
        # concatenate the folder with the file name
        name = os.path.join(folder, filename)
        raw = {"name": name, "url": secure_url, "meta": metadata, "tags": tags}
        raw_data_list.append(raw)

        if line_counter % files_per_request == 0 or line_counter == len(lines):
            # prepare the raw data for the cli tool format
            raw_data = sanitize_rawdata(raw_data_list)
            # erase the list scopes
            raw_data = raw_data[1:-1]
            thread = Thread(target = execute_upload, args = (raw_data, lines[i], log_threads, to_retry_queue))
            thread.start()
            upload_threads.append(thread)

            # time between the iterations
            time.sleep(wait_btw_request)

            # save the last line that includes uploading for multiply files
            last_multiply_line = line_counter

            # clear the list for the next iterations
            raw_data_list = []
        elif (len(lines) - line_counter) < files_per_request and len(lines) - last_multiply_line < files_per_request:
            # Here we check if there are files that are missed from the check of files_per_request
            # and will be uploaded one by one

            # prepare the raw data for the cli tool format
            raw_data = sanitize_rawdata(raw_data_list)
            # erase the list scopes
            raw_data = raw_data[1:-1]

            thread = Thread(target = execute_upload, args = (raw_data, lines[i], log_threads, to_retry_queue))
            thread.start()
            upload_threads.append(thread)
            
            # time between the iterations
            time.sleep(wait_btw_request)

            # clear the list for the next iterations
            raw_data_list = []

        last_line = str(i)
        save_last_uploaded_line(last_line)

    print("=========")
    print("Currently having %s log threads" % len(log_threads))
    print("and %s upload threads still running" % len(upload_threads))
    print("=========")

    print("🟨 Waiting all logs threads done...")
    for thread in log_threads:
        thread.join()

    print("🟨 Waiting all uploads threads done...")
    for thread in upload_threads:
        thread.join()

    if len(to_retry_queue) > 0:
        print("=========")
        print("🟧 There are %s requests failed, now we retry one by one, with time wait between requests == 0.5" % len(to_retry_queue))
        print("=========")

        retry_logs_threads = []
        retry_failed = []
        for line, cmd in to_retry_queue:
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
            time.sleep(0.5)
        print("🟧 Waiting all retry logs threads done...")
        for thread in retry_logs_threads:
            thread.join()

    print("🟩 OK all good!")

    # Open log file
    uploading_status(LOG_FILE_PATH)
