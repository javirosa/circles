#!/usr/bin/python

from __future__ import print_function
import argparse
import os
import errno
import csv
import sys
import math
import subprocess
import time
from PyQt4 import QtCore, QtGui, QtWebKit
import capty
import signal
import uuid

def signal_handler(signal,frame):
    sys.exit(1);
signal.signal(signal.SIGINT,signal_handler)

AUTOITPATH = "C:\Program Files (x86)\AutoIt3\AutoIt3.exe"
IMAGEMAGICKPATH = "C:\Program Files (x86)\ImageMagick-6.8.6-Q16\convert.exe"
NTHREADS=3
RENDEROFFSETX = 8
RENDEROFFSETY = 8

NTFSWHITELIST = "[A-Za-z0-9~!@#$%^&()_-{},.=[]`']"
NTFSBLACKLIST = "\\/:*?\"<>|]"
OSXBLACKLIST="\0/:"
DROPBOXBLACKLIST = "[]/\\=+<>:;\",*."#https://forums.dropbox.com/topic.php?id=23023
CMDBLACKLIST = "\"\'"
BLACKLISt = NTFSBLACKLIST + OSXBLACKLIST + DROPBOXBLACKLIST + CMDBLACKLIST
BLACKLISt = "".join(set(BLACKLISt))
OUTOFBOUNDSCOLR = "#4004"

#TODO Convert these into lists so that we can later call convert in linux. Right now this causes errors when using POpen. Windows has errors when using POpen with shell=true
IMTEXT = " -extent 0x{0[withtextbottom]} -font Arial -pointsize 256 -fill black -strokewidth 1 -stroke black -draw \"text 0,{0[mapbottom]} \'{0[label]}\'\" "
#IMPARMTEXT = "  -font Arial -pointsize 24 -fill black -strokewidth 1 -stroke black -draw \"text 0,{0[mapbottom]} \'{0[label]}\'\" "
IMCIRCLE = " -fill none -strokewidth {0[strokewidth]} -stroke #4004 -draw \"circle {0[centerX]},{0[centerY]} {0[perimeterX]},{0[centerY]}\" " 
IMAGEMAGICKARGS = IMCIRCLE + IMTEXT + "\"{0[inname]}\" -write \"{0[outname1]}\" \"{0[outname2]}\""

#w/2+strokewidth/2+r
#the above requires a label infile and outfile to be present in the format dictionary. TODO: fix the radius and do the caluclaton for it

#Ref: http://msdn.microsoft.com/en-us/library/bb259689.aspx
#2009
#For capturepage
app = QtGui.QApplication(sys.argv) 

def sanitize(name):
    out = ""
    for c in name:
        if c in BLACKLISt:
            c = hex(ord(c))
        out += str(c)
    return out

def metersToPixels(meters,lat,level):
    n = math.cos(lat*math.pi/180)*2*math.pi*6378137
    d = 256*2**level
    return meters/(n/d)

# avoids race condition of directory being created between a check for
# its existence and then its creation:
def make_sure_path_exists(path):
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise

def capturePage(url,outfile):
    c = capty.Capturer(url, outfile)
    c.capture()
    app.exec_()
        
def main():
    #print("pxs:{0}".format(metersToPixels(600,0.01,19)))
    parser = argparse.ArgumentParser(description='Script to take coordinates from a CSV input file and output a series of Google Maps HTML files centered on those coordinates')
    parser.add_argument('-i','--input',help='CSV input filename',default='sites.csv')
    parser.add_argument('-o','--outputdir',
                        help='Output directory (will create if does not exist)',
                        default=os.getcwd(),required=False)
    parser.add_argument('-p','--pixels',help='# of pixels for iframe (in each dimension). Use \'X\' if you would like the dimensions to match the radius.',
                        default='X', required=False);
    parser.add_argument('-r','--radius',default=650,help='radius in meters of circle.')
    parser.add_argument('-l','--level',default=19,help='google maps zoom level')
    parser.add_argument('-s','--skip',default='False',help='skip downloading maps.')

    args = parser.parse_args()

    collectionDir = args.input + "."
    dot = collectionDir.index(".")
    collectionDir = collectionDir[0:dot]
    collectionDir = sanitize(collectionDir)
    outputdir = os.path.join(args.outputdir,collectionDir)
    # check/create output directory
    # (should really test if its writeable too)
    make_sure_path_exists(outputdir);
    make_sure_path_exists(os.path.join(outputdir,"labeled","jpg"));
    make_sure_path_exists(os.path.join(outputdir,"labeled","png"));

    ## debug: show values ##
    print ("Input file: %s" % args.input )
    print ("Output directory: %s" % outputdir )

    # now read the csv file
    with open(args.input, 'rUb') as f, open(os.path.join(outputdir,'listing.csv'),'w') as lst:
        reader = csv.reader(f)
        try:
            headers = reader.next()
            toLabel = []
            for row in reader:
                #name = row[headers.index('name')]#name is ignored?
                lat = row[headers.index('lat')]
                long = row[headers.index('long')]
                if (lat.strip() == "" or long.strip() == "" ): 
                    print("Skipping",name, "due to invalid geopoint.")
                    continue
                id = sanitize(row[headers.index('id')])
                label = sanitize(row[headers.index('label')].strip())
                if (not label):
                    label=id

                # use the ID in the filename:
                outputprefix = 'id[{0}]'.format(id)
                outputhtml = '{0}.html'.format(outputprefix)
                outputhtmlabs = os.path.abspath(os.path.join(outputdir,outputhtml))
                with open(outputhtmlabs,'w') as out:
                    if args.pixels == 'X':
                         pixels = str(2*int(metersToPixels(int(args.radius),float(lat),int(args.level))))
                    else:
                         pixels = args.pixels
                    # write the HTML:
                    # print('ID: {0} Name: {1}\n'.format(id,name),file=out)
                    print('<iframe width="{2}" height="{2}" frameborder="0" scrolling="no" marginheight="0" marginwidth="0" src="https://maps.google.com/maps?f=q&amp;source=s_q&amp;hl=en&amp;geocode=&amp;q={0},{1}&amp;aq=&amp;sll={0},{1}&amp;sspn=0.002789,0.003664&amp;t=h&amp;ie=UTF8&amp;z={3}&amp;ll={0},{1}&amp;output=embed"></iframe>'.format(lat,long,pixels,int(args.level)),file=out)
                print('{0}'.format(outputhtml),file=lst)

                outputImg = os.path.abspath(os.path.join(outputdir,'{0}_{1}.png'.format(outputprefix,label)))
                if (args.skip == 'False') or (not os.path.exists(outputImg)):
                    print("Capturing: \'{0}\'".format(outputhtmlabs))
                    capturePage(outputhtmlabs,outputImg)
                toLabel.append((id,label,outputImg,lat))

#            time.sleep(10) #Make sure the last file has been written to disk
            threads = []
            for id,label,outputImg,lat in toLabel:
                while len(threads) >= NTHREADS:
                    for thread in threads:
                        thread.poll()
                    threads = [thread for thread in threads if thread.returncode == None]
                    time.sleep(.100)

                #call imagemagick to annotate the file
                if os.path.exists(outputImg):
                    if args.pixels == 'X':
                         pixels = str(2*int(metersToPixels(int(args.radius),float(lat),int(args.level))))
                    else:
                         pixels = args.pixels
                    #offset by 8 because the image isn't in the center
                    #offset by 4000/2 becasue we want to have the circle in the center
                    #we are actually using the stroke to create the outline 
                    #so we offset the radius by the strokewidth/2 since 
                    #the stroke is actually put on the center of the perimeter
                    perimeterX = RENDEROFFSETX+int(pixels)/2+int(pixels)/2+metersToPixels(int(args.radius),float(lat),int(args.level)) 
                    centerX = RENDEROFFSETX + int(pixels)/2
                    centerY = RENDEROFFSETY + int(pixels)/2
                    labeledImg1  = os.path.join(outputdir,"labeled","jpg",'id{0}-{1}-labeled.{2}'.format(id,label,"jpg"))
                    labeledImg2  = os.path.join(outputdir,"labeled","png",'id{0}-{1}-labeled.{2}'.format(id,label,"png"))
                    magiccall = IMAGEMAGICKPATH + " " + IMAGEMAGICKARGS.format({'label':label,'inname':outputImg,'outname1':labeledImg1,'outname2':labeledImg2,'strokewidth':int(pixels),'perimeterX':perimeterX,'centerX':centerX,"centerY":centerY,'mapbottom':int(pixels)+RENDEROFFSETY+192,'withtextbottom':int(pixels)+256})
                    print(magiccall)
                    thread = subprocess.Popen(magiccall)
                    threads.append(thread)
            for thread in threads:
                thread.wait()

        except csv.Error as e:
            sys.exit('file %s, line %d: %s' % (args.input, reader.line_num, e))

if __name__ == "__main__":
        main()
