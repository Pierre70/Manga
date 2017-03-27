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
from util import request,get_html,zipper,check_pid,wait,save,function_name

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

batoto_username = args.username
batoto_password = args.password

#TODO
#Add support for following websites?
#  http://www.mangago.com/
#  http://www.mangaeden.com/
#  http://mangadoom.com/
#
#Allow multiple urls(sites) for same manga?
#
#Creae support for chaper urls - rather than series?

tag_dict = {
  'Slice of Life':  'Nichijou'
}
calibredb_executable = 'calibredb'
lib_path='/home/az/Pictures/.manga/Manga_LN'
batoto_lang = 'English'

#My own version of title case
#It's like regular title case but some
#  words such as "the" will not be capitalized
#  (unless they are at the beggining)
def title(string):
  return string.title().replace \
    (' The ' , ' the ' ).replace \
    (' Of '  , ' of '  ).replace \
    (' Is '  , ' is '  ).replace \
    (' In '  , ' in '  ).replace \
    (' For'  , ' for'  ).replace \
    (' On '  , ' on '  ).replace \
    (' If '  , ' if '  ).replace \
    (' Than ', ' than ').replace \
    (' No '  , ' no '  ).replace \
    (' Na '  , ' na '  ).replace \
    (' A '   , ' a '   ).replace \
    (' Nomi ', ' nomi ').replace \
    (' Zo '  , ' zo '  ).replace \
    (' To '  , ' to '  ).replace \
    (' Ga '  , ' ga '  ).replace \
    (' Ni '  , ' ni '  ).replace \
    (' Dxd'  , ' DxD'  ).replace \
    (' Xx'   ,  ' xx'  ).replace \
    (' Xxx'  ,  ' xxx' ).replace \
    ('/'     , '-'     ).strip()

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

def mangareader(url, download_chapters):
  html  = get_html(url)
  global last

  series    = title(re.search('<td.*?>\\s*Name:.*?<h2.*?>\\s*(.*?)\\s*</h2>\\s*</td>', html.replace('\n', '')).group(1))
  status    = re.search('<td.*?>\\s*Status:.*?<td>\\s*(.*?)\\s*</td>', html.replace('\n', '')).group(1)
  author    = re.search('<td.*?>\\s*Author:.*?<td>\\s*(.*?)\\s*</td>', html.replace('\n', '')).group(1).partition('(')[0].strip()
  tags      = re.findall('<a.*?><span class="genretags">(.*?)</span></a>', html)
  for j in range(len(tags)):
    for k in tag_dict:
      tags[j] = re.sub(k, tag_dict[k], tags[j])
  chapters  = []

  for j in re.findall('<tr>\\s*<td>\\s*<div.*?</div>(.*?)</tr>', html, re.DOTALL|re.MULTILINE):
    match = re.search('<a.*?([\\d.,-]+)</a>(\\s*:\\s*)(.*?)\\s*</td>', j)
    num   = float(match.group(1))
    name  = match.group(3)
    link  = 'http://www.mangareader.net' + re.search('<a\\s*href=\"(/.*?)\">', j).group(1)
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

def japscan(url, download_chapters):
 
  html  = get_html(url)
  global last
  series    = title(re.search('(<h1 class="bg-header">).*>(.*)</a>(</h1>)', html.replace('\n', '')).group(2))

#FIND ALL
  info_gen = re.findall('(<div class="cell">\\s*(.*?)\\s*</div>)', html.replace('\n', '')) ## ['alice@google.com', 'bob@abc.com']

  status=info_gen[7][1]
  author=info_gen[5][1]
  tags=info_gen[7][1]
  

  for j in range(len(tags)):
    for k in tag_dict:
       print("")
       #tags[j] = re.sub(k, tag_dict[k], tags[j])
  chapters  = []

  # catch chapters list
  chapitres=re.search('(<div id="liste_chapitres">(.*)</div><div class="col-1-3")', html.replace('\n',''))
    
  # print(chapitres.group(1))
  for j in re.findall('<li>(.*?)</li>', chapitres.group(1), re.DOTALL|re.MULTILINE)[::-1]:
    print(j)
    match = re.search('<a.*[-/]([0-9]+).*',j,re.DOTALL|re.MULTILINE)
# re.search('<a.*?>(.*?)([\\d,.]+)\\s*</a>', j, re.DOTALL|re.MULTILINE)
    print(match.group(1))
    #name  = match.group(2)
    num   = float(match.group(1))
    link  = "http://"+re.search('href=\".*(www.*?)\"', j).group(1)
    name = ""+match.group(1)
    date = "01/01/2000"
    #if name:
    #  name = '{} - {} : {}'.format(series, '{:3.1f}'.format(num).zfill(5), name)
    #else:
    #  name = '{} - {}'.format(series, '{:3.1f}'.format(num).zfill(5))

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
        print(link_page.group(1))
        links.append(link_page.group(1))      

      links.remove('')
#     links     = ['http://www.japscan.com' + i for i in re.findall('<option .* value=\"(.*?)\".*?>.*</option>', chap_html)]
      chapters.append({'name':name, 'links':links, 'backup_links':links, 'date':date, 'pages':len(links), 'num':num})
      
  if chapters:
    function_name(chapters, series, tags, author, status,args)


def mangahere(url, download_chapters):
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

def batoto(url, download_chapters):
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

def mangapanda(url, download_chapters):
  html  = get_html(url)
  global last

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

def goodmanga(url, download_chapters):
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
        mangareader(url, download_chapters)
      elif 'mangahere.co' in url:
        mangahere(url, download_chapters)
      elif 'bato.to' in url:
        batoto(url+'/', download_chapters)
      elif 'mangapanda.com' in url:
        mangapanda(url, download_chapters)
      elif 'goodmanga.net' in url:
        goodmanga(url, download_chapters)
      elif 'japscan.com' in url:
        japscan(url,download_chapters)
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
      mangareader(url, download_chapters)
    elif 'mangahere.co' in url:
      mangahere(url, download_chapters)
    elif 'bato.to' in url:
      batoto(url+'/', download_chapters)
    elif 'mangapanda.com' in url:
      mangapanda(url, download_chapters)
    elif 'goodmanga.net' in url:
      goodmanga(url, download_chapters)
    elif 'japscan.com' in url:
        japscan(url,download_chapters)


if __name__ == "__main__":
  main()
