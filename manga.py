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

#Import lib for each scan site supported
from japscan import japscan 
from mangareader import mangareader
from mangahere import mangahere
from batoto import batoto
from mangapanda import mangapanda
from goodmanga import goodmanga

current_dir = os.path.realpath(os.path.dirname(os.path.realpath(sys.argv[0])))

xml_list    = '{}/list.xml'.format(current_dir)
error_file  = '{}/errors.txt'.format(current_dir)
session     = Session()
session.headers.update({'User-agent': 'Mozilla/5.0'})

parser = argparse.ArgumentParser()
parser . add_argument('-x', '--list',           default = xml_list,     type=str, help='Path to xml list containing data - default list.xml in directory of this script')
parser . add_argument('-D', '--debug',          action  = 'store_true',           help='Print extra stuff(verbose) and don\'t remove temp dirs')
parser . add_argument('-v', '--verbose',        action  = 'store_true',           help='Print extra stuff(verbose)')
parser . add_argument('-d', '--dest',           default = '',           type=str, help='Directory to copy files to after download - default nowhere - Only works if url is also specified')
parser . add_argument('-a', '--add-to-calibre', action  = 'store_true',           help='Add book to calibre')
parser . add_argument('-u', '--username',       default = '',           type=str, help='Batoto username')
parser . add_argument('-p', '--password',       default = '',           type=str, help='Batoto password')
parser . add_argument('url',  nargs='?',                                type=str, help='Url of page to download - do not combine with -x/--list')
parser . add_argument('chap', nargs='?',                                type=str, help='Chaptes to download - Only works if url is also specified')
args   = parser.parse_args()

#TODO
#Add support for following websites?
#  http://www.mangago.com/
#  http://www.mangaeden.com/
#  http://mangadoom.com/
#
#Allow multiple urls(sites) for same manga?
#
#Creae support for chaper urls - rather than series?

global tag_dict 
tag_dict= {
  'Slice of Life':  'Nichijou'
}
calibredb_executable = 'calibredb'
lib_path='/home/az/Pictures/.manga/Manga_LN'

def add_to_calibre(f_name, info):
  pid_file = '{}/.pid'.format(os.path.realpath(os.path.dirname(os.path.realpath(sys.argv[0]))))
  wait(pid_file)

  #Get info to add to meta data
  name        =            info[0]
  series      =            info[1]
  tags        =  ', '.join(info[2])
  pages       =            info[3]
  date        =            info[4]
  if info[0]:
    authors   =            info[5]
  else:
    authors   =           'Unknown'

  if lib_path:
    path = ' --library-path \"{}\"'.format(lib_path)
  else:
    path = ''

  #The extra white space is to remove the previose message
  print('\r  Adding to Calibre                ')

  if args.debug:
    print('    {command} add -d -t \"{title}\" -T \"{tags}\" -a \"{aut}\" -s \"{ser}\" -S \"{index}\" \"{f}\" --dont-notify-gui{lib}'.format(
      command=calibredb_executable,
      title=re.sub('([\"$])', '\\\\\\1', name),
      tags=re.sub('([\"$])', '\\\\\\1', tags),
      f=re.sub('([\"$])', '\\\\\\1', f_name),
      ser=re.sub('([\"$])', '\\\\\\1', series),
      index=re.sub('([\"$])', '\\\\\\1', re.search('^.*?([\d]{2,3}\.\d+).*?$', name).group(1)),
      aut=re.sub('([\"$])', '\\\\\\1', authors),
      lib=path))

  #Add file to calibre - at this point only add tags to the meta data
  book_id = os.popen('{command} add -d -t \"{title}\" -T \"{tags}\" -a \"{aut}\" -s \"{ser}\" -S \"{index}\" \"{f}\" --dont-notify-gui{lib}'.format(
    command=calibredb_executable,
    title=re.sub('([\"$])', '\\\\\\1', name),
    tags=re.sub('([\"$])', '\\\\\\1', tags),
    f=re.sub('([\"$])', '\\\\\\1', f_name),
    ser=re.sub('([\"$])', '\\\\\\1', series),
      index=re.sub('([\"$])', '\\\\\\1', re.search('^.*?([\d]{2,3}\.\d+).*?$', name).group(1)),
    aut=re.sub('([\"$])', '\\\\\\1', authors),
    lib=path)).read()

  book_id = re.search('ids:\\s*(\\d+)', book_id).group(1)

  if args.debug:
    print('    {command} set_metadata -f \"#read:false\" -f \"pubdate:{date}\" -f\"#aut:{aut}\" -f \"#pages:{pages}\" {bid} --dont-notify-gui{lib}'.format(
      command=calibredb_executable,
      date=date,
      pages=pages,
      bid=book_id,
      aut=re.sub('([\"$])', '\\\\\\1', authors),
      lib=path))

  #Add all other meta data - authors, pages, characters(pururin only), and series
  verbose = os.popen('{command} set_metadata -f \"#read:false\" -f \"pubdate:{date}\" -f\"#aut:{aut}\" -f \"#pages:{pages}\" {bid} --dont-notify-gui{lib}'.format(
    command=calibredb_executable,
    date=date,
    pages=pages,
    bid=book_id,
    aut=re.sub('([\"$])', '\\\\\\1', authors),
    lib=path)).read()

  if args.debug or args.verbose:
    print('    Info:\n{}'.format(re.sub('(^|\n)', '\\1      ', verbose.strip())))

  #Open up process for others
  os.remove(pid_file)

def main():
  global xml_list
  global entry
  global last
  global dest
  global url
  global session
  
  if not args.url:
    with open(args.list, 'r') as f:
      xml_list  = f.read()

  download_chapters = []
  if args.chap:
    download_chapters = re.split('\\s*,\\s*', args.chap)
    for i in download_chapters:
      if type(i) == str and '-' in i:
        download_chapters.remove(i)
        for j in range(int(float(re.split('\\s*-\\s*', i, maxsplit=1)[0])*10), int(float(re.split('\\s*-\\s*', i, maxsplit=1)[1])*10)+1):
          download_chapters.append(j/10.0)
    download_chapters = sorted(list(set([float(j) for j in download_chapters])))
  print ('heel')
  if not args.url:
    for item in re.findall('(\n?<entry>\\s*(.*?)\\s*</entry>)', xml_list, re.DOTALL|re.MULTILINE):
      session = Session()
      session.headers.update({'User-agent': 'Mozilla/5.0'})
      entry = item[1]
      try:
        url       = re.search('<url>(.*?)</url>',                  entry, re.DOTALL|re.MULTILINE).group(1).strip()
        try:
          last    = float(re.search('<last>\\s*([\\d.,-]+)\\s*</last>',  entry, re.DOTALL|re.MULTILINE).group(1))
        except:
          last    = -1
        try:
          dest    = re.search('<destination>(.*?)</destination>',  entry, re.DOTALL|re.MULTILINE).group(1)
        except:
          if not args.add_to_calibre:
            dest  = './'
          else:
            dest  = ''
      except:
        print('ERROR - line 681\n\n\"{}\"'.format(item[0].replace('\n', '\\n').replace('\t', '\\t')))
        sys.exit(-1)
      print('URL - {}'.format(url))

      if 'mangareader.net' in url:
        mangareader(url, download_chapters,args)
      elif 'mangahere.co' in url:
        mangahere(url, download_chapters),args
      elif 'bato.to' in url:
        batoto(url+'/', download_chapters,args)
      elif 'mangapanda.com' in url:
        mangapanda(url, download_chapters,args)
      elif 'goodmanga.net' in url:
        goodmanga(url, download_chapters,args)
      elif 'japscan.com' in url:
        japscan(url,download_chapters,args)
      with open(args.list, 'w') as f:
        f.write(xml_list)
  else:
    if args.dest:
      dest = args.dest
    elif not args.add_to_calibre:
      dest = './'
    else:
      dest = ''
    args.dest=dest
    url = args.url
    if not download_chapters:
      last = -1
    if 'mangareader.net' in url:
      mangareader(url, download_chapters,args)
    elif 'mangahere.co' in url:
      mangahere(url, download_chapters,args)
    elif 'bato.to' in url:
      batoto(url+'/', download_chapters,args)
    elif 'mangapanda.com' in url:
      mangapanda(url, download_chapters,args)
    elif 'goodmanga.net' in url:
      goodmanga(url, download_chapters,args)
    elif 'japscan.com' in url:
        japscan(url,download_chapters,args)


if __name__ == "__main__":
  main()
