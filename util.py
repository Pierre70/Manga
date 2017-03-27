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
def function_name(chapters, series, tags, author, status,args):
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

      if 'mangareader.net' in args.url or 'mangapanda.com' in args.url:
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
    dest=args.dest
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

