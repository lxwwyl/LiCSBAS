#!/usr/bin/env python3
"""
========
Overview
========
This script makes a GeoTIFF file from an image file (only in float format). The geotiff file can be read by a GIS software (e.g., QGIS) and used to make a figure. NaN will be relaced with 0 as a default. 0 will be regarded as NoDataValue.
Note: gdal must be installed.

v1.3 20200211 Yu Morishita, Uni of Leeds and GSI

=====
Usage
=====
LiCSBAS_flt2geotiff.py -i infile -p dempar [-o outfile] [--keep_nan] [--zero2nan] [--a_nodata nodata_value] [--bigendian]

 -i  Path to input file (float, little endian)
 -p  Path to dem parameter file (EQA.dem_par)
 -o  Output geotiff file (Default: infile[.geo].tif)
 --a_nodata   Assign a specified nodata value in output (Default: 0)
              "None" assigns no value as nodata
 --keep_nan   Don't replace nan with 0 (Default: replace nan with 0)
 --zero2nan   Replace 0 with nan (Default: NOT replace 0 with nan)
 --bigendian  If input file is in big endian

"""

#%% Change log
'''
v1.3 20200211 Yu Morishita, Uni of Leeds and GSI
 - Add --keep_nan, --zero2nan, and --nodata options
 - Change default to replace nan with 0.
v1.2 20200130 Yu Morishita, Uni of Leeds and GSI
 - Add compress option with DEFLATE for gdal
v1.0 20190729 Yu Morishita, Uni of Leeds and GSI
 - Original implementationf
'''


#%% Import
import getopt
import shutil
import os
import sys
import time
import subprocess as subp
import numpy as np
import LiCSBAS_io_lib as io_lib

class Usage(Exception):
    """Usage context manager"""
    def __init__(self, msg):
        self.msg = msg


#%% Main
def main(argv=None):
        
    #%% Check argv
    if argv == None:
        argv = sys.argv
        
    start = time.time()
    ver=1.3; date=20200211; author="Y. Morishita"
    print("\n{} ver{} {} {}".format(os.path.basename(argv[0]), ver, date, author), flush=True)
    print("{} {}".format(os.path.basename(argv[0]), ' '.join(argv[1:])), flush=True)

    #%% Set default
    infile = []
    dempar = []
    outfile = []
    nodata = 0
    endian = 'little'
    keep_nan_flag = False
    zero2nan_flag = False
    gamma_flag = False

    compress_option = ['COMPRESS=DEFLATE', 'PREDICTOR=3']
    ## ['COMPRESS=LZW', 'PREDICTOR=3'], ['COMPRESS=PACKBITS']

    #%% Read options
    try:
        try:
            opts, args = getopt.getopt(argv[1:], "hi:p:o:", ["help", "a_nodata=", "keep_nan", "zero2nan", "bigendian", "gamma"])
        except getopt.error as msg:
            raise Usage(msg)
        for o, a in opts:
            if o == '-h' or o == '--help':
                print(__doc__)
                return 0
            elif o == '-i':
                infile = a
            elif o == '-p':
                dempar = a
            elif o == '-o':
                outfile = a
            elif o == '--a_nodata':
                if a.isdecimal():
                    nodata = int(a)
                elif a == 'None':
                    nodata = None
                else:
                    nodata = float(a)
            elif o == '--keep_nan':
                keep_nan_flag = True
            elif o == '--zero2nan':
                zero2nan_flag = True
            elif o == '--bigendian':
                endian = 'big'
            elif o == '--gamma':
                gamma_flag = True

        if not infile:
            raise Usage('No input file given, -i is not optional!')
        elif not os.path.exists(infile):
            raise Usage('No {} exists!'.format(infile))
        elif not dempar:
            raise Usage('No dempar file given, -p is not optional!')
        elif not os.path.exists(dempar):
            raise Usage('No {} exists!'.format(dempar))

    except Usage as err:
        print("\nERROR:", file=sys.stderr, end='')
        print("  "+str(err.msg), file=sys.stderr)
        print("\nFor help, use -h or --help.\n", file=sys.stderr)
        return 2


    #%% Read info
    if not outfile:
        outfile = infile+'.geo.tif'

    width = int(io_lib.get_param_par(dempar, 'width'))
    length = int(io_lib.get_param_par(dempar, 'nlines'))


    #%% If data2geotiff (GAMMA) is available and --gamma is used
    gamma_comm = 'data2geotiff'
    if shutil.which(gamma_comm) and gamma_flag:
        dtype = '2' # float
        print('Use data2geotiff in GAMMA')
        ### No replacement of nan and 0 is done
        ### Nodata is set to 0

        if endian == 'little':
            ### Make temporary big endian file
            data = io_lib.read_img(infile, length, width, endian=endian)
            data.byteswap().tofile(infile+'.bigendian')
            infile = infile+'.bigendian'

       
        print('{} {} {} {} {}'.format(gamma_comm, dempar, infile, dtype, outfile))
        call=[gamma_comm, dempar, infile, dtype, outfile]
        subp.run(call)
        
        if endian == 'little':
            ### Remove temporary file
            os.remove(infile)
        
        
    #%% if gdal and osr available
    else:
        print('Use gdal module')
        try:
            import gdal, osr
        except:
            print("\nERROR: gdal must be installed.", file=sys.stderr)
            return 1

        width = int(io_lib.get_param_par(dempar, 'width'))
        length = int(io_lib.get_param_par(dempar, 'nlines'))
        
        dlat = float(io_lib.get_param_par(dempar, 'post_lat'))
        dlon = float(io_lib.get_param_par(dempar, 'post_lon'))
        
        lat_n_g = float(io_lib.get_param_par(dempar, 'corner_lat')) #grid reg
        lon_w_g = float(io_lib.get_param_par(dempar, 'corner_lon')) #grid reg
        
        ## Grid registration to pixel registration by shifing half pixel
        lat_n_p = lat_n_g - dlat/2
        lon_w_p = lon_w_g - dlon/2
                
        data = io_lib.read_img(infile, length, width, endian=endian)

        if not keep_nan_flag: ### Replace nan with 0
            data[np.isnan(data)] = 0
        if zero2nan_flag: ### Replace 0 with nan
            data[data==0] = np.nan
    
        driver = gdal.GetDriverByName('GTiff')
        outRaster = driver.Create(outfile, width, length, 1, gdal.GDT_Float32, options=compress_option)
        outRaster.SetGeoTransform((lon_w_p, dlon, 0, lat_n_p, 0, dlat))
        outband = outRaster.GetRasterBand(1)
        outband.WriteArray(data)
        if nodata is not None: outband.SetNoDataValue(nodata)
        outRaster.SetMetadataItem('AREA_OR_POINT', 'Point')
        outRasterSRS = osr.SpatialReference()
        outRasterSRS.ImportFromEPSG(4326)
        outRaster.SetProjection(outRasterSRS.ExportToWkt())
        outband.FlushCache()


    #%% Finish
    elapsed_time = time.time()-start
    hour = int(elapsed_time/3600)
    minite = int(np.mod((elapsed_time/60),60))
    sec = int(np.mod(elapsed_time,60))
    print("\nElapsed time: {0:02}h {1:02}m {2:02}s".format(hour,minite,sec))

    print('\n{} Successfully finished!!\n'.format(os.path.basename(argv[0])))
    print('Output: {}\n'.format(outfile), flush=True)


#%% main
if __name__ == "__main__":
    sys.exit(main())
