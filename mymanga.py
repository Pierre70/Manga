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


def mymanga(url, download_chapters,args):
  html  = get_html(url)
  global last
  if hasattr(args, 'last'):
    last=args.last
  series    = title(re.search('(<h2 class="text-border">)(.*)(</h2>)', html.replace('\n', '')).group(2))

#FIND ALL
  info_gen = re.findall('(<div class="cell">\\s*(.*?)\\s*</div>)', html.replace('\n', '')) ## ['alice@google.com', 'bob@abc.com']

  status='default' #info_gen[7][1]
  author='default' #info_gen[5][1]
  tags='default' #info_gen[7][1]
  
  
#  for j in range(len(tags)):
    #for k in tag_dict:
       #tags[j] = re.sub(k, tag_dict[k], tags[j])
  chapters  = []

  # catch chapters list
  chapitres=re.search('(<section class="listchapseries fiche block sep">(.*)</section>)', html.replace('\n',''))
  #print(html.replace('\n',''))  
  #print(chapitres.group(1))
  for j in re.findall('<li>(.*?)</li>', chapitres.group(1), re.DOTALL|re.MULTILINE)[::-1]:
    #match = re.search('<a.*[-/]([0-9]+).*',j,re.DOTALL|re.MULTILINE)
   
    match = re.search('<a.* href=".*/chapitre-([0-9.]+)/',j,re.DOTALL|re.MULTILINE)
# re.search('<a.*?>(.*?)([\\d,.]+)\\s*</a>', j, re.DOTALL|re.MULTILINE)
    #name  = match.group(2)
    num   = float(match.group(1))
    link  = "http://"+re.search('href=\".*(www.*?)\" title', j).group(1)
    name = match.group(1)
    date = "01/01/2000"
    serie_short=series
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
      #print(chap_html)
      for content in re.findall('<option value="(.*[0-9]?)" ', chap_html)[::-1]:
        #print("http://www.hitmanga.eu/"+content)
        content_html=get_html("http://www.hitmanga.eu/"+content)
        #print(content_html.replace('\n','').replace('\r',''))
        search='<table id="picture">.*src="(.*[.][a-z]{0,4}?)" alt=.*</table>'
        #link_page=re.search(search,content_html.replace('\n',''),re.MULTILINE)
        link_page=re.search(search,content_html.replace('\n',''),re.MULTILINE)
        #print(content_html.replace('\n',''))
        try:
          #print(link_page.group(1))
          links.append(link_page.group(1))
        except:
          print('An error occurs, unable to search pages')
          print(content_html.replace('\n',''))
        
      links.remove('')
      links=list(reversed(links))
      chapters.append({'name':name, 'links':links, 'backup_links':links, 'date':date, 'pages':len(links), 'num':num})
      args.url=url
  if chapters:
    function_name(chapters, series, tags, author, status,args)





