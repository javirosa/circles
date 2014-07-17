#!/usr/bin/python

from __future__ import print_function
import argparse
import os
import errno
import csv
import sys
import math
import subprocess
from PyQt4 import QtCore, QtGui, QtWebKit
import capty
import signal
import uuid
import PIL.Image as Image
import PIL.ImageDraw as ImageDraw
import PIL.ImageFont as ImageFont
import itertools
from CompletionTimer import CompletionTimer
#Modularize
#sites
#site
#house
#Have house plotter 
#Site plotter which adds label and transformer

#TODO
#How are we trying to download
#Add more circles for overlap
#Arrows to outside of circle
#look for color column

#Need to replace capty
#Glovis
#WorldWind
#MODIS
#http://phantomjs.org/
#http://grabz.it/api/python/
#http://docs.seleniumhq.org/projects/webdriver/

#Ideally each site, including house plots, should be done at the same time, instead of loading and saving twice.

def signal_handler(signal,frame):
    sys.exit(1);
signal.signal(signal.SIGINT,signal_handler)

CIRCLERAD = 8 #meters
RENDEROFFSETX = 8 #pixels
RENDEROFFSETY = 8 #pixels

BOUNDARYCOLOR = (255,0,0,256)
XFRMRCOLOR=(255,255,0)
HOUSECOLOR= 'rgb(255,0,0)'
ELECHOUSECOLOR = 'rgb(0,255,255)'
TXTCOLOR = (255,255,255)
TXTBOLDCOLOR = (0,0,0)
TXTSITELABELCOLOR = (0,0,0)
TXTBORDERWIDTH = 3
TXTFONT = ImageFont.truetype("LiberationMono-Regular.ttf",5*CIRCLERAD)
TXTSITEFONT = ImageFont.truetype("LiberationMono-Regular.ttf",256)

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

#For capturepage
app = QtGui.QApplication(sys.argv)

#Ensures that file names are cross platform compatible.
def sanitize(name):
    out = ""
    for c in name:
        if c in BLACKLIST:
            c = hex(ord(c))
        out += str(c)
    return out

def make_sure_path_exists(path):
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise

def imagePath(basepath,imgPrefix,id,label,siteno,format):
    return os.path.join(basepath,imgPrefix,format,'{2}_{0}.{1}'.format('siteno[{0}]_label[{2}]_id[{1}]'.format(siteno,id,label),format,imgPrefix))
    
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
    
#Given the center lat0/long0 and it's map pixel position X0,Y0 find the map pixel position of lat1,long1
def GPSToMapPixels(lat0,long0,lat1,long1,X0,Y0,level):
    #find global pixel coordinates of location 0 and location 1
    globalX0,globalY0=GPSToPixels(lat0,long0,level)
    globalX1,globalY1=GPSToPixels(lat1,long1,level)

    #Take the difference of the two and add them to X0,Y0
    globalXDiff = globalX1-globalX0
    globalYDiff = globalY1-globalY0
    return X0+globalXDiff,Y0+globalYDiff
    
#NOTE pixels is reused for strokewidth and to get the center of the image
#perimeterX is the right most X of the circle on the middle of the map.
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

#Uses the QT based Capty library. 
#However it doesn't work for AJAX pages.
def capturePage(url,outfile):
    c = capty.Capturer(url, outfile)
    c.capture()
    app.exec_()
    
#TODO remove these floating point conversions 
#   All the data should be in the proper format before hand
def house_parms(housePt,housePtHeader,lat,long,centerX,centerY,level):
    latH = float(housePt[housePtHeader.index('latitude')])
    longH = float(housePt[housePtHeader.index('longitude')])
    HCenterX,HCenterY=GPSToMapPixels(lat,long,latH,longH,centerX,centerY,level)
    return latH,longH,HCenterX,HCenterY
    
def draw_disk(draw_canvas,centerX,centerY,radiusPx,color=(255,255,0)):
    draw_canvas.ellipse((centerX-radiusPx/2,centerY-radiusPx/2,centerX+radiusPx/2,centerY+radiusPx/2),fill=color)

def draw_text_with_border(draw_canvas,border_width,X,Y,label,txt_font,txt_color,txt_bold_color):
    for i,j in itertools.product(xrange(-border_width,border_width+1),xrange(-border_width,border_width+1)):
        draw_canvas.text((X+i,Y+j),label,fill=txt_bold_color,font=txt_font)
    draw_canvas.text((X,Y),label,fill=txt_color,font=txt_font)

def draw_visit_site(srcSiteMap,targetSiteMap,offsetX,offsetY,radius,lat,pixels,level):
    mask = Image.new('L',targetSiteMap.size,color=0)
    maskCanvas = ImageDraw.Draw(mask)
    maskDiameter = metersToPixels(radius,lat,level)*2
    maskCanvas.ellipse((RENDEROFFSETX,RENDEROFFSETY,maskDiameter+RENDEROFFSETX,maskDiameter+RENDEROFFSETY),fill=256)
    targetSiteMap.paste(srcSiteMap,(0,0),mask)
    
def main():
    #TODO use docopt
    parser = argparse.ArgumentParser(description='Script to take coordinates from a CSV input file and output a series of Google Maps HTML files centered on those coordinates')
    parser.add_argument('-i','--input',help='CSV input filename',default='sites.csv')
    parser.add_argument('-o','--outputdir',
                        help='Output directory (will create if does not exist)',
                        default=os.getcwd(),required=False)
    parser.add_argument('-p','--pixels',help='# of pixels for iframe (in each dimension). Use \'X\' or leave blank if you would like the dimensions to match the radius.',
                        default='X', required=False);
    parser.add_argument('-r','--radius',default=650,help='radius in meters of off limits circle.')
    parser.add_argument('-l','--level',default=19,help='google maps zoom level')
    parser.add_argument('-s','--skip',default='true',help='skip downloading unlabeled maps if already downloaded.')
    parser.add_argument('-N','--norelabel',default='false',help='do not relabel the transformer sites.')
    parser.add_argument('-H','--houses',default=None,help='plot houses file.')
    parser.add_argument('-c','--png',default='false',help='Use pngs for all labeled sites and house plots instead of just for raw maps.')
    parser.add_argument('-E','--ignoreEmpty',default='false',help='Skip updating household maps with no houses in housees file.')

    args = parser.parse_args()
    args.radius = int(args.radius)
    args.level = int(args.level)  
    args.input = os.path.abspath(args.input)
    args.png = args.png.lower() =='true' 
    args.skip = args.skip.lower() =='true' 
    args.norelabel = args.norelabel.lower() == 'true'
    args.ignoreEmpty = args.ignoreEmpty.lower() == 'true'
    
    collectionDir = args.input + "."
    collectionDir = collectionDir[0:collectionDir.index(".")]
    outputdir = os.path.join(args.outputdir,collectionDir)
    
    # TODO (should really test if its writeable too)
    make_sure_path_exists(outputdir);
    make_sure_path_exists(os.path.join(outputdir,"lbld","jpg"));
    make_sure_path_exists(os.path.join(outputdir,"hshs","jpg"));
    if args.png:
        make_sure_path_exists(os.path.join(outputdir,"lbld","png"));
        make_sure_path_exists(os.path.join(outputdir,"hshs","png"));
    
    print("Input file: %s" % args.input)
    print("Output directory: %s" % outputdir)

    #READ MASTER CSV FILE
    toLabel = []
    with open(args.input, 'rUb') as f:
        master = csv.reader(f)
        try:
            headers = master.next()
            for row in master:
                id = get_variable(row,headers,'id',get_variable(row,headers,'metainstanceid',""))
                siteno = get_variable(row,headers,'siteno',"None")
                label = get_variable(row,headers,'label',id)
                name = get_variable(row,headers,'name',siteno)
                name = siteno + " " + name
                
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
                
                #outputprefix is the name of the raw file in directory of basename of the master list input csv
                # TODO should actually use the same naming scheme as the other images. i.e. use the imagepath function
                outputprefix = 'siteno[{0}]_id[{1}]_label[{2}]'.format(siteno,id,label)
                rawMap = os.path.abspath(os.path.join(outputdir,'raw_{0}.png'.format(outputprefix)))
                toLabel.append((id,label,rawMap,lat,long,siteno,pixels,name,outputprefix))
        except csv.Error as e:
            sys.exit('Error in file %s, line %d: %s' % (args.input, reader.line_num, e))
        
        #Load house data
        ptsHeader = None
        siteNoDict = None
        if args.houses:
            #PLAN load houses
            with open(args.houses, 'rUb') as f:
                housePts = csv.reader(f)
                ptsHeader = housePts.next()
                #PLAN associate site with houses
                #TODO why can't I just make the dict from siteNoGrps?
                allPts = list(housePts)
                allPts.sort(key=lambda x:x[ptsHeader.index('siteno')]) 
                siteNoGrps=itertools.groupby(allPts, lambda x: x[ptsHeader.index('siteno')])
                siteNoDict = {}
                for siteno,grp in siteNoGrps:
                    siteNoDict[siteno]=list(grp)
        
        #Download and save images from google maps
        for _,_,rawMap,_,_,_,_,_,outputprefix in toLabel:
            outputhtml = os.path.abspath(os.path.join(outputdir,'{0}.html'.format(outputprefix)))
            with open(outputhtml,'w') as out:
                print('<iframe width="{2}" height="{2}" frameborder="0" scrolling="no" marginheight="0" marginwidth="0" src="https://maps.google.com/maps?f=q&amp;source=s_q&amp;hl=en&amp;geocode=&amp;q={0},{1}&amp;aq=&amp;sll={0},{1}&amp;sspn=0.002789,0.003664&amp;t=h&amp;ie=UTF8&amp;z={3}&amp;ll={0},{1}&amp;output=embed"></iframe>'.format(lat,long,pixels,args.level),file=out)
            if not (args.skip and os.path.exists(rawMap)):
                print("Capturing: \'{0}\'".format(outputhtml))
                capturePage(outputhtml,rawMap)
        
        ct = CompletionTimer(units=len(toLabel),eventName="lbld")
        for id,_,rawMap,lat,_,siteno,pixels,name,_ in toLabel:
            if os.path.exists(rawMap) and not args.norelabel:
                ct.startEvent()
                #Paint the town red
                extendedImage = Image.open(rawMap)
                boundSite = Image.new(extendedImage.mode,extendedImage.size,color=BOUNDARYCOLOR)
                boundSite = Image.blend(boundSite,extendedImage,.90)
                draw_visit_site(extendedImage,boundSite,RENDEROFFSETX,RENDEROFFSETY,args.radius,lat,pixels,args.level)
                #extend image
                toName = Image.new(extendedImage.mode,(extendedImage.size[0],extendedImage.size[1]+256),color='white')
                toName.paste(boundSite,(0,0))
                #Write the town name
                X,Y=0,int(pixels)+RENDEROFFSETY
                draw_text_with_border(ImageDraw.Draw(toName),0,X,Y,name,TXTSITEFONT,TXTSITELABELCOLOR,TXTSITELABELCOLOR)
                if args.png:
                    toName.save(imagePath(outputdir,"lbld",id,name,siteno,"png"),"PNG")
                toName.save(imagePath(outputdir,"lbld",id,name,siteno,"jpg"),"JPEG")
                ct.stopEvent()
                print(ct)
        #Plot house coordinates        
        if args.houses:        
                #PLAN have each site have its house data
                #PLAN have each site draw its house data onto the siteMap
                ct = CompletionTimer(eventName="hshs",units=len(toLabel))
                for id,_,_,lat,long,siteno,pixels,name,_ in toLabel:
                    if siteNoDict.has_key(siteno):
                        sitePts = siteNoDict[siteno]
                    else:
                        print('Note: No houses to label for siteno: %s'%siteno) 
                        if args.ignoreEmpty: 
                            break
                        sitePts = []
                    ct.startEvent()
                    #load output img
                    labeledImagePath = imagePath(outputdir,"lbld",id,name,siteno,"jpg")
                    if args.png:
                        labeledImagePath = imagePath(outputdir,"lbld",id,name,siteno,"png")
                    labeledImage = Image.open(labeledImagePath)
                    
                    houseDraw  = ImageDraw.Draw(labeledImage)
                    radiusPx = metersToPixels(CIRCLERAD,lat,args.level)
                    centerX,centerY,_ = circleParms(args.radius,lat,pixels,args.level)
                    #Transformer location
                    draw_disk(houseDraw,centerX,centerY,radiusPx,XFRMRCOLOR)  
                    #Plot housenames
                    for pt in sitePts:
                        if 'first' in ptsHeader :
                            pt_label = get_point_label(pt,ptsHeader,"{first} {middle} {last} ({common})")
                        else:
                            pt_label = get_point_label(pt,ptsHeader,"{Name}")
                        try: 
                            latH,longH,HCenterX,HCenterY=house_parms(pt,ptsHeader,lat,long,centerX,centerY,args.level)
                        except ValueError:
                            print("House %s has invalid coordinates."%id)
                            continue
                        if get_point_label(pt,ptsHeader,"{electrified}") == '1':
                            pt_label = pt_label + " [E]"
                        else:
                            pt_label = pt_label + " [U]"
                        draw_text_with_border(houseDraw,3,HCenterX+(1.1)*radiusPx,HCenterY +(-.9)*radiusPx,pt_label,TXTFONT,TXTCOLOR,TXTBOLDCOLOR)
                    #Plot second to ensure that numbers are above anything else
                    for pt in sitePts:
                        pt_label = get_point_label(pt,ptsHeader,"{hhid}")
                        try:
                            latH,longH,HCenterX,HCenterY=house_parms(pt,ptsHeader,lat,long,centerX,centerY,args.level)                        
                        except ValueError:
                            print("House %s in %s have invalid coordinates. Are the column names and format correct?"%(pt_label,siteno,lat,long))
                            continue
                        housecolor = HOUSECOLOR
                        if get_point_label(pt,ptsHeader,"{electrified}") == '1':
                            housecolor = ELECHOUSECOLOR
                        draw_disk(houseDraw,HCenterX,HCenterY,2*radiusPx,housecolor)
                        draw_text_with_border(houseDraw,TXTBORDERWIDTH,HCenterX+ (-.9)*radiusPx,HCenterY+(-.9)*radiusPx,pt_label,TXTFONT,TXTCOLOR,TXTBOLDCOLOR)
                    labeledImage.save(imagePath(outputdir,"hshs",id,name,siteno,"jpg"),"JPEG")
                    if args.png:
                        labeledImage.save(imagePath(outputdir,"hshs",id,name,siteno,"png"),"PNG")
                    ct.stopEvent()
                    print(ct)
                    
if __name__ == "__main__":
    main()
