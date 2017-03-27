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

def request(url, set_head=False):
  global session
  r = session.get(url)
  if set_head and 'set-cookie' in r.headers:
    session.headers.update({'cookie':r.headers['set-cookie']})
  return r

def get_html(url, set_head=False):
  html = request(url, set_head=set_head)
  return html.text.replace(
    '&amp;' , '&' ).replace(
    '&quot;', '\"').replace(
    '&lt;'  , '<' ).replace(
    '&gt;'  , '>' ).replace(
    '\\n'   , '\n').replace(
    '\\t'   , '\t').replace(
    '\\r'   , ''  )

#Zips directory int a file called zip_file
def zipper(dirName, zip_file):
  zip = zipfile.ZipFile(zip_file, 'w', compression=zipfile.ZIP_DEFLATED)
  root_len = len(os.path.abspath(dirName))
  for root, dirs, files in os.walk(dirName):
    archive_root = os.path.abspath(root)[root_len:]
    for f in files:
      fullpath = os.path.join(root, f)
      archive_name = os.path.join(archive_root, f)
      zip.write(fullpath, archive_name, zipfile.ZIP_DEFLATED)
  zip.close()

#Checks if pid is a running process id
def check_pid(pid):
  import platform
  if platform.system() == "Windows":
    import ctypes

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(1, 0, pid)
    if handle == 0:
      return False
    exit_code = ctypes.wintypes.DWORD()
    running = kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)) == 0
    kernel32.CloseHandle(handle)
    return running or exit_code.value == 259

  else:
    try:
      os.kill(pid, 0)
    except OSError:
      return False
    return True

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

#Prits a little spinner while wating for "pid_file" to be deleted or the proces id in "pid_file" to stop working
def wait(pid_file):
  while True:
    try:
      running = True
      spinner = 0
      while running:
        with open(pid_file, 'r') as f:
          if not check_pid(int(f.read().strip())):
            running = False
          else:
            #If another process is using
            spinner += 1
            print('\r  Waiting for process to finish {}'.format(['\\', '|', '/', '-'][spinner%4]), end="", flush=True)
            time.sleep(0.2)
    except:
      #If file does not exist we asume that no one else is adding to calibre - so don't delete the file
      pass

    #Block other proceses(of this program) from editing calibre's library
    #Prevents corruption - trust me, corruptions are not fun when you have a large collection
    with open(pid_file, 'w') as f:
      f.write(str(os.getpid()))

    #This might seem to take up time(I won't argue with that)
    #  and it might seem overly cautious but I am only adding this
    #  after receiving(countless) errors/coruptions
    #
    #If you really want to save time you -might- be able
    #  to lower the number of seconds to wait(default is ~1/3)
    #  but I heavily stress the might and won't guarantee that 1/3 is safe either
    time.sleep(0.3)
    with open(pid_file, 'r') as f:
      if f.read() == str(os.getpid()):
        return

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

def save(links, dirName, img_type, image_links=False):
  print("hello")
  for i in range(len(links)):
    img_name = '{}{:03}.{}'.format(dirName, i+1, img_type)
    if not os.path.exists(img_name.replace('.jpg', '.png')) and not os.path.exists(img_name.replace('.png', '.jpg')):
      print('\r  Downloading {0} of {1}'.format(*(i+1, len(links))), end="")
      if image_links:
        img_url = links[i]
      elif 'bato.to' in links[i]:
        img_url = re.search('<div.*?>\\s*<img[^<]*?src=\"([^\"]*?)\"[^>]*?/>\\s*</div>', get_html(links[i]), re.DOTALL|re.MULTILINE).group(1)
      elif 'goodmanga.net' in links[i]:
        img_url = re.search('</div>\\s*<a.*?>\\s*<img[^<]*?src=\"(.*?)\".*?>\\s*</a>', get_html(links[i]), re.DOTALL|re.MULTILINE).group(1)
      else:
        img_url = re.search('<a.*?>\\s*<img[^<]*?src=\"(.*?)\".*?>\\s*</a>', get_html(links[i]), re.DOTALL|re.MULTILINE).group(1)
      for j in range(2):
        for k in range(7):
          try:
            r = request(img_url)
            if r.status_code != 200:
              raise NameError('No data')
            data = r.content
            break
          except:
            if k % 2 == 1 and 'bato.to' in img_url:
              if img_url.endswith('png'):
                img_url = re.sub('png$', 'jpg', img_url)
                img_name = '{}{:03}.{}'.format(dirName, i+1, 'jpg')
              else:
                img_url = re.sub('jpg$', 'png', img_url)
                img_name = '{}{:03}.{}'.format(dirName, i+1, 'png')
            if j == 1 and k == 6:
              raise
            pass
          time.sleep(1.7)
      with open(img_name, 'wb') as f:
        f.write(data)
  print()

#I'm calling this function name because I can't think of a better name for it
def function_name(chapters, series, tags, author, status):
  global xml_list
  global entry
  global last
  global dest
  global url

  l = 0
  tmpdir = tempfile.mkdtemp()+'/'

  for i in re.findall('(&#(\\d*?);)', str(series)):
    series = series.replace(i[0], chr(int(i[1])))

  for chapter in chapters:
    for i in re.findall('(&#(\\d*?);)', str(chapter['name'])):
      chapter['name'] = chapter['name'].replace(i[0], chr(int(i[1])))
    
    print(chapter['backup_links'][0])
    print('  Downloading chapter - {}'.format(chapter['name']))
    f_name  = '{}{}.cbz'.format(tmpdir, re.sub('[$&\\*<>:;/]', '_', chapter['name']))
    chapdir = tempfile.mkdtemp(dir=tmpdir)+'/'

    if args.debug or args.verbose:
      print('  Chapdir - \"{}\"'.format(chapdir))

    try:
      if len(list(set(chapter['links']))) <= 1:
        raise NameError('All_Links_are_the_Same')

      if 'mangareader.net' in url or 'mangapanda.com' in url:
        raise NameError('Not_Valid_Site_for_Quick_links')

      save(chapter['links'], chapdir, chapter['links'][0].rpartition('.')[2][:3], True)
    except:
      try:
        print('\r  Slight problem - will use backup solution(may be a bit slower)')
        save(chapter['backup_links'], chapdir, re.search('<a.*?>\\s*<img[^<]*?src=\"(.*?)\".*?>\\s*</a>', get_html(chapter['backup_links'][0]), re.DOTALL|re.MULTILINE).group(1).rpartition('.')[2][:3])
      except:
        with open(error_file, 'a') as f:
          f.write('Series: \"{}\"\nChapter: {}\n\n'.format(series, '{:3.1f}'.format(chapter['num']).zfill(5)))
        print('\n  Failure')
        shutil.rmtree(tmpdir)
        raise
        return


    zipper(chapdir, f_name)

    if args.add_to_calibre:
      add_to_calibre(f_name, [chapter['name'], series, tags, chapter['pages'], chapter['date'], author])

    if dest:
      while dest.endswith('/'):
        dest = dest[:-1]
      dirName = '{}/{}/'.format(dest, re.sub('[$&\\*<>:;/]', '_', series))
      if not os.path.isdir(dirName):
        os.makedirs(dirName)
      shutil.move(f_name, dirName)

    l=chapter['num']

    if not args.debug:
      shutil.rmtree(chapdir)
    print()
    if not args.url:
      xml_list = xml_list.replace(entry, '<url>{url}</url>\n\t<last>{last}</last>'.format(url=url, last=l))
      entry    = '<url>{url}</url>\n\t<last>{last}</last>'.format(url=url, last=l)

  if not args.debug:
    try:
      os.rmdir(tmpdir)
    except:
      print()
      shutil.rmtree(tmpdir)

  if not args.url:
    if status != 'Completed':
      if l > last:
        last = l
      print('   last downloaded chapther = {} or {}'.format(l, last))
      xml_list = xml_list.replace(entry, '<url>{url}</url>\n\t<last>{last}</last>'.format(url=url, last=last))
      entry    = '<url>{url}</url>\n\t<last>{last}</last>'.format(url=url, last=last)
    else:
      xml_list = xml_list.replace(item[0], '')

  if not args.url:
    with open(args.list, 'w') as f:
      f.write(xml_list)

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
    function_name(chapters, series, tags, author, status)

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
    function_name(chapters, series, tags, author, status)


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
    function_name(chapters, series, tags, author, status)

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
    function_name(chapters, series, tags, author, status)

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
    function_name(chapters, series, tags, author, status)

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
    function_name(chapters, series, tags, author, status)

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
