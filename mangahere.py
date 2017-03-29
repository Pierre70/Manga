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


def mangahere(url, download_chapters,args):
  html  = get_html(url)
  global last

  series    = title(re.search('<h1 class="title"><span class="title_icon"></span>(.*?)</h1>', html.replace('\n', '')).group(1))
  status    = re.search('<li><label>Status:</label>(.*?)<', html.replace('\n', '')).group(1)
  author    = ', '.join(re.findall('<a.*?>(.*?)</a>', re.search('<li><label>Author\\(?s?\\)?:</label>(.*?)</li>', html.replace('\n', '')).group(1)))
  tags      = re.search('<li><label>Genre\\(s\\):</label>(.*?)</li>', html).group(1).split(', ')
  for j in range(len(tags)):
    for k in tag_dict:
      tags[j] = re.sub(k, tag_dict[k], tags[j])
  chapters  = []

  for j in re.findall('<li>\\s*<span class=\"left\">\\s*(.*?\\d{4}</span>)\\s*</li>', html, re.DOTALL|re.MULTILINE)[::-1]:
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
      img_url   = re.sub('001.([A-Za-z]{3})', '{:03}.\\1', re.search('<a.*?>\\s*<img[^<]*?src=\"(.*?)\".*?>\\s*</a>', chap_html, re.DOTALL|re.MULTILINE).group(1))
      if '{:03}' not in img_url:
        img_url   = re.sub('01.([A-Za-z]{3})', '{:02}.\\1', img_url)
      pages     = max([int(i) for i in re.findall('<option value=\".*?\".*?>(\\d+)</option>', chap_html)])
      b_links    = {float(i[1]):i[0] for i in re.findall('<option value=\"(.*?)\".*?>(\\d+)</option>', chap_html)}
      b_links    = [b_links[i+1] for i in range(pages)]
      links      = [img_url.format(i+1) for i in range(pages)]

      chapters.append({'name':name, 'links':links, 'backup_links':b_links, 'date':date, 'pages':pages, 'num':num})

  if chapters:
    function_name(chapters, series, tags, author, status,args)


