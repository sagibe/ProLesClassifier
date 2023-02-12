"""
Train and eval functions used in main.py
Modified from DETR (https://github.com/facebookresearch/detr)
"""
import numpy as np
import math
import os
import sys
from typing import Iterable
import torch
from torch import sigmoid

import utils.util as utils
# from datasets.coco_eval import CocoEvaluator
# from datasets.panoptic_eval import PanopticEvaluator

def train_one_epoch(model: torch.nn.Module, criterion: torch.nn.Module,
                    data_loader: Iterable, optimizer: torch.optim.Optimizer,
                    device: torch.device, epoch: int, max_norm: float = 0):
    model.train()
    criterion.train()
    metrics = utils.PerformanceMetrics(device=device)
    metric_logger = utils.MetricLogger(delimiter="  ")
    metric_logger.add_meter('lr', utils.SmoothedValue(window_size=1, fmt='{value:.6f}'))
    metric_logger.add_meter('loss', utils.SmoothedValue(window_size=1, fmt='{value:.6f}'))
    metric_logger.add_meter('acc', utils.SmoothedValue(window_size=1, fmt='{value:.2f}'))
    metric_logger.add_meter('sensitivity', utils.SmoothedValue(window_size=1, fmt='{value:.2f}'))
    metric_logger.add_meter('specificity', utils.SmoothedValue(window_size=1, fmt='{value:.2f}'))
    metric_logger.add_meter('f1', utils.SmoothedValue(window_size=1, fmt='{value:.2f}'))
    header = 'Epoch: [{}]'.format(epoch)
    print_freq = 10
    for samples, targets in metric_logger.log_every(data_loader, print_freq, header):

        samples = samples.squeeze(0).float().to(device)
        targets = targets.float().T.to(device)
        # targets = [{k: v.to(device) for k, v in t.items()} for t in targets]
        outputs = model(samples)
        loss = criterion(outputs, targets)
        loss_value = loss.item()
        metrics.update(outputs, targets)
        # sensitivity, specificity, f1, accuracy = calc_metrics(outputs, targets)
        # acc = calc_accuracy(outputs, targets)

        # weight_dict = criterion.weight_dict
        # losses = sum(loss_dict[k] * weight_dict[k] for k in loss_dict.keys() if k in weight_dict)

        # # reduce losses over all GPUs for logging purposes
        # loss_dict_reduced = utils.reduce_dict(loss_dict)
        # loss_dict_reduced_unscaled = {f'{k}_unscaled': v
        #                               for k, v in loss_dict_reduced.items()}
        # loss_dict_reduced_scaled = {k: v * weight_dict[k]
        #                             for k, v in loss_dict_reduced.items() if k in weight_dict}
        # losses_reduced_scaled = sum(loss_dict_reduced_scaled.values())
        #
        # loss_value = losses_reduced_scaled.item()

        # if not math.isfinite(loss_value):
        #     print("Loss is {}, stopping training".format(loss_value))
        #     print(loss_dict_reduced)
        #     sys.exit(1)
        optimizer.zero_grad()
        loss.backward()
        if max_norm > 0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm)
        optimizer.step()

        metric_logger.update(loss=loss_value)
        metric_logger.update(acc=metrics.accuracy)
        metric_logger.update(sensitivity=metrics.sensitivity)
        metric_logger.update(specificity=metrics.specificity)
        metric_logger.update(f1=metrics.f1)
        # metric_logger.update(class_error=loss_dict_reduced['class_error'])
        metric_logger.update(lr=optimizer.param_groups[0]["lr"])

    # gather the stats from all processes
    metric_logger.synchronize_between_processes()
    print("Averaged stats:", metric_logger)
    return {k: meter.global_avg for k, meter in metric_logger.meters.items()}

def eval_epoch(model: torch.nn.Module, criterion: torch.nn.Module,
                    data_loader: Iterable, device: torch.device, epoch: int, max_norm: float = 0):
    model.eval()
    criterion.eval()
    metrics = utils.PerformanceMetrics(device=device)
    metric_logger = utils.MetricLogger(delimiter="  ")
    metric_logger.add_meter('loss', utils.SmoothedValue(window_size=1, fmt='{value:.6f}'))
    metric_logger.add_meter('acc', utils.SmoothedValue(window_size=1, fmt='{value:.2f}'))
    metric_logger.add_meter('sensitivity', utils.SmoothedValue(window_size=1, fmt='{value:.2f}'))
    metric_logger.add_meter('specificity', utils.SmoothedValue(window_size=1, fmt='{value:.2f}'))
    metric_logger.add_meter('f1', utils.SmoothedValue(window_size=1, fmt='{value:.2f}'))
    header = 'Epoch: [{}]'.format(epoch)
    print_freq = 10
    for samples, targets in metric_logger.log_every(data_loader, print_freq, header):
        samples = samples.squeeze(0).float().to(device)
        targets = targets.float().T.to(device)
        outputs = model(samples)
        loss = criterion(outputs, targets)
        loss_value = loss.item()
        metrics.update(outputs, targets)
        # acc = calc_accuracy(outputs, targets)
        # sensitivity, specificity, f1, accuracy = calc_metrics(outputs, targets)
        if max_norm > 0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm)
        metric_logger.update(loss=loss_value)
        metric_logger.update(acc=metrics.accuracy)
        metric_logger.update(sensitivity=metrics.sensitivity)
        metric_logger.update(specificity=metrics.specificity)
        metric_logger.update(f1=metrics.f1)
        # metric_logger.update(class_error=loss_dict_reduced['class_error'])

    # gather the stats from all processes
    metric_logger.synchronize_between_processes()
    print("Averaged stats:", metric_logger)
    return {k: meter.global_avg for k, meter in metric_logger.meters.items()}


# def eval_epoch(model, loader, criterion, meter, device, epoch):
#     criterion.to(device)
#     model.eval()
#
#     with torch.no_grad():
#         for step, data in enumerate(loader):
#             images, targets = data
#             images = images.to(device)
#             targets = targets.to(device).float()
#             targets = targets.unsqueeze(-1)
#             outputs = model(images)
#             loss = criterion(outputs, targets)
#             loss_val = loss.item()
#             acc = calc_accuracy(outputs, targets)
#             # _show_result(epoch, step, len(loader), loss_val, acc, False)
#             # _update_meter(meter, loss_val, acc)
#
#     return meter

# def calc_accuracy(outputs, targets,  bin_thresh=0.5):
#     if outputs.size(1) == 1:
#         preds = (sigmoid(outputs) > bin_thresh) * 1
#     else:
#         preds = outputs.argmax(-1)
#
#     return torch.mean(1. * (preds == targets)).item()
#
# def calc_metrics(outputs, targets,  bin_thresh=0.5):
#     if outputs.size(1) == 1:
#         preds = (sigmoid(outputs) > bin_thresh) * 1
#     else:
#         preds = outputs.argmax(-1)
#     targets_bools = targets > 0
#     preds_bools = preds > 0
#     tp = sum(targets_bools * preds_bools)
#     tn = sum(~targets_bools * ~preds_bools)
#     fp = sum(~targets_bools * preds_bools)
#     fn = sum(targets_bools * ~preds_bools)
#
#     sensitivity = tp / (tp + fn)
#     specificity = tn / (tn + fp)
#     precision = tp / (tp + fp)
#     f1 = 2 * (precision * sensitivity) / (precision + sensitivity)
#     accuracy = (tp + tn) / (tp + tn + fp + fn)
#     return sensitivity.item(), specificity.item(), f1.item(), accuracy.item()

    # return torch.mean(1. * (preds == targets)).item()


# @torch.no_grad()
# def evaluate(model, criterion, postprocessors, data_loader, base_ds, device, output_dir):
#     model.eval()
#     criterion.eval()
#
#     metric_logger = utils.MetricLogger(delimiter="  ")
#     metric_logger.add_meter('class_error', utils.SmoothedValue(window_size=1, fmt='{value:.2f}'))
#     header = 'Test:'
#
#     iou_types = tuple(k for k in ('segm', 'bbox') if k in postprocessors.keys())
#     coco_evaluator = CocoEvaluator(base_ds, iou_types)
#     # coco_evaluator.coco_eval[iou_types[0]].params.iouThrs = [0, 0.1, 0.5, 0.75]
#
#     panoptic_evaluator = None
#     if 'panoptic' in postprocessors.keys():
#         panoptic_evaluator = PanopticEvaluator(
#             data_loader.dataset.ann_file,
#             data_loader.dataset.ann_folder,
#             output_dir=os.path.join(output_dir, "panoptic_eval"),
#         )
#
#     for samples, targets in metric_logger.log_every(data_loader, 10, header):
#         samples = samples.to(device)
#         targets = [{k: v.to(device) for k, v in t.items()} for t in targets]
#
#         outputs = model(samples)
#         loss_dict = criterion(outputs, targets)
#         weight_dict = criterion.weight_dict
#
#         # reduce losses over all GPUs for logging purposes
#         loss_dict_reduced = utils.reduce_dict(loss_dict)
#         loss_dict_reduced_scaled = {k: v * weight_dict[k]
#                                     for k, v in loss_dict_reduced.items() if k in weight_dict}
#         loss_dict_reduced_unscaled = {f'{k}_unscaled': v
#                                       for k, v in loss_dict_reduced.items()}
#         metric_logger.update(loss=sum(loss_dict_reduced_scaled.values()),
#                              **loss_dict_reduced_scaled,
#                              **loss_dict_reduced_unscaled)
#         metric_logger.update(class_error=loss_dict_reduced['class_error'])
#
#         orig_target_sizes = torch.stack([t["orig_size"] for t in targets], dim=0)
#         results = postprocessors['bbox'](outputs, orig_target_sizes)
#         if 'segm' in postprocessors.keys():
#             target_sizes = torch.stack([t["size"] for t in targets], dim=0)
#             results = postprocessors['segm'](results, outputs, orig_target_sizes, target_sizes)
#         res = {target['image_id'].item(): output for target, output in zip(targets, results)}
#         if coco_evaluator is not None:
#             coco_evaluator.update(res)
#
#         if panoptic_evaluator is not None:
#             res_pano = postprocessors["panoptic"](outputs, target_sizes, orig_target_sizes)
#             for i, target in enumerate(targets):
#                 image_id = target["image_id"].item()
#                 file_name = f"{image_id:012d}.png"
#                 res_pano[i]["image_id"] = image_id
#                 res_pano[i]["file_name"] = file_name
#
#             panoptic_evaluator.update(res_pano)
#
#     # gather the stats from all processes
#     metric_logger.synchronize_between_processes()
#     print("Averaged stats:", metric_logger)
#     if coco_evaluator is not None:
#         coco_evaluator.synchronize_between_processes()
#     if panoptic_evaluator is not None:
#         panoptic_evaluator.synchronize_between_processes()
#
#     # accumulate predictions from all images
#     if coco_evaluator is not None:
#         coco_evaluator.accumulate()
#         coco_evaluator.summarize()
#     panoptic_res = None
#     if panoptic_evaluator is not None:
#         panoptic_res = panoptic_evaluator.summarize()
#     stats = {k: meter.global_avg for k, meter in metric_logger.meters.items()}
#     if coco_evaluator is not None:
#         if 'bbox' in postprocessors.keys():
#             stats['coco_eval_bbox'] = coco_evaluator.coco_eval['bbox'].stats.tolist()
#         if 'segm' in postprocessors.keys():
#             stats['coco_eval_masks'] = coco_evaluator.coco_eval['segm'].stats.tolist()
#     if panoptic_res is not None:
#         stats['PQ_all'] = panoptic_res["All"]
#         stats['PQ_th'] = panoptic_res["Things"]
#         stats['PQ_st'] = panoptic_res["Stuff"]
#     return stats, coco_evaluator
