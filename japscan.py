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


def japscan(url, download_chapters,args):

  html  = get_html(url)
  global last
  if hasattr(args, 'last'):
    last=args.last
  series    = title(re.search('(<h1 class="bg-header">).*>(.*)</a>(</h1>)', html.replace('\n', '')).group(2))

#FIND ALL
  info_gen = re.findall('(<div class="cell">\\s*(.*?)\\s*</div>)', html.replace('\n', '')) ## ['alice@google.com', 'bob@abc.com']

  status=info_gen[7][1]
  author=info_gen[5][1]
  tags=info_gen[7][1]


#  for j in range(len(tags)):
    #for k in tag_dict:
       #tags[j] = re.sub(k, tag_dict[k], tags[j])
  chapters  = []

  # catch chapters list
  chapitres=re.search('(<div id="liste_chapitres">(.*)</div><div class="col-1-3")', html.replace('\n',''))

  # print(chapitres.group(1))
  for j in re.findall('<li>(.*?)</li>', chapitres.group(1), re.DOTALL|re.MULTILINE)[::-1]:
    #match = re.search('<a.*[-/]([0-9]+).*',j,re.DOTALL|re.MULTILINE)
    match = re.search('<a.*[-/]([0-9.]+).*>Scan (.*) ([0-9.]+) VF( : )?(.*)?<.*',j,re.DOTALL|re.MULTILINE)
# re.search('<a.*?>(.*?)([\\d,.]+)\\s*</a>', j, re.DOTALL|re.MULTILINE)
    #name  = match.group(2)
    num   = float(match.group(1))
    link  = "http://"+re.search('href=\".*(www.*?)\"', j).group(1)
    name = match.group(5)
    date = "01/01/2000"
    serie_short=match.group(2)
    if name:
      name = '{} - {} : {}'.format(serie_short, '{:3.1f}'.format(num).zfill(5), name)
    else:
      name = '{} - {}'.format(series, '{:3.1f}'.format(num).zfill(5))

    if (download_chapters and num in download_chapters) or (not download_chapters and num > last):
      if args.debug or args.verbose:
        print('  Gathering info: \"{}\"'.format(series))
      chap_html = get_html(link)
      links=['']
      #HACK : HAVE TO PARSE EACH PAGE TO RETRIEVE IMAGE
      for content in re.findall('<option .* value=\"(.*?)\".*?>.*</option>', chap_html)[::-1]:
        content_html=get_html("http://www.japscan.com"+content)
        search='<div itemscope itemtype="http://schema.org/Article">.*src="(.*[.][a-z]{0,4})"/>'
        link_page=re.search(search,content_html.replace('\n',''),re.MULTILINE)

        link_page=re.search(search,content_html.replace('\n',''),re.MULTILINE)
        links.append(link_page.group(1))

      links.remove('')
      links=list(reversed(links))
      chapters.append({'name':name, 'links':links, 'backup_links':links, 'date':date, 'pages':len(links), 'num':num})
      args.url=url
  if chapters:
    function_name(chapters, series, tags, author, status,args)





