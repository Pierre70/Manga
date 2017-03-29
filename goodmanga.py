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


def goodmanga(url, download_chapters,args):
  html  = get_html(url)
  global last

  series    = title(re.search('<h1>([^<>]*?)</h1>', html.replace('\n', '')).group(1))
  status    = re.search('<span>Status:</span>\\s*(.*?)\\s*</div>', html.replace('\n', '')).group(1)
  author    = re.search('<span>Authors?:</span>\\s*(.*?)\\s*</div>', html.replace('\n', '')).group(1)
  tags      = re.findall('<a.*?>(.*?)</a>', re.search('<span>Genres:</span>(.*?)\\s*</div>', html, re.DOTALL|re.MULTILINE).group(1))
  for j in range(len(tags)):
    for k in tag_dict:
      tags[j] = re.sub(k, tag_dict[k], tags[j])
  chapters  = []

  while True:
    for j in re.findall('<li>\\s*(.{1,300}?\\d{4}</span>)\\s*</li>', html, re.DOTALL|re.MULTILINE):
      match = re.search('<a.*?>.*?([\\d,.]+)\\s*</a>\\s*<span.*?>\\s*(.*?)\\s*</span>', j, re.DOTALL|re.MULTILINE)
      name  = match.group(2)
      num   = float(match.group(1))
      link  = re.search('href=\"(.*?)\"', j).group(1)
      try:
        date  = datetime.strptime(re.search('([A-Za-z]*? \\d{1,2}, \\d{4})</span>', j).group(1), '%b %d, %Y').strftime('%Y-%m-%d')
      except:
        date  = datetime.datetime.today().strftime('%Y-%m-%d')

      if name:
        name = '{} - {} : {}'.format(series, '{:3.1f}'.format(num).zfill(5), name)
      else:
        name = '{} - {}'.format(series, '{:3.1f}'.format(num).zfill(5))

      if (download_chapters and num in download_chapters) or (not download_chapters and num > last):
        if args.debug or args.verbose:
          print('  Gathering info: \"{}\"'.format(name))
        chap_html  = get_html(link)
        img_url    = re.sub('1.([jpgnig]{3})', '{}.\\1', re.search('</div>\\s*<a.*?>\\s*<img[^<]*?src=\"(.*?)\".*?>\\s*</a>', chap_html, re.DOTALL|re.MULTILINE).group(1))
        pages      = max([int(i) for i in re.findall('<option value=\".*?\".*?>\\s*(\\d+)\\s*</option>', chap_html)])
        b_links    = {float(i[1]):i[0] for i in re.findall('<option value=\"(.*?)\".*?>\\s*(\\d+)\\s*</option>', chap_html)}
        b_links    = [b_links[i+1] for i in range(pages)]
        links      = [img_url.format(i+1) for i in range(pages)]

        chapters.insert(0, {'name':name, 'links':links, 'backup_links':b_links, 'date':date, 'pages':pages, 'num':num})
    match   = re.search('<a href=\"(.*?)\">Next</a>', html)
    if match:
      html  = get_html(match.group(1))
    else:
      break
  if chapters:
    function_name(chapters, series, tags, author, status,args)


