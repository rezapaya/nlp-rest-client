"""
This script polls S3 to find new text batches to parse.
"""

from boto import connect_s3
from boto.s3.key import Key
from boto.exception import S3ResponseError
from time import time, sleep
import tarfile
import os
import shutil
import sys
import subprocess

SIG = str(os.getpid()) + '_' + str(int(time()))
TEXT_DIR = '/tmp/text/'
XML_DIR = '/tmp/xml/'
SIG_DIR = '/tmp/text/'+SIG
FILELIST_DIR = '/tmp/filelist/'
BUCKET_NAME = 'nlp-data'
CORENLP_DIR = '/home/ubuntu/corenlp/'

JARS = ['stanford-corenlp-3.2.0.jar', 'stanford-corenlp-3.2.0-models.jar', 
        'xom.jar', 'joda-time.jar', 'jollyday.jar']

conn = connect_s3()
bucket = conn.get_bucket(BUCKET_NAME)

while True:
    # start with fresh directories
    for directory in [TEXT_DIR, XML_DIR, FILELIST_DIR]:
        if not os.path.exists(directory):
            os.mkdir(directory)

    for key in bucket.list('text_events'):
        if not key.key.endswith('.tgz'):
            # we only want gz-formatted tarballs
            continue

        old_key_name = key.key
        # found a tar file, now try to capture it via move
        try:
            new_key_name = '/parser_processing/'+SIG+'.tgz'
            key.copy(bucket, new_key_name)
            key.delete()
            
        except S3ResponseError:
            # we probably hit our race condition -- not to worry!
            # we'll just take the next key.
            continue

        # now that it's been moved, pull it down
        newkey = Key(bucket)
        newkey.key = new_key_name
        newfname = SIG_DIR+'.tgz'
        newkey.get_contents_to_filename(newfname)
        
        # untar that sucker
        tar = tarfile.open(newfname)
        tar.extractall(SIG_DIR)

        # write file list
        filelistname = FILELIST_DIR+'/'+SIG
        with open(filelistname, 'w') as filelist:
            filelist.write("\n".join(SIG_DIR+'/'+f for f in os.listdir(SIG_DIR)))

        # send it to corenlp
        returncode = subprocess.call(['java', '-cp', ':'.join([CORENLP_DIR+j for j in JARS]),
                                      'edu.stanford.nlp.pipeline.StanfordCoreNLP', 
                                      '-filelist',  filelistname, 
                                      '-outputDirectory', XML_DIR,
                                      '-threads', '8'],
                                     stdout=subprocess.STDOUT,
                                     stederr=subprocess.STDOUT)
        
        if returncode != 0:
            # back to queue
            returnkey = Key(bucket)
            returnkey.key = old_key_name
            returnkey.set_contents_from_file(newfname)
            newkey.delete()
            # we should probably report this. for now, die.
            sys.exit()

        # send xml to s3, keep track of data extraction events
        data_events = []
        for xmlfile in os.listdir(XML_DIR):
            key = Key(bucket)
            new_key = '/xml/%s/%s.xml' % tuple(xmlfile.replace('.xml', '').split('_'))
            key.key = new_key
            data_events += [new_key]
            key.set_contents_from_filename(XML_DIR+'/'+xmlfile)

        # write events to a new file
        event_key = Key(bucket)
        event_key.key = '/data_events/'+SIG
        event_key.set_contents_from_string("\n".join(data_events))

        # delete remnant data with extreme prejudice
        newkey.delete()
        shutil.rmtree(XML_DIR)
        shutil.rmtree(TEXT_DIR)
        shutil.rmtree(FILELIST_DIR)

        # at this point we will need to get the list of keys all over again
        # yes this is actually the most sensible way to handle it based on the resultset api.
        break
    sleep(30) # don't want to bug the crap outta amazon
