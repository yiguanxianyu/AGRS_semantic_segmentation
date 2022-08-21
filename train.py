# -*- coding: utf-8 -*-

"""
AGRS_semantic_segmentation
模型训练
~~~~~~~~~~~~~~~~
code by wHy
Aerospace Information Research Institute, Chinese Academy of Sciences
751984964@qq.com
"""
from tkinter.tix import Tree
import torch
import os
import time
import numpy as np
from tqdm import tqdm
from torchsummary import summary

from framework import MyFrame
from loss import CrossEntropyLoss2d, FocalLoss2d
from data import MyDataLoader, DataTrainInform

from networks.DLinknet import DLinkNet34, DLinkNet50, DLinkNet101   
from networks.Unet import Unet
from networks.Dunet import Dunet
from networks.Deeplab_v3_plus import DeepLabv3_plus
from networks.FCN8S import FCN8S
from networks.DABNet import DABNet
from networks.Segformer import Segformer

'''参数设置'''
trainListRoot = r'G:\Huyang_test_0808\2-trainlist\trainlist_0808_first_2.txt' # 训练样本列表
save_model_path = r'G:\Huyang_test_0808\3-weights' # 训练模型保存路径  
model = Unet # 选择的训练模型
save_model_name = 'Unet-huyang_test_0808_first_2_s1.2.th' # 训练模型保存名
mylog = open('logs/'+save_model_name[:-3]+'.log', 'w') # 日志文件   
loss = FocalLoss2d # 损失函数
classes_num = 3 # 样本类别数"""  """
batch_size = 4 # 计算批次大小
init_lr = 0.0005 # 初始学习率
lr_mode = 0 # 学习率更新模式，0为等比下降，1为标准下降
total_epoch = 300 # 训练次数
band_num = 8 # 影像的波段数
if_norm_label = False # 是否对标签进行归一化 针对0/255二分类标签

simulate_batch_size = False #是否模拟大batchsize；除非显存太小一般不开启
simulate_batch_size_num = 4 #模拟batchsize倍数 最终batchsize = simulate_batch_size_num * batch_size

label_weight_scale_factor = 1.2 #标签权重的指数缩放系数 1为不缩放

'''收集系统环境信息'''
tic = time.time()
format_time = time.asctime(time.localtime(tic))
print(format_time)
mylog.write(format_time + '\n')

print('Is cuda availabel: ', torch.cuda.is_available())
print('Cuda device count: ', torch.cuda.device_count())
print('Current device: ', torch.cuda.current_device())

'''收集数据集信息'''
dataCollect = DataTrainInform(classes_num=classes_num, trainlistPath=trainListRoot, band_num=band_num, 
                            label_norm=if_norm_label, label_weight_scale_factor=label_weight_scale_factor) # 计算数据集信息
data_dict = dataCollect.collectDataAndSave()
if data_dict is None:
    print("error while pickling data. Please check.")
    exit(-1)
print('data mean:', data_dict['mean'])
print('data std: ', data_dict['std'])
print('label weight: ', data_dict['classWeights'])
print('img shape: ', data_dict['img_shape'])
mylog.write('data_dict: ' + str(data_dict) + '\n')
mylog.flush()

'''初始化solver'''
weight = torch.from_numpy(data_dict['classWeights']).cuda()
loss = loss(weight=weight) 

solver = MyFrame(net=model(num_classes=classes_num, band_num = band_num), loss=loss, lr=init_lr) # 初始化网络，损失函数，学习率

save_model_full_path = save_model_path + '/' + save_model_name
if os.path.exists(save_model_full_path):
    solver.load(save_model_full_path)
    print('---------\n***Resume Training***\n---------')
else:
    print('---------\n***New Training***\n---------')

'''输出模型信息'''
torch_shape = np.array(data_dict['img_shape'])
torch_shape = [torch_shape[2], torch_shape[0], torch_shape[1]]
summary((solver.net), input_size = tuple(torch_shape), batch_size=batch_size)

'''初始化dataloader'''
dataset = MyDataLoader(root = trainListRoot, normalized_Label=if_norm_label, data_dict=data_dict, band_num=band_num) # 读取训练数据集
data_loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=True, num_workers=0) # 定义训练数据装载器
print('Number of Iterations: ', int(len(dataset)/batch_size))

'''模型训练'''
# 初始化最佳loss和未优化epoch轮数
train_epoch_best_loss = 100 
no_optim = 0
print('---------')

for epoch in tqdm(range(1, total_epoch + 1)):
    
    data_loader_iter = iter(data_loader) # 迭代器
    train_epoch_loss = 0
    cnt = 0
    for img, mask in tqdm(data_loader_iter):
        cnt = cnt + 1
        solver.set_input(img, mask)
        if simulate_batch_size:
            if (cnt % simulate_batch_size_num == 0): # 模拟大batchsize
                train_loss = solver.optimize(ifStep=True)
            else:
                train_loss = solver.optimize(ifStep=False) 
        else:
            train_loss = solver.optimize(ifStep=True) # 非模拟大batchsize 每次迭代都更新参数
        train_epoch_loss += train_loss
    train_epoch_loss /= len(data_loader_iter)

    print('\n---------')
    print('epoch:',epoch, '  training time:', int(time.time()-tic), 's')
    print('epoch average train loss:',train_epoch_loss)
    print('current learn rate: ', solver.optimizer.state_dict()['param_groups'][0]['lr'])
    
    if lr_mode == 0:
        if train_epoch_loss >= train_epoch_best_loss: 
            no_optim += 1
        else: # 若当前epoch的loss小于之前最好的loss
            no_optim = 0
            train_epoch_best_loss = train_epoch_loss # 保留当前epoch的loss
            solver.save(save_model_full_path)
        if no_optim > 15:
            print(mylog, 'early stop at %d epoch' % epoch)
            print('early stop at %d epoch' % epoch)
            break
        if no_optim > 3:
            if solver.old_lr < 1e-6:
                break
            solver.load(save_model_full_path)
            solver.update_lr_geometric_decline(2.0, factor = True, mylog = mylog)
            no_optim = 0
    elif lr_mode == 1:
        if train_epoch_loss >= train_epoch_best_loss:
            train_epoch_best_loss = train_epoch_loss
            solver.save(save_model_full_path)
        solver.update_lr_standard(init_lr=init_lr, now_it=epoch, total_it=total_epoch+1, mylog = mylog)

    mylog.flush()

print('\n---------')
print('Training completed')
mylog.close()