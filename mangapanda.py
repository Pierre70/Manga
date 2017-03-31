#!/usr/bin/env python3

from os.path import expanduser
from datetime import datetime
from requests import Session
import urllib.request
import urllib.parse
import argparse
import tempfile
import logging
import zipfile
import shutil
import time
import sys
import os
import re
from util import request,get_html,zipper,check_pid,wait,save,function_name,title


### TODO : Improve Global var usage. Check Python doc

global tag_dict
tag_dict= {
  'Slice of Life':  'Nichijou'
}

def mangapanda(url, download_chapters,args):
  html  = get_html(url)
  global last

  if hasattr(args, 'last'):
    last=args.last
  series    = title(re.search('<h1.*?>\\s*(.*?)\\s*</h1>', html, re.DOTALL|re.MULTILINE).group(1)).rpartition(' Manga')[0]
  status    = re.search('<td.*?>Status:</td>\\s*<td>\\s*(.*?)\\s*</td>', html.replace('\n', '')).group(1)
  author    = re.search('<td.*?>\\s*Authors?\\s*:?\\s*</td>\\s*<td>(.*?)</td>', html.replace('\n', '')).group(1)
  tags      = re.findall('<a.*?>\\s*<span.*?>\\s*([A-Za-z]*?)\\s*</span>\\s*</a>', re.search('<td.*?>\\s*Genres?\\s*:?\\s*</td>\\s*<td>(.*?)</td>', html.replace('\n', '')).group(1))
  for j in range(len(tags)):
    for k in tag_dict:
      tags[j] = re.sub(k, tag_dict[k], tags[j])
  chapters  = []

  for j in re.findall('<tr>\\s*<td>\\s*<div.*?</div>(.*?)</tr>', html, re.DOTALL|re.MULTILINE):
    match = re.search('<a.*?([\\d.,-]+)</a>(\\s*:\\s*)(.*?)\\s*</td>', j)
    num   = float(match.group(1))
    name  = match.group(3)
    link  = 'http://www.mangapanda.com' + re.search('<a\\s*href=\"(/.*?)\">', j).group(1)
    date  = re.search('<td>(\\d{2})/(\\d{2})/(\\d{4})</td>', j)
    date  = '{:04}-{:02}-{:02}'.format(int(date.group(3)), int(date.group(1)), int(date.group(2)))

    if name:
      name = '{} - {} : {}'.format(series, '{:3.1f}'.format(num).zfill(5), name)
    else:
      name = '{} - {}'.format(series, '{:3.1f}'.format(num).zfill(5))

    if (download_chapters and num in download_chapters) or (not download_chapters and num > last):
      if args.debug or args.verbose:
        print('  Gathering info: \"{}\"'.format(name))
      chap_html = get_html(link)
      links     = ['http://www.mangareader.net' + i for i in re.findall('<option value=\"(.*?)\".*?>\\d+</option>', chap_html)]
      chapters.append({'name':name, 'links':links, 'backup_links':links, 'date':date, 'pages':len(links), 'num':num})

  if chapters:
    function_name(chapters, series, tags, author, status,args)


