#!/usr/bin/python

from __future__ import print_function
import argparse
import os
import errno
import csv
import sys
import math

#Ref: http://msdn.microsoft.com/en-us/library/bb259689.aspx
def metersToPixels(meters,lat,level):
    return meters/((math.cos(lat*math.pi/180)*2*math.pi*6378137)/(256*2**level))

# avoids race condition of directory being created between a check for
# its existence and then its creation:
def make_sure_path_exists(path):
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise

def main():
    parser = argparse.ArgumentParser(description='Script to take coordinates from a CSV input file and output a series of Google Maps HTML files centered on those coordinates')
    parser.add_argument('input',help='CSV input filename')
    parser.add_argument('-o','--outputdir',
                        help='Output directory (will create if does not exist)',
                        default=os.getcwd(),required=False)
    parser.add_argument('-p','--pixels',help='# of pixels for iframe (in each dimension)',
                        default=4000, required=False);


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
                outputfilename = ('id{0}.html'.format(id))
                with open(os.path.join(args.outputdir,outputfilename),'w') as out:
                    # write the HTML:
                    # print('ID: {0} Name: {1}\n'.format(id,name),file=out)
                    print('<iframe width="{2}" height="{2}" frameborder="0" scrolling="no" marginheight="0" marginwidth="0" src="https://maps.google.com/maps?f=q&amp;source=s_q&amp;hl=en&amp;geocode=&amp;q={0},{1}&amp;aq=&amp;sll={0},{1}&amp;sspn=0.002789,0.003664&amp;t=h&amp;ie=UTF8&amp;z=19&amp;ll={0},{1}&amp;output=embed"></iframe>'.format(lat,long,args.pixels),file=out)
                print('{0}'.format(outputfilename),file=lst)
        except csv.Error as e:
            sys.exit('file %s, line %d: %s' % (args.input, reader.line_num, e))

if __name__ == "__main__":
        main()
