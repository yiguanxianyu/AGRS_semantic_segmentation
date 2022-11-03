#!/.conda/envs/learn python
# -*- coding: utf-8 -*-

"""
批量栅格转矢量
~~~~~~~~~~~~~~~~
code by wHy
Aerospace Information Research Institute, Chinese Academy of Sciences
751984964@qq.com
"""
from pathlib import Path
import gdal
import os
import ogr
import osr
import sys
import math
from osgeo.ogr import Geometry, Layer
from tqdm import tqdm
import numpy as np
import fnmatch

def smoothing(inShp, fname, bdistance=0.001):
    """
    :param inShp: 输入的矢量路径
    :param fname: 输出的矢量路径
    :param bdistance: 缓冲区距离
    :return:
    """
    ogr.UseExceptions()
    in_ds = ogr.Open(inShp)
    in_lyr = in_ds.GetLayer()
    # 创建输出Buffer文件
    driver = ogr.GetDriverByName('ESRI Shapefile')
    if Path(fname).exists():
        driver.DeleteDataSource(fname)
    # 新建DataSource，Layer
    out_ds = driver.CreateDataSource(fname)
    out_lyr = out_ds.CreateLayer(fname, in_lyr.GetSpatialRef(), ogr.wkbPolygon)
    def_feature = out_lyr.GetLayerDefn()
    # 遍历原始的Shapefile文件给每个Geometry做Buffer操作
    for feature in in_lyr:
        geometry = feature.GetGeometryRef()
        buffer = geometry.Buffer(bdistance).Buffer(-bdistance)
        out_feature = ogr.Feature(def_feature)
        out_feature.SetGeometry(buffer)
        out_lyr.CreateFeature(out_feature)
        out_feature = None
    out_ds.FlushCache()
    del in_ds, out_ds


def raster2poly(raster, outshp):
    """栅格转矢量
    Args:
        raster: 栅格文件名
        outshp: 输出矢量文件名

    Returns:
    """ 
    inraster = gdal.Open(raster)  # 读取路径中的栅格数据
    inband = inraster.GetRasterBand(1)  # 这个波段就是最后想要转为矢量的波段，如果是单波段数据的话那就都是1
    prj = osr.SpatialReference()
    prj.ImportFromWkt(inraster.GetProjection())  # 读取栅格数据的投影信息，用来为后面生成的矢量做准备
 
    drv = ogr.GetDriverByName("ESRI Shapefile")
    if os.path.exists(outshp):  # 若文件已经存在，则删除它继续重新做一遍
        drv.DeleteDataSource(outshp)
    Polygon = drv.CreateDataSource(outshp)  # 创建一个目标文件
    Poly_layer = Polygon.CreateLayer(raster[:-4], srs=prj, geom_type=ogr.wkbMultiPolygon)  # 对shp文件创建一个图层，定义为多个面类
    newField = ogr.FieldDefn('pValue', ogr.OFTReal)  # 给目标shp文件添加一个字段，用来存储原始栅格的pixel value
    Poly_layer.CreateField(newField)
 
    gdal.FPolygonize(inband, None, Poly_layer, 0)  # 核心函数，执行的就是栅格转矢量操作
    Polygon.SyncToDisk()
    Polygon = None


os.environ['GDAL_DATA'] = r'C:\Users\75198\.conda\envs\learn\Lib\site-packages\GDAL-2.4.1-py3.6-win-amd64.egg-info\gata-data' #防止报error4错误

gdal.SetConfigOption("GDAL_FILENAME_IS_UTF8", "YES")
gdal.SetConfigOption("SHAPE_ENCODING", "GBK")

tif_img_path = r'E:\projict_UAV_yunnan\3-predict_result'
shp_img_path = r'E:\projict_UAV_yunnan\4-predict_result_shp'

listpic = fnmatch.filter(os.listdir(tif_img_path), '*.tif')
for img in tqdm(listpic):
    tif_img_full_path = tif_img_path + '/' + img
    shp_full_path = shp_img_path + '/' + img[:-4] + '.shp'
    print('start processing: '+ img)
    raster2poly(tif_img_full_path, shp_full_path)

    ogr.RegisterAll()# 注册所有的驱动

    driver = ogr.GetDriverByName('ESRI Shapefile')
    shp_dataset = ogr.Open(shp_full_path, 1) # 0只读模式，1读写模式
    if shp_full_path is None:
        print('Failed to open shp_1')

    ly = shp_dataset.GetLayer()

    '''删除矢量化结果中gridcode=0的要素'''
    feature = ly.GetNextFeature()
    while feature is not None:
        gridcode = feature.GetField('pValue')
        if gridcode == 0:
            delID = feature.GetFID()
            ly.DeleteFeature(int(delID))
        feature = ly.GetNextFeature()
    ly.ResetReading() #重置
    del shp_dataset

    '''平滑矢量'''
    #smooth_shp_full_path = shp_img_path + '/' + 'smooth_' + img[:-4] + '.shp'
    #smoothing(shp_full_path, smooth_shp_full_path, bdistance=0.15)