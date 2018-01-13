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


def scan_fr(url, download_chapters,args):
  print("getting url "+url)
  html  = get_html(url)
  global last
  if hasattr(args, 'last'):
    last=args.last
  series    = title(re.search('(<h2 class="widget-title" style="display: inline-block;">)([^<]*)(</h2>)', html.replace('\n', '')).group(2))
  print("series: series"+series)
 
#FIND ALL
 # info_gen = re.findall('(<div class="cell">\\s*(.*?)\\s*</div>)', html.replace('\n', '')) ## ['alice@google.com', 'bob@abc.com']

  status="" # not set in this source
  author="" # not set in this source
  tags="" # not set in this source


#  for j in range(len(tags)):
    #for k in tag_dict:
       #tags[j] = re.sub(k, tag_dict[k], tags[j])
  chapters  = []

  # catch chapters list
  chapitres=re.search('(<ul class="chapters">(.*)</ul>)', html.replace('\n','').replace('\r',''))
  # char ? will be used to allow overlapping regex !
  for j in re.findall('<h5 class="chapter-title-rtl">(.*?)</h5>', chapitres.group(1), re.DOTALL|re.MULTILINE)[::-1]:
    print("ligne trouvée:"+j)
    #match = re.search('<a.*[-/]([0-9]+).*',j,re.DOTALL|re.MULTILINE)
    match = re.search('<a.*[-/]([0-9.]+).*>(.*) ([0-9.]+)</a>',j,re.DOTALL|re.MULTILINE)
# re.search('<a.*?>(.*?)([\\d,.]+)\\s*</a>', j, re.DOTALL|re.MULTILINE)
    #name  = match.group(2)
    num   = float(match.group(1))
    link  = "http://"+re.search('href=\".*(www.*?)\"', j).group(1)
    # no name, we use title instead
    name = ''
    date = "01/01/2000"
    serie_short=match.group(2)
    if name:
      name = '{} - {} : {}'.format(serie_short, '{:3.1f}'.format(num).zfill(5), name)
    else:
      name = '{} - {}'.format(series, '{:3.1f}'.format(num).zfill(5))

    if (download_chapters and num in download_chapters) or (not download_chapters and num > last):
      if args.debug or args.verbose:
        print('  Gathering info: \"{}\"'.format(series))
        print('  downloading chapter '+link)
      chap_html = get_html(link)
      links=['']
      image_regex="data-src='(.*?) '"
      links     = [i for i in re.findall(image_regex, chap_html)]

      chapters.append({'name':name, 'links':links, 'backup_links':links, 'date':date, 'pages':len(links), 'num':num})
      args.url=url
  if chapters:
    function_name(chapters, series, tags, author, status,args)





