from subprocess import check_output
import json
import sys


def ffprobe(filename):
    try:
        result = check_output(["ffprobe", "-v", "quiet",
                               "-show_format", "-show_streams",
                               "-print_format", "json",
                               filename])
        # yes, decoding sometimes fails too :(
        return json.loads(result.decode('utf-8').strip())

    except:
        print("ffprobe error: ", sys.exc_info()[0], file=sys.stderr)
        return dict()


def guess_series_meta(filename):
    pass
