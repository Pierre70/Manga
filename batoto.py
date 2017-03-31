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

batoto_lang = 'English'
global batoto_username
global batoto_password

batoto_username=""
batoto_password=""

def login(username=batoto_username, password=batoto_password):
  global session
  if not username:
    print('It seems like you want to use bato.to, but did not provide a' + \
          'username or password')
    global batoto_username
    batoto_username = username = input('please enter your bato.to username: ')
  if not password:
   global batoto_password
   batoto_password = password = input('please enter your bato.to password: ')
  url = "https://bato.to/forums/"
  html = get_html(url, set_head=True)
  auth_key = re.search('auth_key.*?value=[\'"]([^\'"]+)', html).group(1)
  referer = re.search('referer.*?value=[\'"]([^\'"]+)', html).group(1)
  url = 'https://bato.to/forums/index.php?app=core&module=global&section=login&do=process'
  fields = {
    'anonymous'    : 1,
    'rememberMe'   : 1,
    'auth_key'     : auth_key,
    'referer'      : referer,
    'ips_username' : username,
    'ips_password' : password,
  }
  r = session.post(url, data=fields)
  if 'set-cookie' in r.headers:
    session.headers.update({'cookie':r.headers['set-cookie']})
    return True
  else:
    return False #Login failed

def batoto(url, download_chapters,args):
  batoto_username = args.username
  batoto_password = args.password
  login()
  for i in range(3):
    try:
      html  = get_html(url+'/')
      break
    except:
      if i == 2:
        raise
      else:
        pass

  global last
  global session

  if hasattr(args, 'last'):
    last=args.last

  series    = title(re.search('<h1.*?>[\\s\n]*(.*?)[\\s\n]*</h1>', html, re.DOTALL|re.MULTILINE).group(1))
  status    = re.search('<td.*?>Status:</td>\\s*<td>\\s*(.*?)\\s*</td>', html.replace('\n', '')).group(1)
  author    = ', '.join(re.findall('<a.*?>(.*?)</a>', re.search('<td.*?>\\s*Authors?\\s*:?\\s*</td>\\s*<td>(.*?)</td>', html.replace('\n', '')).group(1)))
  tags      = re.findall('<a.*?>\\s*<span.*?>\\s*([A-Za-z]*?)\\s*</span>\\s*</a>', re.search('<td.*?>\\s*Genres?\\s*:?\\s*</td>\\s*<td>(.*?)</td>', html.replace('\n', '')).group(1))
  for j in range(len(tags)):
    for k in tag_dict:
      tags[j] = re.sub(k, tag_dict[k], tags[j])

  chapters  = []

  for j in re.findall('<tr class=\"row lang_([A-Za-z]*?) chapter_row\".*?>(.*?)</tr>', html, re.DOTALL|re.MULTILINE)[::-1]:
    if j[0]  == batoto_lang:
      match  = re.search('<a href=\"([^\"]*?)\".*?>\\s*<img.*?>\\s*([^\"<>]*)(\\s*:\\s*)?(.*?)\\s*</a>', j[1], re.DOTALL|re.MULTILINE)
      name   = match.group(4)
      m2     = re.search('[Cc]h(ap)?(ter)?\\.?\\s*([Ee]xtra:?)?\\s*([\\d\\.]+)\\s*(-\\s*[\\d\\.]+)?', match.group(2))
      try:
        num    = float(m2.group(4))
      except:
        if args.debug:
          print(j[1])
        raise

      '''
      #TODO
      if m2.group(3):
        if chapters:
          num = chapters[-1]['num'] + .4
        else:
          num = last + .4
      '''
      try:
        vol  = int(re.search('[Vv]ol(ume)?\\.\\s*(\\d+)', match.group(2)).group(2))
      except:
        vol  = 0
      link   = match.group(1)
      uuid   = link.rpartition('#')[2]
      ref    = link.rpartition('/')[0]+'/' + "reader#" + uuid + "_1"
      head   = {'Referer':ref, 'supress_webtoon':'t'}
      link   = link.rpartition('/')[0]+'/'+ 'areader?id='+uuid+'&p=1'
      session.headers.update(head)

      try:
        date = datetime.strptime(re.search('<td.*?>(\\d{2} [A-Za-z]* \\d{4}.*?([Aa][Mm]|[Pp][Mm])).*?</td>', j[1]).group(1), '%d %B %Y - %I:%M %p').strftime('%Y-%m-%dT%H:%M:00')
      except:
        try:
          t  = re.search('(\\d+) [Mm]inutes ago', j[1]).group(1)
        except:
          t  = '1' if re.search('A minute ago', j[1]) else ''
        if t:
          unit = '%M'
        else:
          try:
            t  = re.search('(\\d+) [Hh]ours ago', j[1]).group(1)
          except:
            t  = '1' if re.search('An hour ago', j[1]) else ''
          if t:
            unit = '%H'
          else:
            try:
              t  = re.search('(\\d+) [Dd]ays ago', j[1]).group(1)
            except:
              t  = '1' if re.search('A day ago', j[1]) else ''
            if t:
              unit = '%d'
            else:
              try:
                t  = re.search('(\\d+) [Ww]eeks ago', j[1]).group(1)
              except:
                t  = '1' if re.search('A week ago', j[1]) else ''
              if t:
                unit = '%W'
              else:
                t = '0'
                unit = '%M'
        date = datetime.fromtimestamp((datetime.today()-datetime.strptime(t, unit)).total_seconds()).strftime('%Y-%m-%dT%H:%M:00')

      if name:
        name = '{} - {} : {}'.format(series, '{:3.1f}'.format(num).zfill(5), name)
      else:
        name = '{} - {}'.format(series, '{:3.1f}'.format(num).zfill(5))

      if (download_chapters and num in download_chapters) or (not download_chapters and num > last):
        if args.debug or args.verbose:
          print('  Gathering info: \"{}\"'.format(name))
        chap_html = get_html(link)
        img_url   = re.sub('001\\.([A-Za-z]{3})', '{:03}.\\1', re.search('<div.*?>\\s*<a.*?>\\s*<img[^<]*?src=\"([^\"]*?)\"[^>]*?/>\\s*</div>', chap_html, re.DOTALL|re.MULTILINE).group(1))
        zero = False
        if '{:03}' not in img_url:
          img_url  = re.sub('000\\.([A-Za-z]{3})', '{:03}.\\1', img_url)
          zero = True
        if '{:03}' not in img_url:
          img_url  = re.sub('000\\.([A-Za-z]{3})', '{:03}.\\1', img_url)
          zero = True
          if '{:03}' not in img_url:
            img_url  = re.sub('01\\.([A-Za-z]{3})', '{:02}.\\1', img_url)
            zero = False
            if '{:02}' not in img_url:
              img_url  = re.sub('00\\.([A-Za-z]{3})', '{:02}.\\1', img_url)
              zero = True
        if re.findall('<option value=\".*?\".*?>page (\\d+)</option>', chap_html):
          pages      = max([int(i) for i in re.findall('<option value=\".*?\".*?>page (\\d+)</option>', chap_html)])
        else:
          continue
        b_links    = {float(i[1]):i[0] for i in re.findall('<option value=\"(.*?)\".*?>page (\\d+)</option>', chap_html)}
        b_links    = [b_links[i+1] for i in range(pages)]
        if zero:
          links      = [img_url.format(i) for i in range(pages)]
        else:
          links      = [img_url.format(i+1) for i in range(pages)]

        chapters.append({'name':name, 'links':links, 'backup_links':b_links, 'date':date, 'pages':pages, 'num':num})

  if chapters:
    function_name(chapters, series, tags, author, status,args)


