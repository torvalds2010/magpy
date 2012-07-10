#!/usr/bin/env python
"""
MagPy-getabs: Downloads absolute files from specified ftp-server and analyses the data.
Returns a data stream with either absolute avlues and variometer differences

Written by Roman Leonhardt 2011/2012
Version 1.0 (from the 23.02.2012)
Procedure:
 1. Contact ftp-server
 2. Get file list with absolute data
 3. Compare to local file list
 4. Download all new files to a working directory
 5. Analyze data
    a) if successful append result and move file to preliminary archive
        three directories:
        1) Analysis
        2) Archive-preliminary (tested by program)
        3) Archive-final (tested by observer)
    b) if not leave file in Analysis and send e-mail to obs
 6. Delete files from FTP Server (maybe at step 4
 7. Recalculate baseline and check for its quasi-final character

"""

from core.magpy_stream import *
from core.magpy_transfer import *

MAGPY_SUPPORTED_ABSOLUTES_FORMATS = ['MAGPYABS','UNKNOWN']
ABSKEYLIST = ['time', 'hc', 'vc', 'res', 'f', 'mu', 'md', 'expectedmire', 'varx', 'vary', 'varz', 'varf', 'var1', 'var2']

miredict = {'UA': 290.0, 'MireTower':41.80333,'MireChurch':51.1831,'MireCobenzl':353.698}

class AbsoluteDIStruct(object):
    def __init__(self, time=0, hc=float(nan), vc=float(nan), res=float(nan), f=float(nan), mu=float(nan), md=float(nan), expectedmire=float(nan),varx=float(nan), vary=float(nan), varz=float(nan), varf=float(nan), var1=float(nan), var2=float(nan), temp=float(nan), person='', di_inst='', f_inst=''):
        self.time = time
        self.hc = hc
        self.vc = vc
        self.res = res
        self.f = f
        self.mu = mu
        self.md = md
        self.expectedmire = expectedmire
        self.varx = varx
        self.vary = vary
        self.varz = varz
        self.varf = varf
        self.var1 = var1
        self.var2 = var2
        self.temp = temp
        self.person = person
        self.di_inst = di_inst
        self.f_inst = f_inst

    def __repr__(self):
        return repr((self.time, self.hc, self.vc, self.res, self.f, self.mu, self.md, self.expectedmire, self.varx, self.vary, self.varz, self.varf, self.var1, self.var2))


class AbsoluteData(object):
    """
    Creates a list object from input files /url data
    data is organized in columns

    keys are column identifier:
    key in keys: see ABSKEYLIST

    The following application methods are provided:
    - stream.calcabs(key) -- returns stream (with !var2! filled with aic values)

    Supporting internal methods are:
    - self._calcdec() -- calculates dec
    - self._calcinc() -- calculates inc
    
    """
    def __init__(self, container=None, header=None):
        if container is None:
            container = []
        self.container = container
        if header is None:
            header = {}
        self.header = header

    # ----------------
    # Standard functions and overrides for list like objects
    # ----------------

    def add(self, datlst):
        self.container.append(datlst)

    def __str__(self):
        return str(self.container)

    def __repr__(self):
        return str(self.container)

    def __getitem__(self, index):
        return self.container.__getitem__(index)

    def __len__(self):
        return len(self.container)

    def extend(self,datlst,header):
        self.container.extend(datlst)
        self.header = header

    def sorting(self):
        """
        Sorting data according to time (maybe generalize that to some key)
        """
        liste = sorted(self.container, key=lambda tmp: tmp.time)
        return AbsoluteData(liste, self.header)        

    # ----------------
    # internal methods
    # ----------------

    def _get_max(self, key):
        if not key in ABSKEYLIST:
            raise ValueError, "Column key not valid"
        elem = max(self, key=lambda tmp: eval('tmp.'+key))
        return eval('elem.'+key)


    def _get_min(self, key):
        if not key in ABSKEYLIST:
            raise ValueError, "Column key not valid"
        elem = min(self, key=lambda tmp: eval('tmp.'+key))
        return eval('elem.'+key)


    def _get_column(self, key):
        """
        returns an numpy array of selected columns from Stream
        """
        if not key in ABSKEYLIST:
            raise ValueError, "Column key not valid"

        return np.asarray([eval('elem.'+key) for elem in self])

    def _nan_helper(self, y):
        """Helper to handle indices and logical indices of NaNs. Taken from eat (http://stackoverflow.com/questions/6518811/interpolate-nan-values-in-a-numpy-array)

        Input:
            - y, 1d numpy array with possible NaNs
        Output:
            - nans, logical indices of NaNs
            - index, a function, with signature indices= index(logical_indices),
              to convert logical indices of NaNs to 'equivalent' indices
        Example:
            >>> # linear interpolation of NaNs
            >>> nans, x= nan_helper(y)
            >>> y[nans]= np.interp(x(nans), x(~nans), y[~nans])
        """
        return np.isnan(y), lambda z: z.nonzero()[0]

    def _insert_function_values(self, function,**kwargs):
        """
        Add a function to the selected values of the data stream -> e.g. get baseline
        Optional:
        keys (default = 'x','y','z','f')        
        """
        funckeys = kwargs.get('funckeys')
        offset = kwargs.get('offset')
        if not funckeys:
            funckeys = ['x','y','z','f']
        if not offset:
            offset = 0.0

        for elem in self:
            # check whether time step is in function range
            if function[1] <= elem.time <= function[2]:
                functime = (elem.time-function[1])/(function[2]-function[1])
                for key in funckeys:
                    if not key in KEYLIST[1:15]:
                        raise ValueError, "Column key not valid"
                    fkey = 'f'+key
                    if fkey in function[0]:
                        try:
                            newval = float(function[0][fkey](functime)) + offset
                        except:
                            newval = float('nan')
                        exec('elem.var'+key+' = newval')
                    else:
                        pass
            else:
                pass

        return self

    def _calcdec(self, **kwargs):
        """
        Calculates declination values from input.
        Returns results in terms of linestruct 
        Supports the following optional keywords:
        xstart, ystart - float - default 0.0 - strength of the horizontal component in nT
                       - if variometer is hdf oriented then xstart != 0, ystart = 0 
                       - if baselinecorrected data is used (or dIdD) use xstart = 0, ystart = 0 
        unit - str - default 'deg' - can be either 'deg' or 'gon'
        deltaD - float - default 0.0 - eventual correction factor for declination in angular units (dependent on 'unit')
        usestep - int - use first, second or both of successive measurements
        iterator - int - switch of logging (e.g. vario not present) in case of iterative approach
        """
        plog = PyMagLog()
        xstart = kwargs.get('xstart')
        ystart = kwargs.get('ystart')
        unit = kwargs.get('unit')
        deltaD = kwargs.get('deltaD')
        usestep = kwargs.get('usestep')
        scalevalue = kwargs.get('scalevalue')
        iterator = kwargs.get('iterator')

        scale_x = scalevalue[0]
        scale_y = scalevalue[1]
        scale_z = scalevalue[2]

        if unit=='gon':
            ang_fac = 400./360.
        elif unit == 'rad':
            ang_fac = np.pi/180.
        else:
            ang_fac = 1

        if not iterator:
            iterator = 0

        #drop NANs from input stream - positions
        expmire = self._get_column('expectedmire')
        expmire = np.mean([elem for elem in expmire if not isnan(elem)])
        poslst = [elem for elem in self if not isnan(elem.hc) and not isnan(elem.vc)]
        
        # -- Get mean values for x and y
        # ------------------------------
        meanx, meany = 0.0,0.0
        xcol, ycol = [],[]
        for idx, elem in enumerate(poslst):
            if idx < 9:
                if not isnan(elem.varx):
                    xcol.append(elem.varx)
                if not isnan(elem.vary):
                    ycol.append(elem.vary)
        if len(xcol) > 0:
            meanx = np.mean(xcol)
        if len(ycol) > 0:
            meany = np.mean(ycol)
            
        nr_lines = len(poslst)
        dl1,dl2,dl2tmp,variocorr, variohlst = [],[],[],[],[] # temporary lists
        # -- check, whether inclination and declination values are present:
        if nr_lines < 9:
            linecount = nr_lines
        else:
            linecount = (nr_lines-1)/2

        # -- cylce through declinations measurements:
        for k in range(linecount):
            if (poslst[k].hc > poslst[k].vc):
                val = poslst[k].hc-poslst[k].vc
            else:
                val = poslst[k].hc + (360*ang_fac) - poslst[k].vc
            signum = np.sign(np.tan(val))
            # xstart and ystart are already variometercorrected from iteration step 1 on
            variox = (poslst[k].varx-meanx)*scale_x
            varioy = (poslst[k].vary-meany)*scale_y
            if isnan(variox):
                variox = 0.
            if isnan(varioy):
                varioy = 0.
            hstart = np.sqrt((xstart+variox)**2 + (ystart+varioy)**2)
            if hstart == 0:
                rescorr = 0
            else:
                rescorr = signum * np.arcsin( poslst[k].res / hstart )
            if (xstart+poslst[k].varx) == 0:
                variocorr.append(0)
            else:
                variocorr.append(np.arctan((ystart+varioy)/(xstart+variox)))
            dl1.append( poslst[k].hc*np.pi/(180.0*ang_fac) + rescorr - variocorr[k])

        # use selected steps, default is average....
        for k in range(0,7,2):
            if usestep == 1:
                dl2mean = dl1[k]
            elif usestep == 2:
                dl2mean = dl1[k+1]
            else:
                dl2mean = np.mean([dl1[k],dl1[k+1]])
            dl2tmp.append(dl2mean)
            if dl2mean < np.pi:
                dl2mean += np.pi/2
            else:
                dl2mean -= np.pi/2
            dl2.append(dl2mean)

        decmean = np.mean(dl2)*180.0/np.pi*ang_fac - 180.0*ang_fac
        miremean = np.mean([poslst[1].mu,poslst[1].md]) # fits to mathematica
    
        #Initialize HC if no input in this column = 0
        try:
            if (poslst[8].hc == 0 or poslst[8].hc == 180):
                for k in range(8,16):
                    self[k].hc += decmean
        except:
            if iterator == 0:
                logging.warning("%s : No inclination measurements available"% num2date(poslst[0].time))
            pass

        #print "Miremean: %.3f" % miremean
        if expmire > 180.0*ang_fac:
            mirediff = expmire - (miremean+90.0*ang_fac)
        else:
            mirediff = expmire - (miremean-90.0*ang_fac)

        if (np.max(dl2)-np.min(dl2))>0.1:
            if iterator == 0:
                logging.warning('%s : Check the horizontal input of absolute data (or xstart value)' % num2date(poslst[0].time))
        dec = decmean + mirediff + variocorr[0]*180.0/np.pi*ang_fac + deltaD

        s0d = (dl2tmp[0]-dl2tmp[1]+dl2tmp[2]-dl2tmp[3])/4*hstart
        deH = (-dl2tmp[0]-dl2tmp[1]+dl2tmp[2]+dl2tmp[3])/4*hstart
        if dl2tmp[0]<dl2tmp[1]:
            epZD = (dl2tmp[0]-dl2tmp[1]-dl2tmp[2]+dl2tmp[3]+2*np.pi)/4*hstart
        else:
            epZD = (dl2tmp[0]-dl2tmp[1]-dl2tmp[2]+dl2tmp[3]-2*np.pi)/4*hstart
        
        resultline = LineStruct()
        resultline.time = poslst[0].time
        resultline.y = dec
        resultline.typ = 'idff'         
        resultline.var1 = s0d
        resultline.var2 = deH
        resultline.var3 = epZD
        resultline.t2 = mirediff
        # general info:
        resultline.str1 = poslst[0].person
        resultline.str2 = poslst[0].di_inst
        resultline.str3 = poslst[0].f_inst

        return resultline


    def _calcinc(self, linestruct, **kwargs):
        """
        Calculates inclination values from input.
        Need input of a LineStruct Object containing the results of _calcdec 
        Supports the following optional keywords:
        incstart - float - default 45.0 - inclination value in 'unit'
        unit - str - default 'deg' - can be either 'deg' or 'gon'
        scalevalue - 3comp list - default [1.0,1.0,1.0] - contains scales for varx,vary,varz to nT (not essential if all are equal)
        """
        
        incstart = kwargs.get('incstart')
        scalevalue = kwargs.get('scalevalue')
        unit = kwargs.get('unit')
        deltaI = kwargs.get('deltaI')
        iterator = kwargs.get('iterator')

        scale_x = scalevalue[0]
        scale_y = scalevalue[1]
        scale_z = scalevalue[2]

        if unit=='gon':
            ang_fac = 400./360.
        elif unit == 'rad':
            ang_fac = np.pi/180.
        else:
            ang_fac = 1

        if not iterator:
            iterator = 0

        # Initialize variometer and scalar instruments .... maybe better not here
        variotype = 'None'
        scalartype = 'None'

        #incstart = incstart*ang_fac
        plog = PyMagLog()

        # -- Get the variometer and scalar means from then absolute file
        # --------------------------------------------------------------
        #drop NANs from input stream - positions and get means
        poslst = [elem for elem in self if not isnan(elem.hc) and not isnan(elem.vc)]
        fcol = self._get_column('f')
        mflst = [elem for elem in fcol if not isnan(elem)]
        fvcol = self._get_column('varf')
        mfvlst = [elem for elem in fvcol if not isnan(elem)]
        # Select variometer readings for existing intensity data
        variox, varioy, varioz, flist, fvlist, dflist  = [],[],[],[],[],[]
        foundfirstelem = 0
        for elem in self:
            if len(mflst) > 0 and not isnan(elem.f):
                flist.append(elem.f)
                if not isnan(elem.varz) and not isnan(elem.vary) and not isnan(elem.varx):
                    variox.append(scale_x*elem.varx) 
                    varioy.append(scale_y*elem.vary) 
                    varioz.append(scale_z*elem.varz)
                if not isnan(elem.varf):
                    fvlist.append(elem.varf)
                    dflist.append(elem.f-elem.varf)
            elif len(mflst) == 0 and len(mfvlst) > 0:
                if not isnan(elem.varf) and not isnan(elem.varz) and not isnan(elem.vary) and not isnan(elem.varx):
                    variox.append(scale_x*elem.varx) 
                    varioy.append(scale_y*elem.vary) 
                    varioz.append(scale_z*elem.varz)
                    flist.append(elem.varf)
                    if foundfirstelem == 0:
                        if iterator == 0:
                            logging.info("%s : no f in absolute file -- using scalar values from specified scalarpath" % (num2date(self[0].time)))
                        foundfirstelem = 1

        if len(mflst)>0 or len(mfvlst)>0:
            meanf = np.mean(flist)
        else:
            meanf = 0.
            #return emptyline, 20000.0, 0.0

        if len(variox) == 0:
            if iterator == 0:
                logging.info("%s : no variometervalues found" % num2date(self[0].time))
            # set means to zero...
            meanvariox = 0.0
            meanvarioy = 0.0
            meanvarioz = 0.0
        else:
            meanvariox = np.mean(variox)
            meanvarioy = np.mean(varioy)
            meanvarioz = np.mean(varioz)

        xcorr =  meanf * np.cos( incstart *np.pi/(180.0*ang_fac) ) * np.cos ( linestruct.y *np.pi/(180.0*ang_fac) ) - meanvariox
        ycorr =  meanf * np.cos( incstart *np.pi/(180.0*ang_fac) ) * np.sin ( linestruct.y *np.pi/(180.0*ang_fac) ) - meanvarioy
        zcorr =  meanf * np.sin( incstart *np.pi/(180.0*ang_fac) ) - meanvarioz

        #drop NANs from input stream - fvalues
        if len(dflist) > 0:
            deltaF = np.mean(dflist)
        else:
            deltaF = float(nan)

        # -- Start with the inclination calculation
        # --------------------------------------------------------------

        nr_lines = len(poslst)
        I0Diff1,I0Diff2,xDiff1,zDiff1,xDiff2,zDiff2= 0,0,0,0,0,0
        I0list, ppmval,testlst = [],[],[]
        cnt = 0
        mirediff = linestruct.var1

        # If only D measurements are available then no suitable estimate of H can be obtained
        # Therefore we use an arbitrary start value -- Testing of the validity of this approach needs to be conducted
        if nr_lines < 16: # only declination measurements available so far
            return linestruct, 20000.0, 0.0
        
        for k in range((nr_lines-1)/2,nr_lines):
            val = poslst[k].vc
            try:
                xtmp = (scale_x*poslst[k].varx) + xcorr
                ytmp = (scale_y*poslst[k].vary) + ycorr
                ztmp = (scale_z*poslst[k].varz) + zcorr
                ppmtmp = np.sqrt(xtmp**2 + ytmp**2 + ztmp**2)
                if isnan(ppmtmp):
                    ppmval.append(meanf)
                else:
                    ppmval.append(ppmtmp)
            except:
                ppmval.append(meanf)
            if not ppmval[cnt] == 0:
                rcorri = np.arcsin(poslst[k].res/ppmval[cnt])
            else:
                rcorri = 0.0
            #if poslst[k].hc < 0:
            #    poslst[k].hc = poslst[k].hc + 360*ang_fac
            if poslst[k].vc > (poslst[k].hc + mirediff):
                quad = poslst[k].vc - (poslst[k].hc + mirediff)
            else:
                quad = poslst[k].vc + 360*ang_fac - (poslst[k].hc + mirediff)
            # The signums are essential for the collimation angle calculation
            # ToDo: check regarding correctness for different location/angles 
            # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! 
            #signum1 = np.sign(np.tan(quad*np.pi/180/ang_fac))
            signum1 = np.sign(-np.cos(quad*np.pi/180/ang_fac))
            signum2 = np.sign(np.sin(quad*np.pi/180/ang_fac))
            if signum2>0:
                PiVal=2*np.pi
            else:
                PiVal=np.pi
            I0 = (signum1*poslst[k].vc*np.pi/180/ang_fac - signum2*rcorri - signum1*PiVal)

            # check the quadrant
            if I0 > np.pi:
                I0 = 2*np.pi-I0
            elif I0 < -np.pi:
                I0 += 2*np.pi
            elif  I0 < 0:
                I0 = -I0
                
            if k < nr_lines-1:
                I0list.append(I0)       
                I0Diff1 += signum2*I0
                xDiff1 += signum2*poslst[k].varx
                zDiff1 += signum2*poslst[k].varz
                I0Diff2+= signum1*I0
                xDiff2 += signum1*poslst[k].varx
                zDiff2 += signum1*poslst[k].varz
            else:
                scaleangle = poslst[k].vc
                minimum = 10000
                for n in range((nr_lines-1)/2,nr_lines-1):
                    rotation = np.abs(scaleangle - poslst[n].vc)
                    if rotation < minimum:
                        fieldchange = (-np.sin(np.mean(I0list))*(poslst[n].varx-poslst[k].varx)/ppmval[cnt] + np.cos(np.mean(I0list))*(poslst[n].vary-poslst[k].vary)/ppmval[cnt])*180/np.pi*ang_fac 
                        #print fieldchange
                        deltaB = rotation+fieldchange
                        deltaR = np.abs(poslst[n].res-poslst[k].res)
                        #print deltaR
                        minimum = rotation
                        if (deltaR == 0):
                            calcscaleval = 999.0
                        else:
                            calcscaleval = ppmval[cnt] * deltaB/deltaR * np.pi/180/ang_fac
            cnt += 1

        i1list,i1tmp = [],[]

        for k in range(0,7,2):
            i1mean = np.mean([I0list[k],I0list[k+1]])
            i1tmp.append(i1mean)
            i1list.append(i1mean)

        I0Diff1 = I0Diff1/2.
        xDiff1 = xDiff1/2.
        zDiff1 = zDiff1/2.
        I0Diff2 = I0Diff2/2.
        xDiff2 = xDiff2/2.
        zDiff2 = zDiff2/2.

        # Variometer correction to start time is missing for f value and inc ???
        inc = np.mean(i1list)*180*ang_fac/np.pi + deltaI

        if isnan(inc): # if only dec measurements are available
            inc = 0.0
        # Dec is already variometer corrected (if possible) and transferred to time[0]
        tmpH = meanf * np.cos( inc *np.pi/(180.0*ang_fac) )
        tmpZ = meanf * np.sin( inc *np.pi/(180.0*ang_fac) )
        # check for inclination error in file inc
        #   -- the following part may casue problems in case of close to polar positions and locations were X is larger than Y
        if ((90.*ang_fac)-inc) < 0.1:
            logging.warning('%s : Inclination warning... check your vertical measurements' % num2date(self[0].time))
            h_adder = 0.
        else:
            h_adder = np.sqrt(tmpH**2 - meanvarioy**2) - meanvariox

        if not isnan(poslst[0].varx):
            hstart = np.sqrt((scale_x*poslst[0].varx + h_adder)**2 + (scale_y*poslst[0].vary)**2)
            xstart = hstart * np.cos ( linestruct.y *np.pi/(180.0*ang_fac) )
            ystart = hstart * np.sin ( linestruct.y *np.pi/(180.0*ang_fac) )
            zstart = scale_z*poslst[0].varz + tmpZ - meanvarioz
            fstart = np.sqrt(xstart**2 + ystart**2 + zstart**2)
        else:
            variotype = 'None'
            hstart = tmpH
            zstart = tmpZ
            xstart = hstart
            ystart = 0.0
            fstart = np.sqrt(xstart**2 + ystart**2 + zstart**2)
            xDiff1 = 0.0
            zDiff1 = 0.0
            xDiff2 = 0.0
            zDiff2 = 0.0

        if not meanf == 0:
            inc = np.arctan(zstart/hstart)*180.0*ang_fac/np.pi
            # Divided by 4 - need to be corrected if scalevals are used - don't thing so (leon, June 2012)
            s0i = -I0Diff1/4*fstart - xDiff1*np.sin(inc*np.pi/180) - zDiff1*np.cos(inc*np.pi/180) 
            epzi = (-I0Diff2/4 - (xDiff2*np.sin(inc*np.pi/180) - zDiff2*np.cos(inc*np.pi/180))/(4*fstart))*zstart;
        else:
            logging.info("%s : no intensity measurement available - presently using an x value of 20000 nT for Dec"  % num2date(self[0].time))
            fstart, deltaF, s0i, epzi = float(nan),float(nan),float(nan),float(nan)
            xstart = 20000 ## arbitrary
            ystart = 0.0

        # Baselinevalues:
        basex = xstart - scale_x*poslst[0].varx
        basey = ystart - scale_y*poslst[0].vary
        basez = zstart - scale_z*poslst[0].varz

        # Putting data to linestruct:
        linestruct.x = inc
        linestruct.z = fstart
        linestruct.f = fstart #np.array([basex,basey,basez])
        linestruct.dx = basex
        linestruct.dy = basey
        linestruct.dz = basez
        linestruct.df = deltaF
        linestruct.typ = 'idff'         
        linestruct.t2 = calcscaleval
        linestruct.var4 = s0i  # replaces Mirediff from _calcdec
        linestruct.var5 = epzi

        return linestruct, xstart, ystart

    def calcabsolutes(self, debugmode=None, **kwargs):
        """
        Interation of dec and inc calculation
        Need input of a LineStruct Object containing the results of _calcdec
        Returns a resultsline according to line struct 
        Supports the following optional keywords:
        incstart - float - default 45.0 - inclination value in 'unit'
        unit - str - default 'deg' - can be either 'deg' or 'gon'
        scalevalue - float - default 1.0 - convert varx,vary,varz to nT
        printresults - boolean - if True print results to screen
        """

        plog = PyMagLog()
        incstart = kwargs.get('incstart')
        scalevalue = kwargs.get('scalevalue')
        unit = kwargs.get('unit')
        xstart = kwargs.get('xstart')
        ystart = kwargs.get('ystart')
        deltaD = kwargs.get('deltaD')
        deltaI = kwargs.get('deltaI')
        usestep = kwargs.get('usestep')
        printresults = kwargs.get('printresults')

        for i in range(0,3):
            # Calculate declination value (use xstart and ystart as boundary conditions
            resultline = self._calcdec(unit=unit,xstart=xstart,ystart=ystart,deltaD=deltaD,usestep=usestep,scalevalue=scalevalue,iterator=i)
            # Calculate inclination value
            if debugmode:
                print "Calculated D (%f) - iteration step %d" % (resultline[2],i)
            # requires succesful declination determination
            if isnan(resultline.y):
                logging.warning('%s : CalcAbsolutes: Declination could not be determined - aborting' % num2date(self[0].time))
                break
            # use incstart and ystart as boundary conditions
            try: # check, whether outline already exists
                if isnan(outline.x):
                    inc = incstart
                else:
                    inc = outline.x
            except:
                inc = incstart
            outline, xstart, ystart = self._calcinc(resultline,unit=unit,scalevalue=scalevalue,incstart=inc,deltaI=deltaI,iterator=i)
            if debugmode:
                print "Calculated I (%f) - iteration step %d" %(outline[1],i)

        logging.info('%s : Declination: %s, Inclination: %s, H: %.1f, F: %.1f' % (num2date(outline.time), deg2degminsec(outline.y),deg2degminsec(outline.x),outline.f*np.cos(outline.x*np.pi/180),outline.f))

        if printresults:
            print 'Vector:'
            print 'Declination: %s, Inclination: %s, H: %.1f, F: %.1f' % (deg2degminsec(outline.y),deg2degminsec(outline.x),outline.f*np.cos(outline.x*np.pi/180),outline.f)
            print 'Collimation and Offset:'
            print 'Declination:    S0: %.3f, delta H: %.3f, epsilon Z: %.3f\nInclination:    S0: %.3f, epsilon Z: %.3f' % (outline.var1,outline.var2,outline.var3,outline.var4,outline.var5)

        return outline

#
#  Now import the format libraries
#

from lib.magpy_absformats import *

def deg2degminsec(value):
    """
    Function to convert deg.decimals to a string with deg min and seconds.decimals
    """
    if value > 360:
        return 'larger than 360'

    if isnan(value):
        return 'nan'

    degree = int(value)
    tminutes = np.abs(value - int(value))*60
    minutes = int(tminutes)
    tseconds = (tminutes-minutes)*60
    seconds = int(np.round(tseconds))
    if seconds == 60:
        minutes = minutes+1
        seconds = 0
    if minutes == 60:
        if degree < 0:
            degree = degree - 1
        else:
            degree = degree + 1
        minutes = 0

    return str(degree)+":"+str(minutes)+":"+str(seconds)
    

def absRead(path_or_url=None, dataformat=None, headonly=False, **kwargs):
    """
    optional keywords:
    username: for authentication in ftp and ssh access
    password: for authentication (following the example of http://www.voidspace.org.uk/python/articles/authentication.shtml
    """
    # Not used so far - maybe for simplifying ftp or ssh
    username = kwargs.get('username')
    password = kwargs.get('password')
    archivepath = kwargs.get('archivepath')

    # -- No path
    if not path_or_url:
        messagecont = "File not specified"
        return [],messagecont
    # -- Create Data Container
    stream = AbsoluteData()
    # -- Check file
    if not isinstance(path_or_url, basestring):
        # not a string - we assume a file-like object
        pass
    elif "://" in path_or_url:
        # some URL
        # extract extension if any
        suffix = '.'+os.path.basename(path_or_url).partition('.')[2] or '.tmp'
        fh = NamedTemporaryFile(suffix=suffix,delete=False)
        fh.write(urllib2.urlopen(path_or_url).read())
        fh.close()
        stream = _absRead(fh.name, dataformat, headonly, **kwargs)
        os.remove(fh.name)
    else:
        # some file name
        pathname = path_or_url
        stream = _absRead(pathname, dataformat, headonly, **kwargs)
        if len(stream) == 0:
            # try to give more specific information why the stream is empty
            if has_magic(pathname) and not glob(pathname):
                raise Exception("No file matching file pattern: %s" % pathname)
            elif not has_magic(pathname) and not os.path.isfile(pathname):
                raise IOError(2, "No such file or directory", pathname)
            # Only raise error if no starttime/endtime has been set. This
            # will return an empty stream if the user chose a time window with
            # no data in it.
            # XXX: Might cause problems if the data is faulty and the user
            # set starttime/endtime. Not sure what to do in this case.
            #elif not 'starttime' in kwargs and not 'endtime' in kwargs:
            #    raise Exception("Cannot open file/files: %s" % pathname)

    return stream

def _absRead(filename, dataformat=None, headonly=False, **kwargs):
    """
    Reads a single file into a ObsPy Stream object.
    """
    # get format type
    format_type = None
    if not dataformat:
        # auto detect format - go through all known formats in given sort order
        for format_type in MAGPY_SUPPORTED_ABSOLUTES_FORMATS:
            # check format
            if isAbsFormat(filename, format_type):
                break
    else:
        # format given via argument
        dataformat = dataformat.upper()
        try:
            formats = [el for el in MAGPY_SUPPORTED_ABSOLUTES_FORMATS if el == dataformat]
            format_type = formats[0]
        except IndexError:
            msg = "Format \"%s\" is not supported. Supported types: %s"
            raise TypeError(msg % (dataformat, ', '.join(MAGPY_SUPPORTED_ABSOLUTES_FORMATS)))
    # file format should be known by now
    #print format_type

    stream = readAbsFormat(filename, format_type, headonly=headonly, **kwargs)
    print stream

    return stream


def analyzeAbsFiles(debugmode=None,**kwargs):
    """
    Analyze absolute files from a specific path
    Requires an analysis directory for treatment of downloaded absolute files.
    Optional keywords:
    archivepath -- archive directory to which tsuccessfully analyzed data is moved to
    access_ftp -- retrives data from an ftp directory first and removes them after successful analysis
    printresults (boolean) -- screen output of calculation results
    -- if access_ftp = True then the follwoing keywords are also required:
            localpath
            ftppath
            filestr(ing)
            myproxy
            port
            login
            passwd
            logfile
            archivepath
    -- calcabs calculation parameters:
            usestep: (int) for selecting whether first (1), second (2) or a mean (0) of both repeated measurements at each "Lage" is used 
    """

    plog = PyMagLog()
    
    path_or_url = kwargs.get('path_or_url')
    variopath = kwargs.get('variopath')
    scalarpath = kwargs.get('scalarpath')
    deltaF = kwargs.get('deltaF')
    printresults = kwargs.get('printresults')
    # Parameters for absolute calculation (used in calcabs -> und subfunctions _calcdev, _calcinc
    incstart = kwargs.get('incstart')
    scalevalue = kwargs.get('scalevalue')
    unit = kwargs.get('unit')
    xstart = kwargs.get('xstart')
    ystart = kwargs.get('ystart')
    deltaD = kwargs.get('deltaD')
    deltaI = kwargs.get('deltaI')
    alpha = kwargs.get('alpha')
    beta = kwargs.get('beta')
    usestep = kwargs.get('usestep')
    outputformat  = kwargs.get('outputformat')
    summaryfile = kwargs.get('summaryfile')
    analysispath = kwargs.get('analysispath')
    archivepath = kwargs.get('archivepath')
    absidentifier = kwargs.get('absidentifier') # Part of filename, which defines absolute files
    # Not used so far are username and passwd
    username = kwargs.get('username')
    password = kwargs.get('password')
    
    if not absidentifier:
        absidentifier = '*AbsoluteMeas.txt'
    if not deltaF:
        deltaF = 0.0
    if not deltaI:
        deltaI = 0.0
    if not deltaD:
        deltaD = 0.0
    if not scalevalue:
        scalevalue = [1.0,1.0,1.0]
    if not unit:
        unit = 'deg'
    if unit=='gon':
        ang_fac = 400./360.
    elif unit == 'rad':
        ang_fac = np.pi/180.
    else:
        ang_fac = 1
    if not incstart:
        incstart = 45.0
    if not xstart:
        xstart = 20000.0
    if not ystart:
        ystart = 0.0
    if not usestep: 
        usestep = 0
    if not outputformat: # accepts idf, hdz and xyz
        outputformat = 'xyz'
    if username: # Needs to be checked: Using username and passwd within url instead
        passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
        passman.add_password(None, path_or_url, username, password)
        authhandler = urllib2.HTTPBasicAuthHandler(passman)
        opener = urllib2.build_opener(authhandler)
        urllib2.install_opener(opener)

    localfilelist = []
    st = DataStream()
    varioinst = '-'
    scalarinst = '-'

    logging.info('--- Start absolute analysis at %s ' % str(datetime.now()))

    # now check the contents of the analysis path - url part is yet missing
    if not os.path.isfile(path_or_url):
        if os.path.exists(path_or_url):
            for infile in iglob(os.path.join(path_or_url,absidentifier)):
                localfilelist.append(infile)
        elif  "://" in path_or_url: # URL part
            # get all files in ftp path
            logging.info('--- -- Accessing absolutes from URL (not shown for security reason)')
            response = urllib2.urlopen(path_or_url)
            path = response.geturl()
            html_string = response.read()
            # Distinguish between directory and file - get filename and add to path -> add to list
            datlst = html_string.split("\n")
            firstline = datlst[0].split()
            print firstline
            if datlst[0].startswith('# MagPy absolutes'):
                # found single file
                localfilelist = path
                pass
            elif len(datlst[0].split()) > 8: 
                for elem in datlst:
                    try:
                        absfile = elem.split()[-1]
                        localfilelist.append(path+absfile)
                    except:
                        pass
            else:
                logging.error('--- -- Aborting AbsAnalysis: no apropriate file found')              
        else:
            logging.error('--- -- Aborting AbsAnalysis: could not identify path_or_url')
            return  
    else:
        localfilelist.append(path_or_url)

    # get files from localfilelist and analyze them (localfilelist is not sorted!)
    cnt = 0
    for fi in localfilelist:
        # Get the amount of warning messages prior to a new analysis
        lengthofwarningsbefore = len(plog.warnings)
        cnt += 1
        plog.addcount(cnt, len(localfilelist))
        # ######## Process counter
        print plog.proc_count
        # ######## Process counter
        # initialize the move function for each fi
        if not archivepath:
            movetoarchive = False
        else:
            movetoarchive = True # this variable will be set false in case of warnings
        stream = absRead(path_or_url=fi,archivepath=archivepath)
        logging.info('Analyzing absolute file: %s of length %d' % (fi,len(stream)))
        if len(stream) > 0:
            mint = stream._get_min('time')
            maxt = stream._get_max('time')
            # -- Obtain variometer record and f record for the selected time (1 hour more before and after)
            # Problem: Logging and Warning information from PyMagLog is lost !!!!!!!!!!
            if variopath:
                variost = pmRead(path_or_url=variopath,starttime=mint-0.04,endtime=maxt+0.04)
                # Provide reorientation angles in case of non-geographically oriented systems: simple case HDZ -> use alpha = dec (at time of sensor setup)
                variost = variost.rotation(alpha=alpha,beta=beta,unit=unit)
                # get instrument from header info
                if len(variost) > 0:
                    func = variost.interpol(['x','y','z'])
                    stream = stream._insert_function_values(func)
                    varioinst = os.path.split(variopath)[0]
                else:
                    #movetoarchive = False
                    logging.info('%s : No variometer correction possible' % fi) 
            # Now check for f values in file
            fcol = stream._get_column('f')
            if not len(fcol) > 0 and not scalarpath:
                movetoarchive = False
                logging.error('%s : f values are required for analysis -- aborting' % fi)
                break
            if scalarpath:
                # scalar instrument and dF are then required
                scalarst = pmRead(path_or_url=scalarpath,starttime=mint-0.04,endtime=maxt+0.04)
                if len(scalarst) > 0:
                    func = scalarst.interpol(['f'])
                    stream = stream._insert_function_values(func, funckeys=['f'],offset=deltaF)
                    scalarinst = os.path.split(scalarpath)[0]
                else:
                    #movetoarchive = False
                    logging.info('%s : Did not find independent scalar values' % fi)
            # use DataStream and its LineStruct to store results
            result = stream.calcabsolutes(incstart=incstart,xstart=xstart,ystart=ystart,unit=unit,scalevalue=scalevalue,deltaD=deltaD,deltaI=deltaI,usestep=usestep,printresults=printresults,debugmode=debugmode)
            result.str4 = varioinst
            if (result.str3 == '-' or result.str3 == '') and not scalarinst == '-':
                result.str3 = scalarinst

            # Get the amount of warning messages after the analysis
            lengthofwarningsafter = len(plog.warnings)

            if lengthofwarningsafter > lengthofwarningsbefore:
                movetoarchive = False
                
            # check for presence of result in summary-file and append / replace existing data (if more non-NAN values are present)
            nonnan_result, nonnan_line = [],[]
            for key in KEYLIST:
                try:
                    if not isnan(eval('result.'+key)):
                        nonnan_result.append(eval('result.'+key))
                except:
                    pass
            newst = DataStream()

            # Create header keys and attributes
            line = LineStruct()
            st.header['col-time'] = 'Epoch'
            st.header['col-x'] = 'i'
            st.header['unit-col-x'] = unit
            st.header['col-y'] = 'd'
            st.header['unit-col-y'] = unit
            st.header['col-z'] = 'f'
            st.header['unit-col-z'] = 'nT'
            st.header['col-f'] = 'f'
            st.header['col-dx'] = 'basex'
            st.header['col-dy'] = 'basey'
            st.header['col-dz'] = 'basez'
            st.header['col-df'] = 'dF'
            st.header['col-t1'] = 'T'
            st.header['col-t2'] = 'ScaleValueDI'
            st.header['col-var1'] = 'Dec_S0'
            st.header['col-var2'] = 'Dec_deltaH'
            st.header['col-var3'] = 'Dec_epsilonZ'
            st.header['col-var4'] = 'Inc_S0'
            st.header['col-var5'] = 'Inc_epsilonZ'
            st.header['col-str1'] = 'Person'
            st.header['col-str2'] = 'DI-Inst'
            st.header['col-str3'] = 'F-Inst'
            st.header['col-str4'] = 'Vario-Inst'

            if outputformat == 'xyz':
                #for elem in st:
                result = result.idf2xyz(unit=unit)
                result.typ = 'xyzf'         
                st.header['col-x'] = 'x'
                st.header['unit-col-x'] = 'nT'
                st.header['col-y'] = 'y'
                st.header['unit-col-y'] = 'nT'
                st.header['col-z'] = 'z'
                st.header['unit-col-z'] = 'nT'
            elif outputformat == 'hdz':
                #for elem in st:
                result = result.idf2xyz(unit=unit)
                #for elem in st:
                result = result.xyz2hdz(unit=unit)
                result.typ = 'hdzf'         
                st.header['col-x'] = 'h'
                st.header['unit-col-x'] = 'nT'
                st.header['col-y'] = 'd'
                st.header['unit-col-y'] = unit
                st.header['col-z'] = 'z'
                st.header['unit-col-z'] = 'nT'

            # only write results if no warnings were issued:
            #if movetoarchive:
            newst.add(result)
            st.extend(newst, st.header)
        else: # len(stream) <= 0
            movetoarchive = False
            logging.warning('%s: File or data format problem - please check' % fi)
        if movetoarchive:
            if not "://" in fi: 
                src = fi
                fname = os.path.split(src)[1]
                dst = os.path.join(archivepath,fname)
                shutil.move(src,dst)
            else:
                print fi
                fname = fi.split('/')[-1]
                print fname
                dst = os.path.join(archivepath,fname)
                fh = NamedTemporaryFile(suffix=suffix,delete=False)
                fh.write(urllib2.urlopen(path_or_url).read())
                fh.close()
                shutil.move(fh.name,dst)

    st = st.sorting()
    
    logging.info('--- Finished absolute analysis at %s ' % str(datetime.now()))
                            
    return st


def getAbsFilesFTP(**kwargs):
    """
    Obtain files from the selected directory
    Requires an analysis and an archive directory for treatment of downloaded absolute files
    Analysis directory:
    - contains the newly downloaded files. These files are then analyzed in in case of success transfered to the Archive directory.
    Archive directory:
    - contains successfully analyzed data (requires on errors and variometer correction)
    - downloaded data is checked, whether files are already exist in the archive directory. If true, they are deleted from the ftp server
    Keywords:
    localpath
    ftppath
    filestr(ing)
    myproxy
    port
    login
    passwd
    logfile
    archivepath
    """
    localpath = kwargs.get('localpath')
    ftppath = kwargs.get('ftppath')
    filestr = kwargs.get('filestr')
    myproxy = kwargs.get('myproxy')
    port = kwargs.get('port')
    login = kwargs.get('login')
    passwd = kwargs.get('passwd')
    logfile = kwargs.get('logfile')
    analysispath = kwargs.get('analysispath')
    archivepath = kwargs.get('archivepath')
    absidentifier = kwargs.get('absidentifier') # Part of filename, which defines absolute files

    if not absidentifier:
        absidentifier = '*AbsoluteMeas.txt'

    filelist = []
    
    msg = PyMagLog()
    logging.info(" -- Starting downloading Absolute files from %s" % ftppath)

    # -- Checking whether new data is available
    ftplist = ftpdirlist (localpath=localpath, ftppath=ftppath, filestr=filestr, myproxy=myproxy, port=port, login=login, passwd=passwd, logfile=logfile)
    if len(ftplist) == 0:
        logging.info(" ---- AbsDownload: no new data on ftp directory")
    # -- get local list
    for infile in iglob(os.path.join(archivepath,absidentifier)):
        filelist.append(infile)

    # -- Download files to Analysis folder
    for f in ftplist:
        logging.info(" ---- Now getting %s" % f) 
        ftpget (localpath=analysispath, ftppath=ftppath, filestr=f, myproxy=myproxy, port=port, login=login, passwd=passwd, logfile=logfile)

    logging.info(" -- Download procedure finished at %s" % ftppath)

    return ftpfilelist, localfilelist

def removeAbsFilesFTP(**kwargs):
    """
    Remove files from the selected directory
    Requires an analysis and an archive directory for treatment of downloaded absolute files
    Analysis directory:
    - contains the newly downloaded files. These files are then analyzed in in case of success transfered to the Archive directory.
    Archive directory:
    - contains successfully analyzed data (requires on errors and variometer correction)
    - downloaded data is checked, whether files are already exist in the archive directory. If true, they are deleted from the ftp server
    Keywords:
    ftppath
    filestr(ing)
    myproxy
    port
    login
    passwd
    ftpfilelist
    localfilelist
    """
    ftppath = kwargs.get('ftppath')
    filestr = kwargs.get('filestr')
    myproxy = kwargs.get('myproxy')
    port = kwargs.get('port')
    login = kwargs.get('login')
    passwd = kwargs.get('passwd')
    ftpfilelist = kwargs.get('ftpfilelist')
    localfilelist = kwargs.get('localfilelist')

    msg = PyMagLog()
    logging.info(" -- Starting removing already successfully analyzed files from %s" % ftppath)

    doubles = list(set(ftpfilelist) & set(localfilelist))
    print doubles

    for f in doubles:
        ftpremove (ftppath=ftppath, filestr=f, myproxy=myproxy, port=port, login=login, passwd=passwd)

    logging.info(" -- Removing procedure finished at %s" % ftppath)


# ##################
# ------------------
# Main program
# ------------------
# ##################

localpath = os.path.normpath(r'e:\leon\Programme\Python\PyMag\ExperimentalFolder')
ftppath = '/cobenzlabs'
filestr = 'test'
#myproxy = '94.136.40.103'
#port = 21
login = 'data@conrad-observatory.at'
myproxy = '138.22.156.44'
port = 8021
login = 'data@conrad-observatory.at@94.136.40.103'
passwd = 'data2COBS'

logfile = os.path.normpath(r'e:\leon\Programme\Python\PyMag\ExperimentalFolder\upload.log')
analysispath = os.path.normpath(r'e:\leon\Programme\Python\PyMag\ExperimentalFolder\AbsAnalysis')
testpath = os.path.normpath(r'e:\leon\Programme\Python\PyMag\ExperimentalFolder\AbsTest')
#analysispath = os.path.normpath(r'e:\leon\Programme\Python\PyMag\ExperimentalFolder\AbsTest\2011-07-07_11-02-00_AbsoluteMeas.txt')
archivepath = os.path.normpath(r'e:\leon\Programme\Python\PyMag\ExperimentalFolder\AbsArchive')
summarypath = os.path.normpath(r'e:\leon\Programme\Python\PyMag\ExperimentalFolder\AbsTest')
#summarypath = os.path.normpath(r'e:\leon\Observatory\Messdaten\Data-Magnetism\GmoPy\WIK\di\absolutes_didd.txt')
variopath = os.path.normpath(r'f:\Vario-Cobenzl\dIdD-System\*')
#variopath = os.path.normpath(r'f:\Vario-Cobenzl\dIdD-System\LEMI\*')
scalarpath = os.path.normpath(r'f:\Vario-Cobenzl\dIdD-System\*')
#variopath=os.path.normpath('e:\leon\Observatory\Messdaten\Data-Magnetism\didd\*')
#variopath=os.path.normpath('e:\leon\Observatory\Messdaten\Data-Magnetism\lemi\*')
#variopath=os.path.normpath(r'e:\leon\Observatory\Messdaten\Data-Magnetism\gdas\rawdata\*')

if __name__ == '__main__':
    print "Starting the GetAbsolutes program:"
    msg = PyMagLog()
    # getAbsFTP()
    #st = analyzeAbsFiles(path_or_url=testpath, variopath=variopath, scalarpath=variopath)
    st = analyzeAbsFiles(path_or_url=os.path.normpath(r'e:\leon\Programme\Python\PyMag\ExperimentalFolder'), alpha=3.25, beta=0.0, variopath=variopath, scalarpath=scalarpath)
    #st = analyzeAbsFiles(path_or_url=os.path.normpath(r'e:\leon\Programme\Python\PyMag\ExperimentalFolder'), alpha=3.25, beta=0.0, variopath=os.path.normpath('..\\dat\\lemi025\\*'), scalarpath=os.path.normpath('..\\dat\\didd\\*'), archivepath=os.path.normpath('..\\dat\\absolutes\\analyzed'))
    st.pmwrite(analysispath,coverage='all',mode='replace',filenamebegins='absolutes_didd')

    #loglst = msg.combineWarnLog(msg.warnings,msg.logger)
    #print loglst

    #msg.sendLogByMail(loglst,user="roman_leonhardt",pwd="2kippen")

    #newst = pmRead(path_or_url=summarypath)
    #newst.pmplot(['x','y','z'])
    #print newst.header

    ### ToDo
    # test for input variations (e.g. no f, scalevals, lemi vs didd etc)
    # eventually develop plot routine for absstruct....
