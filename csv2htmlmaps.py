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
import PIL.Image as Image
import PIL.ImageDraw as ImageDraw
import PIL.ImageFont as ImageFont
import itertools

#How are we trying to download
#Change output filename label and id
#color based on code (blue,red,orange)
#Add more circles for overlap
#Arrows to outside of circle

#Need to replace capty
#http://phantomjs.org/
#http://grabz.it/api/python/
#http://docs.seleniumhq.org/projects/webdriver/

def signal_handler(signal,frame):
    sys.exit(1);
signal.signal(signal.SIGINT,signal_handler)

AUTOITPATH = "C:\Program Files (x86)\AutoIt3\AutoIt3.exe"
IMAGEMAGICKPATH = "C:\Program Files\ImageMagick-6.8.8-Q16\convert.exe"
#IMAGEMAGICKPATH = "C:\Program Files (x86)\ImageMagick-6.8.6-Q16\convert.exe"
NTHREADS=1
#offset by 8 because the image isn't in the center
CIRCLERAD = 8 #meters
RENDEROFFSETX = 8 #pixels
RENDEROFFSETY = 8 #pixels

XFRMRCOLOR=(255,255,0)
HOUSECOLOR=(255,0,0)
TXTCOLOR = (255,255,255)
TXTBOLDCOLOR = (0,0,0)
TXTFONT = ImageFont.truetype("LiberationMono-Regular.ttf",5*CIRCLERAD)
TXTBOLDFONT = ImageFont.truetype("LiberationMono-Bold.ttf",5*CIRCLERAD)

#These are not totally correct as they are overly restrictive, but it works for my purposes.
NTFSWHITELIST = "[A-Za-z0-9~!@#$%^&()_-{},.=[]`']"
NTFSBLACKLIST = "\\/:*?\"<>|"
FATBLACKLIST = NTFSBLACKLIST+"^"
OSXBLACKLIST="\0/:"
DROPBOXBLACKLIST = "[]/\\=+<>:;\",*."#https://forums.dropbox.com/topic.php?id=23023
CMDBLACKLIST = "\"\'"
BLACKLIST = NTFSBLACKLIST + OSXBLACKLIST + DROPBOXBLACKLIST + CMDBLACKLIST + FATBLACKLIST
BLACKLIST = "".join(set(BLACKLIST))
OUTOFBOUNDSCOLR = "#4004"

#TODO Convert these into lists so that we can later call convert in linux. Right now this causes errors when using POpen. Windows has errors when using POpen with shell=true
IMTEXT = " -extent 0x{0[withtextbottom]} -font Arial -pointsize 256 -fill black -strokewidth 1 -stroke black -draw \"text 0,{0[mapbottom]} \'{0[label]}\'\" "
#IMPARMTEXT = "  -font Arial -pointsize 24 -fill black -strokewidth 1 -stroke black -draw \"text 0,{0[mapbottom]} \'{0[label]}\'\" "
IMCIRCLE = " -fill none -strokewidth {0[strokewidth]} -stroke #4004 -draw \"circle {0[centerX]},{0[centerY]} {0[perimeterX]},{0[centerY]}\" " 
IMAGEMAGICKARGS = IMCIRCLE + IMTEXT + "\"{0[inname]}\" -write \"{0[outname1]}\" \"{0[outname2]}\""

#w/2+strokewidth/2+r
#the above requires a label infile and outfile to be present in the format dictionary. 

#2009
#For capturepage
app = QtGui.QApplication(sys.argv)

def sanitize(name):
    out = ""
    for c in name:
        if c in BLACKLIST:
            c = hex(ord(c))
        out += str(c)
    return out
    
#Ref: http://msdn.microsoft.com/en-us/library/bb259689.aspx
def metersToPixels(meters,lat,level):
    n = math.cos(lat*math.pi/180)*2*math.pi*6378137
    mapSize = 256*2**level
    return meters/(n/mapSize)
    
#Ref: http://msdn.microsoft.com/en-us/library/bb259689.aspx
#not sure about the 0.5
def GPSToPixels(lat,long,level):
    sinLat = math.sin(lat*math.pi/180)
    mapSize = 256*2**level
    pixelX = ((long + 180)/360)*mapSize
    pixelY = (0.5 - math.log((1 + sinLat)/(1 - sinLat)) / (4 * math.pi))*mapSize
    return (pixelX,pixelY)
    
#Given the center lat0/long0 and it's local pixel position X0,Y0 find the local pixel position of lat1,long1
def GPSToLocalPixels(lat0,long0,lat1,long1,X0,Y0,level):
    #find global pixel coordinates of location 0 and location 1
    globalX0,globalY0=GPSToPixels(lat0,long0,level)
    globalX1,globalY1=GPSToPixels(lat1,long1,level)

    #Take the difference of the two and add them to X0,Y0
    globalXDiff = globalX1-globalX0
    globalYDiff = globalY1-globalY0
    return X0+globalXDiff,Y0+globalYDiff

# avoids race condition of directory being created between a check for
# its existence and then its creation:
def make_sure_path_exists(path):
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise

#Uses the QT based Capty library. 
#However it doesn't work for AJAX pages.
def capturePage(url,outfile):
    c = capty.Capturer(url, outfile)
    c.capture()
    app.exec_()
    
#NOTE pixels is reused for strokewidth and to get the center of the image
def circleParms(radius,lat,pixels,level):
    centerX = RENDEROFFSETX + pixels/2
    centerY = RENDEROFFSETY + pixels/2
    #offset by 4000/2 because we want to have the circle in the center
    #we are actually using the stroke to create the outline 
    #so we offset the radius by the strokewidth/2 (pixels/2) since 
    #the stroke is actually along the center of the perimeter line
    perimeterX = centerX+metersToPixels(radius,lat,level)+pixels/2
    return centerX,centerY,perimeterX
    
#TODO is it most accurate to turn it into an int before or after the multiply by 2?
def pixelWidth(radius,lat,level):
    return 2*int(metersToPixels(radius,lat,level))
        
def imagePath(basepath,imgPrefix,id,label,siteno,format):
    return os.path.join(basepath,imgPrefix,format,'{2}_{0}.{1}'.format('siteno[{0}]_label[{2}]_id[{1}]'.format(siteno,id,label),format,imgPrefix))
    
def get_variable(row,headers,colname,alternative):
    var = None
    try:
        var = sanitize(row[headers.index(colname)]).strip()
    except ValueError,ve:
        pass
    if (not var):
        return alternative
    return var

def get_point_label(pt_row,pt_header,fmt_str):
    non_null_pt_row = list(pt_row)
    for k,v in enumerate(pt_row):
        if (not v) or (v.upper().strip() == 'NULL'):
            non_null_pt_row[k]=""
    row = dict(zip(pt_header,non_null_pt_row))
    return fmt_str.format(**row)

#TODO remove these floating point conversions 
#   All the data should be in the proper format before hand
def house_parms(housePt,housePtHeader,lat,long,centerX,centerY,level):
    latH = float(housePt[housePtHeader.index('latitude')])
    longH = float(housePt[housePtHeader.index('longitude')])
    HCenterX,HCenterY=GPSToLocalPixels(lat,long,latH,longH,centerX,centerY,level)
    return latH,longH,HCenterX,HCenterY
    
def draw_ellipse(draw_canvas,centerX,centerY,radiusPx,color=(255,255,0)):
    draw_canvas.ellipse((centerX-radiusPx/2,centerY-radiusPx/2,centerX+radiusPx/2,centerY+radiusPx/2),fill=color)

def draw_text_with_border(draw_canvas,border_width,X,Y,label,txt_color,txt_bold_color,txt_font):
    for i,j in itertools.product(xrange(-border_width,border_width+1),xrange(-border_width,border_width+1)):
        draw_canvas.text((X+i,Y+j),label,fill=txt_bold_color,font=txt_font)
    draw_canvas.text((X,Y),label,fill=txt_color,font=txt_font)

def main():
    #TODO use docopt
    parser = argparse.ArgumentParser(description='Script to take coordinates from a CSV input file and output a series of Google Maps HTML files centered on those coordinates')
    parser.add_argument('-i','--input',help='CSV input filename',default='sites.csv')
    parser.add_argument('-o','--outputdir',
                        help='Output directory (will create if does not exist)',
                        default=os.getcwd(),required=False)
    parser.add_argument('-p','--pixels',help='# of pixels for iframe (in each dimension). Use \'X\' or leave blank if you would like the dimensions to match the radius.',
                        default='X', required=False);
    parser.add_argument('-r','--radius',default=650,help='radius in meters of off limites circle.')
    parser.add_argument('-l','--level',default=19,help='google maps zoom level')
    parser.add_argument('-s','--skip',default='False',help='skip downloading unlabeled maps if already downloaded.')
    parser.add_argument('-H','--houses',default=None,help='plot houses file.')

    args = parser.parse_args()
    args.radius = int(args.radius)
    args.level = int(args.level)  
    args.input = os.path.abspath(args.input)
    
    collectionDir = args.input + "."
    dot = collectionDir.index(".")
    collectionDir = collectionDir[0:dot]
    outputdir = os.path.join(args.outputdir,collectionDir)
    
    # TODO (should really test if its writeable too)
    make_sure_path_exists(outputdir);
    make_sure_path_exists(os.path.join(outputdir,"lbld","jpg"));
    make_sure_path_exists(os.path.join(outputdir,"lbld","png"));
    make_sure_path_exists(os.path.join(outputdir,"hshs","jpg"));
    make_sure_path_exists(os.path.join(outputdir,"hshs","png"));
    
    print("Input file: %s" % args.input)
    print("Output directory: %s" % outputdir)

    #READ MASTER CSV FILE
    toLabel = []
    with open(args.input, 'rUb') as f, open(os.path.join(outputdir,'listing.csv'),'w') as lst:
        reader = csv.reader(f)
        try:
            headers = reader.next()
            for row in reader:
                id = get_variable(row,headers,'id',get_variable(row,headers,'metainstanceid',""))
                siteno = get_variable(row,headers,'siteno',"None")
                label = get_variable(row,headers,'label',id)
                name = get_variable(row,headers,'name',siteno)
                
                lat,long = 0.0,0.0
                try:
                    lat = float(row[headers.index('lat')])
                    long = float(row[headers.index('long')])
                except ValueError, ve:
                    print("Error skipping %s:%s due to invalid geopoint."%(id,label))
                    continue
                
                pixels=0
                if args.pixels == 'X':
                    pixels = pixelWidth(args.radius,lat,args.level)
                else:
                    pixels = int(args.pixels)
                
                # use the ID in the filename:
                #outputprefix is the name of the raw file in directory of basename of the master list input csv
                outputprefix = 'siteno[{0}]_id[{1}]_label[{2}]'.format(siteno,id,label)
                outputhtml = '{0}.html'.format(outputprefix)
                outputhtmlabs = os.path.abspath(os.path.join(outputdir,outputhtml))
                        
                with open(outputhtmlabs,'w') as out:
                    print('<iframe width="{2}" height="{2}" frameborder="0" scrolling="no" marginheight="0" marginwidth="0" src="https://maps.google.com/maps?f=q&amp;source=s_q&amp;hl=en&amp;geocode=&amp;q={0},{1}&amp;aq=&amp;sll={0},{1}&amp;sspn=0.002789,0.003664&amp;t=h&amp;ie=UTF8&amp;z={3}&amp;ll={0},{1}&amp;output=embed"></iframe>'.format(lat,long,pixels,args.level),file=out)
                print('{0}'.format(outputhtml),file=lst)

                outputImg = os.path.abspath(os.path.join(outputdir,'raw_{0}.png'.format(outputprefix)))
                if (args.skip == 'False') or (not os.path.exists(outputImg)):
                    print("Capturing: \'{0}\'".format(outputhtmlabs))
                    capturePage(outputhtmlabs,outputImg)
                toLabel.append((id,label,outputImg,lat,long,siteno,pixels,name))
        except csv.Error as e:
            sys.exit('Error in file %s, line %d: %s' % (args.input, reader.line_num, e))
            
        # Ideally a callback would be used instead of polling the threads continuously
        # Even better stop using image magick
        threads = []
        for id,label,outputImg,lat,long,siteno,pixels,name in toLabel:
            while len(threads) >= NTHREADS:
                for thread in threads:
                    thread.poll()
                threads = [thread for thread in threads if thread.returncode == None]
                time.sleep(.100)

            #call imagemagick to annotate the file
            if os.path.exists(outputImg):
                centerX,centerY,perimeterX = circleParms(args.radius,lat,pixels,args.level)
                
                labeledImg1  = imagePath(outputdir,"lbld",id,name,siteno,"jpg")
                labeledImg2  = imagePath(outputdir,"lbld",id,name,siteno,"png")
                magiccall = IMAGEMAGICKPATH + " " + IMAGEMAGICKARGS.format({'label':name,'inname':outputImg,'outname1':labeledImg1,'outname2':labeledImg2,'strokewidth':int(pixels),'perimeterX':perimeterX,'centerX':centerX,"centerY":centerY,'mapbottom':int(pixels)+RENDEROFFSETY+192,'withtextbottom':int(pixels)+256})
                print("Boundary %s processing."%siteno)
                thread = subprocess.Popen(magiccall)
                threads.append(thread)
        for thread in threads:
            thread.wait()
        
        #Plot house coordinates
        if args.houses:
            #load associated site file
            with open(args.houses, 'rUb') as f:
                housePts = csv.reader(f)
                ptsHeader = housePts.next()
                allPts = list(housePts)
                
                #TODO why can't I just make the dict from siteNoGrps?
                allPts.sort(key=lambda x:x[ptsHeader.index('siteno')]) 
                siteNoGrps=itertools.groupby(allPts, lambda x: x[ptsHeader.index('siteno')])
                siteNoDict = {}
                for siteno,grp in siteNoGrps:
                    siteNoDict[siteno]=list(grp)
                
                for id,label,outputImg,lat,long,siteno,pixels,name in toLabel:
                    #load output img
                    houseImagePNG = Image.open(imagePath(outputdir,"lbld",id,name,siteno,"png"))
                    houseDrawPNG  = ImageDraw.Draw(houseImagePNG)
                    radiusPx = metersToPixels(CIRCLERAD,lat,args.level)
                    centerX,centerY,_ = circleParms(args.radius,lat,pixels,args.level)
                    
                    #Transformer location
                    draw_ellipse(houseDrawPNG,centerX,centerY,radiusPx,XFRMRCOLOR)  
                    sitePts = siteNoDict[siteno]
                    #Plot housenames
                    for pt in sitePts:
                        pt_label = get_point_label(pt,ptsHeader,"{first} {middle} {last} ({common})")
                        latH,longH,HCenterX,HCenterY=house_parms(pt,ptsHeader,lat,long,centerX,centerY,args.level)
                        draw_text_with_border(houseDrawPNG,3,HCenterX+(1.1)*radiusPx,HCenterY +(-.9)*radiusPx,pt_label,TXTCOLOR,TXTBOLDCOLOR,TXTFONT)
                    #Plot second to ensure that numbers are above anything else
                    for pt in sitePts:
                        pt_label = get_point_label(pt,ptsHeader,"{hhid}")
                        latH,longH,HCenterX,HCenterY=house_parms(pt,ptsHeader,lat,long,centerX,centerY,args.level)
                        draw_ellipse(houseDrawPNG,HCenterX,HCenterY,2*radiusPx,HOUSECOLOR)
                        draw_text_with_border(houseDrawPNG,3,HCenterX+ (-.9)*radiusPx,HCenterY+(-.9)*radiusPx,pt_label,TXTCOLOR,TXTBOLDCOLOR,TXTFONT)
                        
                    houseImagePNG.save(imagePath(outputdir,"hshs",id,name,siteno,"png"),"PNG")
                    houseImagePNG.save(imagePath(outputdir,"hshs",id,name,siteno,"jpg"),"JPEG")
                    
if __name__ == "__main__":
        main()
