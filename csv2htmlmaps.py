#!/usr/bin/python

from __future__ import print_function
import argparse
import os
import errno
import csv
import sys
import math
import subprocess

STROKEWIDTH = 2000
AUTOITPATH = "C:\Program Files (x86)\AutoIt3\AutoIt3.exe"
IMAGEMAGICKPATH = "C:\Program Files (x86)\ImageMagick-6.8.6-Q16\convert.exe"
IMTEXT = " -font Arial -pointsize 100 -fill white -strokewidth 1 -stroke black -draw \"text 100,100 \'{0}\'\" "
IMCIRCLE = " -fill none -strokewidth {3} -stroke #4004 -draw \"circle 2008,2008 {4},2008\" " #2016 because we actually have a 4000x4000 image and it's offset by 8 and 16
IMAGEMAGICKARGS = "-size 4008x4016" + IMCIRCLE + IMTEXT + "{1} {2}"

#w/2+strokewidth/2+r
#the above requires a label infile and outfile to be present in the format dictionary. TODO: fix the radius and do the caluclaton for it

#Ref: http://msdn.microsoft.com/en-us/library/bb259689.aspx
#2009
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

def main():
    #print("pxs:{0}".format(metersToPixels(600,0.01,19)))
    parser = argparse.ArgumentParser(description='Script to take coordinates from a CSV input file and output a series of Google Maps HTML files centered on those coordinates')
    parser.add_argument('input',help='CSV input filename')
    parser.add_argument('-o','--outputdir',
                        help='Output directory (will create if does not exist)',
                        default=os.getcwd(),required=False)
    parser.add_argument('-p','--pixels',help='# of pixels for iframe (in each dimension)',
                        default=4000, required=False);
    parser.add_argument('-a','--annotate',help='add label and radius markings to images.')

    args = parser.parse_args()

    ## debug: show values ##
    print ("Input file: %s" % args.input )
    print ("Output directory: %s" % args.outputdir )

    # check/create output directory
    # (should really test if its writeable too)
    make_sure_path_exists(args.outputdir);

    # now read the csv file

    with open(args.input, 'rUb') as f, open(os.path.join(args.outputdir,'listing.csv'),'w') as lst:
        reader = csv.reader(f)
        try:
            headers = reader.next()
            for row in reader:
                name = row[headers.index('name')]
                lat = row[headers.index('lat')]
                long = row[headers.index('long')]
                id = row[headers.index('id')]
                label = row[headers.index('label')]

                # use the ID in the filename:
                outputprefix = 'id{0}'.format(id)
                outputhtml = '{0}.html'.format(outputprefix)
                outputhtmlabs = os.path.abspath(os.path.join(args.outputdir,outputhtml))
                with open(outputhtmlabs,'w') as out:
                    # write the HTML:
                    # print('ID: {0} Name: {1}\n'.format(id,name),file=out)
                    print('<iframe width="{2}" height="{2}" frameborder="0" scrolling="no" marginheight="0" marginwidth="0" src="https://maps.google.com/maps?f=q&amp;source=s_q&amp;hl=en&amp;geocode=&amp;q={0},{1}&amp;aq=&amp;sll={0},{1}&amp;sspn=0.002789,0.003664&amp;t=h&amp;ie=UTF8&amp;z=19&amp;ll={0},{1}&amp;output=embed"></iframe>'.format(lat,long,args.pixels),file=out)
                print('{0}'.format(outputhtml),file=lst)

                #call autoit script on the url
                outputpng = os.path.abspath(os.path.join(args.outputdir,'{0}.png'.format(outputprefix)))
                autoitcall = AUTOITPATH + " mapcapture.au3 file://{0} {1}".format(outputhtmlabs,outputpng)
                #print(autoitcall)
                subprocess.call(autoitcall)
                #call imagemagick to annotate the file
                if os.path.exists(outputpng):
                    edgecoord = 8+4000/2+STROKEWIDTH/2+metersToPixels(600,float(lat),19) 
		    #image is offset with capture + width/2 + stroke is on center of edge + radius
                    outfile = os.path.join(args.outputdir,'id{0}labeled.png'.format(id))
                    magiccall = IMAGEMAGICKPATH + " " + IMAGEMAGICKARGS.format(label,outputpng,outfile,STROKEWIDTH,edgecoord)
                    subprocess.call(magiccall)
        except csv.Error as e:
            sys.exit('file %s, line %d: %s' % (args.input, reader.line_num, e))

if __name__ == "__main__":
        main()
