# -*- coding: utf-8 -*-a
"""
Dependency:
    geoviews
    holoviews

Class:
    Visualize()

Todo:
    * faster and efficient IO
    * discharge hydrograph
    * visualize multiple output over time
"""
import pandas as pd
import numpy as np
import xarray as xr
import geoviews as gv
import holoviews as hv
from holoviews.operation import datashader
from bokeh.models import WMTSTileSource
from bokeh.io import save
hv.extension("bokeh")

class Visualize(object):
    """Wrapper to visualize output from lisflood-fp"""

    def __init__(self):
        
        self.mapTiles = self.__defineMap()
    
    # basic IO modules
    def __defineMap(self):
        """define a backgound map tile source"""
        from bokeh.models import WMTSTileSource
        url = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{Z}/{Y}/{X}.jpg'
        wmts = WMTSTileSource(url=url)
        mapTiles = gv.WMTS(wmts)
        return mapTiles

    def readData(self, filename, headerNum=6):
        """read output file from LISFLOOD-FP.
        
        Args:
            filename (str): a file path to the output.
            headerNum (int): a number of header lines.
        
        Returns:
            dataframe containing results (pandas.dataframe)
        """
        df = pd.read_csv(filename, skiprows=headerNum, header=None, sep="\s+")
        return df

    def readCache(self, filename, kind="nc"):
        """
        Read cached model domain.
        This cache should be created from the lispy.PreProcess.(mf)preprocess()

        Args:
            filename (str): a file path of cached file.  
            kind (nc): data format type

        Returns:
            lats (np.ndarray): latitudinal series of your domain.
            lons (np.ndarray): longitudinal series of your domain.
        """
        if kind == "nc":
            data = (xr.open_dataset(filename)).to_array()
            lats = data.lat.values
            lons = data.lon.values
        else:
            raise IOError("data type %s is not supported." % kind)
        return lats, lons

    def constDataArray(self, df, lats, lons, name, undef=-9999):
        """
        constract DataArray from pandas.dataframe. Mask undefined values.
        
        Args:
            df (pandas.dataframe): data frame of your 2d output.
            lats (numpy.ndarray): latitudinal series of your map domain.
            lons (numpy.ndarray): longitudinal series of your map domain.
            name (str): name of you output (e.g., width, elevation, etc.).
            undef (int or float): undefined value in your output.
        
        Returns:
            DataArray of your output (xarray.DataArray)
        """
        data = df.values
        data[data == undef] = np.nan
        dArray = xr.DataArray(data, coords={"lat":lats, "lon":lons}, dims=["lat","lon"]).rename(name)
        return dArray

    def constDataSet(self, dArrayList, dateList):
        """
        constract DataSet from xarray.DataArray. Create new dimention "time".
        
        Args:
            dArrayList (list): lisf of DataArray.
            timeList (list): list of datetime.datetime. The order should be identical to the dArrayList.
        
        Returns:
            xarray.DataSet
        """
        dataset = xr.concat(dArrayList, "time")
        dataset["time"] = dateList

        return dataset

    # visualization modules
    def plotMap(self, dArray, name, width=500, height=250, cmap="gist_earth_r", dataShader=True, alpha=0.5):
        """
        plot the DataArray onto the map.
        
        Args:
            dArray (xarray.DataArray): DataArray of your output.
            name (str): name of your data
            width (int): width of the output image
            height (int): height of the output image
            cmap (str): colormap
            alpha (float): alpha value
        
        Returns:
            bokeh image object
        """
        dataset = gv.Dataset(dArray)
        img = dataset.to(gv.Image, ["lon","lat"], name)
        if dataShader:
            img = datashader.regrid(img)
        img_out = img.opts(width=width, height=height, alpha=alpha, colorbar=True, cmap=cmap, tools=["hover"]) * self.mapTiles
        return img_out

    # higher ranked API for easy use
    def show(self, filename, name, cacheFile, dataShader=True, undef=-9999):
        """Higher API for an instant visualization of 2D map output.
        
        Args:
            filename (str): a file path to your output
            name (str): a name of your output (e.g. width, elevation, etc.)
            cacheFile (str): a file path to your cached netcdf data (should be in cache/ directory)
            undef (int or float): undefined value in your output data

        Returns:
            bokeh image object
        """
        df = self.readData(filename)
        lats, lons = self.readCache(cacheFile)
        dArray = self.constDataArray(df, lats, lons, name, undef=undef)
        img = self.plotMap(dArray, name, dataShader=dataShader)
        return img

    def animate(self, filenamefmt, name, cacheFile, startIdx, endIdx, startDate, freq, dataShader=True, undef=-9999):
        """
        Higher API for an instant visualization of 2D map output with time sliders.
        
        Args:
            filenamefmt (str): a file name format (path format) to visualize.
            name (str): a name of your output (e.g. width, elevation, etc.)
            cacheFile (str): a file path to your cached netcdf data (should be in cache/ directory)
            startIdx (int): starting index to visualize.
            endIdx (int): ending index to visualize.
            startDate (datetime.datetime): starting datetime
            dataShader (bool): using datashader or not.
            undef (int or float): undefined value in your output data

        Returns:
            image object
        """
        periods = endIdx - startIdx
        dateList = pd.date_range(start=startDate, periods=periods, freq=freq)
        lats, lons = self.readCache(cacheFile)
        dArrayList = []
        for i in range(startIdx, endIdx):
            filename = filenamefmt%i
            df = self.readData(filename)
            dArray = self.constDataArray(df, lats, lons, name, undef=undef)
            dArrayList.append(dArray)
        dSet = self.constDataSet(dArrayList, dateList)
        img = self.plotMap(dSet, name, dataShader=dataShader)
        return img

    def saveHtml(self, img, outName):
        """save bokeh object in a outName html file."""
        save(img, outName)

