#!/usr/bin/env python3
'''
Downloads the Open Know-How (OKH) meta-data files
from the main list,
parses them, and gathers statistics about the used properties within.
'''

from __future__ import print_function
import sys
import re
import os
import glob
from collections import OrderedDict
import csv
import urllib
import urllib.request
import yaml
import click

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

OKH_LIST_URL = 'https://raw.githubusercontent.com/OpenKnowHow/okh-search/master/projects_okhs.csv'

@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option()
def version_token():
    pass

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

class AppURLopener(urllib.request.FancyURLopener):
    version = "Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/47.0.2526.69 Safari/537.36"

urllib._urlopener = AppURLopener()


def download(url, path):
    '''
    Downloads a URL pointing to a file into a local file,
    pointed to by path.
    '''
    print('downloading %s to %s ...' % (url, path))
    if os.path.exists(path):
        os.remove(path)
    urllib._urlopener.retrieve(url, path)

def urlify(s):

    # Remove all non-word characters (everything except numbers and letters)
    s = re.sub(r"[^\w\s]", '', s)

    # Replace all runs of whitespace with a single dash
    s = re.sub(r"\s+", '-', s)

    return s

def download_all_ymls(okh_dir):

    if not os.path.exists(okh_dir):
        os.mkdir(okh_dir)

    csv_file = os.path.join(okh_dir, 'projects.csv')
    download(OKH_LIST_URL, csv_file)

    num_entries = -1
    num_success = 0
    url_bases = {}
    errors = []
    error_url_codes = {}
    error_code_reason = {}
    with open(csv_file, newline='') as csv_h:
        row_i = 0
        for row in csv.reader(csv_h):
            row_i = row_i + 1
            if row_i == 1:
                continue
            name = urlify(row[0])
            url = row[2].strip()
            local_yml_file = os.path.join(okh_dir, name + '-okh.yml')
            try:
                url_parts = urllib.parse.urlparse(url)
                url_base = url_parts.scheme + '://' + url_parts.netloc
                if not url_base in url_bases:
                    url_bases[url_base] = 0
                url_bases[url_base] = url_bases[url_base] + 1
                download(url, local_yml_file)
                num_success = num_success + 1
            except urllib.error.HTTPError as err:
                eprint('WARNING: Failed to download %s to %s, because %s'
                        % (url, local_yml_file, err))
                errors.append((url, err.code, err.reason))
                error_code_reason[err.code] = err.reason
                if not url_base in error_url_codes:
                    error_url_codes[url_base] = {}
                if not err.code in error_url_codes[url_base]:
                    error_url_codes[url_base][err.code] = 0
                error_url_codes[url_base][err.code] = error_url_codes[url_base][err.code] + 1
                continue
        num_entries = row_i -1

    dl_stats = {
            'num_entries': num_entries,
            'num_success': num_success,
            'url_bases': url_bases,
            #'errors': errors,
            'error_url_codes': error_url_codes,
            'error_code_reason': error_code_reason
            }

    return (csv_file, dl_stats)

def increase_key(stats, key):
    if key in stats:
        stats[key] = stats[key] + 1
    else:
        stats[key] = 1

def append_stats(stats, yaml_cont, prefix=''):
    for key, val in yaml_cont.items():
        key_full = prefix + key
        if isinstance(val, dict):
            append_stats(stats, val, key_full + '.')
        elif isinstance(val, list):
            for entry in val:
                if isinstance(entry, str):
                    increase_key(stats, key_full)
                else:
                    append_stats(stats, entry, key_full + '.')
        else:
            increase_key(stats, key_full)

def sort_by_value(dic):
    return OrderedDict(sorted(dic.items(), key=lambda x: x[1]))

@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('stats_file', type=click.Path(), envvar='STATS_FILE', default='okh1_stats.txt')
@click.argument('okh_dir', type=click.Path(), envvar='OHK_DIR', default='okh1_files')
@click.option('--redownload', '-r')
@click.version_option("1.0")
def gather_stats(stats_file='okh1_stats.txt', okh_dir='okh1_files',
        redownload=False):
    '''
    1. Downloads the Open Know-How (OKH) meta-data files
       from the main list,
    2. parses them, and
    3. gathers statistics about the used properties within.
    '''

    if not os.path.exists(okh_dir) or redownload:
        dl_stats = download_all_ymls(okh_dir)
        print(dl_stats)

    stats = {}
    file_i = 0
    for yaml_file in glob.glob(os.path.join(okh_dir, '*-okh.yml')):
        print('')
        #if yaml_file.endswith('/Incubator-okh.yml') or
        #        yaml_file.endswith('/Hand-Pump-Drill-SpringLoaded-okh.yml'):
        #    eprint('WARNING: Skipping invalid file "%s" ...' % yaml_file)
        #    continue
        print('Cleaning up "%s" ...' % yaml_file)
        yaml_file_clean = yaml_file + ".clean"
        with open(yaml_file, 'rt') as fin:
            with open(yaml_file_clean, 'wt') as fout:
                for line in fin:
                    fout.write(line.replace(': @', ': '))
        #os.rename(yaml_file_clean, yaml_file)

        print('Parsing "%s" ...' % yaml_file)
        with open(yaml_file, 'r') as yaml_h:
            # skip first line
            next(yaml_h)
            yaml_cont = yaml.load(yaml_h, Loader=yaml.SafeLoader)
            #yaml_cont = yaml.load(yaml_h, Loader=yaml.CLoader)
            #yaml_cont = yaml.load(yaml_h)
            append_stats(stats, yaml_cont)
            file_i = file_i + 1

    stats = sort_by_value(stats)

    with open(stats_file, 'w') as stats_h:
        for k, v in stats.items():
            stats_h.write('{:40} {}\n'.format(k, v))
        stats_h.write('\n')
        stats_h.write('{:40} {}\n'.format('Parsed-files', file_i))

if __name__ == '__main__':
    gather_stats()
