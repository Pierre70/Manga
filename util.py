#!/usr/bin/env python3

from os.path import expanduser
import datetime
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


def requestTimeOut(url):
  global session
  try:
    r = session.get(url, timeout=20)
    return r
  except requests.exceptions.Timeout:
    # Maybe set up for a retry, or continue in a retry loop
    raise NameError('TIMEOUT')
  


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

def get_fileName(name):
   print('replacing name'+name)
   return name.replace(
      '?','').replace(
      '!','').replace(
      '/','').replace(
      '\\','').replace(
      '*','').replace(
      '<','').replace(
      '>','').replace(
      ':','').replace(
      '|','')

#Zips directory int a file called zip_file
def zipper(dirName, zip_file):
 
  zip = zipfile.ZipFile(zip_file, 'w', compression=zipfile.ZIP_DEFLATED)
  root_len = len(os.path.abspath(dirName))
  for root, dirs, files in os.walk(dirName):
    archive_root = os.path.abspath(root)[root_len:]
    for f in files:
      fullpath = os.path.join(root, f)
      archive_name = os.path.join(archive_root, f)
      print(archive_name)
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
            print('requesting url :'+img_url)
            r = requestTimeOut(img_url)
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


# When used with update function, createJump groups all downloaded chapter together
def createJump(args):
  finalTmp=tempfile.mkdtemp()
  if hasattr(args,"listzip"):
    listz=args.listzip
    for x in range(0, len(listz)):
      print ("unzipfile...")
      tmpdir = tempfile.mkdtemp()
      zip_ref = zipfile.ZipFile(listz[x], 'r')
      zip_ref.extractall(tmpdir)
      zip_ref.close()
      print ("unzipped")
      print ("moove and rename file")

      for root, dirs, files in os.walk(tmpdir):
        for f in files:
          fullpath = os.path.join(root, f)
          cname=os.path.splitext(os.path.basename(fullpath))[0]
          newNum=int(float(cname))
          newNum=(1000*(x+1))+newNum
          newName=str(newNum)+os.path.splitext(os.path.basename(fullpath))[1]
          print (cname + "->"+newName)
          shutil.move(fullpath,finalTmp+"/"+newName)
      try:
        shutil.rmtree(tmpdir)
      except:
        print ("deletion failled. Please clean your tmp")
      print ("all copy under finalTmp")
      if x%10 == 0 and x>0 :
        print("zip it and clean tmpDir : "+datetime.datetime.now().strftime ("%Y%m%d")+"-"+str(x)+".zip")
        zipper(finalTmp,"Jump"+datetime.datetime.now().strftime ("%Y%m%d")+"-"+str(x)+".zip")
        shutil.rmtree(finalTmp)
        finalTmp=tempfile.mkdtemp()
      else:
        print ("not yet 10 : we continue")
    zipper(finalTmp,"Jump"+datetime.datetime.now().strftime ("%Y%m%d")+"-"+str(x)+".zip")
  else:
    print ("no Zip to groups")


#I'm calling this function name because I can't think of a better name for it
def function_name(chapters, series, tags, author, status,args):
  global xml_list
  global entry
  global last
  global dest
  global url
  
  try:
    last=args.last
  except:
    last=-1
  l = 0
  tmpdir = tempfile.mkdtemp()+'/'

  for i in re.findall('(&#(\\d*?);)', str(series)):
    series = series.replace(i[0], chr(int(i[1])))

  for chapter in chapters:
    for i in re.findall('(&#(\\d*?);)', str(chapter['name'])):
      chapter['name'] = chapter['name'].replace(i[0], chr(int(i[1])))

    print(chapter['backup_links'][0])
    print('  Downloading chapter - {}'.format(chapter['name']))
    f_name  = '{}{}.cbz'.format(tmpdir, re.sub('[$&\\*<>:;?!"/]', '_', chapter['name']))
    chapdir = tempfile.mkdtemp(dir=tmpdir)+'/'

    if args.debug or args.verbose:
      print('  Chapdir - \"{}\"'.format(chapdir))

    try:
      if len(list(set(chapter['links']))) <= 1:
        raise NameError('All_Links_are_the_Same')

      if 'mangareader.net' in args.url or 'mangapanda.com' in args.url:
        raise NameError('Not_Valid_Site_for_Quick_links')

      save(chapter['links'], chapdir, chapter['links'][0].rpartition('.')[2][:3], True)
    except Exception as e:
      print (str(e))
      try:
        print('\r  Slight problem - will use backup solution(may be a bit slower)')
        save(chapter['backup_links'], chapdir, re.search('<a.*?>\\s*<img[^<]*?src=\"(.*?)\".*?>\\s*</a>', get_html(chapter['backup_links'][0]), re.DOTALL|re.MULTILINE).group(1).rpartition('.')[2][:3])
      except:
        with open(error_file, 'a') as f:
          f.write('Series: \"{}\"\nChapter: {}\n\n'.format(series, '{:3.1f}'.format(chapter['num']).zfill(5)))
        print('\n  Failure')
        #shutil.rmtree(tmpdir)
        #raise
        #return

    try:
      zipper(chapdir, f_name)
    except:
      print()

    if args.add_to_calibre:
      add_to_calibre(f_name, [chapter['name'], series, tags, chapter['pages'], chapter['date'], author])
    dest=args.dest
    print ("ma dest : "+dest)
    if dest:
      while dest.endswith('/'):
        dest = dest[:-1]
      dirName = '{}/{}/'.format(dest, re.sub('[$&\\*<>:;/]', '_', series))
      print(dirName)
      if not os.path.isdir(dirName):
        os.makedirs(dirName)
      try: 
        tmpOut= shutil.move(f_name, dirName)
        print ("add zip file")
        if not hasattr(args, 'listzip'):
          print ("add zip to lis")
          listzip=[tmpOut]
          args.listzip=listzip
        else:
          print ("append zip")
          args.listzip.append(tmpOut)
      except:
        print()

    l=chapter['num']

    if not args.debug:
      shutil.rmtree(chapdir)
    if not args.url and not args.update:
      xml_list = xml_list.replace(entry, '<url>{url}</url>\n\t<last>{last}</last>'.format(url=url, last=l))
      entry    = '<url>{url}</url>\n\t<last>{last}</last>'.format(url=url, last=l)

  if args.debug:
    print ("debug will remove temp file. Implement dedicated option to override this way of working")
  try:
    #os.rmdir(tmpdir)
    print()
  except:
    print()
    shutil.rmtree(tmpdir)

  if not args.url and not args.update:
    if status != 'Completed':
      if l > last:
        last = l
      print('   last downloaded chapther = {} or {}'.format(l, last))
      xml_list = xml_list.replace(entry, '<url>{url}</url>\n\t<last>{last}</last>'.format(url=url, last=last))
      entry    = '<url>{url}</url>\n\t<last>{last}</last>'.format(url=url, last=last)
    else:
      xml_list = xml_list.replace(item[0], '')

  if not args.url and not args.update:
    with open(args.list, 'w') as f:
      f.write(xml_list)
  #Writting last chapter downloaded and url from file
  if not  hasattr(args, 'url') or args.url is None :
    print("re read url")
    # no url : read it from chapters
    with open(dirName+"/chapters.txt", 'r') as filo:
      url = filo.readline().replace("\n","")
  else:
    print("url from args")
    url=args.url
  

  lastTxt(dirName+"/chapters.txt",l,last,url)  

def lastTxt(file,l,last,url):
  print (url)
  try:
    if l > last:
      status=open(file,"w")
      status.write(url+"\n")
      status.write(str(l))
  except NameError:
    status=open(file,"w")
    status.write(url+"\n")
    status.write(str(l))


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

