import json
from collections import OrderedDict
from pathlib import Path
import os
import pickle
import matplotlib.pyplot as plt
import cv2

import monai
import nibabel as nib
import numpy as np
import skimage
import scipy
import torch
import SimpleITK as sitk

from batchgenerators.dataloading.data_loader import DataLoader
from monai.transforms import Compose, EnsureType
from picai_baseline.unet.training_setup.image_reader import SimpleITKDataset
from torch.utils.data import Dataset, DataLoader


class PICAI2021Dataset:
    def __init__(self, data_dir, transforms=None, fold_id=0, scan_set='', input_size=128,
                 resize_mode='interpolate', mask=True, crop_prostate=True, padding=0, task='cls'):
        # ignore_list = ['10084_1000084', '11441_1001465', '10152_1000154']  # '11441_1001465'
        files_dir = os.path.join(data_dir, f'fold_{fold_id}',scan_set) if (scan_set == 'train' or scan_set == 'val') else data_dir
        self.scan_list = [os.path.join(files_dir,f) for f in os.listdir(files_dir) if f.endswith('.pkl')]
        # self.scan_list = [os.path.join(files_dir, f) for f in os.listdir(files_dir) if f.endswith('.pkl') and f.split('.')[0] not in ignore_list]
        self.input_size = input_size
        self.mask = mask
        self.resize_mode = resize_mode
        self.crop_prostate = crop_prostate
        self.padding = padding
        self._transforms = transforms
        self.task = task

    def __len__(self):
        return len(self.scan_list)

    def __getitem__(self, idx):
        with open(self.scan_list[idx], 'rb') as handle:
            scan_dict = pickle.load(handle)

        img_t2w = scan_dict['modalities']['t2w']
        img_adc = scan_dict['modalities']['adc']
        img_dwi = scan_dict['modalities']['dwi']
        prostate_slices = np.ones(scan_dict['prostate_mask'].shape[0], dtype=bool)

        if self.mask:
            img_t2w *= scan_dict['prostate_mask']
            img_adc *= scan_dict['prostate_mask']
            img_dwi *= scan_dict['prostate_mask']
            if self.crop_prostate:
                y1, y2, x1, x2 = get_square_crop_coords(scan_dict['prostate_mask'], padding=self.padding) # CHECK HERE
                prostate_slices = np.sum(scan_dict['prostate_mask'], axis=(1,2)) > 0
                img_t2w = img_t2w[prostate_slices, y1:y2, x1:x2]
                img_adc = img_adc[prostate_slices, y1:y2, x1:x2]
                img_dwi = img_dwi[prostate_slices, y1:y2, x1:x2]

        if self.input_size != img_t2w.shape[1]:
            if self.resize_mode == 'interpolate' or (self.resize_mode == 'padding' and self.input_size < img_t2w.shape[1]):
                img_t2w = resize_scan(img_t2w, size=self.input_size)
                img_adc = resize_scan(img_adc, size=self.input_size)
                img_dwi = resize_scan(img_dwi, size=self.input_size)
            elif self.resize_mode == 'padding':
                padding = self.input_size - img_t2w.shape[1]
                side_pad = padding//2
                if padding % 2 == 0:
                    img_t2w = np.pad(img_t2w, ((0,0),(side_pad,side_pad),(side_pad,side_pad)))
                    img_adc = np.pad(img_adc, ((0,0),(side_pad,side_pad),(side_pad,side_pad)))
                    img_dwi = np.pad(img_dwi, ((0,0),(side_pad,side_pad),(side_pad,side_pad)))
                else:
                    img_t2w = np.pad(img_t2w, ((0,0),(side_pad,side_pad+1),(side_pad,side_pad+1)))
                    img_adc = np.pad(img_adc, ((0,0),(side_pad,side_pad+1),(side_pad,side_pad+1)))
                    img_dwi = np.pad(img_dwi, ((0,0),(side_pad,side_pad+1),(side_pad,side_pad+1)))

        # f, ax = plt.subplots(1, 3)
        # slice = 10
        # ax[0].imshow(img_t2w[slice,:,:], cmap='gray')
        # ax[1].imshow(img_adc[slice,:,:], cmap='gray')
        # ax[2].imshow(img_dwi[slice,:,:], cmap='gray')
        # plt.show()

        # img_concat = np.concatenate([img_t2w, img_adc, img_dwi], axis=1).squeeze(0).transpose(1, 0, 2, 3)
        img_concat = np.stack([img_t2w, img_adc, img_dwi], axis=1)

        # apply the transforms
        if self._transforms is not None:
            img_concat = self._transforms(img_concat)

        # if self.seg_transform is not None:
        #     seg = apply_transform(self.seg_transform, seg, map_items=False)
        labels = scan_dict['cls_labels'] if self.task=='cls' else scan_dict['seg_labels']
        labels =labels[prostate_slices]

        return tuple([img_concat, labels])
        # return tuple([img_concat, seg_labels if self.get_seg_labels else cls_labels])

def get_square_crop_coords(mask, padding=0):
    y1 = x1 = np.inf
    y2 = x2 = 0
    for slice_num in range(mask.shape[0]):
        y_nonzero, x_nonzero = np.nonzero(mask[slice_num, :, :])
        if len(y_nonzero) > 0:
            y1 = min(np.min(y_nonzero), y1)
            y2 = max(np.max(y_nonzero), y2)
            x1 = min(np.min(x_nonzero), x1)
            x2 = max(np.max(x_nonzero), x2)

    crop_x_diff = x2 - x1
    crop_y_diff = y2 - y1
    if crop_x_diff > crop_y_diff:
        pad = crop_x_diff - crop_y_diff
        y1_temp, y2_temp = y1, y2
        y1 -= int(min(y1_temp, pad // 2) + max(y2_temp + np.ceil(pad / 2) - mask.shape[1], 0))
        y2 += int(min(np.ceil(pad / 2), mask.shape[1] - y2_temp) + max(0 - (y1_temp - pad // 2), 0))
    elif crop_y_diff > crop_x_diff:
        pad = crop_y_diff - crop_x_diff
        x1_temp, x2_temp = x1, x2
        x1 -= int(min(x1_temp, pad // 2) + max(x2_temp + np.ceil(pad / 2) - mask.shape[1], 0))
        x2 += int(min(np.ceil(pad / 2), mask.shape[1] - x2_temp) + max(0 - (x1_temp - pad // 2), 0))

    y1 -= padding
    y2 += padding
    x1 -= padding
    x2 += padding
    return y1, y2, x1, x2

def resize_scan(scan, size=128):
    # zoom_factor = (1, size/scan.shape[1], size/scan.shape[2])
    # scan_rs = scipy.ndimage.zoom(scan,zoom_factor)
    scan_rs = np.zeros((len(scan), size, size))
    for idx in range(len(scan)):
        cur_slice = scan[idx, :, :]
        # cur_slice_rs = skimage.transform.resize(cur_slice, (size, size),anti_aliasing=True)
        cur_slice_rs = cv2.resize(cur_slice, (size, size), interpolation=cv2.INTER_CUBIC)
        scan_rs[idx, :, :] = cur_slice_rs
    return scan_rs
