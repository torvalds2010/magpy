#!/usr/bin/env python

import sys
sys.path.append('/home/leon/Software/magpy/trunk/src')

from stream import *
from absolutes import *
from transfer import *
from database import *

import wx

from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.backends.backend_wx import NavigationToolbar2Wx
from matplotlib.figure import Figure

from wx.lib.pubsub import Publisher

from gui.streampage import *
from gui.dialogclasses import *
from gui.absolutespage import *
from gui.developpage import *

   
class PlotPanel(wx.Panel):
    def __init__(self, *args, **kwds):
        wx.Panel.__init__(self, *args, **kwds)
        self.figure = plt.figure()
        scsetmp = ScreenSelections()
        self.canvas = FigureCanvas(self,-1,self.figure)
        self.initialPlot()
        self.__do_layout()
        
    def __do_layout(self):
        # Resize graph and toolbar, create toolbar
        self.vbox = wx.BoxSizer(wx.VERTICAL)
        self.vbox.Add(self.canvas, 1, wx.LEFT | wx.TOP | wx.GROW)
        self.toolbar = NavigationToolbar2Wx(self.canvas)
        self.vbox.Add(self.toolbar, 0, wx.EXPAND)
        self.SetSizer(self.vbox)
        self.vbox.Fit(self)

    def guiPlot(self,stream,keys,**kwargs):
        """
        DEFINITION:
            embbed matplotlib figure in canvas

        PARAMETERS:
        kwargs:  - all plot args
        """
        self.figure.clear()
        try:
            self.axes.clear()
        except:
            pass
        self.axes = stream.plot(keys,figure=self.figure)
        self.canvas.draw()

    def initialPlot(self):
        """
        DEFINITION:
            loads an image for the startup screen
        """

        self.axes = self.figure.add_subplot(111)
        plt.axis("off") # turn off axis
        startupimage = 'magpy.png'
        img = imread(startupimage)
        self.axes.imshow(img)
        self.canvas.draw()

    def linkRep(self):
        return ReportPage(self)

    class AnnoteFinder:
        """
        callback for matplotlib to display an annotation when points are clicked on.  The
        point which is closest to the click and within xtol and ytol is identified.

        Register this function like this:

        scatter(xdata, ydata)
        af = AnnoteFinder(xdata, ydata, annotes)
        connect('button_press_event', af)
        """

        def __init__(self, xdata, ydata, annotes, axis=None, xtol=None, ytol=None):
            self.data = zip(xdata, ydata, annotes)
            if xtol is None:
                xtol = ((max(xdata) - min(xdata))/float(len(xdata)))/2
            if ytol is None:
                ytol = ((max(ydata) - min(ydata))/float(len(ydata)))/2
            ymin = min(ydata)
            ymax = max(ydata)
            self.xtol = xtol
            self.ytol = ytol
            if axis is None:
                self.axis = pylab.gca()
            else:
                self.axis= axis
            self.drawnAnnotations = {}
            self.links = []

        def distance(self, x1, x2, y1, y2):
            """
            return the distance between two points
            """
            return math.hypot(x1 - x2, y1 - y2)

        def __call__(self, event):
            if event.inaxes:
                clickX = event.xdata
                clickY = event.ydata
                if self.axis is None or self.axis==event.inaxes:
                    annotes = []
                    for x,y,a in self.data:
                        #if  clickX-self.xtol < x < clickX+self.xtol and clickY-self.ytol < y < clickY+self.ytol:
                        if  clickX-self.xtol < x < clickX+self.xtol :
                            annotes.append((self.distance(x,clickX,y,clickY),x,y, a) )
                    if annotes:
                        annotes.sort()
                        distance, x, y, annote = annotes[0]
                        self.drawAnnote(event.inaxes, x, y, annote)
                        for l in self.links:
                            l.drawSpecificAnnote(annote)

        def drawAnnote(self, axis, x, y, annote):
            """
            Draw the annotation on the plot
            """
            if (x,y) in self.drawnAnnotations:
                markers = self.drawnAnnotations[(x,y)]
                for m in markers:
                    m.set_visible(not m.get_visible())
                self.axis.figure.canvas.draw()
            else:
                #t = axis.text(x,y, "(%3.2f, %3.2f) - %s"%(x,y,annote), )
                datum = datetime.strftime(num2date(x).replace(tzinfo=None),"%Y-%m-%d")
                t = axis.text(x,y, "(%s, %3.2f)"%(datum,y), )
                m = axis.scatter([x],[y], marker='d', c='r', zorder=100)
                scse = ScreenSelections()
                scse.seldatelist.append(x)
                scse.selvallist.append(y)
                scse.updateList()
                #test = MainFrame(parent=None)
                #test.ReportPage.addMsg(str(x))
                #rep_page.logMsg('Datum is %s ' % (datum))
                #l = axis.plot([x,x],[0,y])
                self.drawnAnnotations[(x,y)] =(t,m)
                self.axis.figure.canvas.draw()

        def drawSpecificAnnote(self, annote):
            annotesToDraw = [(x,y,a) for x,y,a in self.data if a==annote]
            for x,y,a in annotesToDraw:
                self.drawAnnote(self.axis, x, y, a)


    def mainPlot(self,magdatastruct1,magdatastruct2,array3,xlimit,pltlist,symbol,errorbar,title):
        # add here the plt order
        # e.g.variable pltorder = [1,2,3,4,9] corresponds to x,y,z,f,t1 with len(pltorder) giving the amount
        # symbol corresponds to ['-','o'] etc defining symbols of magstruct 1 and 2
        # array3 consists of time, val1, val2: for an optional auxiliary plot of data which is not part of the magdatastructs e.g. data density
        self.axes.clear()
        self.figure.clear()
        msg = ''

        acceptedflags = [0,2,20,22]

        titleline = title
        myyfmt = ScalarFormatter(useOffset=False)
            
        t,x,y,z,f,temp1 = [],[],[],[],[],[]
        dx,dy,dz,df,flag,com = [],[],[],[],[],[]
        ctyp = "xyzf"
        try:
            nr_lines = len(magdatastruct1)
            for i in range (nr_lines):
                #if findflag(magdatastruct1[i].flag,acceptedflags):
                    t.append(magdatastruct1[i].time)
                    x.append(magdatastruct1[i].x)
                    y.append(magdatastruct1[i].y)
                    z.append(magdatastruct1[i].z)
                    f.append(magdatastruct1[i].f)
                    flag.append(magdatastruct1[i].flag)
                    com.append(magdatastruct1[i].comment)
                    temp1.append(magdatastruct1[i].t1)
                    dx.append(magdatastruct1[i].dx)
                    dy.append(magdatastruct1[i].dy)
                    dz.append(magdatastruct1[i].dz)
                    df.append(magdatastruct1[i].df)
                    ctyp = magdatastruct1[i].typ
        except:
            msg += 'Primary data file not defined'
            pass

        varlist = [t,x,y,z,f,dx,dy,dz,df,temp1]
        colorlist = ["b","g","m","c","y","k"]

        t2,x2,dx2,y2,dy2,z2,dz2,f2,df2,temp2 = [],[],[],[],[],[],[],[],[],[]
        try:
            nr_lines = len(magdatastruct2)
            ctyp2 = "xyzf"
            for i in range (nr_lines):
                #if findflag(magdatastruct2[i].flag,acceptedflags):
                    t2.append(magdatastruct2[i].time)
                    x2.append(magdatastruct2[i].x)
                    dx2.append(magdatastruct2[i].dx)
                    y2.append(magdatastruct2[i].y)
                    dy2.append(magdatastruct2[i].dy)
                    z2.append(magdatastruct2[i].z)
                    dz2.append(magdatastruct2[i].dz)
                    f2.append(magdatastruct2[i].f)
                    df2.append(magdatastruct2[i].df)
                    temp2.append(magdatastruct2[i].t1)
                    ctyp2 = magdatastruct2[i].typ
        except:
            msg += 'Secondary data file not defined'
            pass

        # get max time:
        #maxti = max([magdatastruct1[-1].time,magdatastruct2[-1].time])
        #minti = min([magdatastruct1[0].time,magdatastruct2[0].time])
        
        var2list = [t2,x2,y2,z2,f2,dx2,dy2,dz2,df2,temp2]

        nsub = len(pltlist)
        plt1 = "%d%d%d" %(nsub,1,1)

        if array3 != []:
            nsub += 1
            pltlist.append(999)

        for idx, ax in enumerate(pltlist):
            n = "%d%d%d" %(nsub,1,idx+1)
            if ax != 999:
                yplt = varlist[ax]
                yplt2 = var2list[ax]
            # check whether yplt is empty:Do something useful here (e.g. fill with 0 to length t
            ypltdat = True
            for elem in yplt:
                if is_number(elem) and np.isfinite(elem):
                    ypltdat = False
                    break
            if len(yplt) == 0 or ypltdat:
                yplt = [-999]*len(t)
            #    print " Zero length causes problems!"
            #    pass
            # Create xaxis an its label
            if idx == 0:
                self.ax = self.figure.add_subplot(n)
                if xlimit == "day":
                    self.ax.set_xlim(date2num(datetime.strptime(day + "-00-00","%Y-%m-%d-%H-%M")),date2num(datetime.strptime(day + "-23-59","%Y-%m-%d-%H-%M")))
                #else:
                #    self.ax.set_xlim(minti,maxti)
                self.a = self.ax
            else:
                self.ax = self.figure.add_subplot(n, sharex=self.a)
            if idx < len(pltlist)-1:
                setp(self.ax.get_xticklabels(), visible=False)
            else:
                self.ax.set_xlabel("Time (UTC)")
            if ax == 999:
                self.ax.plot_date(array3[:,0],array3[:,1],'g-')
                self.ax.fill_between(array3[:,0],0,array3[:,1],facecolor='green',where=np.isfinite(array3[:,1]))
                self.ax.fill_between(array3[:,0],array3[:,1],1,facecolor='red',where=np.isfinite(array3[:,1]))
            else:                
                # switch color
                self.ax.plot_date(t,yplt,colorlist[idx]+symbol[0])
                if errorbar == 1:
                    self.ax.errorbar(t,yplt,yerr=varlist[ax+4],fmt=colorlist[idx]+'o')
                self.ax.plot_date(t2,yplt2,"r"+symbol[1],markersize=4)
            # is even function for left/right
            if bool(idx & 1):
                self.ax.yaxis.tick_right()
                self.ax.yaxis.set_label_position("right")
            # choose label for y-axis
            if ax == 1 or ax == 2 or ax == 3:
                label = ctyp[idx]
            elif ax == 4 or ax == 8:
                label = "f"
            elif ax == 9:
                label = "t"
            else:
                label = "unkown"
            #if ax == 1:
            #    label = ctyp[idx]
            #except:
            #    label = "t"
            if label == "d" or label == "i":
                unit = "(deg)"
            elif label == "t":
                unit = "(deg C)"
            else:
                unit = "(nT)"
            self.ax.set_ylabel(label.capitalize()+unit)
            self.ax.get_yaxis().set_major_formatter(myyfmt)
            self.ax.af2 = self.AnnoteFinder(t,yplt,flag,self.ax)
            self.figure.canvas.mpl_connect('button_press_event', self.ax.af2)
           
        self.figure.subplots_adjust(hspace=0)

        if (max(t)-min(t) < 2):
            self.a.xaxis.set_major_formatter( matplotlib.dates.DateFormatter('%H:%M'))
        elif (max(t)-min(t) < 90):
            self.a.xaxis.set_major_formatter( matplotlib.dates.DateFormatter('%b%d'))
        else:
            self.a.xaxis.set_major_formatter( matplotlib.dates.DateFormatter('%y-%m'))
            
        
class MenuPanel(wx.Panel):
    #def __init__(self, parent):
    #    wx.Panel.__init__(self,parent,-1,size=(100,100))
    def __init__(self, *args, **kwds):
        wx.Panel.__init__(self, *args, **kwds)
        # Create pages on MenuPanel
	nb = wx.Notebook(self,-1)
	self.gra_page = GraphPage(nb)
	self.str_page = StreamPage(nb)
	self.ana_page = AnalysisPage(nb)
	self.abs_page = AbsolutePage(nb)
	self.gen_page = GeneralPage(nb)
	self.bas_page = BaselinePage(nb)
	self.rep_page = ReportPage(nb)
	self.com_page = PortCommunicationPage(nb)
	nb.AddPage(self.str_page, "Stream")
	nb.AddPage(self.gra_page, "Variometer")
	nb.AddPage(self.ana_page, "Analysis")
	nb.AddPage(self.abs_page, "Absolutes")
	nb.AddPage(self.bas_page, "Baseline")
	nb.AddPage(self.gen_page, "Auxiliary")
	nb.AddPage(self.rep_page, "Report")
	nb.AddPage(self.com_page, "Monitor")

        sizer = wx.BoxSizer()
        sizer.Add(nb, 1, wx.EXPAND)
        self.SetSizer(sizer)
                
class MainFrame(wx.Frame):   
    def __init__(self, *args, **kwds):
	kwds["style"] = wx.DEFAULT_FRAME_STYLE
        wx.Frame.__init__(self, *args, **kwds)
        # The Splitted Window
        self.sp = wx.SplitterWindow(self, -1, style=wx.SP_3D|wx.SP_BORDER)
        self.plot_p = PlotPanel(self.sp,-1)
        self.menu_p = MenuPanel(self.sp,-1)
        Publisher().subscribe(self.changeStatusbar, 'changeStatusbar')

        # The Status Bar
	self.StatusBar = self.CreateStatusBar(2, wx.ST_SIZEGRIP)
        #self.changeStatusbar("Ready")

        # Some variable initializations
        self.db = None
        self.filename = 'noname.txt'
        self.dirname = '.'

        self.compselect = "xyz"
        self.abscompselect = "xyz"
        self.bascompselect = "bspline"

        # Menu Bar
        self.MainMenu = wx.MenuBar()
        self.FileMenu = wx.Menu()
        self.FileOpen = wx.MenuItem(self.FileMenu, 101, "&Open File...\tCtrl+O", "Open file", wx.ITEM_NORMAL)
        self.FileMenu.AppendItem(self.FileOpen)
        self.DirOpen = wx.MenuItem(self.FileMenu, 102, "Select &Directory...\tCtrl+D", "Select an existing directory", wx.ITEM_NORMAL)
        self.FileMenu.AppendItem(self.DirOpen)
        self.WebOpen = wx.MenuItem(self.FileMenu, 103, "Open &URL...\tCtrl+U", "Get data from the internet", wx.ITEM_NORMAL)
        self.FileMenu.AppendItem(self.WebOpen)
        self.DBOpen = wx.MenuItem(self.FileMenu, 104, "&Select DB table...\tCtrl+S", "Select a MySQL database", wx.ITEM_NORMAL)
        self.FileMenu.AppendItem(self.DBOpen)
        self.DBOpen.Enable(False)
        self.FileMenu.AppendSeparator()
        self.FileQuitItem = wx.MenuItem(self.FileMenu, wx.ID_EXIT, "&Quit\tCtrl+Q", "Quit the program", wx.ITEM_NORMAL)
        self.FileMenu.AppendItem(self.FileQuitItem)
        self.MainMenu.Append(self.FileMenu, "&File")
        self.DatabaseMenu = wx.Menu()
        self.DBConnect = wx.MenuItem(self.DatabaseMenu, 201, "&Connect MySQL DB...\tCtrl+C", "Connect Database", wx.ITEM_NORMAL)
        self.DatabaseMenu.AppendItem(self.DBConnect)
        self.MainMenu.Append(self.DatabaseMenu, "Data&base")
        self.HelpMenu = wx.Menu()
        self.HelpAboutItem = wx.MenuItem(self.HelpMenu, 301, "&About...", "Display general information about the program", wx.ITEM_NORMAL)
        self.HelpMenu.AppendItem(self.HelpAboutItem)
        self.MainMenu.Append(self.HelpMenu, "&Help")
        self.OptionsMenu = wx.Menu()
        self.OptionsCalcItem = wx.MenuItem(self.OptionsMenu, 401, "&Calculation parameter", "Modify calculation parameters (e.g. filters, sensitivity)", wx.ITEM_NORMAL)
        self.OptionsMenu.AppendItem(self.OptionsCalcItem)
        self.OptionsMenu.AppendSeparator()
        self.OptionsObsItem = wx.MenuItem(self.OptionsMenu, 402, "&Observatory specifications", "Modify observatory specific initialization data (e.g. paths, pears, offsets)", wx.ITEM_NORMAL)
        self.OptionsMenu.AppendItem(self.OptionsObsItem)
        self.MainMenu.Append(self.OptionsMenu, "&Options")
        self.SetMenuBar(self.MainMenu)
        # Menu Bar end


	self.__set_properties()

        # BindingControls on the menu
        self.Bind(wx.EVT_MENU, self.OnOpenDir, self.DirOpen)
        self.Bind(wx.EVT_MENU, self.OnOpenFile, self.FileOpen)
        self.Bind(wx.EVT_MENU, self.OnOpenURL, self.WebOpen)
        self.Bind(wx.EVT_MENU, self.OnOpenDB, self.DBOpen)
        self.Bind(wx.EVT_MENU, self.OnFileQuit, self.FileQuitItem)
        self.Bind(wx.EVT_MENU, self.OnDBConnect, self.DBConnect)
        self.Bind(wx.EVT_MENU, self.OnOptionsCalc, self.OptionsCalcItem)
        self.Bind(wx.EVT_MENU, self.OnOptionsObs, self.OptionsObsItem)
        self.Bind(wx.EVT_MENU, self.OnHelpAbout, self.HelpAboutItem)
        # BindingControls on the notebooks
        #       Base Page
        self.Bind(wx.EVT_BUTTON, self.onDrawBaseButton, self.menu_p.bas_page.DrawBaseButton)
        self.Bind(wx.EVT_BUTTON, self.onDrawBaseFuncButton, self.menu_p.bas_page.DrawBaseFuncButton)
        self.Bind(wx.EVT_BUTTON, self.onStabilityTestButton, self.menu_p.bas_page.stabilityTestButton)
        self.Bind(wx.EVT_RADIOBOX, self.onBasCompchanged, self.menu_p.bas_page.funcRadioBox)
        #       Stream Page
        self.Bind(wx.EVT_BUTTON, self.onOpenStreamButton, self.menu_p.str_page.openStreamButton)
        #self.Bind(wx.EVT_BUTTON, self.onScalarDrawButton, self.menu_p.str_page.DrawButton)
        #self.Bind(wx.EVT_COMBOBOX, self.onSecscalarComboBox, self.menu_p.str_page.secscalarComboBox)
        #self.Bind(wx.EVT_BUTTON, self.onGetGraphMarksButton, self.menu_p.str_page.GetGraphMarksButton)
        #self.Bind(wx.EVT_BUTTON, self.onFlagSingleButton, self.menu_p.str_page.flagSingleButton)
        #self.Bind(wx.EVT_BUTTON, self.onFlagRangeButton, self.menu_p.str_page.flagRangeButton)
        #self.Bind(wx.EVT_BUTTON, self.onSaveScalarButton, self.menu_p.str_page.SaveScalarButton)
        #       Vario Page
        #self.Bind(wx.EVT_BUTTON, self.onGetGraphMarksButton, self.menu_p.gra_page.GetGraphMarksButton)
        #self.Bind(wx.EVT_BUTTON, self.onFlagSingleButton, self.menu_p.gra_page.flagSingleButton)
        #self.Bind(wx.EVT_BUTTON, self.onFlagRangeButton, self.menu_p.gra_page.flagRangeButton)
        self.Bind(wx.EVT_BUTTON, self.onSaveVarioButton, self.menu_p.gra_page.SaveVarioButton)
        self.Bind(wx.EVT_BUTTON, self.onGraDrawButton, self.menu_p.gra_page.DrawButton)
        self.Bind(wx.EVT_RADIOBOX, self.onGraCompchanged, self.menu_p.gra_page.drawRadioBox)
        #       Absolute PAge
        #self.Bind(wx.EVT_BUTTON, self.onFlagSingleButton, self.menu_p.abs_page.flagSingleButton)
        #self.Bind(wx.EVT_BUTTON, self.onGetGraphMarksButton, self.menu_p.abs_page.GetGraphMarksButton)
        self.Bind(wx.EVT_BUTTON, self.onSaveFlaggedAbsButton, self.menu_p.abs_page.SaveFlaggedAbsButton)
        self.Bind(wx.EVT_BUTTON, self.onDrawAllAbsButton, self.menu_p.abs_page.DrawAllAbsButton)
        self.Bind(wx.EVT_BUTTON, self.onOpenAbsButton, self.menu_p.abs_page.OpenAbsButton)
        self.Bind(wx.EVT_BUTTON, self.onNewAbsButton, self.menu_p.abs_page.NewAbsButton)
        self.Bind(wx.EVT_BUTTON, self.onCalcAbsButton, self.menu_p.abs_page.CalcAbsButton)
        self.Bind(wx.EVT_RADIOBOX, self.onAbsCompchanged, self.menu_p.abs_page.drawRadioBox)
        #        Analysis Page
        self.Bind(wx.EVT_BUTTON, self.onDrawAnalysisButton, self.menu_p.ana_page.DrawButton)
        #        Auxiliary Page
        self.Bind(wx.EVT_BUTTON, self.onOpenAuxButton, self.menu_p.gen_page.OpenAuxButton)
        
        #self.Bind(wx.EVT_CUSTOM_NAME, self.addMsg)
        # Put something on Report page
        self.menu_p.rep_page.logMsg('Begin logging...')
 
        self.sp.SplitVertically(self.plot_p,self.menu_p,700)

    def __set_properties(self):
        self.SetTitle("MagPy")
        self.SetSize((1100, 700))
        self.SetFocus()
        self.StatusBar.SetStatusWidths([-1, -1])
        # statusbar fields
        StatusBar_fields = ["Ready", ""]
        for i in range(len(StatusBar_fields)):
            self.StatusBar.SetStatusText(StatusBar_fields[i], i)
        self.menu_p.SetMinSize((100, 100))
        self.plot_p.SetMinSize((100, 100))


    # ################
    # Helper methods:

    def defaultFileDialogOptions(self):
        ''' Return a dictionary with file dialog options that can be
            used in both the save file dialog as well as in the open
            file dialog. '''
        return dict(message='Choose a file', defaultDir=self.dirname,
                    wildcard='*.*')

    def askUserForFilename(self, **dialogOptions):
        dialog = wx.FileDialog(self, **dialogOptions)
        if dialog.ShowModal() == wx.ID_OK:
            userProvidedFilename = True
            self.filename = dialog.GetFilename()
            self.dirname = dialog.GetDirectory()
            #self.SetTitle() # Update the window title with the new filename
        else:
            userProvidedFilename = False
        dialog.Destroy()
        return userProvidedFilename


    def OnInitialPlot(self, stream):
        """
        DEFINITION:
            read stream, extract columns with values and display up to three of them by defailt
            executes guiPlot then
        """
        keylist = []
        keylist = stream._get_key_headers(limit=9)
        self.plot_p.guiPlot(stream,keylist)

    # ################
    # Top menu methods:

    def OnHelpAbout(self, event):
        dlg = wx.MessageDialog(self, "This program is developed for\n"
                        "geomagnetic analysis. Written by RL 2011/2012\n",
                        "About MagPy", wx.OK|wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()

    def OnExit(self, event):
        self.Close()  # Close the main window.

    def ReactivateStreamPage(self):
            self.menu_p.str_page.fileTextCtrl.Enable()
            self.menu_p.str_page.pathTextCtrl.Enable()
            self.menu_p.str_page.startDatePicker.Enable()
            self.menu_p.str_page.endDatePicker.Enable()
            self.menu_p.str_page.startTimePicker.Enable()
            self.menu_p.str_page.endTimePicker.Enable()
            self.menu_p.str_page.openStreamButton.Enable()
        
    def OnOpenDir(self, event):
        dialog = wx.DirDialog(None, "Choose a directory:",style=wx.DD_DEFAULT_STYLE | wx.DD_NEW_DIR_BUTTON)
        if dialog.ShowModal() == wx.ID_OK:
            self.ReactivateStreamPage()
            self.menu_p.str_page.pathTextCtrl.SetValue(dialog.GetPath())
        self.menu_p.rep_page.logMsg('- Directory defined')
        dialog.Destroy()

    def OnOpenFile(self, event):
        self.dirname = ''
        dlg = wx.FileDialog(self, "Choose a file", self.dirname, "", "*.*", wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            stream = DataStream()
            stream.header = {}
            print stream.header
            self.ReactivateStreamPage()
            self.filename = dlg.GetFilename()
            self.dirname = dlg.GetDirectory()
            self.changeStatusbar("Loading data ...")
            stream = read(path_or_url=os.path.join(self.dirname, self.filename))
            #self.menu_p.str_page.lengthStreamTextCtrl.SetValue(str(len(stream)))
            self.menu_p.str_page.fileTextCtrl.SetValue(self.filename)
            self.menu_p.str_page.pathTextCtrl.SetValue(self.dirname)
            self.menu_p.str_page.fileTextCtrl.Disable()
            self.menu_p.str_page.pathTextCtrl.Disable()
            if len(stream) > 0:
                mintime = stream._get_min('time')
                maxtime = stream._get_max('time')
                self.menu_p.str_page.startDatePicker.SetValue(wx.DateTimeFromTimeT(time.mktime(num2date(mintime).timetuple())))
                self.menu_p.str_page.endDatePicker.SetValue(wx.DateTimeFromTimeT(time.mktime(num2date(maxtime).timetuple())))
                self.menu_p.str_page.startTimePicker.SetValue(num2date(mintime).strftime('%X'))
                self.menu_p.str_page.endTimePicker.SetValue(num2date(maxtime).strftime('%X'))
                self.menu_p.str_page.startDatePicker.Disable()
                self.menu_p.str_page.endDatePicker.Disable()
                self.menu_p.str_page.startTimePicker.Disable()
                self.menu_p.str_page.endTimePicker.Disable()
                self.menu_p.str_page.openStreamButton.Disable()
        self.menu_p.rep_page.logMsg('- %i data point loaded' % len(stream))
        dlg.Destroy()

        # plot data
        self.OnInitialPlot(stream)
        self.changeStatusbar("Ready")


    def OnOpenURL(self, event):
        dlg = OpenWebAddressDialog(None, title='Open URL')
        if dlg.ShowModal() == wx.ID_OK:
            self.ReactivateStreamPage()
            url = dlg.urlTextCtrl.GetValue()
            if not url.endswith('/'):
                self.changeStatusbar("Loading data ...")
                self.menu_p.str_page.pathTextCtrl.SetValue(url)
                self.menu_p.str_page.fileTextCtrl.SetValue(url.split('/')[-1])
                stream = read(path_or_url=url)
                mintime = stream._get_min('time')
                maxtime = stream._get_max('time')
                self.menu_p.str_page.startDatePicker.SetValue(wx.DateTimeFromTimeT(time.mktime(num2date(mintime).timetuple())))
                self.menu_p.str_page.endDatePicker.SetValue(wx.DateTimeFromTimeT(time.mktime(num2date(maxtime).timetuple())))
                self.menu_p.str_page.startTimePicker.SetValue(num2date(mintime).strftime('%X'))
                self.menu_p.str_page.endTimePicker.SetValue(num2date(maxtime).strftime('%X'))
                self.menu_p.str_page.startDatePicker.Disable()
                self.menu_p.str_page.endDatePicker.Disable()
                self.menu_p.str_page.startTimePicker.Disable()
                self.menu_p.str_page.endTimePicker.Disable()
                self.menu_p.str_page.openStreamButton.Disable()
                self.OnInitialPlot(stream)
                self.changeStatusbar("Ready")
            else:
                self.menu_p.str_page.pathTextCtrl.SetValue(url)
        self.menu_p.rep_page.logMsg('- %i data point loaded' % len(stream))
        dlg.Destroy()        


    def OnOpenDB(self, event):
        # a) get all DATAINFO IDs and store them in a list
        # b) disable pathTextCtrl (DB: dbname)
        # c) Open dialog which lets the user select list and time window
        # d) update stream menu
        if self.db:
            self.menu_p.rep_page.logMsg('- Accessing database ...')
            cursor = self.db.cursor()
            sql = "SELECT DataID, DataMinTime, DataMaxTime FROM DATAINFO"
            cursor.execute(sql)
            output = cursor.fetchall()
            datainfoidlist = [elem[0] for elem in output]
            if len(datainfoidlist) < 1:
                dlg = wx.MessageDialog(self, "No data tables available!\n"
                            "please check your database\n",
                            "OpenDB", wx.OK|wx.ICON_INFORMATION)
                dlg.ShowModal()
                dlg.Destroy()
                return
            dlg = DatabaseContentDialog(None, title='MySQL Database: Get content',datalst=datainfoidlist)
            if dlg.ShowModal() == wx.ID_OK:
                datainfoid = dlg.dataComboBox.GetValue()
                stream = DataStream()
                mintime = stream._testtime([elem[1] for elem in output if elem[0] == datainfoid][0])
                maxtime = stream._testtime([elem[2] for elem in output if elem[0] == datainfoid][0])
                self.menu_p.str_page.startDatePicker.SetValue(wx.DateTimeFromTimeT(time.mktime(mintime.timetuple())))
                self.menu_p.str_page.endDatePicker.SetValue(wx.DateTimeFromTimeT(time.mktime(maxtime.timetuple())))
                self.menu_p.str_page.startTimePicker.SetValue(mintime.strftime('%X'))
                self.menu_p.str_page.endTimePicker.SetValue(maxtime.strftime('%X'))
                self.menu_p.str_page.pathTextCtrl.SetValue('MySQL Database')
                self.menu_p.str_page.fileTextCtrl.SetValue(datainfoid)
            dlg.Destroy()
        else:
            dlg = wx.MessageDialog(self, "Could not access database!\n"
                        "please check your connection\n",
                        "OpenDB", wx.OK|wx.ICON_INFORMATION)
            dlg.ShowModal()
            dlg.Destroy()


    def OnDBConnect(self, event):
        """
        Provide access for local network:
        Open your /etc/mysql/my.cnf file in your editor.
        scroll down to the entry:
        bind-address = 127.0.0.1
        and you can either hash that so it binds to all ip addresses assigned
        #bind-address = 127.0.0.1
        or you can specify an ipaddress to bind to. If your server is using dhcp then just hash it out.
        Then you'll need to create a user that is allowed to connect to your database of choice from the host/ip your connecting from.
        Login to your mysql console:
        milkchunk@milkchunk-desktop:~$ mysql -uroot -p
        GRANT ALL PRIVILEGES ON *.* TO 'user'@'%' IDENTIFIED BY 'some_pass' WITH GRANT OPTION;
        You change out the 'user' to whatever user your wanting to use and the '%' is a hostname wildcard. Meaning that you can connect from any hostname with it. You can change it to either specify a hostname or just use the wildcard.
        Then issue the following:
        FLUSH PRIVILEGES;
        Be sure to restart your mysql (because of the config file editing):
        /etc/init.d/mysql restart
        """
        dlg = DatabaseConnectDialog(None, title='MySQL Database: Connect to')
        if dlg.ShowModal() == wx.ID_OK:
            host = dlg.hostTextCtrl.GetValue()
            user = dlg.userTextCtrl.GetValue()
            passwd = dlg.passwdTextCtrl.GetValue()
            mydb = dlg.dbTextCtrl.GetValue()
            self.db = MySQLdb.connect (host=host,user=user,passwd=passwd,db=mydb)
            if self.db:
                self.DBOpen.Enable(True)
                self.menu_p.rep_page.logMsg('- MySQL Database selcted')
        dlg.Destroy()        



    def OnFileQuit(self, event):
	self.Close()


    def OnSave(self, event):
        textfile = open(os.path.join(self.dirname, self.filename), 'w')
        textfile.write(self.control.GetValue())
        textfile.close()

    def OnSaveAs(self, event):
        if self.askUserForFilename(defaultFile=self.filename, style=wx.SAVE,
                                   **self.defaultFileDialogOptions()):
            self.OnSave(event)
 

    def OnOptionsCalc(self, event):
        dlg = wx.MessageDialog(self, "Coming soon:\n"
                        "Modify calculation options\n",
                        "MagPy by RL", wx.OK|wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()

    def OnOptionsObs(self, event):
        dlg = OptionsObsDialog(None, title='Options: Observatory specifications')
        dlg.ShowModal()
        dlg.Destroy()        

        #dlg = wx.MessageDialog(self, "Coming soon:\n"
        #                "Modify observatory specifications\n",
        #                "PyMag by RL", wx.OK|wx.ICON_INFORMATION)
        #dlg.ShowModal()
        #dlg.Destroy()

    def onOpenAuxButton(self, event):
        if self.askUserForFilename(style=wx.OPEN,
                                   **self.defaultFileDialogOptions()):
            #dat = read_general(os.path.join(self.dirname, self.filename), 0)            
            textfile = open(os.path.join(self.dirname, self.filename), 'r')
            self.menu_p.gen_page.AuxDataTextCtrl.SetValue(textfile.read())
            textfile.close()
            #print dat

    def changeStatusbar(self,msg):
        self.SetStatusText(msg)


    # ################
    # page methods:

    # pages: stream (plot, coordinate), analysis (smooth, filter, fit, baseline etc),
    #          specials(spectrum, power), absolutes (), report (log), monitor (access web socket)

        
    def abs_test(self, event):
        xx = [10,9,8,7,6,5]
        yy = [7,3,8,3,4,2]
        FigurePlot(plot_p,xx,yy)

    def onDrawAnalysisButton(self, event):
        datastruct = []
        fstruct = []
        tmpfstruct = []
        msg = ''
        pltlist = [1,2,3]
        fval = 0 # 0: no reviewed files->only vario, 1: reviewed files

        # get from options
        duration = 380
        bspldeg = 2
        func = "bspline"
        funcweight = 1
        
        stday = self.menu_p.ana_page.startDatePicker.GetValue()
        sd = datetime.fromtimestamp(stday.GetTicks()) 
        enday = self.menu_p.ana_page.endDatePicker.GetValue()
        ed = datetime.fromtimestamp(enday.GetTicks()) 
        instr = self.menu_p.ana_page.varioComboBox.GetValue()
        finstr = self.menu_p.ana_page.scalarComboBox.GetValue()
        pass
    
    def onDrawBaseButton(self, event):
        instr = self.menu_p.bas_page.basevarioComboBox.GetValue()
        stday = self.menu_p.bas_page.startDatePicker.GetValue()
        day = datetime.strftime(datetime.fromtimestamp(stday.GetTicks()),"%Y-%m-%d")
        duration = int(self.menu_p.bas_page.durationTextCtrl.GetValue())
        degree = float(self.menu_p.bas_page.degreeTextCtrl.GetValue())
        func = "bspline"
        useweight = self.menu_p.bas_page.baseweightCheckBox.GetValue()
        #if not os.path.isfile(os.path.join(baselinepath,instr,day+"_"+str(duration)+"_"+'func.obj')):
        #    self.menu_p.rep_page.logMsg(' --- Baseline files recaluclated')
        #    GetBaseline(instr, day, duration, func, degree, useweight)
        #meandiffabs = read_magstruct(os.path.join(baselinepath,instr,"baseline_"+day+"_"+str(duration)+".txt"))
        #diffabs = read_magstruct(os.path.join(baselinepath,instr,"diff2di_"+day+"_"+str(duration)+".txt"))

        #self.plot_p.mainPlot(meandiffabs,diffabs,[],"auto",[1,2,3],['o','o'],1,"Baseline")
        #self.plot_p.canvas.draw()

    def onDrawBaseFuncButton(self, event):
        instr = self.menu_p.bas_page.basevarioComboBox.GetValue()
        stday = self.menu_p.bas_page.startDatePicker.GetValue()
        day = datetime.strftime(datetime.fromtimestamp(stday.GetTicks()),"%Y-%m-%d")
        duration = int(self.menu_p.bas_page.durationTextCtrl.GetValue())
        degree = float(self.menu_p.bas_page.degreeTextCtrl.GetValue())
        #func = self.bascompselect
        #print func
        #func = "bspline"
        useweight = self.menu_p.bas_page.baseweightCheckBox.GetValue()
        recalcselect = self.menu_p.bas_page.baserecalcCheckBox.GetValue()
        self.menu_p.rep_page.logMsg('Base func for %s for range %s minus %d days using %s with degree %s, recalc %d' % (instr,day,duration,func,degree,recalcselect))
        #if not (os.path.isfile(os.path.join(baselinepath,instr,day+"_"+str(duration)+"_"+'func.obj')) and recalcselect == False):
        #    self.menu_p.rep_page.logMsg(' --- Baseline files recaluclated')
        #    GetBaseline(instr, day, duration, func, degree, useweight)
        #meandiffabs = read_magstruct(os.path.join(baselinepath,instr,"baseline_"+day+"_"+str(duration)+".txt"))
        #modelfile = os.path.normpath(os.path.join(baselinepath,instr,day+"_"+str(duration)+"_"+'func.obj'))
        #outof = Model2Struct(modelfile,5000)

        #self.plot_p.mainPlot(meandiffabs,outof,[],"auto",[1,2,3],['o','-'],0,"Baseline function")
        #self.plot_p.canvas.draw()

    def onStabilityTestButton(self, event):
        self.menu_p.rep_page.logMsg(' --- Starting baseline stability analysis')
        stday = self.menu_p.bas_page.startDatePicker.GetValue()
        day = datetime.fromtimestamp(stday.GetTicks()) 

    def onBasCompchanged(self, event):
        self.bascompselect = self.menu_p.bas_page.func[event.GetInt()]

    def onGraCompchanged(self, event):
        self.compselect = self.menu_p.gra_page.comp[event.GetInt()]

    def onGraDrawButton(self, event):
        datastruct = []
        fstruct = []
        tmpfstruct = []
        msg = ''
        pltlist = [1,2,3]
        fval = 0 # 0: no reviewed files->only vario, 1: reviewed files

        # get from options
        duration = 380
        bspldeg = 2
        func = "bspline"
        funcweight = 1
        
        stday = self.menu_p.gra_page.startDatePicker.GetValue()
        sd = datetime.fromtimestamp(stday.GetTicks()) 
        enday = self.menu_p.gra_page.endDatePicker.GetValue()
        ed = datetime.fromtimestamp(enday.GetTicks()) 
        instr = self.menu_p.gra_page.varioComboBox.GetValue()
        finstr = self.menu_p.gra_page.scalarComboBox.GetValue()

        # 1.) Select the datafiles for the instrument
        self.menu_p.rep_page.logMsg('Starting Variometer analysis:')
        # a) produce day list
        day = sd
        daylst = []
        while ed >= day:
            daylst.append(datetime.strftime(day,"%Y-%m-%d"))
            day += timedelta(days=1)
        # b) check whether raw or mod
        datatype = self.menu_p.gra_page.datatypeComboBox.GetValue()
        loadres = self.menu_p.gra_page.resolutionComboBox.GetValue()
        #if loadres == "hour":
        #    strres = "hou"
        #elif loadres == "minute":
        #    strres = "min"
        #elif loadres == "second":
        #    strres = "sec"
        #else:
        #    strres = "raw"
        # c) if reviewed use day lst and check formats (cdf) - use raw if not available
        """
        for day in daylst:
            if datatype == 'reviewed':
                # ToDo: cdf-file read problem                
                # - check for the presence of cdf and txt files
                if os.path.exists(os.path.normpath(os.path.join(preliminarypath,instr,'va_'+day + '_'+ instr+'_' + strres + '.cdf'))):
                    loadname = os.path.normpath(os.path.join(preliminarypath,instr,'va_'+day + '_'+ instr+'_' + strres + '.cdf'))
                    struct = read_magstruct_cdf(loadname)
                    self.menu_p.rep_page.logMsg(' --- cdf for %s' % day)
                elif os.path.exists(os.path.normpath(os.path.join(preliminarypath,instr,'va_'+day + '_'+ instr+'_' + strres + '.txt'))):
                    loadname = os.path.normpath(os.path.join(preliminarypath,instr,'va_'+day + '_'+ instr+'_' + strres + '.txt'))
                    struct = read_magstruct(loadname)
                    self.menu_p.rep_page.logMsg(' --- txt for %s' % day)
                else:
                    struct = readmagdata(day+"-00:00:00",day+"-23:59:59",instr)
                    self.menu_p.rep_page.logMsg(' --- using raw data for %s' % day)
                datastruct.extend(struct)
            else:
                struct = readmagdata(day+"-00:00:00",day+"-23:59:59",instr)
                datastruct.extend(struct)
            # Get f data:
            if (finstr != 'selected vario'):
                fval = 1
                if os.path.exists(os.path.normpath(os.path.join(preliminarypath,finstr,'sc_'+day + '_'+ finstr+'_' + strres + '.cdf'))):
                    fname = os.path.normpath(os.path.join(preliminarypath,finstr,'sc_'+day + '_'+ finstr+'_' + strres + '.cdf'))
                    tmpfstruct = read_magstruct_cdf(fname)
                elif os.path.exists(os.path.normpath(os.path.join(preliminarypath,finstr,'sc_'+day + '_'+ finstr+'_' + strres + '.txt'))):
                    fname = os.path.normpath(os.path.join(preliminarypath,finstr,'sc_'+day + '_'+ finstr+'_' + strres + '.txt'))
                    tmpfstruct = read_magstruct(fname)
                fstruct.extend(tmpfstruct)
            else:
                #tmpfstruct = readmagdata(day+"-00:00:00",day+"-23:59:59",instr)
                fstruct.extend(struct)

        # 2.) Check resolution and give a warning if resolution is too low (provide choice accordingly
        res = [-999,-999]
        xa,xb = CheckTimeResolution(datastruct)
        res[0] = xb[1]
        self.datacont.struct1res = xb[1]

        primstruct = datastruct
                                
        # 3.) Filter the data
        #     a) check resolution and provide choice accordingly
        
        #     b) do the filtering
        filteropt = [1.86506,0]
        msg = ''
        filterdata = []
        
        if self.menu_p.gra_page.resolutionComboBox.GetValue() == "intrinsic":
            self.menu_p.rep_page.logMsg(' --- Using intrinsiy resolution:')
            self.menu_p.rep_page.logMsg(' --- Primary data resolution: %f sec' % (res[0]*24*3600))
            filterdata = primstruct
        else:
            if self.menu_p.gra_page.resolutionComboBox.GetValue() == "hour":
                increment = timedelta(hours=1)
                offset = timedelta(hours=0.5)
                filtertype = "linear"
                incr = ahour
            elif self.menu_p.gra_page.resolutionComboBox.GetValue() == "minute":
                increment = timedelta(minutes=1)
                offset = 0
                filtertype = "gauss"
                incr = aminute
            elif self.menu_p.gra_page.resolutionComboBox.GetValue() == "second":
                increment = timedelta(seconds=1)
                offset = 0
                filtertype = "gauss"
                incr = asecond
            # Prim data
            if (res[0] < incr*0.9):
                filterdata, msg = filtermag(increment,offset,datastruct,filtertype,[],filteropt)
                self.menu_p.rep_page.logMsg(' --- Filtering primary data\n %s' % msg)
            else:
                self.menu_p.rep_page.logMsg(' --- Primary data resolution equal or larger then requested: Skipping filtering')
                filterdata = primstruct

        primstruct = filterdata
        # Filtered data to short for hour data  - didd !! 

        # 4.) Baselinecorrection
        corrdata = []
        bc = self.menu_p.gra_page.baselinecorrCheckBox.GetValue()
        if bc == True:
            # a) get the approporate baseline file  - if not exisiting create it
            endyear = datetime.strftime(ed,"%Y")
            if (datetime.strftime(sd,"%Y")) == (datetime.strftime(ed,"%Y")):
                if endyear == datetime.strftime(datetime.utcnow(),"%Y"):
                    # case -- 1a: sd to ed range within current year
                    day = datetime.strftime(datetime.utcnow(),"%Y-%m-%d")
                else:
                    # case -- 1b: sd to ed range within one year
                    day = datetime.strftime(datetime.strptime(str(int(endyear)+1),"%Y"),"%Y-%m-%d")
            else:
                td = ed-sd
                # case -- 2a: sd to ed range not within one year
                if int(td.days) > duration:
                    # case -- 2b: sd to ed range not within one year and differ by more then 380 days
                    self.menu_p.rep_page.logMsg(' --- Standard duration of baseline exceeded - using %s days now' % td.days)
                    duration = td.days
                day = datetime.strftime(ed,"%Y-%m-%d")
            if not os.path.isfile(os.path.normpath(os.path.join(baselinepath,instr,day+"_"+str(duration)+"_"+'func.obj'))):
                self.menu_p.rep_page.logMsg(' --- Creating baseline file')
                GetBaseline(instr, day, duration, func, bspldeg, funcweight)
            self.menu_p.rep_page.logMsg(' --- used Baseline: %s' % (day+"_"+str(duration)+"_"+'func.obj'))
            # use a day list with selected day for last input parameter
            dayl = sd
            daylst = []
            while ed >= dayl:
                daylst.append(datetime.strftime(dayl,"%Y-%m-%d"))
                dayl += timedelta(days=1)
            for dayl in daylst:
                cdata = BaselineCorr(instr,os.path.join(baselinepath,instr,day+"_"+str(duration)+"_"+'func.obj'),dayl)
                corrdata.extend(cdata)
        else:
            corrdata = primstruct

        primstruct = corrdata

        # 5.) F (if T is available)
        if fstruct == []:
            self.menu_p.rep_page.logMsg(' --- Use Scalar analysis first')
            dlg = wx.MessageDialog(self, "For using F you need to conduct the scalar analysis first:\n produce -reviewed- scalar data",
                        "PyMag by RL", wx.OK|wx.ICON_INFORMATION)
            dlg.ShowModal()
            dlg.Destroy()
            self.menu_p.gra_page.fCheckBox.Disable()
            self.menu_p.gra_page.dfCheckBox.Disable()
            newdatastruct = primstruct
            mf = float("nan")
        elif fval == 0:
            # only variovalues available
            self.menu_p.rep_page.logMsg(' --- Can only use vario x,y,z')
            self.menu_p.gra_page.fCheckBox.Enable()
            self.menu_p.gra_page.dfCheckBox.Disable()
            newdatastruct,mf,fmsg = combineVarioandF(primstruct,fstruct,fval,[0,2,20,22])
        else:
            newdatastruct,mf,fmsg = combineVarioandF(primstruct,fstruct,fval,[0,2,20,22])
            self.menu_p.gra_page.fCheckBox.Enable()
            self.menu_p.gra_page.dfCheckBox.Enable()
            self.menu_p.rep_page.logMsg(' --- Combination of Vario and F data:\n %s' % fmsg)

        
        valobsini = 10
        if self.menu_p.gra_page.baselinecorrCheckBox.GetValue():
            var = 'DI'
        else:
            var = self.menu_p.gra_page.varioComboBox.GetValue()
        self.menu_p.gra_page.dfIniTextCtrl.SetValue('dF(%s - %s): %.2f nT' % (var,finstr,valobsini))
        self.menu_p.gra_page.dfCurTextCtrl.SetValue('dF(cur): %.2f nT' % mf)
        primstruct = newdatastruct

        #for i in range(10,1000):
        #    print primstruct[i].f,primstruct[i].flag
            
        drawf = self.menu_p.gra_page.fCheckBox.GetValue()
        if drawf == True:
            pltlist.append(4)
        drawdf = self.menu_p.gra_page.dfCheckBox.GetValue()
        if drawdf == True:
            pltlist.append(8)

        # 6.) Draw temperature function (if T is available)
        # check whether temp data is available
        drawt = self.menu_p.gra_page.tCheckBox.GetValue()
        if drawt == True:
            pltlist.append(9)

        # 7.) Showing flagged data
        secdata = []
        seconddata = []
        flagging = self.menu_p.gra_page.showFlaggedCheckBox.GetValue()
        if flagging:
            try:
                acceptedflags = [0,1,2,3,10,11,12,13,20,21,22,23,30,31,32,33]
                secdata, msg = filterFlag(primstruct,acceptedflags)
                self.menu_p.rep_page.logMsg(' --- flagged data added \n %s' % msg)
            except:
                self.menu_p.rep_page.logMsg(' --- Unflagging failed')
                pass
     
        # 8.) Changing coordinatesystem
        self.menu_p.rep_page.logMsg('Vario: Selected %s' % self.compselect)
        if (self.compselect == "xyz"):
            showdata = primstruct
            if secdata != []:
                seconddata = secdata
        elif (self.compselect == "hdz"):
            showdata = convertdatastruct(primstruct,"xyz2hdz")
            if secdata != []:
                seconddata = convertdatastruct(secdata,"xyz2hdz")
        elif (self.compselect == "idf"):
            showdata = convertdatastruct(primstruct,"xyz2idf")
            if secdata != []:
                seconddata = convertdatastruct(secdata,"xyz2idf")
        else:
            showdata = primstruct
            if secdata != []:
                seconddata = secdata

        self.datacont.magdatastruct1 = primstruct

        displaydata, filtmsg = filterFlag(showdata,[0,2,10,12,20,22,30,32])

        self.plot_p.mainPlot(displaydata,seconddata,[],"auto",pltlist,['-','-'],0,"Variogram")
        self.plot_p.canvas.draw()
        """

    def onSaveVarioButton(self, event):
        self.menu_p.rep_page.logMsg('Save button pressed')
        if len(self.datacont.magdatastruct1) > 0:
            # 1.) open format choice dialog
            choicelst = [ 'txt', 'cdf',  'netcdf' ]
            # iaga and wdc do not make sense for scalar values
            # ------ Create the dialog
            dlg = wx.SingleChoiceDialog( None, message='Save data as', caption='Choose dataformat', choices=choicelst)
            # ------ Show the dialog
            if dlg.ShowModal() == wx.ID_OK:
                response = dlg.GetStringSelection()

                # 2.) message box informing about predefined path
                # a) generate predefined path and name: (scalar, instr, mod, resolution
                firstday = datetime.strptime(datetime.strftime(num2date(self.datacont.magdatastruct1[0].time).replace(tzinfo=None),"%Y-%m-%d"),"%Y-%m-%d")
                lastday = datetime.strptime(datetime.strftime(num2date(self.datacont.magdatastruct1[-1].time).replace(tzinfo=None),"%Y-%m-%d"),"%Y-%m-%d")
                tmp,res = CheckTimeResolution(self.datacont.magdatastruct1)
                loadres = self.menu_p.gra_page.resolutionComboBox.GetValue()
                if loadres == 'intrinsic':
                    resstr = 'raw'
                else:
                    resstr = GetResolutionString(res[1])
                instr = self.menu_p.str_page.scalarComboBox.GetValue()
                # b) create day list
                day = firstday
                daylst = []
                while lastday >= day:
                    daylst.append(datetime.strftime(day,"%Y-%m-%d"))
                    day += timedelta(days=1)

                # 3.) save data
                if not os.path.exists(os.path.normpath(os.path.join(preliminarypath,instr))):
                    os.makedirs(os.path.normpath(os.path.join(preliminarypath,instr)))

                curnum = 0
                for day in daylst:
                    savestruct = []
                    idx = curnum
                    for idx, elem in enumerate(self.datacont.magdatastruct1):
                        if datetime.strftime(num2date(elem.time), "%Y-%m-%d") == day:
                            savestruct.append(self.datacont.magdatastruct1[idx])
                            curnum = idx

                    if response == "txt":
                        savename = os.path.normpath(os.path.join(preliminarypath,instr,'va_'+day + '_'+ instr+'_' + resstr + '.txt'))
                        write_magstruct(savename,savestruct)
                        self.menu_p.rep_page.logMsg('Saved %s data for %s' % (response,day))
                    if response == "cdf":
                        savename = os.path.normpath(os.path.join(preliminarypath,instr,'va_'+day + '_'+ instr+'_' + resstr + '.cdf'))
                        write_magstruct_cdf(savename,savestruct)
                        self.menu_p.rep_page.logMsg('Saved %s data for %s' % (response,day))
       
                # 4.) Open a message Box to inform about save

            # ------ Destroy the dialog
            dlg.Destroy()


    # ################
    # Stream functions

    def onOpenStreamButton(self, event):
        stream = DataStream()
        stday = self.menu_p.str_page.startDatePicker.GetValue()
        sttime = self.menu_p.str_page.startTimePicker.GetValue()
        sd = datetime.fromtimestamp(stday.GetTicks()) 
        enday = self.menu_p.str_page.endDatePicker.GetValue()
        ed = datetime.fromtimestamp(enday.GetTicks()) 
        path = self.menu_p.str_page.pathTextCtrl.GetValue()
        files = self.menu_p.str_page.fileTextCtrl.GetValue()
        
        if path == "":
            dlg = wx.MessageDialog(self, "Please select a path first!\n"
                        "go to File -> Select Dir\n",
                        "OpenStream", wx.OK|wx.ICON_INFORMATION)
            dlg.ShowModal()
            dlg.Destroy()
            return
        if files == "":
            dlg = wx.MessageDialog(self, "Please select a file first!\n"
                        "accepted wildcards are * (e.g. *, *.dat, FGE*)\n",
                        "OpenStream", wx.OK|wx.ICON_INFORMATION)
            dlg.ShowModal()
            dlg.Destroy()
            return

        start= datetime.strftime(sd, "%Y-%m-%d %H:%M:%S")
        end= datetime.strftime(ed, "%Y-%m-%d %H:%M:%S")

        try:
            self.changeStatusbar("Loading data ...")
            if path.endswith('/'):
                address = path
                stream = read(path_or_url=address,starttime=sd, endtime=ed)
            elif path.startswith('MySQL'):
                start= datetime.strftime(sd, "%Y-%m-%d %H:%M:%S")
                end= datetime.strftime(ed, "%Y-%m-%d %H:%M:%S")
                stream = db2stream(self.db, None, start, end, files, None)
            else:
                address = os.path.join(path,files)
                stream = read(path_or_url=address,starttime=sd, endtime=ed)
            mintime = stream._get_min('time')
            maxtime = stream._get_max('time')
            self.menu_p.str_page.startDatePicker.SetValue(wx.DateTimeFromTimeT(time.mktime(num2date(mintime).timetuple())))
            self.menu_p.str_page.endDatePicker.SetValue(wx.DateTimeFromTimeT(time.mktime(num2date(maxtime).timetuple())))
            self.menu_p.str_page.startTimePicker.SetValue(num2date(mintime).strftime('%X'))
            self.menu_p.str_page.endTimePicker.SetValue(num2date(maxtime).strftime('%X'))
            self.menu_p.str_page.startDatePicker.Disable()
            self.menu_p.str_page.endDatePicker.Disable()
            self.menu_p.str_page.startTimePicker.Disable()
            self.menu_p.str_page.endTimePicker.Disable()
            self.menu_p.str_page.openStreamButton.Disable()
        except:
            dlg = wx.MessageDialog(self, "Could not read file(s)!\n"
                        "check your files and/or selected time range\n",
                        "OpenStream", wx.OK|wx.ICON_INFORMATION)
            dlg.ShowModal()
            dlg.Destroy()
            return

        #self.menu_p.str_page.lengthStreamTextCtrl.SetValue(str(len(stream)))
        self.OnInitialPlot(stream)
        self.changeStatusbar("Ready")


    # ####################
    # Absolute functions
    
    def onAbsCompchanged(self, event):
        self.abscompselect = self.menu_p.abs_page.comp[event.GetInt()]

    def onDrawAllAbsButton(self, event):
        # 1.) Load data
        """
        meanabs = read_magstruct(os.path.normpath(os.path.join(abssummarypath,'absolutes.out')))
        self.menu_p.rep_page.logMsg('Absolute Anaylsis: Selected %s' % self.abscompselect)
         2.) Select components
        if (self.abscompselect == "xyz"):
            showdata = meanabs
        elif (self.abscompselect == "hdz"):
            showdata = convertdatastruct(meanabs,"xyz2hdz")
        elif (self.abscompselect == "idf"):
            showdata = convertdatastruct(meanabs,"xyz2idf")
        else:
            showdata = meanabs
        # 3.) Select flagging
        secdata = []
        flagging = self.menu_p.abs_page.showFlaggedCheckBox.GetValue()
        if flagging:
            try:
                acceptedflags = [1,3]
                secdata, msg = filterFlag(showdata,acceptedflags)
                print len(secdata)
                self.menu_p.rep_page.logMsg(' --- flagged data added \n %s' % msg)
            except:
                self.menu_p.rep_page.logMsg(' --- Unflagging failed')
                pass

        # 4.) Add data to container
        # use xyz data here
        #self.datacont.magdatastruct1 = meanabs

        #display1data, filtmsg = filterFlag(showdata,[0,2])

        #self.plot_p.mainPlot(display1data,secdata,[],"auto",[1,2,3],['o','o'],0,"Absolutes")
        """
        self.plot_p.canvas.draw()

    def onSaveFlaggedAbsButton(self, event):
        self.menu_p.rep_page.logMsg(' --- Saving data - soon')
        savestruct=[]
        #for elem in self.datacont.magdatastruct1:
        #    savestruct.append(elem)
        #savename = os.path.normpath(os.path.join(abssummarypath,'absolutes.out'))
        #write_magstruct(savename,savestruct)
        self.menu_p.rep_page.logMsg('Saved Absolute file')

    def onCalcAbsButton(self, event):
        chgdep = LoadAbsDialog(None, title='Load Absolutes')
        chgdep.ShowModal()
        chgdep.Destroy()        

        #abslist = read_general(os.path.join(abssummarypath,'absolutes.out'),0)
        #meanabs = extract_absolutes(abslist)
        #self.plot_p.mainPlot(meanabs,[],[],"auto",[1,2,3],['o','o'],0,"Absolutes")
        self.plot_p.canvas.draw()

    def onNewAbsButton(self, event):
        abslist = read_general(os.path.join(abssummarypath,'absolutes.out'),0)
        meanabs = extract_absolutes(abslist)
        self.plot_p.mainPlot(meanabs,[],[],"auto",[1,2,3],['o','o'],0,"Absolutes")
        self.plot_p.canvas.draw()

    def onOpenAbsButton(self, event):
        abslist = read_general(os.path.join(abssummarypath,'absolutes.out'),0)
        meanabs = extract_absolutes(abslist)
        self.plot_p.mainPlot(meanabs,[],[],"auto",[1,2,3],['o','o'],0,"Absolutes")
        self.plot_p.canvas.draw()

    def addMsg(self, msg):
        print 'Got here'
        #mf = MainFrame(None,"PyMag")
        #mf.changeStatusbar('test')
        #self.menu_p.str_page.deltaFTextCtrl.SetValue('test')
        #self.menu_p.rep_page.logMsg('msg')
        #self.menu_p.str_page.deltaFTextCtrl.SendTextUpdatedEvent()

        
app = wx.App(redirect=False)
frame = MainFrame(None,-1,"")
frame.Show()
app.MainLoop()
